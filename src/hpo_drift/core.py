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

    def __init__(self, tag: str, path: Path | None = None, root: str = ROOT):
        self.tag = tag
        self.root = root
        self.g = obonet.read_obo(str(path or fetch(tag)), ignore_obsolete=False)  # keep obsolete terms so `obsoleted → replaced_by` and lint can see them
        # IC / ancestors / MICA are computed on the is_a graph only (child -> parent), never on other relationship types
        self.isa = nx.DiGraph()
        self.isa.add_nodes_from(self.g.nodes())
        self.isa.add_edges_from((u, v) for u, v, k in self.g.edges(keys=True) if k == "is_a")
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
        # N for Seco IC = active terms inside the root's is_a closure (default: Phenotypic abnormality), not the whole ontology
        self._domain = ({t for t in nx.ancestors(self.isa, root)} | {root}) if root in self.isa else set(self.isa.nodes())
        self._domain = {t for t in self._domain if not self.obsolete(t)}
        self._n_active = len(self._domain)

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

    @lru_cache(maxsize=None)
    def ancestors(self, tid: str) -> frozenset[str]:
        """All superclasses (following child->parent edges) incl. self."""
        return frozenset(nx.descendants(self.isa, tid) | {tid}) if tid in self.isa else frozenset()

    def in_domain(self, tid: str) -> bool:
        """Inside the root's is_a closure and not obsolete — i.e. carries IC and can enter a pair."""
        return tid in self._domain

    @lru_cache(maxsize=None)
    def n_descendants(self, tid: str) -> int:
        return len(nx.ancestors(self.isa, tid) & self._domain) if tid in self.isa else 0

    @lru_cache(maxsize=None)
    def ic(self, tid: str) -> float:
        """Intrinsic information content (Seco 2004): 1 - log(desc+1)/log(N).
        Structure-only, so drift here isolates the effect of ontology edits."""
        if tid not in self._domain:
            return float("nan")   # obsolete, or outside the root closure (e.g. inheritance / frequency / modifier branches)
        return 1.0 - math.log(self.n_descendants(tid) + 1) / math.log(self._n_active)

    def mica(self, a: str, b: str) -> tuple[str | None, float]:
        common = (self.ancestors(a) & self.ancestors(b)) & self._domain   # only ancestors inside the root closure carry IC
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
    domain: str = "in"               # in | OUT_OF_DOMAIN (term exists but lies outside the similarity root's is_a closure: no IC, no pairs)
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
        if c.status in ("unchanged", "renamed") and old.has(tid) and not (old.in_domain(tid) and new.in_domain(tid)):
            c.domain = "OUT_OF_DOMAIN"
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
    kind: str = "INFORMATIVE"    # INFORMATIVE (MICA below the root in at least one release) | ROOT_ONLY (MICA = root in both: Lin 0 -> 0 by construction)

    @property
    def lin_delta(self) -> float:
        return self.lin_new - self.lin_old


def usable_terms(old: Release, new: Release, terms: list[str]) -> list[str]:
    """Terms that carry IC in both releases: present, not obsolete, inside the similarity domain. Order kept, duplicates dropped."""
    return [t for t in dict.fromkeys(terms) if old.in_domain(t) and new.in_domain(t)]


def similarity_drift(old: Release, new: Release, terms: list[str]) -> list[PairDrift]:
    """All pairs among the usable terms. Nothing is dropped: root-only pairs are returned with kind=ROOT_ONLY."""
    live = usable_terms(old, new, terms)
    out = []
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            mo, ro = old.mica(a, b)
            mn, rn = new.mica(a, b)
            kind = "ROOT_ONLY" if mo in (None, old.root) and mn in (None, new.root) else "INFORMATIVE"
            out.append(PairDrift(a, b, ro, rn, old.lin(a, b), new.lin(a, b), mo, mn, kind))
    return out


