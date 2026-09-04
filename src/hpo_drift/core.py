"""Core: load HPO releases, diff a user's term list, compute similarity drift, lint."""
from __future__ import annotations

import hashlib
import json
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
RELEASE_API = "https://api.github.com/repos/obophenotype/human-phenotype-ontology/releases/tags/{tag}"
HP_ID = re.compile(r"^HP:\d{7}$")
SYN_RE = re.compile(r'^"(.*?)"')
ROOT = "HP:0000118"  # Phenotypic abnormality


# ---------------------------------------------------------------- loading
def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def official_digest(tag: str, asset: str = "hp.obo") -> str | None:
    """SHA-256 that the official GitHub release publishes for an asset (None if the API is unreachable)."""
    try:
        r = requests.get(RELEASE_API.format(tag=tag), timeout=30, headers={"Accept": "application/vnd.github+json"})
        r.raise_for_status()
        for a in r.json().get("assets", []):
            if a.get("name") == asset and str(a.get("digest", "")).startswith("sha256:"):
                return a["digest"][7:]
    except Exception:
        return None
    return None


def fetch(tag: str) -> Path:
    """Download hp.obo for a release tag (e.g. v2026-06-23) into the cache.
    Atomic: download to .tmp, hash, verify against the release's published digest when available, then rename.
    A cached file is trusted only with its .sha256 sidecar (written after a verified download); a partial download never becomes the cache."""
    CACHE.mkdir(parents=True, exist_ok=True)
    dest = CACHE / f"hp-{tag}.obo"
    side = CACHE / f"hp-{tag}.obo.sha256"
    if dest.exists() and side.exists() and side.read_text().strip() == sha256_file(dest):
        return dest
    tmp = CACHE / f"hp-{tag}.obo.tmp"
    r = requests.get(RELEASE_URL.format(tag=tag), timeout=120, stream=True)
    r.raise_for_status()
    with open(tmp, "wb") as fh:
        for chunk in r.iter_content(1 << 20):
            fh.write(chunk)
    digest = sha256_file(tmp)
    want = official_digest(tag)
    if want and want != digest:
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{tag}: downloaded hp.obo sha256 {digest} != published digest {want}; refusing to cache")
    if not tmp.read_bytes()[:20].startswith(b"format-version"):
        tmp.unlink(missing_ok=True)
        raise RuntimeError(f"{tag}: downloaded file is not an OBO document; refusing to cache")
    os.replace(tmp, dest)
    side.write_text(digest)
    return dest


class Release:
    """One HPO release, parsed. Edges in the obonet graph go child -> parent."""

    def __init__(self, tag: str, path: Path | None = None, root: str = ROOT):
        self.tag = tag
        self.root = root
        self.path = Path(path or fetch(tag))
        self.sha256 = sha256_file(self.path)
        self.g = obonet.read_obo(str(self.path), ignore_obsolete=False)  # keep obsolete terms so `obsoleted → replaced_by` and lint can see them
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

    def provenance(self) -> dict:
        return {"tag": self.tag, "file": str(self.path), "sha256": self.sha256}

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

    @lru_cache(maxsize=4_000_000)
    def mica(self, a: str, b: str) -> tuple[str | None, float]:
        if a > b:
            return self.mica(b, a)
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
def resolve_across(old: Release, new: Release, token: str) -> tuple[str | None, str, str]:
    """Resolve an ID or label against BOTH releases. Returns (term id or None, hint, how).
    hint: ok | new-only | ambiguous | unknown.  how: id | alt_id | label.
    ID in old (primary or alt)       -> that id, ok            (the diff then says missing / obsoleted / merged / renamed / unchanged)
    ID absent from old, in new       -> that id, new-only
    label in both, same id           -> ok;   label in old only -> old id, ok;   label in new only -> new id, new-only
    label mapping to different ids   -> ambiguous (the two releases disagree on what the label means)
    nothing                          -> unknown"""
    t = token.strip()
    if HP_ID.match(t):
        if t in old.g:
            return t, "ok", "id"
        if t in old.alt:
            return old.alt[t], "ok", "alt_id"
        if t in new.g:
            return t, "new-only", "id"
        if t in new.alt:
            return new.alt[t], "new-only", "alt_id"
        return None, "unknown", "id"
    a, b = old.labels.get(t.lower()), new.labels.get(t.lower())
    if a and b:
        return (a, "ok", "label") if a == b or new.alt.get(a) == b else (a, "ambiguous", "label")
    if a:
        return a, "ok", "label"
    if b:
        return b, "new-only", "label"
    return None, "unknown", "label"


