# Changelog

## 0.1.5 (2026-09-03)

Arbitrary term sets, no cutoffs. `report` handles 0 / 1 / N terms; pairs whose MICA is the root in both releases are kept and marked `ROOT_ONLY` (Lin 0 → 0 by construction); terms outside the similarity root (inheritance, onset, modifiers) are marked `OUT_OF_DOMAIN` with a pointer to `--root` instead of silently yielding NaN; the IC line now also reports how many terms moved by more than 0.01 and says that N changed. New `cohort` command: drift summary for every disease profile in a `phenotype.hpoa`, whatever its size, with a status (`NO_USABLE_TERMS`, `TERM_ONLY`, `NO_INFORMATIVE_PAIRS`, `RANKABLE`) and the annotation file's version and SHA-256 in a sidecar `.meta.json`. New `rank` command as a separate, optional step over that table. `examples/rank_profiles.py` (which filtered to 12–60 terms and ≥ 10 informative pairs before computing) is removed; the corpus was recomputed in full: 12 935 profiles, 11 947 rankable, CGD 50th. README lint example corrected (HP:0002960 is not obsolete; HP:0002961 is). Cached ancestors and IC (30 s for the whole corpus).

## 0.1.4 (2026-09-03)

Example and documentation: the headline example is the chronic granulomatous disease profile (ORPHA:379); `examples/rank_profiles.py` ranks every OMIM/Orphanet profile with 12–60 terms (7121) by Lin drift as a context check (CGD = 12th) and now prints the `#version` and SHA-256 of the `phenotype.hpoa` it was given; the annotation file used is pinned in the README (HPO v2026-06-23). Documentation site rebuilt from the README (it still described an earlier experiment). CLI report wording: edge changes "can propagate into downstream similarity scores" (not "every"). `__version__` was stuck at 0.1.0 and now matches the package version.

## 0.1.3 (2026-09-03)

Method: IC, ancestors and MICA now use an `is_a`-only graph; `N` and descendant counts are taken inside the closure of a root (default `HP:0000118` Phenotypic abnormality, `--root` to change), so the root's IC is exactly 0 and non-phenotype branches are excluded; common ancestors outside the domain no longer enter MICA. Reports and JSON state the IC method, root and `N`. Consequence on the example: 25 / 25 informative pairs moved (previously '91 / 91' counted root-only pairs whose tiny non-zero root IC shifted). README wording tightened (label/status/direct-parent changes; Lin under Seco intrinsic IC; HPO updated regularly). `.coverage` removed.

## 0.1.2 (2026-09-03)

Author name and ORCID corrected in package metadata and citation. No functional changes.

## 0.1.1 (2026-09-03)

Public release: PyPI package, Zenodo archiving, PyPI metadata, trusted-publishing workflow. No functional changes.

## Unreleased

- Fix: obsolete terms were dropped at parse time (obonet default `ignore_obsolete=True`), so the `obsoleted → replaced_by` status and the lint `OBSOLETE` error never fired. Found by the new toy-ontology tests.

## 0.1.0 — 2026-09-03

First release. report (per-term status, IC, Resnik/Lin drift with MICA), lint (label/obsolete hygiene, CI exit code), fetch; monthly GitHub Action; real Feb→Jun 2026 run.