# ---------------------------------------------------------------- profile summary (any term set, any size)
PROFILE_COLUMNS = ["n_raw_terms", "n_retained_terms", "n_missing_old", "n_missing_new", "n_obsolete", "n_out_of_domain", "n_ic_changed",
                   "n_pairs", "n_informative_pairs", "n_root_only_pairs", "n_pairs_changed", "n_pairs_abs_delta_gt_0.01", "n_pairs_abs_delta_gt_0.1",
                   "mean_abs_dlin", "max_abs_dlin", "status"]
PROFILE_STATUSES = ("NO_USABLE_TERMS", "TERM_ONLY", "NO_INFORMATIVE_PAIRS", "RANKABLE")


def profile_drift(old: Release, new: Release, terms: list[str]) -> dict:
    """Drift summary for one term set of any size. Never raises on 0/1/N terms; the `status` says what could be computed:
    NO_USABLE_TERMS (nothing carries IC in both releases), TERM_ONLY (one usable term: IC drift, no pairs),
    NO_INFORMATIVE_PAIRS (2+ terms but every pair shares only the root), RANKABLE (mean/max |dLin| defined)."""
    raw = list(dict.fromkeys(terms))
    live = usable_terms(old, new, raw)
    r = {"n_raw_terms": len(raw), "n_retained_terms": len(live),
         "n_missing_old": sum(1 for t in raw if not old.has(t)), "n_missing_new": sum(1 for t in raw if not new.has(t) and t not in new.alt),
         "n_obsolete": sum(1 for t in raw if old.obsolete(t) or new.obsolete(t)),
         "n_out_of_domain": sum(1 for t in raw if old.has(t) and new.has(t) and not old.obsolete(t) and not new.obsolete(t) and not (old.in_domain(t) and new.in_domain(t))),
         "n_ic_changed": sum(1 for t in live if abs(new.ic(t) - old.ic(t)) > 1e-9),
         "n_pairs": 0, "n_informative_pairs": 0, "n_root_only_pairs": 0, "n_pairs_changed": 0, "n_pairs_abs_delta_gt_0.01": 0, "n_pairs_abs_delta_gt_0.1": 0,
         "mean_abs_dlin": float("nan"), "max_abs_dlin": float("nan")}
    if not live:
        r["status"] = "NO_USABLE_TERMS"; return r
    if len(live) == 1:
        r["status"] = "TERM_ONLY"; return r
    pairs = similarity_drift(old, new, live)
    inf = [abs(p.lin_delta) for p in pairs if p.kind == "INFORMATIVE"]
    r.update(n_pairs=len(pairs), n_informative_pairs=len(inf), n_root_only_pairs=len(pairs) - len(inf),
             n_pairs_changed=sum(1 for v in inf if v > 1e-9), **{"n_pairs_abs_delta_gt_0.01": sum(1 for v in inf if v > 0.01), "n_pairs_abs_delta_gt_0.1": sum(1 for v in inf if v > 0.1)})
    if not inf:
        r["status"] = "NO_INFORMATIVE_PAIRS"; return r
    r.update(mean_abs_dlin=sum(inf) / len(inf), max_abs_dlin=max(inf), status="RANKABLE")
    return r


def read_hpoa(path: str) -> tuple[dict, dict[str, tuple[str, list[str]]]]:
    """phenotype.hpoa -> (metadata, {disease_id: (name, [unique positive phenotypic-abnormality HP ids])}).
    Keeps aspect P rows only (inheritance/course/modifier rows are not phenotypes), drops qualifier NOT. Every disease is kept, whatever its size."""
    import hashlib
    raw = Path(path).read_bytes()
    meta = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "version": None, "n_rows": 0}
    profiles: dict[str, tuple[str, list[str]]] = {}
    for line in raw.decode("utf-8", "replace").splitlines():
        if line.startswith("#"):
            if line.startswith("#version:"):
                meta["version"] = line.split(":", 1)[1].strip()
            continue
        if line.startswith("database_id") or not line.strip():
            continue
        f = line.split("\t")
        meta["n_rows"] += 1
        if len(f) < 11 or f[2] == "NOT" or f[10] != "P":
            continue
        name, terms = profiles.get(f[0], (f[1], []))
        if f[3] not in terms:
            terms.append(f[3])
        profiles[f[0]] = (name, terms)
    return meta, profiles


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
