# Run 19: the full growth study re-run, with a working anxiety relief loop

Launched from this commit. Design is identical to run 13 (see
`docs/brain_growth.md`): off / linear / transformer predictive-cortex
conditions, seed 11, 240,000 ticks each, four world phases (east,
west mirror, fouling, retention), telemetry sampled every 250 ticks
from the engine's own bookkeeping.

What is different from run 13 is the engine itself:

* the headless trainer now runs the engine's anxiety relief loop every
  tick (run 13 never did, so anxiety pinned at 100 and the stress cap
  became a forbidden plateau);
* the relief loop's own deadlock is fixed - stress neurons are driven
  from the anxiety the squid actually feels (pre-cap), and the body is
  clamped to the suppression cap every tick (run 18's quick smoke:
  mean anxiety 0-7 everywhere vs ~100 in run 13);
* seeded reproducibility is restored (deterministic activation
  stamps, single constructor), and 55/55 baseline tests pass.

Run 18's 6k smoke (also in `docs/brain_growth.md`) suggests the
transformer condition may now keep growing past the east phase and
that the binding deficit has moved from anxiety to hunger. This run
settles it at full length.

Expected publication: `ci-logs/<CI run number>/results/growth_results.json`,
`growth_summary.json`, per-mode timeseries CSVs and event lists, plus
the logs, as a `[skip ci]` publish commit on this branch.
