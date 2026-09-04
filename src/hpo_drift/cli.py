"""CLI: hpo-drift {fetch,lint,report,cohort,rank} (diff/sim are aliases of report)."""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
import sys

from . import __version__
from .core import PROFILE_COLUMNS, PROFILE_STATUSES, Release, diff_terms, fetch, global_counts, lint, profile_drift, profile_similarity, rank_diseases, read_hpoa, read_terms, similarity_drift, usable_terms


def _f(x: float) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.3f}"


def _dedupe(tokens: list[str]) -> list[str]:
    return list(dict.fromkeys(t.strip() for t in tokens if t.strip()))


def cmd_fetch(a):
    for tag in a.tags:
        print(fetch(tag))


def cmd_lint(a):
    rel = Release(a.release)
    issues = lint(rel, read_terms(a.terms))
    if a.json:
        print(json.dumps([i.__dict__ for i in issues], ensure_ascii=False, indent=2)); return
    if not issues:
        print(f"✅ {a.terms}: clean against {a.release}"); return
    for i in issues:
        mark = {"error": "❌", "warn": "⚠️", "info": "ℹ️"}[i.level]
        print(f"{mark} {i.token}: {i.message}" + (f" → {i.suggestion}" if i.suggestion else ""))
    sys.exit(1 if any(i.level == "error" for i in issues) else 0)