@dataclass
class TermChange:
    tid: str
    status: str = "unchanged"        # unchanged | renamed | obsoleted | merged | missing | new-in-new | ambiguous | unknown
    domain: str = "in"               # in | OUT_OF_DOMAIN (term exists but lies outside the similarity root's is_a closure: no IC, no pairs)
    token: str | None = None         # what the user wrote, when it differs from tid (label, alt id)
    how: str = "id"                  # id | alt_id | label
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
    """Per-term diff for IDs *or labels*, resolved against both releases. Nothing disappears: a token that exists only in the new
    release is reported as new-in-new, a label the releases disagree on as ambiguous, an unresolvable token as unknown."""
    out = []
    for tok in terms:
        tid, hint, how = resolve_across(old, new, tok)
        if tid is None:
            out.append(TermChange(tid=tok, status="unknown", domain="OUT_OF_DOMAIN", token=tok, how=how)); continue
        c = TermChange(tid=tid, old_name=old.name(tid), new_name=new.name(tid), token=(tok if tok != tid else None), how=how)
        if hint == "ambiguous":
            c.status, c.domain, c.new_name = "ambiguous", "OUT_OF_DOMAIN", new.name(new.labels.get(tok.strip().lower()))
            c.replaced_by = [new.labels.get(tok.strip().lower())]
            out.append(c); continue
        if hint == "new-only":
            c.status, c.domain = "new-in-new", "OUT_OF_DOMAIN"
            c.parents_added = new.parents(tid); c.ic_new = new.ic(tid)
            out.append(c); continue
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
PROFILE_COLUMNS = ["n_raw_terms", "n_retained_terms", "n_unknown", "n_new_only", "n_missing_new", "n_merged_or_alt", "n_obsolete", "n_out_of_domain", "n_ic_changed",
                   "n_pairs", "n_informative_pairs", "n_root_only_pairs", "n_pairs_changed", "n_pairs_abs_delta_gt_0.01", "n_pairs_abs_delta_gt_0.1",
                   "mean_abs_dlin", "max_abs_dlin", "status"]
PROFILE_STATUSES = ("NO_USABLE_TERMS", "TERM_ONLY", "NO_INFORMATIVE_PAIRS", "RANKABLE")


def disposition(old: Release, new: Release, t: str) -> str:
    """Mutually exclusive fate of one raw term id, in this priority order — so the counts add up to n_raw_terms:
    unknown (in neither release) | new_only (absent from old, present in new) | merged_or_alt (alt/secondary id in old, or merged into another id in new)
    | missing_new (in old, gone from new) | obsolete (obsolete in old or new) | out_of_domain (outside the similarity root in either) | retained"""
    in_old, in_new = old.has(t), new.has(t)
    if not in_old and t not in old.alt:
        return "new_only" if (in_new or t in new.alt) else "unknown"
    if t in old.alt or (not in_new and t in new.alt):
        return "merged_or_alt"
    if not in_new:
        return "missing_new"
    if old.obsolete(t) or new.obsolete(t):
        return "obsolete"
    if not (old.in_domain(t) and new.in_domain(t)):
        return "out_of_domain"
    return "retained"


