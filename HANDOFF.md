# HANDOFF — Dosidicus predictive-cognition research branch

Last updated: 2026-11-09 ~02:35 UTC, while CI run 13 (full growth study) is in flight.
Branch head at time of writing: `cce3c199`.

## Standing rules for anyone picking this up

- Work ONLY on branch `research/transformer-predictive-cognition` of `ViciousSquid/Dosidicus`.
  Pushes and CI runs on this branch are pre-authorized by Rufus.
- NEVER merge, open PRs, delete, or touch any other branch.
- Document results honestly, including failures and non-replications.
- Commit and push often. Keep commit messages free of CI depth tags unless a
  specific CI depth is intended. Tags: `[full]` = full experiment,
  `[growth]` = growth study, `[save-squid]` = squid-222 preservation run,
  `[skip ci]` = no CI. (Run 14's full save was triggered accidentally by a
  message that happened to contain "[save-squid]"; it was lucky, not planned.)

## Current state

### Run 13: full growth study — IN FLIGHT

- Launched by commit `d2e8f412` at 2026-11-09T01:58:30Z. Three modes
  (off / linear / transformer) x seed 11 x 240,000 ticks each.
- Expected duration 75-90 minutes (publish commit `ci: publish run 13 ...`
  around 03:13-03:28 UTC); hard CI timeout is 180 minutes.
- World design: four phases per 240k-tick life: east 0-60k, west 60k-120k
  (contingency startle every 700 ticks, food lands 16 ticks later, mirrored
  side), fouling 120k-180k (poop_spawn_chance 0.06, a new cleanliness problem),
  retention 180k-240k (clean water again). Ambient startles 0, learning live.
- The scientific question: is the early-life growth plateau a *forbidden*
  plateau (type caps binding: stress 5, novelty 6, reward 6, connector 10 grown
  neurons; global ceiling 100; 60 sim-second cooldown) or a *satisfied* plateau
  (no open deficits, caps nowhere near binding)? Quick 6k-tick smokes
  (runs 10/12) suggested the latter: growth stopped early in ALL conditions at
  12-15 grown neurons (ceiling 100) while synaptic churn continued after the
  last birth; capability-monitor stand-downs ran ~1,045 per 6k ticks.

**When run 13 publishes**, the branch gains `ci-logs/13/results/`:

- `growth_summary.json` (~57KB) — fetch via github_app get_file_contents
  (comes back as an "Additional content" resource) or
  `raw.githubusercontent.com/ViciousSquid/Dosidicus/<head-sha>/ci-logs/13/results/growth_summary.json`.
- `growth_timeseries_{off,linear,transformer}.csv` — live neuron count vs tick.
- `growth_events_{off,linear,transformer}.json` — aggregated capability-monitor
  decisions: counts, per_phase, by_reason, by_deficit, examples, full birth lists.
- `growth_results.json` (~17MB) — DO NOT FETCH.

**Then:**

1. Build the chart the user asked for: live neuron count against simulation
   time for all three modes, with the capability monitor's decisions overlaid
   (births marked with their deficit kinds, stood-down/declined decisions
   marked), phase boundaries drawn (0/60k/120k/180k/240k), and weight-churn +
   food-eaten overlays showing that learning continues after the neuron count
   plateaus. Load the rich-ui data-visualization skill first.
2. Append an honest Results section to `docs/brain_growth.md` (fetch its current
   content from the branch, append, do not rewrite) and push as `[skip ci]`.
3. Deliver the final report with the chart, verdict (forbidden vs satisfied
   plateau) stated honestly in either direction.

### Squid 222 preservation — COMPLETE

- The supernova seed's brain is preserved at `experiments/results/squid_222/`
  (run 14 publish `3e01e347`): `brain_222.json` (45 neurons, standard game
  format, with neurons/connections/state/plasticity/capability/
  enhanced_neurogenesis keys), `predictive_cortex_222.json`,
  `cortex_report_222.json`, `metadata.json`.
