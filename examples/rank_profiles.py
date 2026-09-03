"""Which disease phenotype profiles drift most between two HPO releases?

For every OMIM or Orphanet disease whose phenotype.hpoa profile has 12-25 phenotypic-abnormality terms present and
non-obsolete in both releases, compute Lin drift (Seco intrinsic IC, is_a graph under Phenotypic abnormality) over the
profile's informative term pairs (pairs whose most-informative common ancestor is below the root in either release).

Usage:
  python examples/rank_profiles.py OLD NEW phenotype.hpoa > profiles.csv
  python examples/rank_profiles.py OLD NEW phenotype.hpoa --subset examples/wellknown_syndromes.txt > wellknown.csv

Selection protocol used for the README example: run without --subset (full ranking) and with the pre-declared
well-known-syndromes subset; the README example is the top entry of the subset ranking."""
import argparse, csv, itertools, statistics, sys
from collections import defaultdict
from hpo_drift.core import Release

ap = argparse.ArgumentParser(); ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("hpoa")
ap.add_argument("--min-terms", type=int, default=12); ap.add_argument("--max-terms", type=int, default=25); ap.add_argument("--min-pairs", type=int, default=10)
ap.add_argument("--subset", help="file with one disease id (OMIM:… / ORPHA:…) per line; rank only these")
a = ap.parse_args()
old, new = Release(a.old), Release(a.new)
subset = None
if a.subset: subset = {l.split("#")[0].strip() for l in open(a.subset) if l.split("#")[0].strip()}
dis, name = defaultdict(set), {}
for line in open(a.hpoa, encoding="utf-8"):
    if line.startswith("#") or line.startswith("database_id"): continue
    f = line.rstrip("\n").split("\t")
    if not f[0].startswith(("OMIM:", "ORPHA:")) or f[2] == "NOT": continue
    if subset is not None and f[0] not in subset: continue
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
print(f"# {len(rows)} profiles ({a.min_terms}-{a.max_terms} terms) · median mean_abs_dlin {statistics.median(r[8] for r in rows):.4f}", file=sys.stderr)