def _report(old: Release, new: Release, tokens: list[str], top: int) -> str:
    tokens = _dedupe(tokens)
    g = global_counts(old, new)
    changes = diff_terms(old, new, tokens)
    ids = list(dict.fromkeys(c.tid for c in changes if c.status not in ("unknown", "ambiguous")))
    drift = similarity_drift(old, new, ids)
    L = [f"# hpo-drift: {old.tag} → {new.tag}", "", f"_IC: Seco 2004 intrinsic, on the `is_a` graph under root {old.root} ({old.name(old.root) or '?'}); N = {old._n_active} → {new._n_active} active terms. Similarity: Resnik / Lin via MICA._",
         f"_Inputs: hp.obo {old.tag} sha256 `{old.sha256[:12]}…`, hp.obo {new.tag} sha256 `{new.sha256[:12]}…` (full hashes in `--json`)._", ""]
    L += ["## Ontology-wide",
          f"- active terms: {g['terms_old']} → {g['terms_new']} (added {g['added']}, obsoleted {g['obsoleted']}, renamed {g['renamed']})",
          f"- `is_a` edges: +{g['is_a_added']} / −{g['is_a_removed']}  ← edge changes move information content and can propagate into downstream similarity scores", ""]
    L += [f"## Your {len(changes)} terms", ""]
    if not changes:
        L += ["**No usable terms**: the list is empty.", ""]
        return "\n".join(L)
    L += ["| term | status | old → new label | parents | IC old → new |", "|---|---|---|---|---|"]
    for c in changes:
        lab = c.old_name if c.status == "unchanged" else f"{c.old_name} → {c.new_name}"
        if c.status == "unknown":
            lab = f"`{c.tid}` resolves in neither release"
        elif c.status == "new-in-new":
            lab = f"{c.new_name} (not in {old.tag})"
        elif c.status == "ambiguous":
            lab = f"label `{c.token}` = {c.tid} ({c.old_name}) in {old.tag} but {c.replaced_by[0]} ({c.new_name}) in {new.tag}"
        elif c.status in ("obsoleted", "merged"):
            lab += f" (→ {', '.join(c.replaced_by) or '?'})"
        if c.token and c.status not in ("unknown", "ambiguous"):
            lab += f" (from `{c.token}`, by {c.how})"
        par = ("+" + ",".join(sorted(c.parents_added)) if c.parents_added else "") + (" −" + ",".join(sorted(c.parents_removed)) if c.parents_removed else "")
        st = "OUT_OF_DOMAIN" if (c.domain == "OUT_OF_DOMAIN" and c.status in ("unchanged", "renamed")) else c.status
        L.append(f"| {c.tid} | {st} | {lab} | {par or '='} | {_f(c.ic_old)} → {_f(c.ic_new)} |")
    n_ic = sum(1 for c in changes if not math.isnan(c.ic_delta) and abs(c.ic_delta) > 1e-9)
    n_ic01 = sum(1 for c in changes if not math.isnan(c.ic_delta) and abs(c.ic_delta) > 0.01)
    L += ["", f"IC changed for **{n_ic}/{len(changes)}** of your terms (|ΔIC| > 0.01 for **{n_ic01}/{len(changes)}**). N also changed ({old._n_active} → {new._n_active}), which by itself shifts non-leaf intrinsic IC even without a direct edit to the term; leaves stay at 1.", ""]
    special = [c for c in changes if c.status in ("new-in-new", "ambiguous", "unknown")]
    if special:
        L += ["**Resolved against both releases**: " + "; ".join(f"{c.tid if c.status != 'unknown' else c.token} {c.status}" for c in special) + ". new-in-new terms have IC only in the new release and enter no pair; ambiguous labels are not compared — store IDs.", ""]
    ood = [c for c in changes if c.domain == "OUT_OF_DOMAIN" and c.status in ("unchanged", "renamed")]
    if ood:
        L += [f"**{len(ood)} term(s) OUT_OF_DOMAIN**: {', '.join(f'{c.tid} ({c.old_name})' for c in ood)} lie outside the similarity domain {old.root} ({old.name(old.root) or '?'}). "
              "They have no IC here and enter no pair. If that branch is what you mean to compare, choose it with `--root HP:...`.", ""]
    live = usable_terms(old, new, ids)
    if len(live) == 1:
        L += [f"**Single usable term** ({live[0]}): IC drift is reported above; pairwise similarity needs two or more usable terms.", ""]
        return "\n".join(L)
    if len(live) == 0:
        L += ["**No usable terms for similarity**: every term is missing, obsolete or out of domain in one of the releases; see the statuses above.", ""]
        return "\n".join(L)
    inf = [d for d in drift if d.kind == "INFORMATIVE"]
    root_only = len(drift) - len(inf)
    moved = sorted((d for d in inf if abs(d.lin_delta) > 1e-9), key=lambda d: -abs(d.lin_delta))
    L += [f"## Similarity drift ({len(drift)} pairs: {len(inf)} informative, {root_only} ROOT_ONLY; {len(moved)} informative pairs moved)", ""]
    if root_only:
        L += [f"_ROOT_ONLY pairs share only the root {old.root} in both releases: Lin 0 → 0 by construction; they are listed in `--json` with `kind`._", ""]
    if not inf:
        L += ["**NO_INFORMATIVE_PAIRS**: every pair shares only the root, so no similarity drift is defined for this set.", ""]
        return "\n".join(L)
    L += ["| pair | Lin old → new | Δ | Resnik old → new | MICA old → new |", "|---|---|---|---|---|"]
    for d in moved[:top]:
        L.append(f"| {d.a} ↔ {d.b} | {_f(d.lin_old)} → {_f(d.lin_new)} | {d.lin_delta:+.3f} | {_f(d.resnik_old)} → {_f(d.resnik_new)} | {d.mica_old} → {d.mica_new} |")
    if not moved:
        L.append("| (no informative pair moved) | | | | |")
    L += ["", "_Lin/Resnik use intrinsic IC (Seco 2004), so this drift is caused purely by ontology structure edits — pin your HPO release in Methods._"]
    return "\n".join(L)


