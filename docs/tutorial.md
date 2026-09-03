# Tutorial: one disease profile, two HPO releases

## 1 · The term list

`examples/fih_omim146200_terms.txt`: the 11 phenotypic-abnormality terms annotated to familial isolated hypoparathyroidism (OMIM:146200) in `phenotype.hpoa` (release v2026-06-23), IDs with the label as a comment. Inheritance, onset and frequency terms are not phenotypes and are left out: they sit outside *Phenotypic abnormality* and carry no IC (if you include them, `report` marks them `OUT_OF_DOMAIN`).

Why this disease? Its drift comes from a single edit that any clinician can judge. As a context check, `hpo-drift cohort` then ran over the complete `phenotype.hpoa` corpus (12 935 disease profiles, no size cutoff; 11 947 with at least one informative pair, the rest kept with a status) and `hpo-drift rank` ordered them by mean |ΔLin|: this profile is 20 of 11 947, and the same edit drives four of the top five. The complete table is `examples/cohort-v2026-02-16_v2026-06-23.csv`.

## 2 · Run

```bash
pip install hpo-drift
hpo-drift report --old v2026-02-16 --new v2026-06-23 --terms examples/fih_omim146200_terms.txt
hpo-drift report --old v2026-02-16 --new v2026-06-23 --terms examples/fih_omim146200_terms.txt --json > drift.json
```

The first run downloads both `hp.obo` files (about 10 MB each) from the official HPO GitHub release, verifies them against the SHA-256 the release publishes, and caches them under `~/.cache/hpo-drift`. The report header states the IC method, the root, N in each release, and the hash of each ontology file.

## 3 · Read the per-term table

Every term is `unchanged`: no rename, nothing obsoleted. One row has a `parents` entry: `HP:0002199 Hypocalcemic seizures  −HP:0002901`. The `is_a Hypocalcemia` edge was removed; the term keeps its other parent, *Symptomatic seizures*. *Hypocalcemia* itself lost its last child and became a leaf, so its IC went 0.888 → 1.000. Every other IC moved by less than 0.01 (N changed, which shifts non-leaf IC a little).

## 4 · Read the pair table

55 pairs: 14 informative, 41 `ROOT_ONLY` (they share only *Phenotypic abnormality* in both releases and are 0 → 0 by construction). All 14 informative pairs moved, three by more than 0.1:

| pair | Lin old → new | MICA old → new |
|---|---|---|
| Hypocalcemic seizures ↔ Hypocalcemia | 0.941 → 0.000 | Hypocalcemia → root |
| Hypocalcemic seizures ↔ Hyperphosphatemia | 0.594 → 0.000 | Abnormal blood ion concentration → root |
| Hypocalcemic seizures ↔ Decreased circulating PTH level | 0.205 → 0.000 | Abnormality of metabolism/homeostasis → root |

Removing that edge takes *Hypocalcemic seizures* out of the metabolism branch entirely: it now lives only under the nervous-system branch, so it shares nothing below the root with any calcium or phosphate term.

## 5 · What to write in Methods

"Phenotype similarity was computed with Lin similarity on Seco intrinsic IC over the HPO `is_a` graph (root HP:0000118), release v2026-06-23 (hp.obo SHA-256 a5092cbd…)." One sentence; `hpo-drift` gives you the numbers to justify it, and `hpo-drift cohort` tells you where your disease of interest sits in the whole annotation corpus.
