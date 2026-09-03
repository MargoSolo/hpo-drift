"""Which disease phenotype profiles drift most between two HPO releases?

Inclusion (declared once, applied to everything): every OMIM or Orphanet disease whose phenotype.hpoa profile has
12-60 phenotypic-abnormality terms present and non-obsolete in both releases. Score: Lin drift (Seco intrinsic IC,
is_a graph under Phenotypic abnormality) over the profile's informative term pairs (pairs whose most-informative common
ancestor is below the root in either release). Output: the full ranking, one row per profile; nothing is subset.

Usage:
  python examples/rank_profiles.py OLD NEW phenotype.hpoa > profiles.csv"""
import argparse, csv, hashlib, itertools, statistics, sys
from collections import defaultdict
from hpo_drift.core import Release

ap = argparse.ArgumentParser(); ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("hpoa")
ap.add_argument("--min-terms", type=int, default=12); ap.add_argument("--max-terms", type=int, default=60); ap.add_argument("--min-pairs", type=int, default=10)
a = ap.parse_args()
old, new = Release(a.old), Release(a.new)
_raw = open(a.hpoa, "rb").read(); _ver = next((l.split(":", 1)[1].strip() for l in _raw.decode("utf-8", "replace").splitlines()[:10] if l.startswith("#version:")), "unknown")
print(f"# phenotype.hpoa version {_ver} · sha256 {hashlib.sha256(_raw).hexdigest()}", file=sys.stderr)
dis, name = defaultdict(set), {}
for line in open(a.hpoa, encoding="utf-8"):
    if line.startswith("#") or line.startswith("database_id"): continue
    f = line.rstrip("\n").split("\t")
    if not f[0].startswith(("OMIM:", "ORPHA:")) or f[2] == "NOT": continue
    t = f[3]
    if t in old.g and t in new.g and not old.obsolete(t) and not new.obsolete(t) and old.ic(t) == old.ic(t) and new.ic(t) == new.ic(t): dis[f[0]].add(t); name[f[0]] = f[1]
w = csv.writer(sys.stdout); w.writerow(["rank", "disease", "name", "n_terms", "reparented", "ic_moved", "informative_pairs", "pairs_moved", "pairs_moved_gt_0.1", "mean_abs_dlin", "max_abs_dlin"])
rows = []
for d, ts in dis.items():
    if not a.min_terms <= len(ts) <= a.max_terms: continue
    ts = sorted(ts); dl = []
    for x, y in itertools.combinations(ts, 2):
        lo, ln = old.lin(x, y), new.lin(x, y)
        if lo > 0 or ln > 0: dl.append(abs(ln - lo))
    if len(dl) < a.min_pairs: continue
    rows.append([d, name[d], len(ts), sum(1 for t in ts if old.parents(t) != new.parents(t)), sum(1 for t in ts if abs(new.ic(t) - old.ic(t)) > 1e-9),
                 len(dl), sum(1 for v in dl if v > 1e-9), sum(1 for v in dl if v > 0.1), round(statistics.mean(dl), 4), round(max(dl), 3)])
rows.sort(key=lambda r: -r[8])
for i, r in enumerate(rows, 1): w.writerow([i] + r)
vals = sorted(r[8] for r in rows); q = lambda p: vals[min(len(vals) - 1, int(p * len(vals)))]
print(f"# {len(rows)} profiles ({a.min_terms}-{a.max_terms} terms) · mean_abs_dlin median {q(.5):.4f} · p90 {q(.9):.4f} · p99 {q(.99):.4f} · max {vals[-1]:.4f}", file=sys.stderr)
