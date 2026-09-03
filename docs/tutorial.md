# Tutorial: reading a drift report

This walks through the real run behind the README figures — the HPO-annotated phenotype profile of severe combined immunodeficiency, AR, T−B+NK+ (OMIM:608971), HPO v2026-02-16 → v2026-06-23 — and shows how to read each part of the report.

## 1. The term list

`examples/scid_omim608971_terms.txt`: the 15 phenotypic-abnormality terms annotated to the disease in `phenotype.hpoa`, IDs with the label as a comment. Inheritance and onset terms were removed: they sit outside *Phenotypic abnormality* and carry no IC.

Why this disease? `examples/rank_profiles.py` scores every OMIM profile with 12–18 terms by mean |ΔLin| over its informative pairs. This one ranks first of 1 345 (0.085 vs a median of 0.001); the whole top of the list is inborn errors of immunity, because the immunology branch was restructured between the two releases.

## 2. Lint first

```
hpo-drift lint --release v2026-06-23 --terms examples/scid_omim608971_terms.txt
```

All IDs resolve; nothing is obsolete. For a label-based list you would see warnings with the ID to store and errors for labels that are not exact HPO names (e.g. "Recurrent infection" vs the term *Recurrent infections*).

## 3. The report

```
hpo-drift report --old v2026-02-16 --new v2026-06-23 --terms examples/scid_omim608971_terms.txt
```

The header states the method: Seco 2004 intrinsic IC on the `is_a` graph under root HP:0000118 (Phenotypic abnormality), N = 18 690 → 19 120 active terms. Then the ontology-wide counts, then your terms:

## Your 15 terms

| term | status | old → new label | parents | IC old → new |
|---|---|---|---|---|
| HP:0000155 | unchanged | Oral ulcer | = | 1.000 → 1.000 |
| HP:0000388 | unchanged | Otitis media | = | 0.818 → 0.803 |
| HP:0000403 | unchanged | Recurrent otitis media | = | 1.000 → 1.000 |
| HP:0000964 | unchanged | Eczematoid dermatitis | = | 0.766 → 0.757 |
| HP:0001744 | unchanged | Splenomegaly | = | 0.888 → 0.889 |
| HP:0002014 | unchanged | Diarrhea | = | 0.747 → 0.748 |
| HP:0002020 | unchanged | Gastroesophageal reflux | = | 1.000 → 1.000 |
| HP:0002090 | unchanged | Pneumonia | +HP:5210123 −HP:0011947 | 0.802 → 0.789 |
| HP:0002240 | unchanged | Hepatomegaly | = | 0.888 → 0.889 |
| HP:0002716 | unchanged | Lymphadenopathy | = | 0.739 → 0.732 |
| HP:0002728 | renamed | Chronic mucocutaneous candidiasis → Recurrent mucocutaneous candidiasis | +HP:5210236 | 0.859 → 0.859 |
| HP:0004430 | unchanged | Severe combined immunodeficiency | = | 1.000 → 1.000 |
| HP:0005390 | unchanged | Recurrent opportunistic infections | = | 1.000 → 1.000 |
| HP:0005403 | unchanged | Decreased total T cell count | +HP:5210411 −HP:0011839 | 1.000 → 1.000 |
| HP:0008866 | unchanged | Failure to thrive secondary to recurrent infections |  −HP:0002719,HP:0032169 | 1.000 → 1.000 |

Four terms changed direct parents. Three gained a new intermediate parent (`HP:5210123` Unusual lower respiratory tract infection, `HP:5210236` Unusual fungal skin infection, `HP:5210411` Decreased total T cell number). One — `HP:0008866` *Failure to thrive secondary to recurrent infections* — lost *Recurrent infections* and *Severe infection* as parents.

## 4. Similarity drift

## Similarity drift (105 pairs; 61 moved)

| pair | Lin old → new | Δ | Resnik old → new | MICA old → new |
|---|---|---|---|---|
| HP:0002728 ↔ HP:0008866 | 0.604 → 0.000 | -0.604 | 0.561 → 0.000 | HP:0002719 → HP:0000118 |
| HP:0000403 ↔ HP:0008866 | 0.561 → 0.000 | -0.561 | 0.561 → 0.000 | HP:0002719 → HP:0000118 |
| HP:0005390 ↔ HP:0008866 | 0.561 → 0.000 | -0.561 | 0.561 → 0.000 | HP:0002719 → HP:0000118 |
| HP:0000964 ↔ HP:0008866 | 0.336 → 0.000 | -0.336 | 0.297 → 0.000 | HP:0010978 → HP:0000118 |
| HP:0002090 ↔ HP:0008866 | 0.329 → 0.000 | -0.329 | 0.297 → 0.000 | HP:0010978 → HP:0000118 |
| HP:0000388 ↔ HP:0008866 | 0.327 → 0.000 | -0.327 | 0.297 → 0.000 | HP:0010978 → HP:0000118 |
| HP:0002716 ↔ HP:0008866 | 0.305 → 0.000 | -0.305 | 0.266 → 0.000 | HP:0002715 → HP:0000118 |
| HP:0004430 ↔ HP:0008866 | 0.297 → 0.000 | -0.297 | 0.297 → 0.000 | HP:0010978 → HP:0000118 |

Losing those parents moves `HP:0008866` out of the immune branch: its most-informative common ancestor with every infection term becomes the root, and Lin drops from 0.60 (with *Recurrent mucocutaneous candidiasis*) to 0.00. That is one edit to one term, and it changes 14 of the profile's pairwise scores at once. All 61 informative pairs moved; the 44 root-only pairs stay at 0.

## 5. What to write in Methods

"Phenotype similarity was computed with Lin similarity on Seco intrinsic IC over the HPO `is_a` graph (root HP:0000118), release v2026-06-23." One sentence; `hpo-drift` gives you the numbers to justify it, and `rank_profiles.py` tells you whether your disease of interest is among the exposed ones.
