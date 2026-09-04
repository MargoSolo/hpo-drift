"""Does the HPO release change a phenotype-driven diagnosis? Synthetic-patient protocol, declared before running.

For each of N disease profiles drawn at random (seed) from ALL profiles in phenotype.hpoa (no size filter, profiles with < 3 usable terms are skipped and counted):
  patient = a random KEEP fraction of the disease's annotated terms (at least 3)  +  NOISE random terms from the Phenotypic-abnormality domain of both releases
The patient is scored (symmetric Best Match Average of Lin) against EVERY disease profile — the source disease included — in each release.
Recorded per patient: rank and score of the true diagnosis in each release, top-1 disease in each release, whether it changed,
Jaccard overlap of the top-5 sets, Spearman rho of all disease ranks. The query is therefore independent of any single target profile
(a subset with noise), and the question is the clinical one: same patient, same annotations, different ontology release.

Noise-A = --noise-mode global (generic random annotation noise); Noise-B = --noise-mode neighbor (terms from nearby phenotype branches, clinically plausible noise).
Usage: python examples/sweep_synthetic_patients.py OLD NEW phenotype.hpoa --n 500 --keep 0.6 --noise 2 --noise-mode global --seed 0 --out sweep.csv"""
import argparse, csv, math, random, sys, time
from hpo_drift.core import Release, read_hpoa, best_match_average

ap = argparse.ArgumentParser(); ap.add_argument("old"); ap.add_argument("new"); ap.add_argument("hpoa")
ap.add_argument("--n", type=int, default=500); ap.add_argument("--keep", type=float, default=0.6); ap.add_argument("--noise", type=int, default=2); ap.add_argument("--seed", type=int, default=0); ap.add_argument("--out", required=True)
ap.add_argument("--noise-mode", choices=["global", "ic-matched", "neighbor"], default="global",
                help="global: uniform over the Phenotypic-abnormality domain (generic annotation noise). ic-matched: IC within ±0.05 of a randomly chosen kept term (old release). "
                     "neighbor: shares a common ancestor of IC ≥ 0.3 with a kept term, i.e. from a nearby phenotype branch (clinically plausible noise).")
a = ap.parse_args()
old, new = Release(a.old), Release(a.new)
meta, prof = read_hpoa(a.hpoa)
ids = sorted(prof); rng = random.Random(a.seed)
domain_both = sorted(t for t in old._domain if new.in_domain(t))
print(f"# hpoa {meta['version']} {meta['sha256'][:12]} · hp.obo {old.sha256[:12]} → {new.sha256[:12]} · {len(ids)} profiles · n {a.n} keep {a.keep} noise {a.noise} ({a.noise_mode}) seed {a.seed}", file=sys.stderr)

def ranking(rel, q):
    sc = {d: best_match_average(rel, q, prof[d][1])[0] for d in ids}
    order = sorted(ids, key=lambda d: (math.isnan(sc[d]), -(0 if math.isnan(sc[d]) else sc[d])))
    return sc, {d: i for i, d in enumerate(order, 1)}, order

def spearman(r1, r2):
    n = len(ids); m = (n + 1) / 2
    cov = sum((r1[k] - m) * (r2[k] - m) for k in ids); v = sum((r1[k] - m) ** 2 for k in ids)
    return cov / v if v else float("nan")   # both rankings are permutations of 1..n, so var1 == var2

cols = ["true_disease", "name", "n_annotated", "n_kept", "kept_terms", "noise_terms", "rank_true_old", "rank_true_new", "score_true_old", "score_true_new",
        "top1_old", "top1_new", "top1_changed", "jaccard_top5", "spearman_all"]
w = csv.writer(open(a.out, "w", newline="")); w.writerow(cols); t0 = time.time(); skipped = 0; done = 0
for q in rng.sample(ids, len(ids)):
    if done >= a.n: break
    name, terms = prof[q]
    usable = [t for t in terms if old.in_domain(t) and new.in_domain(t)]
    if len(usable) < 3:
        skipped += 1; continue
    k = max(3, round(a.keep * len(usable))); kept = rng.sample(usable, k)
    pool = [t for t in domain_both if t not in usable]
    if a.noise_mode == "ic-matched":
        ref = old.ic(rng.choice(kept)); pool = [t for t in pool if abs(old.ic(t) - ref) <= 0.05] or pool
    elif a.noise_mode == "neighbor":
        anchors = rng.sample(kept, min(3, len(kept))); pool = [t for t in pool if any(old.mica(t, k)[1] >= 0.3 for k in anchors)] or pool
    noise = rng.sample(pool, a.noise)
    patient = kept + noise
    so, ro, oo = ranking(old, patient); sn, rn, on = ranking(new, patient)
    j5 = len(set(oo[:5]) & set(on[:5])) / len(set(oo[:5]) | set(on[:5]))
    w.writerow([q, name, len(terms), k, ";".join(kept), ";".join(noise), ro[q], rn[q], f"{so[q]:.4f}", f"{sn[q]:.4f}", oo[0], on[0], int(oo[0] != on[0]), f"{j5:.3f}", f"{spearman(ro, rn):.4f}"])
    done += 1
    if done % 25 == 0: print(f"  {done}/{a.n} · {time.time() - t0:.0f}s", file=sys.stderr)
print(f"# done {done} patients ({skipped} source profiles skipped: < 3 usable terms) in {time.time() - t0:.0f}s → {a.out}", file=sys.stderr)
