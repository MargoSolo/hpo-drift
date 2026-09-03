"""Two figures from a `hpo-drift report --json` file: Lin drift per informative pair, IC per term.
Usage: python examples/figures.py docs/drift.json --outdir docs"""
import argparse, json, math
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
ap = argparse.ArgumentParser(); ap.add_argument("json"); ap.add_argument("--outdir", default="docs"); ap.add_argument("--top", type=int, default=12)
a = ap.parse_args(); d = json.load(open(a.json)); nm = {t["tid"]: (t["new_name"] or t["old_name"]) for t in d["terms"]}
pairs = sorted([p for p in d["pairs"] if p["kind"] == "INFORMATIVE" and abs(p["lin_new"] - p["lin_old"]) > 1e-9], key=lambda p: -abs(p["lin_new"] - p["lin_old"]))[: a.top]
fig, ax = plt.subplots(figsize=(9.5, 0.42 * len(pairs) + 1.4), dpi=150)
lab = [f"{nm[p['a']]} ↔ {nm[p['b']]}" for p in pairs][::-1]; dl = [p["lin_new"] - p["lin_old"] for p in pairs][::-1]
ax.barh(lab, dl, color=["#c0392b" if v < 0 else "#1f7a5c" for v in dl]); ax.axvline(0, color="#333", lw=.8)
for i, (p, v) in enumerate(zip(pairs[::-1], dl)): ax.text(v + (0.01 if v >= 0 else -0.01), i, f"{p['lin_old']:.2f} → {p['lin_new']:.2f}", va="center", ha="left" if v >= 0 else "right", fontsize=8)
ax.set_xlabel(f"ΔLin, HPO {d['old']} → {d['new']} (Seco intrinsic IC)"); ax.set_xlim(min(dl + [0]) - 0.45, max(dl + [0]) + 0.3)
ax.set_title(f"Lin similarity drift · {len([p for p in d['pairs'] if p['kind']=='INFORMATIVE'])} informative pairs, top {len(pairs)} shown", fontsize=10)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(f"{a.outdir}/lin-drift.png")
terms = [t for t in d["terms"] if not math.isnan(t["ic_old"])]
fig, ax = plt.subplots(figsize=(9.5, 0.4 * len(terms) + 1.4), dpi=150)
y = range(len(terms)); ax.hlines(y, [t["ic_old"] for t in terms], [t["ic_new"] for t in terms], color="#999", lw=2)
ax.scatter([t["ic_old"] for t in terms], y, color="#1f3b57", label=d["old"], zorder=3); ax.scatter([t["ic_new"] for t in terms], y, color="#e07b00", label=d["new"], zorder=3)
ax.set_yticks(list(y)); ax.set_yticklabels([f"{t['tid']}  {nm[t['tid']]}" + ("   ← parent removed" if t["parents_removed"] else "") + ("   ← parent added" if t["parents_added"] else "") for t in terms], fontsize=8)
ax.set_xlabel("intrinsic IC (Seco 2004)"); ax.legend(frameon=False, fontsize=8); ax.set_title("Information content per term, old vs new release", fontsize=10)
for s in ("top", "right"): ax.spines[s].set_visible(False)
fig.tight_layout(); fig.savefig(f"{a.outdir}/ic-drift.png"); print("figures ok")
