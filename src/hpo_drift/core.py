"""Core: load HPO releases, diff a user's term list, compute similarity drift, lint."""
from __future__ import annotations

import math
import os
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

import networkx as nx
import obonet
import requests

CACHE = Path(os.environ.get("HPO_DRIFT_CACHE", Path.home() / ".cache" / "hpo-drift"))
RELEASE_URL = "https://github.com/obophenotype/human-phenotype-ontology/releases/download/{tag}/hp.obo"
HP_ID = re.compile(r"^HP:\d{7}$")
SYN_RE = re.compile(r'^"(.*?)"')
ROOT = "HP:0000118"  # Phenotypic abnormality


# ---------------------------------------------------------------- loading
def fetch(tag: str) -> Path:
    """Download hp.obo for a release tag (e.g. v2026-06-23) into the cache."""
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"hp-{tag}.obo"
    if dest.exists() and dest.stat().st_size > 1_000_000:
        return dest
    r = requests.get(RELEASE_URL.format(tag=tag), timeout=120, stream=True)
    r.raise_for_status()
    with open(dest, "wb") as fh:
        for chunk in r.iter_content(1 << 20):
            fh.write(chunk)
    return dest


class Release:
    """One HPO release, parsed. Edges in the obonet graph go child -> parent."""

    def __init__(self, tag: str, path: Path | None = None):
        self.tag = tag
        self.g = obonet.read_obo(str(path or fetch(tag)), ignore_obsolete=False)  # keep obsolete terms so `obsoleted → replaced_by` and lint can see them
        self.alt: dict[str, str] = {}
        self.labels: dict[str, str] = {}
        for tid, d in self.g.nodes(data=True):
            for a in d.get("alt_id", []):
                self.alt[a] = tid
            name = d.get("name")
            if name:
                self.labels.setdefault(name.lower(), tid)
            for s in d.get("synonym", []):
                m = SYN_RE.match(s)
                if m:
                    self.labels.setdefault(m.group(1).lower(), tid)
        self._n_active = sum(1 for _, d in self.g.nodes(data=True) if not self.obsolete(_))

    def has(self, tid: str) -> bool:
        return tid in self.g

    def name(self, tid: str) -> str | None:
        return self.g.nodes[tid].get("name") if tid in self.g else None

    def obsolete(self, tid: str) -> bool:
        return tid in self.g and self.g.nodes[tid].get("is_obsolete") == "true"

    def replaced_by(self, tid: str) -> list[str]:
        return list(self.g.nodes[tid].get("replaced_by", [])) if tid in self.g else []

    def parents(self, tid: str) -> set[str]:
        return {v for _, v, k in self.g.out_edges(tid, keys=True) if k == "is_a"} if tid in self.g else set()

    def ancestors(self, tid: str) -> set[str]:
        """All superclasses (following child->parent edges) incl. self."""
        return (nx.descendants(self.g, tid) | {tid}) if tid in self.g else set()

    @lru_cache(maxsize=None)
    def n_descendants(self, tid: str) -> int:
        return len(nx.ancestors(self.g, tid)) if tid in self.g else 0

    def ic(self, tid: str) -> float:
        """Intrinsic information content (Seco 2004): 1 - log(desc+1)/log(N).
        Structure-only, so drift here isolates the effect of ontology edits."""
        if tid not in self.g or self.obsolete(tid):
            return float("nan")
        return 1.0 - math.log(self.n_descendants(tid) + 1) / math.log(self._n_active)

    def mica(self, a: str, b: str) -> tuple[str | None, float]:
        common = self.ancestors(a) & self.ancestors(b)
        if not common:
            return None, 0.0
        best = max(common, key=self.ic)
        return best, self.ic(best)

    def resnik(self, a: str, b: str) -> float:
        return self.mica(a, b)[1]

    def lin(self, a: str, b: str) -> float:
        _, m = self.mica(a, b)
        d = self.ic(a) + self.ic(b)
        return 2 * m / d if d else 0.0

    def resolve(self, token: str) -> tuple[str | None, str]:
        """Map an ID or a label/synonym to a term id. Returns (id, how)."""
        t = token.strip()
        if HP_ID.match(t):
            if t in self.g:
                return t, "id"
            if t in self.alt:
                return self.alt[t], "alt_id"
            return None, "unknown-id"
        tid = self.labels.get(t.lower())
        return (tid, "label") if tid else (None, "unknown-label")


