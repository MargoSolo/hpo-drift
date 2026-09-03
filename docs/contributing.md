# Contributing to hpo-drift

Thanks for looking. Bug reports, real-data examples and small focused pull requests are all welcome.

## Before you open an issue
- **Bug:** include the exact command, the input (or a minimal example), the output you got and the output you expected. Version: `hpo-drift --version` or the release tag.
- **Feature:** describe the problem you are solving, not only the solution. One paragraph is enough.
- **Wrong result on real data:** these are the most valuable issues. Say which release / database version you used.

## Pull requests
1. Fork, branch from `main`, keep the change focused (one thing per PR).
2. Run the tests locally:
   ```bash
   pip install -e . pytest && pytest -q
   ```
3. Add or adjust a test for every behaviour change. Coverage must not drop (CI enforces a floor).
4. Update `CHANGELOG.md` / `NEWS.md` under **Unreleased**.
5. Commit under your own name; no generated co-author trailers.

## Scope
Read the *Limitations* section of the README first: several things are left out on purpose (documented there), and a PR that "fixes" one of them without discussion will be closed with a pointer to that section.

## Code of conduct
See [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).