def profile_drift(old: Release, new: Release, terms: list[str]) -> dict:
    """Drift summary for one term set of any size. Never raises on 0/1/N terms; the `status` says what could be computed:
    NO_USABLE_TERMS (nothing carries IC in both releases), TERM_ONLY (one usable term: IC drift, no pairs),
    NO_INFORMATIVE_PAIRS (2+ terms but every pair shares only the root), RANKABLE (mean/max |dLin| defined)."""
    raw = list(dict.fromkeys(terms))
    disp = {t: disposition(old, new, t) for t in raw}
    live = [t for t in raw if disp[t] == "retained"]
    assert live == usable_terms(old, new, raw)
    n = lambda k: sum(1 for v in disp.values() if v == k)
    r = {"n_raw_terms": len(raw), "n_retained_terms": len(live), "n_unknown": n("unknown"), "n_new_only": n("new_only"), "n_missing_new": n("missing_new"),
         "n_merged_or_alt": n("merged_or_alt"), "n_obsolete": n("obsolete"), "n_out_of_domain": n("out_of_domain"),
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
    A profile = the unique HP ids of a disease's rows with aspect P and no NOT qualifier (inheritance / course / modifier rows are not
    phenotypes, negated rows are not present phenotypes). Every disease with at least one such row is kept, whatever its size; a disease id
    that has only NOT or non-P rows has no positive phenotype profile and is counted in meta['n_diseases_without_positive_P']."""
    raw = Path(path).read_bytes()
    meta = {"path": str(path), "sha256": hashlib.sha256(raw).hexdigest(), "version": None, "n_rows": 0, "n_disease_ids_in_file": 0, "n_diseases_without_positive_P": 0}
    seen: set[str] = set()
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
        if len(f) >= 11:
            seen.add(f[0])
        if len(f) < 11 or f[2] == "NOT" or f[10] != "P":
            continue
        name, terms = profiles.get(f[0], (f[1], []))
        if f[3] not in terms:
            terms.append(f[3])
        profiles[f[0]] = (name, terms)
    meta["n_disease_ids_in_file"] = len(seen)
    meta["n_diseases_without_positive_P"] = len(seen - set(profiles))
    return meta, profiles


# ---------------------------------------------------------------- profile-to-profile similarity (the question a genomicist asks)
def best_match_average(rel: Release, query: list[str], target: list[str]) -> tuple[float, list[tuple[str, str, float]]]:
    """Symmetric Best Match Average of Lin similarity between two term sets within ONE release
    (mean over query terms of their best match in the target, averaged with the reverse direction).
    Only terms that carry IC in this release are used. Returns (score, best match per query term)."""
    q = [t for t in dict.fromkeys(query) if rel.in_domain(t)]
    d = [t for t in dict.fromkeys(target) if rel.in_domain(t)]
    if not q or not d:
        return float("nan"), []
    matches = []
    for a in q:
        b = max(d, key=lambda t: rel.lin(a, t))
        matches.append((a, b, rel.lin(a, b)))
    q2d = sum(m[2] for m in matches) / len(matches)
    d2q = sum(max(rel.lin(a, b) for a in q) for b in d) / len(d)
    return (q2d + d2q) / 2, matches


def profile_similarity(old: Release, new: Release, query: list[str], target: list[str]) -> dict:
    """Score the same query × target pair in both releases; list the query terms whose best match changed most."""
    so, mo = best_match_average(old, query, target)
    sn, mn = best_match_average(new, query, target)
    mo_d, mn_d = {m[0]: m for m in mo}, {m[0]: m for m in mn}
    changed = []
    for a in dict.fromkeys(query):
        if a in mo_d and a in mn_d:
            changed.append({"query": a, "best_old": mo_d[a][1], "lin_old": mo_d[a][2], "best_new": mn_d[a][1], "lin_new": mn_d[a][2], "delta": mn_d[a][2] - mo_d[a][2]})
    changed.sort(key=lambda r: -abs(r["delta"]))
    return {"score_old": so, "score_new": sn, "delta": sn - so, "n_query_used_old": len(mo), "n_query_used_new": len(mn),
            "n_target_used_old": sum(1 for t in dict.fromkeys(target) if old.in_domain(t)), "n_target_used_new": sum(1 for t in dict.fromkeys(target) if new.in_domain(t)),
            "matches": changed}


def rank_diseases(old: Release, new: Release, query: list[str], profiles: dict[str, tuple[str, list[str]]]) -> list[dict]:
    """Score one query against every disease profile in both releases; rank within each release (1 = most similar).
    Diseases whose profile has no usable term in a release get NaN there and sort last."""
    rows = []
    for d, (name, terms) in profiles.items():
        so, _ = best_match_average(old, query, terms)
        sn, _ = best_match_average(new, query, terms)
        rows.append({"disease": d, "name": name, "n_terms": len(terms), "score_old": so, "score_new": sn, "delta": sn - so})
    key = lambda k: (lambda r: (math.isnan(r[k]), -(0 if math.isnan(r[k]) else r[k])))
    for k, rk in (("score_old", "rank_old"), ("score_new", "rank_new")):
        for i, r in enumerate(sorted(rows, key=key(k)), 1):
            r[rk] = i
    for r in rows:
        r["rank_change"] = r["rank_new"] - r["rank_old"]
    rows.sort(key=lambda r: r["rank_new"])
    return rows


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
