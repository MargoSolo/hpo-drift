# Methods

## Information content and similarity
IC is **intrinsic** (Seco et al. 2004): `1 − log(descendants + 1) / log(N)`, computed on the `is_a` graph only, with `N` and descendant counts taken inside the closure of a root — `HP:0000118` *Phenotypic abnormality* by default (`--root` to change). Inheritance, onset, frequency and modifier branches are outside the domain: their terms have no IC and are reported as `OUT_OF_DOMAIN`. The root's IC is exactly 0. Pairwise similarity is Resnik (IC of the most-informative common ancestor, MICA) and Lin (`2·IC(MICA) / (IC(a) + IC(b))`). A pair whose MICA is the root in both releases is `ROOT_ONLY`: Lin 0 → 0 by construction; it is kept and counted, never dropped. Because this IC depends only on the graph, drift measured here is caused purely by ontology edits. Annotation-based IC is on the roadmap as a second, independent source.

## Profile similarity
`profiles` and `rank-diseases` use the symmetric **Best Match Average**: for each query term its best Lin match in the target, averaged; the same from the target side; the two means averaged. Terms that do not exist, are obsolete, or are outside the domain in a release do not enter that release's score; the report says how many terms were used on each side in each release (e.g. `target 7 → 10 of 10`), because that count is often the whole explanation.

## Resolving terms against two releases
IDs and labels are resolved against **both** releases (`resolve_across`). An id present in the old release is compared (`unchanged`, `renamed`, `obsoleted → replaced_by`, `merged` via alt_id, `missing` from new). An id or label that exists only in the new release is reported as `new-in-new`, never silently dropped. A label the two releases map to different ids is `ambiguous`; an unresolvable token is `unknown`.

## Cohort semantics
A disease profile is the set of unique HP ids in a disease's `phenotype.hpoa` rows with aspect `P` and no `NOT` qualifier. Every disease with at least one such row is in the table (v2026-06-23: 12 956 disease ids, 12 935 profiles, 21 ids have only negated or non-`P` rows). There is no size cutoff; a profile that cannot support pairwise analysis keeps a status: `NO_USABLE_TERMS`, `TERM_ONLY`, `NO_INFORMATIVE_PAIRS`, `RANKABLE`. Every raw term gets exactly one disposition — `retained`, `unknown`, `new_only`, `missing_new`, `merged_or_alt`, `obsolete`, `out_of_domain` — and the counts add up to `n_raw_terms` (tested, and verified on all 12 935 profiles). `rank` is a separate, optional step over the complete table.

## Provenance
Each `hp.obo` is downloaded to a temporary file, hashed, compared with the SHA-256 the official HPO GitHub release publishes for the asset, and only then moved into the cache with a `.sha256` sidecar; a cached file without a matching sidecar is re-downloaded. Reports, JSON output and the `cohort` / `rank-diseases` sidecars record the SHA-256 of both ontology inputs and of the annotation file.

## Synthetic-patient protocol
`examples/sweep_synthetic_patients.py` — declared before running: N disease profiles drawn at random (seed) from all profiles; patient = a random `--keep` fraction of the disease's terms that exist in both releases (at least 3) + `--noise` terms (`--noise-mode global`: uniform over the domain; `neighbor`: sharing an ancestor of IC ≥ 0.3 with a kept term; `ic-matched`: IC within ±0.05 of a kept term). The patient is ranked against every disease in both releases; recorded: rank and score of the true diagnosis, top-1, Jaccard of the top-5 sets, Spearman ρ of all ranks. The query is a noisy subset, so it is independent of any single target profile; the source disease is included among the targets because the question is whether the true diagnosis is still found.
