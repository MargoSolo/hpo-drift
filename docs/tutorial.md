# Tutorial: reading a drift report

This walks through the real run behind the README figures — the HPO-annotated phenotype profile of chronic granulomatous disease (ORPHA:379), HPO v2026-02-16 → v2026-06-23 — and shows how to read each part of the report.

## 1. The term list

`examples/cgd_orpha379_terms.txt`: the 22 phenotypic-abnormality terms annotated to the disease in `phenotype.hpoa`, IDs with the label as a comment. Inheritance, onset and frequency terms are not phenotypes and are left out: they sit outside *Phenotypic abnormality* and carry no IC.

Why this disease? `examples/rank_profiles.py` scores every OMIM and Orphanet profile with 12–60 terms (7121 profiles, one inclusion rule, no subsets) by mean |ΔLin| over informative pairs. CGD ranks 12 of 7121 (top 0.2 %). It is shown because it is a classic monogenic disease whose drift mechanism fits in two sentences; the profiles ranked above it are in the CSV. The top of the ranking is dominated by inborn errors of immunity: the immunology branch was restructured in this interval.

## 2. Lint first

```
hpo-drift lint --release v2026-06-23 --terms examples/cgd_orpha379_terms.txt
```

All IDs resolve; nothing is obsolete. For a label-based list you would see warnings with the ID to store and errors for labels that are not exact HPO names.

## 3. The report

```
hpo-drift report --old v2026-02-16 --new v2026-06-23 --terms examples/cgd_orpha379_terms.txt
```

The header states the method: Seco 2004 intrinsic IC on the `is_a` graph under root HP:0000118 (Phenotypic abnormality), N = 18 690 → 19 120 active terms. Then the ontology-wide counts, then your terms:

## Your 22 terms

| term | status | old → new label | parents | IC old → new |
|---|---|---|---|---|
| HP:0000230 | unchanged | Gingivitis | +HP:5210280 | 1.000 → 0.859 |
| HP:0000246 | unchanged | Sinusitis | +HP:5210121 | 0.859 → 0.859 |
| HP:0000388 | unchanged | Otitis media | = | 0.818 → 0.803 |
| HP:0000964 | unchanged | Eczematoid dermatitis | = | 0.766 → 0.757 |
| HP:0000992 | unchanged | Cutaneous photosensitivity | = | 0.818 → 0.818 |
| HP:0001034 | unchanged | Hypermelanotic macule | = | 0.789 → 0.789 |
| HP:0001287 | unchanged | Meningitis | = | 0.836 → 0.748 |
| HP:0001744 | unchanged | Splenomegaly | = | 0.888 → 0.889 |
| HP:0001874 | unchanged | Abnormality of neutrophils | = | 0.641 → 0.642 |
| HP:0001945 | unchanged | Fever | = | 0.777 → 0.777 |
| HP:0002021 | unchanged | Pyloric stenosis | = | 1.000 → 1.000 |
| HP:0002024 | unchanged | Malabsorption | = | 0.836 → 0.837 |
| HP:0002205 | unchanged | Recurrent respiratory infections | = | 0.701 → 0.713 |
| HP:0002240 | unchanged | Hepatomegaly | = | 0.888 → 0.889 |
| HP:0002575 | unchanged | Tracheoesophageal fistula | = | 1.000 → 1.000 |
| HP:0006510 | unchanged | Chronic pulmonary obstruction | = | 1.000 → 1.000 |
| HP:0012733 | unchanged | Macule | = | 0.712 → 0.713 |
| HP:0100523 | unchanged | Liver abscess | = | 1.000 → 0.757 |
| HP:0100533 | unchanged | Inflammatory abnormality of the eye | = | 0.665 → 0.658 |
| HP:0100721 | unchanged | Mediastinal lymphadenopathy | = | 1.000 → 1.000 |
| HP:0100806 | unchanged | Sepsis | = | 0.888 → 0.803 |
| HP:0200042 | unchanged | Skin ulcer | = | 0.818 → 0.818 |

Two terms gained a direct parent from the new *Unusual infection* hierarchy: *Gingivitis* → `HP:5210280` Unusual oral cavity infection, *Sinusitis* → `HP:5210121` Unusual upper respiratory tract infection. Everything else about the terms is unchanged; IC still moved for 18 of 22, because IC is a function of the graph below each term and of N.

## 4. Similarity drift

## Similarity drift (231 pairs; 95 moved)

| pair | Lin old → new | Δ | Resnik old → new | MICA old → new |
|---|---|---|---|---|
| HP:0000230 ↔ HP:0001287 | 0.000 → 0.553 | +0.553 | 0.000 → 0.444 | HP:0000118 → HP:0032158 |
| HP:0000230 ↔ HP:0002205 | 0.000 → 0.456 | +0.456 | 0.000 → 0.358 | HP:0000118 → HP:0032101 |
| HP:0000230 ↔ HP:0100806 | 0.000 → 0.431 | +0.431 | 0.000 → 0.358 | HP:0000118 → HP:0032101 |
| HP:0000230 ↔ HP:0100533 | 0.000 → 0.351 | +0.351 | 0.000 → 0.266 | HP:0000118 → HP:0010978 |
| HP:0000230 ↔ HP:0000964 | 0.000 → 0.330 | +0.330 | 0.000 → 0.266 | HP:0000118 → HP:0010978 |
| HP:0000230 ↔ HP:0001874 | 0.000 → 0.321 | +0.321 | 0.000 → 0.241 | HP:0000118 → HP:0002715 |
| HP:0000230 ↔ HP:0000388 | 0.000 → 0.321 | +0.321 | 0.000 → 0.266 | HP:0000118 → HP:0010978 |
| HP:0000246 ↔ HP:0002205 | 0.480 → 0.781 | +0.301 | 0.374 → 0.614 | HP:0012252 → HP:0011947 |

Gaining that parent moves *Gingivitis* into the immune branch: its most-informative common ancestor with *Meningitis*, *Sepsis* or *Recurrent respiratory infections* is no longer the root, and Lin rises from 0.00 to 0.55, 0.43, 0.46. Two edits to two terms, and 95 of 95 informative pairs move, 15 of them by more than 0.1. The 136 root-only pairs stay at 0.

## 5. What to write in Methods

"Phenotype similarity was computed with Lin similarity on Seco intrinsic IC over the HPO `is_a` graph (root HP:0000118), release v2026-06-23." One sentence; `hpo-drift` gives you the numbers to justify it, and `rank_profiles.py` tells you whether your disease of interest is among the exposed ones.
