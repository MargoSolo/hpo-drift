"""Endpoints of a synthetic-patient sweep: % true-diagnosis rank changed, % top-1 changed, % top-5 membership changed, |Δrank| quantiles.
Usage: python examples/summarize_sweep.py sweep.csv [more.csv ...]"""
import csv, statistics, sys
for f in sys.argv[1:]:
    rows = [r for r in csv.DictReader(open(f)) if r["rank_true_old"]]
    n = len(rows); dr = [abs(int(r["rank_true_new"]) - int(r["rank_true_old"])) for r in rows]
    q = lambda v, p: sorted(v)[min(len(v) - 1, int(p * len(v)))]
    changed = sum(1 for d in dr if d > 0); top1 = sum(int(r["top1_changed"]) for r in rows); top5 = sum(1 for r in rows if float(r["jaccard_top5"]) < 1)
    worse = sum(1 for r in rows if int(r["rank_true_new"]) > int(r["rank_true_old"])); better = sum(1 for r in rows if int(r["rank_true_new"]) < int(r["rank_true_old"]))
    in_top1 = (sum(1 for r in rows if r["rank_true_old"] == "1"), sum(1 for r in rows if r["rank_true_new"] == "1"))
    in_top10 = (sum(1 for r in rows if int(r["rank_true_old"]) <= 10), sum(1 for r in rows if int(r["rank_true_new"]) <= 10))
    print(f"{f}: n={n}")
    print(f"  true-diagnosis rank changed: {changed}/{n} ({100*changed/n:.1f} %) — worse {worse}, better {better}")
    print(f"  |Δrank| median {q(dr,.5)} · p90 {q(dr,.9)} · p95 {q(dr,.95)} · max {max(dr)}")
    print(f"  top-1 disease changed: {top1}/{n} ({100*top1/n:.1f} %) · top-5 membership changed: {top5}/{n} ({100*top5/n:.1f} %)")
    print(f"  true diagnosis at rank 1: {in_top1[0]} → {in_top1[1]} · within top 10: {in_top10[0]} → {in_top10[1]}")
    print(f"  Spearman rho over all diseases: median {statistics.median(float(r['spearman_all']) for r in rows):.4f} · min {min(float(r['spearman_all']) for r in rows):.4f}")
    big = sorted(rows, key=lambda r: -abs(int(r["rank_true_new"]) - int(r["rank_true_old"])))[:5]
    for r in big: print(f"    {r['name'][:60]} ({r['true_disease']}): true rank {r['rank_true_old']} → {r['rank_true_new']}, score {r['score_true_old']} → {r['score_true_new']}")