# ---------------------------------------------------------------- diff
@dataclass
class TermChange:
    tid: str
    status: str = "unchanged"        # unchanged | renamed | obsoleted | merged | missing | new-in-new
    old_name: str | None = None
    new_name: str | None = None
    replaced_by: list[str] = field(default_factory=list)
    parents_added: set[str] = field(default_factory=set)
    parents_removed: set[str] = field(default_factory=set)
    ic_old: float = float("nan")
    ic_new: float = float("nan")

    @property
    def ic_delta(self) -> float:
        return self.ic_new - self.ic_old


def diff_terms(old: Release, new: Release, terms: list[str]) -> list[TermChange]:
    out = []
    for tid in terms:
        c = TermChange(tid=tid, old_name=old.name(tid), new_name=new.name(tid))
        if not new.has(tid) and tid in new.alt:
            c.status, c.replaced_by, c.new_name = "merged", [new.alt[tid]], new.name(new.alt[tid])
        elif not new.has(tid):
            c.status = "missing"
        elif new.obsolete(tid) and not old.obsolete(tid):
            c.status, c.replaced_by = "obsoleted", new.replaced_by(tid)
        elif old.has(tid) and c.old_name != c.new_name:
            c.status = "renamed"
        else:
            c.status = "unchanged"
        po, pn = old.parents(tid), new.parents(tid)
        c.parents_added, c.parents_removed = pn - po, po - pn
        c.ic_old, c.ic_new = old.ic(tid), new.ic(tid)
        out.append(c)
    return out


def global_counts(old: Release, new: Release) -> dict[str, int]:
    o = {t for t in old.g if not old.obsolete(t)}
    n = {t for t in new.g if not new.obsolete(t)}
    renamed = sum(1 for t in o & n if old.name(t) != new.name(t))
    e_old = {(u, v) for u, v, k in old.g.edges(keys=True) if k == "is_a"}
    e_new = {(u, v) for u, v, k in new.g.edges(keys=True) if k == "is_a"}
    return {
        "terms_old": len(o), "terms_new": len(n),
        "added": len(n - o), "obsoleted": len(o - n), "renamed": renamed,
        "is_a_added": len(e_new - e_old), "is_a_removed": len(e_old - e_new),
    }


# ---------------------------------------------------------------- similarity drift
@dataclass
class PairDrift:
    a: str
    b: str
    resnik_old: float
    resnik_new: float
    lin_old: float
    lin_new: float
    mica_old: str | None
    mica_new: str | None

    @property
    def lin_delta(self) -> float:
        return self.lin_new - self.lin_old


def similarity_drift(old: Release, new: Release, terms: list[str]) -> list[PairDrift]:
    live = [t for t in terms if old.has(t) and new.has(t) and not old.obsolete(t) and not new.obsolete(t)]
    out = []
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            mo, ro = old.mica(a, b)
            mn, rn = new.mica(a, b)
            out.append(PairDrift(a, b, ro, rn, old.lin(a, b), new.lin(a, b), mo, mn))
    return out


# ---------------------------------------------------------------- lint
@dataclass
class LintIssue:
    token: str
    level: str      # error | warn | info
    message: str
    suggestion: str | None = None


def lint(rel: Release, tokens: list[str]) -> list[LintIssue]:
    issues = []
    for tok in tokens:
        tid, how = rel.resolve(tok)
        if how == "unknown-id":
            issues.append(LintIssue(tok, "error", "ID not found in this release (typo? removed?)"))
        elif how == "unknown-label":
            issues.append(LintIssue(tok, "error", "label not found (exact match on names/synonyms)"))
        elif how == "alt_id":
            issues.append(LintIssue(tok, "warn", f"secondary (alt) ID — merged into {tid}", f"use {tid} ({rel.name(tid)})"))
        elif how == "label":
            issues.append(LintIssue(tok, "warn", "matched by LABEL — labels get renamed; store the ID", f"{tid} ({rel.name(tid)})"))
        if tid and rel.obsolete(tid):
            rb = rel.replaced_by(tid)
            issues.append(LintIssue(tok, "error", "OBSOLETE term", (f"replaced_by {', '.join(rb)}" if rb else "no replacement listed")))
    return issues


def read_terms(path: str) -> list[str]:
    toks = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        s = line.split("#", 1)[0].strip()
        if s:
            toks.append(s)
    return toks
