# Tutorial: measuring drift for your own term list

This walks through the real run behind the README figures — 14 paediatric-rheumatology terms, HPO v2026-02-16 → v2026-06-23 — and shows how to read each part of the report.

## 1. Write your terms, one per line

```
Arthritis
Uveitis
Fever
Recurrent fever
Skin rash
Hepatosplenomegaly
Macrophage activation syndrome   # not an HPO label → lint error; HPO captures it as HP:0012156 (Hemophagocytosis)
Lymphadenopathy
…
```

IDs are safest. Labels work, and `lint` will tell you which ones it matched by label so you can replace them with IDs.

## 2. Run lint against the release you are pinning

```bash
hpo-drift lint --release v2026-06-23 --terms examples/pediatric_rheum_terms.txt
```

Every label match is a warning with the ID to store; unknown labels and obsolete IDs are errors (exit code 1). In the example set two labels are unresolvable on purpose: "Dactylitis" is split into two HPO terms and "Macrophage activation syndrome" is a disease-level concept.

## 3. Run the report

```bash
hpo-drift report --old v2026-02-16 --new v2026-06-23 --terms examples/pediatric_rheum_terms.txt
```

Full output of this exact run:

```
# hpo-drift: v2026-02-16 → v2026-06-23

## Ontology-wide
- active terms: 19389 → 19836 (added 469, obsoleted 22, renamed 266)
- `is_a` edges: +886 / −185  ← edge changes move information content, hence every similarity score

## Your 14 terms

| term | status | old → new label | parents | IC old → new |
|---|---|---|---|---|
| HP:0001369 | unchanged | Arthritis | = | 0.682 → 0.667 |
| HP:0000554 | unchanged | Uveitis | = | 0.803 → 0.778 |
| HP:0001945 | unchanged | Fever | = | 0.777 → 0.778 |
| HP:0001954 | unchanged | Recurrent fever | = | 0.860 → 0.860 |
| HP:0000988 | unchanged | Skin rash | = | 0.733 → 0.733 |
| HP:0001433 | unchanged | Hepatosplenomegaly | = | 1.000 → 1.000 |
| HP:0002716 | unchanged | Lymphadenopathy | = | 0.740 → 0.733 |
| HP:0001701 | unchanged | Pericarditis | = | 0.930 → 0.837 |
| HP:0000155 | unchanged | Oral ulcer | = | 1.000 → 1.000 |
| HP:0100686 | unchanged | Enthesitis | = | 1.000 → 1.000 |
| HP:0003765 | unchanged | Psoriasiform dermatitis | = | 1.000 → 1.000 |
| HP:0011227 | unchanged | Elevated circulating C-reactive protein concentration | = | 1.000 → 1.000 |
| HP:0045073 | unchanged | Serositis | = | 0.837 → 0.790 |
| HP:0003326 | unchanged | Myalgia | = | 0.889 → 0.889 |

IC changed for **9/14** of your terms even where nothing about the term itself changed.

## Similarity drift (91 pairs; 91 moved)

| pair | Lin old → new | Δ | Resnik old → new | MICA old → new |
|---|---|---|---|---|
| HP:0000988 ↔ HP:0003765 | 0.664 → 0.619 | -0.045 | 0.576 → 0.537 | HP:0011123 → HP:0011123 |
| HP:0000554 ↔ HP:0000988 | 0.598 → 0.566 | -0.032 | 0.459 → 0.428 | HP:0012649 → HP:0012649 |
| HP:0000988 ↔ HP:0002716 | 0.364 → 0.332 | -0.032 | 0.268 → 0.244 | HP:0002715 → HP:0002715 |
| HP:0000988 ↔ HP:0001433 | 0.310 → 0.281 | -0.028 | 0.268 → 0.244 | HP:0002715 → HP:0002715 |
| HP:0000554 ↔ HP:0003765 | 0.510 → 0.481 | -0.028 | 0.459 → 0.428 | HP:0012649 → HP:0012649 |
| HP:0002716 ↔ HP:0003765 | 0.308 → 0.281 | -0.027 | 0.268 → 0.244 | HP:0002715 → HP:0002715 |
| HP:0000554 ↔ HP:0002716 | 0.348 → 0.323 | -0.025 | 0.268 → 0.244 | HP:0002715 → HP:0002715 |
| HP:0001433 ↔ HP:0003765 | 0.268 → 0.244 | -0.025 | 0.268 → 0.244 | HP:0002715 → HP:0002715 |
| HP:0000988 ↔ HP:0045073 | 0.585 → 0.562 | -0.024 | 0.459 → 0.428 | HP:0012649 → HP:0012649 |
| HP:0000554 ↔ HP:0001433 | 0.298 → 0.274 | -0.023 | 0.268 → 0.244 | HP:0002715 → HP:0002715 |
| HP:0001701 ↔ HP:0045073 | 0.947 → 0.971 | +0.023 | 0.837 → 0.790 | HP:0045073 → HP:0045073 |
| HP:0003765 ↔ HP:0045073 | 0.500 → 0.478 | -0.022 | 0.459 → 0.428 | HP:0012649 → HP:0012649 |

_Lin/Resnik use intrinsic IC (Seco 2004), so this drift is caused purely by ontology structure edits — pin your HPO release in Methods._
…
```

## 4. Reading it

- **Ontology-wide counts** tell you how busy the release was.
- **Per term:** `unchanged` with a moved IC is the key case — the term was not touched, the graph around it was.
- **Per pair:** the MICA column explains a move; if the MICA changed, the two terms now share a different most-informative ancestor.

## 5. Machine-readable

```bash
hpo-drift report --old v2026-02-16 --new v2026-06-23 --terms my_terms.txt --json > drift.json
```

The README figures are generated from that JSON. A threshold on `lin_delta` turns the monthly Action into a failing check.
