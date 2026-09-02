# hpo-drift

**What did an HPO release change for *your* phenotype terms — and by how much did your similarity scores move?**

The Human Phenotype Ontology is updated roughly monthly. Terms get renamed, obsoleted, merged, and — the part nobody notices — the hierarchy gets new edges. New edges change information content, and information content is what Resnik and Lin similarity are made of. So the *same* patient set, scored against two HPO releases, gives *different* numbers, even if none of your terms were touched.

`hpo-drift` makes that visible for the term list you actually use, in seconds.

## Real example — Feb 2026 → Jun 2026, 14 paediatric-rheumatology terms

```
active terms: 19389 → 19836 (added 469, obsoleted 22, renamed 266)
is_a edges:   +886 / −185
```

None of the 14 terms changed — not a label, not a parent. And yet:

| term | label | IC old → new |
|---|---|---|
| HP:0001701 | Pericarditis | 0.930 → 0.837 |
| HP:0045073 | Serositis | 0.837 → 0.790 |
| HP:0000554 | Uveitis | 0.803 → 0.778 |
| HP:0001369 | Arthritis | 0.682 → 0.667 |

IC moved for **9 / 14** terms, and **91 / 91** pairwise Lin/Resnik scores moved (largest Lin shift −0.045, Skin rash ↔ Psoriasiform dermatitis). Full report: [`examples/report-v2026-02-16_v2026-06-23.md`](examples/report-v2026-02-16_v2026-06-23.md).

**Consequence:** if you publish phenotype-similarity results, pin the HPO release in Methods and match on IDs, not labels. `hpo-drift` gives you the numbers to say *how much* it matters for your data.

## Install

```bash
pip install git+https://github.com/MargoSolo/hpo-drift
```

## Use

```bash
# one term per line: HP IDs or labels (labels are resolved, and flagged — see lint)
hpo-drift report --old v2026-02-16 --new v2026-06-23 --terms my_terms.txt
hpo-drift report ... --json > drift.json          # machine-readable

# hygiene check of a term list against one release
hpo-drift lint --release v2026-06-23 --terms my_terms.txt
#  ⚠️ Arthritis: matched by LABEL — labels get renamed; store the ID → HP:0001369
#  ❌ Dactylitis: label not found (exact match on names/synonyms)
#  ❌ <obsolete id>: OBSOLETE term → replaced_by HP:…
# exit code 1 on errors → usable as a CI gate

hpo-drift fetch v2026-06-23                        # cache a release (~11 MB) under ~/.cache/hpo-drift
```

Releases are pulled from the official GitHub releases of `obophenotype/human-phenotype-ontology`; any tag like `v2026-06-23` works.

## What it reports

- **Per term:** status (`unchanged` / `renamed` / `obsoleted` → replacement / `merged` / `missing`), label change, parents added/removed, IC old → new.
- **Per pair:** Resnik and Lin in both releases, Δ, and the most-informative common ancestor (MICA) — so you can see *why* a pair moved.
- **Ontology-wide:** terms added / obsoleted / renamed, `is_a` edges added / removed.

## How similarity is computed (and why)

IC is **intrinsic** (Seco et al. 2004): `IC(t) = 1 − log(descendants(t)+1) / log(N)`. It depends only on the ontology graph, so drift measured here is caused **purely by ontology edits** — that is the effect this tool isolates. Annotation-based IC (from `phenotype.hpoa`) adds a second source of drift (annotation changes) and is on the roadmap as an option.

## GitHub Action

`.github/workflows/drift.yml` runs monthly: fetches the latest HPO release, compares it with your pinned release (`PINNED_HPO`), and uploads the report as an artifact. Turn it into a failing check by adding a threshold on `lin_delta` — trivial with `--json`.

## Roadmap

- `--ic annotations` (phenotype.hpoa-based IC) alongside intrinsic IC
- fuzzy / partial label resolution in `lint` (today: exact names + synonyms only)
- Phenopackets v2 export of a cleaned term list
- `--pairs` file to score only the pairs you care about (patient × disease)
- JOSS paper

## Cite

Solosenko M. *hpo-drift: quantifying the effect of HPO release changes on phenotype-similarity results.* 2026. (software, v0.1.0)

MIT License.
