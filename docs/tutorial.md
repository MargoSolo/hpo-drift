# Tutorial: reading a drift report

This walks through the real run behind the README figures — 14 terms of a syndromic neurodevelopmental presentation as a clinical geneticist records it, HPO v2026-02-16 → v2026-06-23 — and shows how to read each part of the report.

## 1. The term list

`examples/clinical_genetics_terms.txt`, IDs with the label as a comment, plus two label-only lines left in on purpose:

```
HP:0001263   # Global developmental delay
HP:0001249   # Intellectual disability
HP:0001250   # Seizure
…
Seizures                        # not an exact HPO label ('Seizure' is) → lint error
Developmental delay             # synonym → resolves, with a warning to store the ID
```

## 2. Lint first

```
hpo-drift lint --release v2026-06-23 --terms examples/clinical_genetics_terms.txt
```

Every label match is a warning with the ID to store; unknown labels and obsolete IDs are errors (exit code 1). "Seizures" fails because matching is exact on purpose — the same failure mode a label-matching pipeline has; "Developmental delay" resolves through a synonym to HP:0001263 with a warning.

## 3. The report

```
hpo-drift report --old v2026-02-16 --new v2026-06-23 --terms examples/clinical_genetics_terms.txt
```

The header states the method: Seco 2004 intrinsic IC on the `is_a` graph under root HP:0000118 (Phenotypic abnormality), with N = 18 690 → 19 120 active terms. Then the ontology-wide counts, then your terms:

## Your 14 terms

| term | status | old → new label | parents | IC old → new |
|---|---|---|---|---|
| HP:0001263 | unchanged | Global developmental delay | = | 0.836 → 0.837 |
| HP:0001249 | unchanged | Intellectual disability | = | 0.818 → 0.818 |
| HP:0001250 | unchanged | Seizure | = | 0.405 → 0.407 |
| HP:0000252 | unchanged | Microcephaly | = | 0.836 → 0.837 |
| HP:0001252 | unchanged | Hypotonia | = | 0.739 → 0.740 |
| HP:0004322 | unchanged | Short stature | = | 0.673 → 0.673 |
| HP:0000175 | unchanged | Cleft palate | = | 0.725 → 0.725 |
| HP:0000589 | unchanged | Coloboma | = | 0.777 → 0.777 |
| HP:0000365 | unchanged | Hearing impairment | = | 0.630 → 0.631 |
| HP:0000028 | unchanged | Cryptorchidism | = | 0.888 → 0.889 |
| HP:0000508 | unchanged | Ptosis | = | 0.789 → 0.789 |
| HP:0000316 | unchanged | Hypertelorism | = | 1.000 → 1.000 |
| HP:0001631 | unchanged | Atrial septal defect | = | 0.818 → 0.818 |
| HP:0000637 | unchanged | Long palpebral fissure | = | 1.000 → 1.000 |

Status is about the term record itself (label, obsoletion, direct `is_a` parents). IC moves anyway, because IC is a function of the whole graph below the term and of N.

## 4. Similarity drift

## Similarity drift (91 pairs; 13 moved)

| pair | Lin old → new | Δ | Resnik old → new | MICA old → new |
|---|---|---|---|---|
| HP:0001263 ↔ HP:0001249 | 0.736 → 0.731 | -0.004 | 0.609 → 0.605 | HP:0012759 → HP:0012759 |
| HP:0000252 ↔ HP:0001252 | 0.178 → 0.179 | +0.002 | 0.140 → 0.141 | HP:0033127 → HP:0033127 |
| HP:0000589 ↔ HP:0000316 | 0.375 → 0.377 | +0.002 | 0.334 → 0.335 | HP:0012372 → HP:0012372 |
| HP:0001249 ↔ HP:0001250 | 0.411 → 0.413 | +0.002 | 0.251 → 0.253 | HP:0012638 → HP:0012638 |
| HP:0001263 ↔ HP:0001250 | 0.405 → 0.407 | +0.002 | 0.251 → 0.253 | HP:0012638 → HP:0012638 |
| HP:0000589 ↔ HP:0000508 | 0.357 → 0.359 | +0.002 | 0.279 → 0.281 | HP:0000478 → HP:0000478 |
| HP:0000508 ↔ HP:0000316 | 0.312 → 0.314 | +0.001 | 0.279 → 0.281 | HP:0000478 → HP:0000478 |
| HP:0001249 ↔ HP:0000252 | 0.234 → 0.234 | +0.001 | 0.193 → 0.194 | HP:0000707 → HP:0000707 |

Only pairs whose most-informative common ancestor is below the root carry a non-zero Lin; here 13 of 91 pairs do, and all 13 moved. The remaining 78 pairs share only *Phenotypic abnormality* and stay at 0 in both releases. Shifts are small in this set (largest −0.004) — small, systematic, and invisible unless the release tag is written down.

## 5. What to write in Methods

"Phenotype similarity was computed with Lin similarity on Seco intrinsic IC over the HPO `is_a` graph (root HP:0000118), release v2026-06-23." One sentence; `hpo-drift` gives you the numbers to justify it.