def cmd_report(a):
    old, new = Release(a.old, root=a.root), Release(a.new, root=a.root)
    tokens = read_terms(a.terms)
    if a.json:
        changes = diff_terms(old, new, _dedupe(tokens))
        ids = list(dict.fromkeys(c.tid for c in changes if c.status not in ("unknown", "ambiguous")))
        out = {"old": a.old, "new": a.new, "old_ontology": old.provenance(), "new_ontology": new.provenance(),
               "ic": {"method": "Seco 2004 intrinsic IC on the is_a graph", "root": a.root, "n_terms_old": old._n_active, "n_terms_new": new._n_active},
               "similarity": "Resnik and Lin via most-informative common ancestor (is_a only)", "global": global_counts(old, new),
               "terms": [c.__dict__ | {"parents_added": sorted(c.parents_added), "parents_removed": sorted(c.parents_removed)} for c in changes],
               "pairs": [d.__dict__ for d in similarity_drift(old, new, ids)], "profile": profile_drift(old, new, ids)}
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str)); return
    print(_report(old, new, tokens, a.top))


def _fmt(v):
    return "" if isinstance(v, float) and math.isnan(v) else (f"{v:.6f}" if isinstance(v, float) else v)


def cmd_cohort(a):
    """Every disease profile in phenotype.hpoa, whatever its size. No inclusion cutoff: profiles that cannot support pairwise analysis stay in the table with a status."""
    old, new = Release(a.old, root=a.root), Release(a.new, root=a.root)
    meta, profiles = read_hpoa(a.hpoa)
    cols = ["disease", "name", "database"] + PROFILE_COLUMNS
    counts = {s: 0 for s in PROFILE_STATUSES}
    with open(a.out, "w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh); w.writerow(cols)
        for i, (d, (name, terms)) in enumerate(profiles.items(), 1):
            r = profile_drift(old, new, terms); counts[r["status"]] += 1
            w.writerow([d, name, d.split(":")[0]] + [_fmt(r[k]) for k in PROFILE_COLUMNS])
            if a.progress and i % 1000 == 0:
                print(f"  {i}/{len(profiles)}", file=sys.stderr)
    meta.update(old=a.old, new=a.new, old_ontology=old.provenance(), new_ontology=new.provenance(), root=a.root, ic="Seco 2004 intrinsic IC on the is_a graph",
                profile_definition="unique HP ids of rows with aspect P and no NOT qualifier; diseases with no such row have no profile", n_profiles=len(profiles), status_counts=counts, columns=cols)
    with open(a.out + ".meta.json", "w", encoding="utf-8") as fh:
        json.dump(meta, fh, indent=2)
    print(f"phenotype.hpoa version {meta['version']} · sha256 {meta['sha256']} · {meta['n_rows']} rows", file=sys.stderr)
    print(f"hp.obo {a.old} sha256 {old.sha256} · hp.obo {a.new} sha256 {new.sha256}", file=sys.stderr)
    print(f"{len(profiles)} disease profiles (of {meta['n_disease_ids_in_file']} disease ids in the file; {meta['n_diseases_without_positive_P']} have no positive P row) → {a.out}: " + ", ".join(f"{k} {v}" for k, v in counts.items()), file=sys.stderr)


def cmd_rank(a):
    """Optional step after cohort: keep RANKABLE rows, sort by a metric, add a rank column. The complete table is untouched."""
    with open(a.csv, encoding="utf-8") as fh:
        rows = list(csv.DictReader(fh))
    if a.metric not in (rows[0].keys() if rows else []):
        sys.exit(f"unknown metric {a.metric!r}; columns: {', '.join(rows[0].keys()) if rows else '(empty file)'}")
    rk = [r for r in rows if r["status"] == "RANKABLE" and r[a.metric] != ""]
    rk.sort(key=lambda r: -float(r[a.metric]))
    w = csv.writer(sys.stdout); w.writerow(["rank"] + list(rows[0].keys()))
    for i, r in enumerate(rk[: a.top] if a.top else rk, 1):
        w.writerow([i] + list(r.values()))
    vals = sorted(float(r[a.metric]) for r in rk)
    if vals:
        q = lambda p: vals[min(len(vals) - 1, int(p * len(vals)))]
        print(f"# {len(rk)} RANKABLE of {len(rows)} profiles · {a.metric}: median {q(.5):.4f} · p90 {q(.9):.4f} · p99 {q(.99):.4f} · max {vals[-1]:.4f}", file=sys.stderr)
    skipped = {s: sum(1 for r in rows if r["status"] == s) for s in PROFILE_STATUSES if s != "RANKABLE"}
    print("# not ranked (kept in the cohort table): " + ", ".join(f"{k} {v}" for k, v in skipped.items()), file=sys.stderr)


def _ids(old: Release, new: Release, tokens: list[str]) -> list[str]:
    return list(dict.fromkeys(c.tid for c in diff_terms(old, new, _dedupe(tokens)) if c.status not in ("unknown", "ambiguous")))


def cmd_profiles(a):
    """Set-to-set similarity (symmetric Best Match Average of Lin) between a query and a target term list, in both releases."""
    old, new = Release(a.old, root=a.root), Release(a.new, root=a.root)
    q, t = _ids(old, new, read_terms(a.query)), _ids(old, new, read_terms(a.target))
    r = profile_similarity(old, new, q, t)
    if a.json:
        print(json.dumps({"old": a.old, "new": a.new, "old_ontology": old.provenance(), "new_ontology": new.provenance(), "method": "symmetric Best Match Average of Lin (Seco intrinsic IC, is_a graph)", "root": a.root, "query": q, "target": t} | r, indent=2, default=str)); return
    print(f"# hpo-drift profiles: {a.query} × {a.target}\n")
    print(f"_Symmetric Best Match Average of Lin; Seco intrinsic IC on the `is_a` graph under {a.root}. Query terms used {r['n_query_used_old']} → {r['n_query_used_new']} of {len(q)}; target {r['n_target_used_old']} → {r['n_target_used_new']} of {len(t)}._\n")
    print("| release | profile similarity |\n|---|---|"); print(f"| {a.old} | {_f(r['score_old'])} |"); print(f"| {a.new} | {_f(r['score_new'])} |"); print(f"| Δ | {r['delta']:+.3f} |\n")
    print("| query term | best match old → new | Lin old → new | Δ |\n|---|---|---|---|")
    for m in r["matches"][: a.top]:
        bm = f"{m['best_old']} {old.name(m['best_old'])}" + ("" if m["best_old"] == m["best_new"] else f" → {m['best_new']} {new.name(m['best_new'])}")
        print(f"| {m['query']} {old.name(m['query']) or new.name(m['query'])} | {bm} | {_f(m['lin_old'])} → {_f(m['lin_new'])} | {m['delta']:+.3f} |")


def cmd_rank_diseases(a):
    """Rank every disease profile in phenotype.hpoa against a query in both releases; report rank and score changes."""
    old, new = Release(a.old, root=a.root), Release(a.new, root=a.root)
    q = _ids(old, new, read_terms(a.query))
    meta, profiles = read_hpoa(a.hpoa)
    rows = rank_diseases(old, new, q, profiles)
    cols = ["disease", "name", "n_terms", "score_old", "rank_old", "score_new", "rank_new", "rank_change", "delta"]
    if a.out:
        with open(a.out, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh); w.writerow(cols); [w.writerow([_fmt(r[k]) for k in cols]) for r in rows]
        with open(a.out + ".meta.json", "w", encoding="utf-8") as fh:
            json.dump({"query_file": a.query, "query": q, "hpoa": {k: meta[k] for k in ("path", "version", "sha256")}, "old_ontology": old.provenance(), "new_ontology": new.provenance(),
                       "method": "symmetric Best Match Average of Lin (Seco intrinsic IC, is_a graph)", "root": a.root, "n_diseases": len(rows)}, fh, indent=2)
    print(f"# hpo-drift rank-diseases: {a.query} ({len(q)} terms) × {len(rows)} disease profiles, {a.old} → {a.new}\n")
    print(f"| disease | terms | score old → new | rank old → new |\n|---|---|---|---|")
    for r in rows[: a.top]:
        print(f"| {r['name']} ({r['disease']}) | {r['n_terms']} | {_f(r['score_old'])} → {_f(r['score_new'])} | {r['rank_old']} → {r['rank_new']} |")
    moved = sorted([r for r in rows if r["rank_old"] <= a.top or r["rank_new"] <= a.top], key=lambda r: -abs(r["rank_change"]))[:10]
    print(f"\nLargest rank changes among diseases in either top {a.top}:\n\n| disease | rank old → new | score old → new |\n|---|---|---|")
    for r in moved:
        print(f"| {r['name']} ({r['disease']}) | {r['rank_old']} → {r['rank_new']} | {_f(r['score_old'])} → {_f(r['score_new'])} |")
    if a.out:
        print(f"\nFull table: {a.out} (+ .meta.json with query, hpoa and ontology provenance)", file=sys.stderr)


def main(argv=None):
    p = argparse.ArgumentParser(prog="hpo-drift", description="What did an HPO release change for YOUR terms?")
    p.add_argument("--version", action="version", version=__version__)
    s = p.add_subparsers(dest="cmd", required=True)
    f = s.add_parser("fetch", help="download hp.obo for release tag(s)"); f.add_argument("tags", nargs="+"); f.set_defaults(fn=cmd_fetch)
    l = s.add_parser("lint", help="check a term list against one release"); l.add_argument("--release", required=True); l.add_argument("--terms", required=True); l.add_argument("--json", action="store_true"); l.set_defaults(fn=cmd_lint)
    r = s.add_parser("report", help="diff + similarity drift between two releases for your terms")
    r.add_argument("--old", required=True); r.add_argument("--new", required=True); r.add_argument("--terms", required=True)
    r.add_argument("--top", type=int, default=15); r.add_argument("--json", action="store_true"); r.add_argument("--root", default="HP:0000118", help="root of the is_a closure used for IC (default Phenotypic abnormality)"); r.set_defaults(fn=cmd_report)
    co = s.add_parser("cohort", help="drift summary for EVERY disease profile in a phenotype.hpoa (no size cutoff; statuses instead)")
    co.add_argument("--hpoa", required=True); co.add_argument("--old", required=True); co.add_argument("--new", required=True); co.add_argument("--out", required=True)
    co.add_argument("--root", default="HP:0000118"); co.add_argument("--progress", action="store_true"); co.set_defaults(fn=cmd_cohort)
    rk = s.add_parser("rank", help="optional: rank the RANKABLE rows of a cohort table by a metric")
    rk.add_argument("csv"); rk.add_argument("--metric", default="mean_abs_dlin"); rk.add_argument("--top", type=int, default=0); rk.set_defaults(fn=cmd_rank)
    pf = s.add_parser("profiles", help="query × target set-to-set similarity (Best Match Average of Lin) in both releases")
    pf.add_argument("--query", required=True); pf.add_argument("--target", required=True); pf.add_argument("--old", required=True); pf.add_argument("--new", required=True)
    pf.add_argument("--root", default="HP:0000118"); pf.add_argument("--top", type=int, default=15); pf.add_argument("--json", action="store_true"); pf.set_defaults(fn=cmd_profiles)
    rd = s.add_parser("rank-diseases", help="rank every phenotype.hpoa disease profile against a query in both releases")
    rd.add_argument("--query", required=True); rd.add_argument("--hpoa", required=True); rd.add_argument("--old", required=True); rd.add_argument("--new", required=True)
    rd.add_argument("--root", default="HP:0000118"); rd.add_argument("--top", type=int, default=20); rd.add_argument("--out"); rd.set_defaults(fn=cmd_rank_diseases)
    for alias, target in (("diff", cmd_report), ("sim", cmd_report)):
        d = s.add_parser(alias, help=f"alias of report"); d.add_argument("--old", required=True); d.add_argument("--new", required=True); d.add_argument("--terms", required=True); d.add_argument("--top", type=int, default=15); d.add_argument("--json", action="store_true"); d.add_argument("--root", default="HP:0000118"); d.set_defaults(fn=target)
    a = p.parse_args(argv); a.fn(a)


if __name__ == "__main__":
    main()
