"""CLI: hpo-drift {fetch,diff,sim,lint,report}."""
from __future__ import annotations

import argparse
import json
import math
import sys

from . import __version__
from .core import Release, diff_terms, fetch, global_counts, lint, read_terms, similarity_drift


def _f(x: float) -> str:
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{x:.3f}"


def _resolve_all(rel: Release, tokens: list[str]) -> list[str]:
    ids = []
    for t in tokens:
        tid, _ = rel.resolve(t)
        if tid:
            ids.append(tid)
    return list(dict.fromkeys(ids))


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
    ids = _resolve_all(old, tokens)
    g = global_counts(old, new)
    changes = diff_terms(old, new, ids)
    drift = similarity_drift(old, new, ids)
    L = [f"# hpo-drift: {old.tag} → {new.tag}", "", f"_IC: Seco 2004 intrinsic, on the `is_a` graph under root {old.root} ({old.name(old.root) or '?'}); N = {old._n_active} → {new._n_active} active terms. Similarity: Resnik / Lin via MICA._", ""]
    L += ["## Ontology-wide",
          f"- active terms: {g['terms_old']} → {g['terms_new']} (added {g['added']}, obsoleted {g['obsoleted']}, renamed {g['renamed']})",
          f"- `is_a` edges: +{g['is_a_added']} / −{g['is_a_removed']}  ← edge changes move information content, hence every similarity score", ""]
    L += [f"## Your {len(ids)} terms", "", "| term | status | old → new label | parents | IC old → new |", "|---|---|---|---|---|"]
    for c in changes:
        lab = c.old_name if c.status == "unchanged" else f"{c.old_name} → {c.new_name}"
        if c.status in ("obsoleted", "merged"):
            lab += f" (→ {', '.join(c.replaced_by) or '?'})"
        par = ("+" + ",".join(sorted(c.parents_added)) if c.parents_added else "") + (" −" + ",".join(sorted(c.parents_removed)) if c.parents_removed else "")
        L.append(f"| {c.tid} | {c.status} | {lab} | {par or '='} | {_f(c.ic_old)} → {_f(c.ic_new)} |")
    n_ic = sum(1 for c in changes if not math.isnan(c.ic_delta) and abs(c.ic_delta) > 1e-9)
    L += ["", f"IC changed for **{n_ic}/{len(changes)}** of your terms even where nothing about the term itself changed.", ""]
    if drift:
        moved = sorted((d for d in drift if abs(d.lin_delta) > 1e-9), key=lambda d: -abs(d.lin_delta))
        L += [f"## Similarity drift ({len(drift)} pairs; {len(moved)} moved)", "",
              "| pair | Lin old → new | Δ | Resnik old → new | MICA old → new |", "|---|---|---|---|---|"]
        for d in moved[:top]:
            L.append(f"| {d.a} ↔ {d.b} | {_f(d.lin_old)} → {_f(d.lin_new)} | {d.lin_delta:+.3f} | {_f(d.resnik_old)} → {_f(d.resnik_new)} | {d.mica_old} → {d.mica_new} |")
        L += ["", "_Lin/Resnik use intrinsic IC (Seco 2004), so this drift is caused purely by ontology structure edits — pin your HPO release in Methods._"]
    return "\n".join(L)


def cmd_report(a):
    old, new = Release(a.old, root=a.root), Release(a.new, root=a.root)
    tokens = read_terms(a.terms)
    if a.json:
        ids = _resolve_all(old, tokens)
        out = {"old": a.old, "new": a.new, "ic": {"method": "Seco 2004 intrinsic IC on the is_a graph", "root": a.root, "n_terms_old": old._n_active, "n_terms_new": new._n_active},
               "similarity": "Resnik and Lin via most-informative common ancestor (is_a only)", "global": global_counts(old, new),
               "terms": [c.__dict__ | {"parents_added": sorted(c.parents_added), "parents_removed": sorted(c.parents_removed)} for c in diff_terms(old, new, ids)],
               "pairs": [d.__dict__ for d in similarity_drift(old, new, ids)]}
        print(json.dumps(out, ensure_ascii=False, indent=2, default=str)); return
    print(_report(old, new, tokens, a.top))


def main(argv=None):
    p = argparse.ArgumentParser(prog="hpo-drift", description="What did an HPO release change for YOUR terms?")
    p.add_argument("--version", action="version", version=__version__)
    s = p.add_subparsers(dest="cmd", required=True)
    f = s.add_parser("fetch", help="download hp.obo for release tag(s)"); f.add_argument("tags", nargs="+"); f.set_defaults(fn=cmd_fetch)
    l = s.add_parser("lint", help="check a term list against one release"); l.add_argument("--release", required=True); l.add_argument("--terms", required=True); l.add_argument("--json", action="store_true"); l.set_defaults(fn=cmd_lint)
    r = s.add_parser("report", help="diff + similarity drift between two releases for your terms")
    r.add_argument("--old", required=True); r.add_argument("--new", required=True); r.add_argument("--terms", required=True)
    r.add_argument("--top", type=int, default=15); r.add_argument("--json", action="store_true"); r.add_argument("--root", default="HP:0000118", help="root of the is_a closure used for IC (default Phenotypic abnormality)"); r.set_defaults(fn=cmd_report)
    for alias, target in (("diff", cmd_report), ("sim", cmd_report)):
        d = s.add_parser(alias, help=f"alias of report"); d.add_argument("--old", required=True); d.add_argument("--new", required=True); d.add_argument("--terms", required=True); d.add_argument("--top", type=int, default=15); d.add_argument("--json", action="store_true"); d.add_argument("--root", default="HP:0000118"); d.set_defaults(fn=target)
    a = p.parse_args(argv); a.fn(a)


if __name__ == "__main__":
    main()