- Run 15 (commit `0059733f`, publish `2e30b6d3`): verdict **REPRODUCED**.
  All 24 strict fields match run 9 bit-for-bit: 463 foods on 880 approaches,
  696 Hebbian updates, train_steps 1511, loss_ema 0.00489973, 73 synapses
  grown from predictions, weights checksum round-trip exact at 313.006211.
  The 8 stochastic-tape fields (adaptation 18 foods, retention 131 foods on
  222 approaches) also matched this time. Run 14's only divergence had been
  self-inflicted: artifact validation ran an extra make_sim between training
  and evals and consumed shared RNG; the fix moved validation after the evals
  (strict fields counted for the verdict, stochastic fields reported).
- Pipeline: `experiments/save_special_squid.py`, triggered by a
  `[save-squid]` commit. Every no-tag CI run smoke-validates the save path to
  `/tmp/squid_222_smoke`. Reference record for verification lives at
  `ci-logs/9/results/full_results.json` (script reads it automatically).
- Documentation: "The supernova is preserved" section at the end of Results III
  in `docs/predictive_cognition.md` (commit `cce3c199`); `experiments/README.md`
  has a "## Preserved organisms" section.

### Run 9 (12-seed calm-world replication) — COMPLETE

- Verdict documented in `docs/predictive_cognition.md` "Results III"
  (commit `c0a67372`): the transformer population feeding advantage did NOT
  replicate. The transformer mean of 41.6 foods is one seed: 222 ate 463; the
  other 11 averaged 3.3 vs off 3.9 and linear 2.0 (paired excl. 222: t=1.67,
  p~=0.13; sign test p~=0.23). Seed 222 is the first existence proof: ate in
  all 5 frozen delayed-consequence trials (latency 2), 18 foods in
  stress-adaptation, 131 in frozen retention, precise predictions
  (baseline pred_food_ahead 0 vs 44-87 for others), Hebbian 696.
  op_alignment healed: transformer 0.543 (10/12 seeds positive), linear 0.779
  replicated exactly. Transformer overhead: 160 vs 425 ticks/s off-mode;
  23.2s inference + 22.6s training per 24k. Anxiety still pins at 100 in the
  adaptation eval.

## Branch head ledger (newest first)

```
cce3c199 docs: the supernova is preserved - squid 222 rebuilt and verified against run 9 [skip ci]
2e30b6d3 ci: publish run 15 diagnostics and results [skip ci]
0059733f experiments: preserve squid 222 - deterministic rebuild, strict/stochastic verification [save-squid]
3e01e347 ci: publish run 14 diagnostics and results [skip ci]
83b063d8 experiments: save_special_squid.py - deterministic rebuild + [save-squid] workflow depth
d2e8f412 experiments: launch the full growth study - 3 modes x 1 seed x 240k ticks [growth]
c0a67372 docs: Results III - run 9 calm-world replication [skip ci]
f3964bdd ci: publish run 12 diagnostics and results [skip ci]
57a209e0 experiments: aggregate growth stand-downs and resolutions into per-phase tallies
adbe5e59 ci: publish run 11 diagnostics and results [skip ci]
0580af78 experiments: growth study emits compact per-mode timeseries CSVs, event lists and summary JSON
5e4cd2f0 ci: publish run 9 diagnostics and results [skip ci]
```

## Operational gotchas

- `tools.github_app.push_files({owner:'ViciousSquid', repo:'Dosidicus', branch,
  message, files:[{path,content}]})` is the push path; list_commits with
  `sha:branch` returns only shas, use the returned messages for publish detection.
- The GitHub Actions API JSON (`/repos/ViciousSquid/Dosidicus/actions/runs`)
  truncates above ~32KB — regex-extract `"run_number":N` blocks for
  status/conclusion instead of JSON.parsing.
- `raw.githubusercontent.com` hard-wraps single-line files every 2001 chars —
  strip all stray newlines before JSON.parse.
- get_file_contents returns large files as "Additional content" resources;
  outputs above ~100KB auto-save to the local tool-results directory, process
  with jq.
- Poll pattern that works: two 25-second sleeps per sandbox program (~60s
  budget per program), then check the branch head for a new
  `ci: publish run N` commit.
- Workflow depths by commit-message grep: `[full]` -> full, `[growth]` -> growth,
  `[save-squid]` -> squid save; otherwise quick depth (which also runs
  `save_special_squid.py --quick`).
