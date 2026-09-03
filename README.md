# hpo-drift <img src="docs/logo.svg" align="right" width="110" alt="">

[![ci](https://github.com/MargoSolo/hpo-drift/actions/workflows/ci.yml/badge.svg)](https://github.com/MargoSolo/hpo-drift/actions/workflows/ci.yml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22286170.svg)](https://doi.org/10.5281/zenodo.22286170)
[![drift check](https://github.com/MargoSolo/hpo-drift/actions/workflows/drift.yml/badge.svg)](https://github.com/MargoSolo/hpo-drift/actions/workflows/drift.yml)
![coverage](https://img.shields.io/badge/coverage-91%25-brightgreen) ![python](https://img.shields.io/badge/python-3.10%2B-3776ab)
![HPO releases](https://img.shields.io/badge/HPO-any%20release%20tag-8e44ad)
![License: MIT](https://img.shields.io/badge/license-MIT-blue)

**What did a new HPO release change for *your* phenotype terms — and by how much did your similarity scores move?**

The Human Phenotype Ontology is updated regularly. Terms get renamed, obsoleted and merged — and, the part nobody notices, the hierarchy gets new edges. New edges change information content, and information content is what Resnik and Lin similarity are made of. So the **same patient set, scored against two HPO releases, gives different numbers even if none of your terms were touched.** `hpo-drift` shows you exactly that, for the term list you actually use, in about three seconds.

## The headline result

Feb 2026 → Jun 2026. The example is not a hand-picked list: it is the **HPO-annotated phenotype profile of chronic granulomatous disease** (ORPHA:379), 22 phenotypic-abnormality terms straight from `phenotype.hpoa`. It was chosen by a declared protocol, not by hand: `examples/rank_profiles.py` scores every OMIM and Orphanet profile with 12–25 terms (3 901 profiles) by mean |ΔLin| between the two releases, and the same script with `--subset examples/wellknown_syndromes.txt` scores a list of 30 well-known syndromes declared before ranking. CGD ranks **10th of 3 901** overall and **1st among the well-known syndromes**. The upper part of both rankings is inborn errors of immunity — the immunology branch was restructured in this interval.

![Lin similarity drift](docs/lin-drift.png)

What happened to this profile, computed with Seco intrinsic IC on the `is_a` graph under *Phenotypic abnormality*:

- **Two terms gained a parent.** HPO introduced an *Unusual infection* hierarchy: *Gingivitis* (`HP:0000230`) is now also an *Unusual oral cavity infection* (`HP:5210280`), *Sinusitis* (`HP:0000246`) also an *Unusual upper respiratory tract infection* (`HP:5210121`). No label changed, nothing was obsoleted.
- Consequence: *Gingivitis* entered the immune branch. Its Lin similarity with *Meningitis* went **0.00 → 0.55**, with *Recurrent respiratory infections* 0.00 → 0.46, with *Sepsis* 0.00 → 0.43 — their most-informative common ancestor is no longer the root but *Unusual infection*. *Sinusitis* ↔ *Recurrent respiratory infections* rose 0.48 → 0.78.
- **IC moved for 18 of 22 terms; all 95 informative pairs moved**, 15 of them by more than 0.1 (136 pairs share only the root). Mean |ΔLin| 0.067; the median disease profile: 0.001.

![Information-content drift](docs/ic-drift.png)

The edit is clinically intuitive: gingivitis and sinusitis now connect more explicitly to the infection hierarchy. But even a sensible ontology improvement changes the numerical representation of a CGD phenotype profile, without anything about the patient changing. **Pin the release tag in Methods, match on IDs, and report how much the numbers depend on the release.** `hpo-drift` gives you that sentence with real figures; `examples/rank_profiles.py` tells you whether your disease of interest is among the exposed ones.

| full ranking (3 901 profiles, 12–25 terms) | terms | pairs moved | mean \|ΔLin\| |
|---|---|---|---|
| 1 · Pseudohypoparathyroidism type 2 (ORPHA:94090) | 12 | 20 / 20 | 0.209 |
| 4 · Severe combined immunodeficiency, AR, T−B+NK+ (OMIM:608971) | 15 | 61 / 61 | 0.085 |
| 5 · Leukocyte adhesion deficiency, type I (OMIM:116920) | 17 | 51 / 51 | 0.084 |
| **10 · Chronic granulomatous disease (ORPHA:379)** | 22 | 95 / 95 | 0.067 |
| median | | | 0.001 |

| well-known syndromes (pre-declared list of 30; 19 with ≥ 12 terms) | terms | pairs moved | mean \|ΔLin\| |
|---|---|---|---|
| **1 · Chronic granulomatous disease (ORPHA:379)** | 22 | 95 / 95 | 0.067 |
| 2 · Hyper-IgE recurrent infection syndrome 1 (OMIM:147060) | 51 | 399 / 399 | 0.047 |
| 3 · X-linked agammaglobulinemia (OMIM:300755) | 35 | 330 / 330 | 0.033 |
| 9 · Cystic fibrosis (ORPHA:586) | 35 | 104 / 104 | 0.023 |
| 17–19 · Noonan, Marfan, Angelman | 43–70 | all | 0.001 |

Reproduce:
```bash
python examples/rank_profiles.py v2026-02-16 v2026-06-23 phenotype.hpoa > profiles.csv
python examples/rank_profiles.py v2026-02-16 v2026-06-23 phenotype.hpoa --subset examples/wellknown_syndromes.txt --max-terms 80 > wellknown.csv
```
Outputs as run on 2026-09-03: [`examples/profiles-v2026-02-16_v2026-06-23.csv`](examples/profiles-v2026-02-16_v2026-06-23.csv), [`examples/wellknown-v2026-02-16_v2026-06-23.csv`](examples/wellknown-v2026-02-16_v2026-06-23.csv).

## 30-second start

```bash
pip install hpo-drift

# one term per line — HP IDs (recommended) or labels
hpo-drift report --old v2026-02-16 --new v2026-06-23 --terms my_terms.txt
```
```
active terms: 19389 → 19836 (added 469, obsoleted 22, renamed 266)
is_a edges:   +886 / −185

term        label          status     IC old → new
HP:0001250  Seizure                      unchanged  0.405 → 0.407
HP:0000365  Hearing impairment           unchanged  0.630 → 0.631
…
pair                                                  Lin old → new   Δ       MICA
Global developmental delay ↔ Intellectual disability  0.736 → 0.731   −0.004  HP:0012759
…
```
Add `--json` for a machine-readable report. Releases are pulled from the official GitHub assets of `obophenotype/human-phenotype-ontology`; any tag like `v2026-06-23` works and is cached under `~/.cache/hpo-drift`.

## Three things it does

### 1 · `report` — the drift itself
Per term: status (`unchanged` / `renamed` / `obsoleted` → replacement / `merged` / `missing`), label change, parents added or removed, IC before and after. Per pair: Resnik and Lin in both releases, the delta, and the most-informative common ancestor — so you can see *why* a pair moved. Plus the ontology-wide counts.

### 2 · `lint` — hygiene for a term list
```bash
hpo-drift lint --release v2026-06-23 --terms my_terms.txt
```
```
⚠️ Arthritis: matched by LABEL — labels get renamed; store the ID → HP:0001369
❌ Recurrent infection: label not found (exact match on names/synonyms; the term is 'Recurrent infections')
❌ HP:0002960: OBSOLETE → replaced_by HP:0025095
```
Exit code 1 on errors, so it works as a CI gate for a phenotype spreadsheet. Matching is **exact** on purpose: it reproduces the failure mode of a pipeline that matches by label. Store IDs, not labels: 266 labels changed in this interval alone, and fuzzy resolution (roadmap) must suggest, never auto-map.

### 3 · a monthly GitHub Action
`.github/workflows/drift.yml` fetches the latest release, compares it with your pinned one (`PINNED_HPO`) and uploads the report. Add a threshold on `lin_delta` from the JSON and it becomes a failing check.

## How it works

```mermaid
flowchart LR
  A["release tag<br/>v2026-02-16"] -->|hp.obo| C[parse: terms · is_a · alt_id · obsolete]
  B["release tag<br/>v2026-06-23"] -->|hp.obo| C
  C --> D["intrinsic IC<br/>Seco 2004"]
  T[your term list] --> E[resolve IDs / labels]
  E --> F[per-term status · parents · IC Δ]
  D --> G[Resnik / Lin per pair · MICA · Δ]
  F --> R[report · JSON · lint]
  G --> R
```

IC is **intrinsic** (Seco et al. 2004: `1 − log(descendants+1)/log(N)`), computed on the **`is_a` graph only**, with `N` and descendant counts taken inside the closure of a root — `HP:0000118` *Phenotypic abnormality* by default (`--root` to change; inheritance, frequency and modifier branches are excluded, and the root's IC is exactly 0). Every report states the method, the root and `N`. Because this IC depends only on the graph, the drift measured here is caused purely by ontology edits, which is the effect this tool isolates. Annotation-based IC (from `phenotype.hpoa`) adds a second, independent source of drift and is the next option on the roadmap — then the two can be shown side by side.

## Companion tools

- [`hpotools`](https://github.com/MargoSolo/hpotools) — HPO in R: release-pinned loading, similarity, Phenomizer-style ranking, enrichment.
- [`awesome-human-phenotype-ontology`](https://github.com/MargoSolo/awesome-human-phenotype-ontology) — link-verified list of HPO tools.

## Roadmap

`--ic annotations` · fuzzy label suggestions in `lint` · Phenopackets v2 export · `--pairs` file for patient × disease scoring · JOSS paper.

## Cite

DOI (all versions): 10.5281/zenodo.22286170 · this version: 10.5281/zenodo.22286739

Soloshenko M. *hpo-drift: quantifying the effect of HPO release changes on phenotype-similarity results.* 2026, v0.1.0. MIT License.
