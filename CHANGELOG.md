# Changelog

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
