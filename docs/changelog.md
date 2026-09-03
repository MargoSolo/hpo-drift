# Changelog

## Unreleased

- Fix: obsolete terms were dropped at parse time (obonet default `ignore_obsolete=True`), so the `obsoleted → replaced_by` status and the lint `OBSOLETE` error never fired. Found by the new toy-ontology tests.

## 0.1.0 — 2026-09-03

First release. report (per-term status, IC, Resnik/Lin drift with MICA), lint (label/obsolete hygiene, CI exit code), fetch; monthly GitHub Action; real Feb→Jun 2026 run.
