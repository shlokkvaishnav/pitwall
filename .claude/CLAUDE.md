# pitwall: notes for the agent

Formula 1 race-strategy models from public lap data: a LightGBM lap-time forecaster with conformal
ranges, a logistic undercut-probability tool, and a Monte Carlo race simulator. Each was tested
under a written spec; the 2026 races from 1 September were a locked holdout, now used once
(spec 11). Live site: https://shlokkvaishnav.github.io/pitwall/ (the browser runs the undercut model).

## Start here
1. The SessionStart hook prints the branch and the next step from `.claude/STATE.md`.
2. `README.md` gives the results table; `docs/method.md` how everything was tested;
   `docs/specs/NN-*.md` each experiment (design first, result appended).
3. Code: `src/pitwall/` (dump loader, splits and holdout lock, lap model, intervals, simulator,
   undercut); scripts per spec in `scripts/`; outputs in `results/`; site in `site/`.

## Hard rules
- MUST write a new spec in `docs/specs/` and commit it before running any new evaluation. MUST NOT
  edit a registered rule after its result exists; append a dated note. (Why: every claim on the
  README rests on this.)
- MUST NOT use the spent holdout (2026 rounds 13-18) to fit, calibrate or choose anything new;
  `pitwall.splits.assert_not_holdout` guards loaders. New out-of-sample tests use new races
  (spec 13: rounds 19-23 and later).
- The site describes odds, never advice on whether to pit (README "What works").
- Git: work on a branch; merge and push only when the owner asks. A failed CI run sends an email,
  so run `make check` before any push. No co-author or AI attribution lines.
- Plain English; the README is for engineers reading the project, no process notes.
- Never Read `data/` (raw dumps); print summaries with a short script.

## Commands (repo root)
- Setup: `make install`. Done check: `make check` (ruff, mypy, pytest, Node site tests).
- Rebuild every result from raw data: `make reproduce` (downloads the pinned dump first).
- Results agree with files: `python scripts/compare_results.py` after a reproduce.

## Definition of done
`make check` passes; every number in README/method/site comes from a file in `results/` written
by a committed script; screenshots in `docs/` match the site. One task at a time.

## End of session
Rewrite `.claude/STATE.md` (about 25 lines): branch, next step, open items. Replace it.
