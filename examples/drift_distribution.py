"""Histogram of mean |dLin| over the RANKABLE rows of a ranked cohort table, with one profile marked.

Usage: python examples/drift_distribution.py ranked.csv --mark ORPHA:379 --old v2026-02-16 --new v2026-06-23 --out docs/drift-distribution.png"""
import argparse, csv
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ap = argparse.ArgumentParser(); ap.add_argument("csv"); ap.add_argument("--mark"); ap.add_argument("--old", default=""); ap.add_argument("--new", default=""); ap.add_argument("--out", default="drift-distribution.png")
a = ap.parse_args()
rows = list(csv.DictReader(open(a.csv, encoding="utf-8")))
v = np.array([float(r["mean_abs_dlin"]) for r in rows]); v = v[v > 0]
fig, ax = plt.subplots(figsize=(10, 4.4), dpi=150)
ax.hist(v, bins=np.logspace(np.log10(v.min()), np.log10(v.max()), 45), color="#6b7f85")
ax.set_xscale("log"); ax.set_xlabel(f"mean |ΔLin| over informative term pairs, {a.old} → {a.new} (log scale)"); ax.set_ylabel("disease profiles")
med, p99 = np.median(v), np.quantile(v, .99)
ax.axvline(med, color="#1f3b57", ls=":"); ax.text(med * 1.08, ax.get_ylim()[1] * .92, f"median {med:.4f}", color="#1f3b57", fontsize=9)
ax.axvline(p99, color="#e07b00", ls=":"); ax.text(p99 / 1.08, ax.get_ylim()[1] * .78, f"p99 {p99:.3f}", color="#e07b00", fontsize=9, ha="right")
if a.mark:
    r = next(x for x in rows if x["disease"] == a.mark); x = float(r["mean_abs_dlin"])
    ax.axvline(x, color="#c0392b", lw=2); ax.text(x * 1.08, ax.get_ylim()[1] * .62, f"{r['name'].lower()}\nrank {r['rank']} of {len(rows)} · {x:.3f}", color="#c0392b", fontsize=9)
ax.set_title(f"hpo-drift: {len(rows)} RANKABLE disease profiles (every OMIM/Orphanet/DECIPHER profile with ≥1 informative pair)", fontsize=10)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(a.out); print(a.out)
