"""Which disease phenotype profiles drift most between two HPO releases?
For every OMIM disease with 12-18 annotated phenotypic-abnormality terms (phenotype.hpoa), compute Lin drift over its
informative term pairs. Usage: python examples/rank_profiles.py v2026-02-16 v2026-06-23 phenotype.hpoa > profiles.csv"""
import csv, itertools, statistics, sys
from collections import defaultdict
from hpo_drift.core import Release
old, new = Release(sys.argv[1]), Release(sys.argv[2]); hpoa = sys.argv[3]
dis, name = defaultdict(set), {}
for line in open(hpoa, encoding="utf-8"):
    if line.startswith("#") or line.startswith("database_id"): continue
    f = line.rstrip("\n").split("\t")
    if not f[0].startswith("OMIM") or f[2] == "NOT": continue
    t = f[3]
    if t in old.g and t in new.g and not old.obsolete(t) and not new.obsolete(t) and old.ic(t) == old.ic(t) and new.ic(t) == new.ic(t): dis[f[0]].add(t); name[f[0]] = f[1]
w = csv.writer(sys.stdout); w.writerow(["disease", "name", "n_terms", "ic_moved", "informative_pairs", "pairs_moved", "mean_abs_dlin", "max_abs_dlin"])
rows = []
for d, ts in dis.items():
    if not 12 <= len(ts) <= 18: continue
    ts = sorted(ts); dl = []
    for a, b in itertools.combinations(ts, 2):
        lo, ln = old.lin(a, b), new.lin(a, b)
        if lo > 0 or ln > 0: dl.append(abs(ln - lo))
    if len(dl) < 10: continue
    rows.append([d, name[d], len(ts), sum(1 for t in ts if abs(new.ic(t) - old.ic(t)) > 1e-9), len(dl), sum(1 for x in dl if x > 1e-9), round(statistics.mean(dl), 4), round(max(dl), 3)])
rows.sort(key=lambda r: -r[6]); [w.writerow(r) for r in rows]
print(f"# {len(rows)} diseases · median mean_abs_dlin {statistics.median(r[6] for r in rows):.4f}", file=sys.stderr)
