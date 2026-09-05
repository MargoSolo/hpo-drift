# Evidence

Everything here was produced by the commands in this repository, with the protocol written down before running. Inputs are pinned: `phenotype.hpoa` from HPO release v2026-06-23 (SHA-256 `89004f85…`), `hp.obo` v2022-10-05 (`02f133a7…`), v2026-02-16 (`8d6c2379…`), v2026-06-23 (`a5092cbd…`); every report and sidecar records the full hashes.

## 1 · Does the HPO release change a phenotype-driven diagnosis?

`examples/sweep_synthetic_patients.py`: 500 synthetic patients per run, each a random 60 % of one disease's `phenotype.hpoa` terms (at least 3) plus 2 noise terms, drawn with seed 0 from all 12 935 disease profiles, no size filter. Noise-A draws the 2 noise terms uniformly from the Phenotypic-abnormality domain (generic annotation noise); Noise-B draws them from branches neighbouring the kept terms (clinically plausible noise). Each patient is scored — symmetric Best Match Average of Lin, Seco intrinsic IC — against every disease profile in the old and in the new release. `examples/summarize_sweep.py` computes the endpoints.

| endpoint | 4 months, v2026-02-16 → v2026-06-23 (A / B) | 3 y 8 m, v2022-10-05 → v2026-06-23 (A / B) |
|---|---|---|
| top-1 disease changed | 0 / 500 · 0 / 500 | **6 / 500 · 2 / 500** |
| true diagnosis changed rank | 1 / 500 · 0 / 500 | 9 / 500 · 7 / 500 |
| top-5 membership changed | 50 / 500 · 43 / 500 | **206 / 500 · 206 / 500** |
| max |Δrank| of the true diagnosis | 1 · 0 | 27 · 29 |
| Spearman ρ of all 12 935 disease ranks, median (min) | 0.9997 (0.973) · 0.9998 (0.894) | 0.9969 (0.934) · 0.9970 (0.846) |
| disease profiles with < 3 terms that exist in the old release | 0 | **1 303 / 12 935** |

Per-patient tables (kept terms, noise terms, rank and score of every true diagnosis in both releases): [4 months A](https://github.com/MargoSolo/hpo-drift/blob/main/examples/sweep-synthetic-patients-v2026-02-16_v2026-06-23.csv), [4 months B](https://github.com/MargoSolo/hpo-drift/blob/main/examples/sweep-synthetic-patients-neighbor-v2026-02-16_v2026-06-23.csv), [3 y 8 m A](https://github.com/MargoSolo/hpo-drift/blob/main/examples/sweep-synthetic-patients-v2022-10-05_v2026-06-23.csv), [3 y 8 m B](https://github.com/MargoSolo/hpo-drift/blob/main/examples/sweep-synthetic-patients-neighbor-v2022-10-05_v2026-06-23.csv).

Reading: over four months the ranking did not move at the top; over four years about 1 in 100 synthetic patients loses its top-1 diagnosis, two in five get a reshuffled top-5, and one disease in ten cannot be queried at all with the old ontology because its annotations use terms that did not exist yet.

**Caveat.** A patient built from 60 % of the true disease's own annotations is an easy query (rank 1 in about 97 % of cases in both releases), so these numbers bound the effect for well-annotated presentations. Sparser and noisier patients are one flag away (`--keep`, `--noise`, `--noise-mode`).

### The mechanism, on one patient

Gamma-glutamyl transpeptidase deficiency (ORPHA:33573), patient = 4 of its 10 annotated terms (Tremor, Strabismus, Seizure, Hyperreflexia) + 2 noise terms (`examples/ggt_orpha33573_patient.txt`). `rank-diseases`: **rank 1 → 28**, score 0.698 → 0.588, in both noise regimes.

```bash
hpo-drift profiles --query examples/ggt_orpha33573_patient.txt --target <(hpo-drift disease ORPHA:33573 --hpoa phenotype.hpoa) --old v2022-10-05 --new v2026-06-23
```
```
Query terms used 6 → 6 of 6; target 7 → 10 of 10.
release        profile similarity
v2022-10-05    0.698
v2026-06-23    0.588
```
All four true matches stay at Lin 1.000 in both releases. What changed is the disease side: 3 of its 10 annotations — *Elevated circulating glutathione concentration* (HP:0034456), *Glutathionuria* (HP:0034586), *Reduced tissue gamma-glutamyltransferase activity* (HP:6000578) — do not exist in HPO 2022. In the old release the disease profile has 7 representable terms and the patient covers it well; in the new release it has 10, three of which nothing in the patient matches, and Best Match Average falls. The disease became better described and, for this patient, harder to find. This is the reproducibility problem in one line, and it is invisible unless both releases are computed.

## 2 · Every disease profile: how much do pairwise scores move?

`hpo-drift cohort` over all 12 935 profiles, v2026-02-16 → v2026-06-23: 11 947 have at least one informative pair; **every one of them** had at least one pairwise Lin score move. Median mean |ΔLin| 0.0013, p99 0.043, max 0.298. Statuses of the rest: TERM_ONLY 705, NO_INFORMATIVE_PAIRS 283. Tables: [cohort](https://github.com/MargoSolo/hpo-drift/blob/main/examples/cohort-v2026-02-16_v2026-06-23.csv), [ranked](https://github.com/MargoSolo/hpo-drift/blob/main/examples/ranked-v2026-02-16_v2026-06-23.csv).

![Drift across all disease profiles](drift-distribution.png)

The top of that ranking is dominated by one edit. Familial isolated hypoparathyroidism (OMIM:146200, 11 terms, `examples/fih_omim146200_terms.txt`): *Hypocalcemic seizures* (HP:0002199) lost its `is_a Hypocalcemia` (HP:0002901) edge, so Lin between the two went **0.941 → 0.000** and *Hypocalcemia* became a leaf (IC 0.888 → 1.000); all 14 informative pairs of the profile moved. Whether a seizure caused by hypocalcemia is a *kind of* hypocalcemia is an ontology-design question; the size of the numerical footprint is not.

![Lin similarity drift](lin-drift.png)

![Information-content drift](ic-drift.png)

## 3 · Ontology-wide counts

| | v2026-02-16 → v2026-06-23 | v2022-10-05 → v2026-06-23 |
|---|---|---|
| terms added | 469 | 3 323 |
| obsoleted | 22 | 178 |
| labels renamed | 266 | 986 |
| `is_a` edges added / removed | 886 / 185 | 4 479 / 1 052 |
| `phenotype.hpoa` (2026-06-23) terms absent from the old release | 14 | 684 of 11 546 |

Labels are the quiet one: a pipeline that matches phenotypes by name silently loses 266 terms in four months. `hpo-drift lint` exists for that.
