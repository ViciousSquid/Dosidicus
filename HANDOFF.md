# HANDOFF — Dosidicus predictive-cognition research branch

Last updated: 2026-11-09, after CI run 20 published and while CI **run 21**
(synaptic-input diagnostic) was in progress. Branch head before this update:
`db7f7e32`. **Do not treat this timestamp or run status as live**; check
GitHub branch HEAD and Actions on resumption.

## Rules / scope

- Work **only** on `ViciousSquid/Dosidicus`, branch
  `research/transformer-predictive-cognition`. Pushes and CI runs *on this
  branch* have been pre-authorised. Do not merge, open PRs, delete branches, or
  alter other branches.
- Keep control/linear/transformer conditions fair; do not silently change
  behaviour, random-number consumption, baselines or outcome definitions.
  Document failed experiments and non-replication as prominently as successes.
- Commit and push in small stages. CI depth tags in a commit **message**:
  `[full]` = 12-seed predictive trial; `[growth]` = 240k-tick growth study;
  `[save-squid]` = rebuild squid 222; `[skip ci]` = no run.
  **Avoid depth tags unless expressly intending that job.** Ordinary
  experiment-code changes trigger the default quick experiment (6k-tick
  growth, seed 11, alongside baseline and predictive tests).
- Read latest `docs/brain_growth.md`, `docs/predictive_cognition.md` and
  the **actual data**, rather than taking this handoff as a substitute.

## Current result: the anxiety problem was fixed, but feeding and movement fail

### Run 13 — original 240k growth study (complete, historical baseline)

- `ci-logs/13/results/`; all three modes completed seed 11 x 240,000 ticks,
  with four phases: east 0–60k, west mirror 60–120k, fouling 120–180k,
  clean-water retention 180–240k. Scheduled startles every 700 ticks followed
  by food after 16 ticks; ambient random startles = 0.
- Final neurons **31 / 42 / 44** for off / linear / transformer; last births
  at **1,000 / 1,000 / 1,500**; all plateaued in early east phase.
- **Forbidden plateau**, not a contented brain: five-stress-neuron type cap
  exhausted, persistent high anxiety, unmet drive deficits, growth requests
  blocked by cap-deepening/cooldown. The headless simulator was not applying
  the engine's anxiety-relief loop; stress cells were growing but not
  suppressing anxiety in the body. Later phases had no food eaten or births.

### Runs 16–18 — anxiety relief correction (complete)

- **Run 16 INVALID**: commit `6501e917` had a corrupted trainer
  (`SyntaxError`); its published result directory must never be used as
  evidence. **Run 17 FAILED**: duplicate constructor changed RNG stream and
  relief loop itself deadlocked because suppression activation was computed
  *after* clamping anxiety; nondeterministic activation timestamps also broke
  reproducibility.
- Fix `fec24337`: single constructor; compute stress drive from pre-cap
  anxiety; clamp the *body* as well as brain state; deterministic simulation
  timestamps. Run 18 passed 55/55 baseline tests. Short 6k growth experiment
  showed anxiety essentially zero and transformer births late in that
  *compressed* run. Those births did **not** establish growth during later
  phases of a 240k life.

### Run 19 — corrected full growth replication (COMPLETE, CI green)

- Workflow: https://github.com/ViciousSquid/Dosidicus/actions/runs/42616155402
- Data: `ci-logs/19/results/growth_summary.json`,
  `growth_timeseries_{off,linear,transformer}.csv`,
  `growth_events_{off,linear,transformer}.json`.
  The full `growth_results.json` is ~15 MB; avoid fetching it just to
  examine the summary. An explanatory chart is committed at
  `docs/figures/run19_growth_study.svg`, with detailed write-up in
  `docs/brain_growth.md`.
- All three conditions: **240,000 ticks, seed 11**, same four long phases,
  no truncation; **36 predictive tests + 55 baseline tests** passed.

| Run 19 measurement | Off | Linear | Transformer |
|---|---:|---:|---:|
| Final neurons | 30 | 44 | 45 |
| Newly grown | 11 | 15 | 16 |
| Last birth tick | 750 | 1,000 | 3,750 |
| Final synapses | 378 | 514 | 593 |
| Weight updates, whole life | 127 | 912 | 213 |
| Weight updates after last birth | 64 | 800 | 55 |
| Capability deficit resolutions | 172 | 432 | 381 |
| Total **earned** foods eaten | 1 | 1 | 4 |
| Food eaten after final birth | 0 | 0 | 0 |
| Growth requests stood down | 19,145 | 19,145 | 19,145 |

- The anxiety fix **works**: anxiety ~0 in the last three phases
  instead of ~100 in run 13, and `regulation:anxiety:down` leaves the
  active deficit list. **But** chronic hunger (100), cleanliness (0),
  sleepiness and satisfaction remain. The **stress type cap is still 5/5**
  in all modes, while the 100-neuron global cap is far away. Of the
  19,145 stand-downs, **19,140 / 19,120 / 18,920** (off / linear /
  transformer) concern `regulation:hunger:down`. The type-cap/deepening
  response keeps restarting the cooldown. **The plateau is still forbidden**,
  now mainly by an unfulfilled hunger drive rather than anxiety.
- All new neurons are born by tick 3,750 (early east) and **no mode grows
  in west, fouling or retention**, or eats in those later phases. The run-18
  claim of fouling-phase births refers only to its compressed world.
- The large new finding is **action collapse**: over the 240k life, the
  transformer chose **239,477 idle** actions and only **510 exploring**
  (plus 13 eating). Off and linear chose 198,785 and 191,875 exploring.
  Continued weight updates / deficit 'resolutions' must **not** be described
  as demonstrated learning: none produced feeding recovery.
- Run 19's phase-summary 'east food eaten' subtracts the first sample,
  which omits meals eaten before tick 250. Use `food_eaten_total` and
  the action counters for lifetime totals.
- n=1 per mode; the transformer had more synapses but **no evidence of
  sustainable survival advantage**. Very low anxiety might erase useful
  motivational signal, but that remains a hypothesis.

### Run 20 — read-only motor-pathway diagnostic (COMPLETE, CI green)

- Commit `379991eb`, publish commit `c75a0f72`, workflow
  https://github.com/ViciousSquid/Dosidicus/actions/runs/42652663624
- 6,000 ticks, seed 11, all three modes. Adds observation-only fields to
  `experiments/growth_experiment.py`: `food_visible`, `food_items`,
  `food_seen_ticks`, action counts and motor activations. Quick-sampled CSVs
  are `ci-logs/20/results/growth_timeseries_{off,linear,transformer}.csv`.
  The result is documented in `docs/brain_growth.md`.
- Locomotion `act_move` has a resting level **50**, firing threshold **45**.
  Transformer: **51.98** at tick 100, **47.41** at tick 500, **0** by
  tick 900, remaining 0 through at least tick 5,700. Off and linear stay
  approximately 49–60 over those samples. Transformer actions in 6k ticks:
  **5,477 idle, 510 exploring, 13 eating**; no exhaustion.
- Crucially, this is **not lack of food**: the transformer could see food at
  tick 900 and later samples; `food_seen_ticks` = **5,209** at tick 5,700,
  with **105 uneaten food items** in the tank at that sample.
- **Shared failure**: `act_eat` measured **0** at later samples in *all*
  modes, even with food visible. Its threshold is **38**. The innate
  `can_see_food → act_eat` prior is meant to drive feeding, yet the
  net pathway no longer delivers a usable command. Mechanism not yet
  established: learned negative weights, lateral inhibition, propagation or
  another source may be responsible. Do not assume the transformer directly
  broke the food-to-eat synapse without testing.
- Run 20 6k totals: earned food **1 / 1 / 4**, and neuron counts
  **30 / 44 / 45** (off / linear / transformer), mirroring the full run.

## NEXT: run 21 is in flight — analyse signed synaptic contributors

- Latest code commit as of this handoff: **`db7f7e32`**, message
  `experiments: inspect signed synaptic inputs and learned weights behind motor shutdown`.
  This launches the **quick-depth run 21** (not a 240k study).
  On resumption check GitHub Actions for its actual status; do not infer
  success from launch:
  https://github.com/ViciousSquid/Dosidicus/actions?query=branch%3Aresearch%2Ftransformer-predictive-cognition
- The new `_motor_synaptic_probe` in `experiments/growth_experiment.py`
  records approximate signed source contributions for `act_move` and
  `act_eat`, plus weights of the innate
  `can_see_food → act_eat`, `hunger → act_eat` and
  `curiosity → act_move` pathways. The contributions use **post-step
  brain state**, so they are diagnostic approximations, **not** an
  exact replay of the pre-propagation snapshot. Explicitly inspect this
  caveat before drawing causal conclusions.
- When run 21 has published, read its new
  `ci-logs/21/results/growth_timeseries_*.csv`,
  `growth_summary.json`, logs and experiment telemetry. Check:
  1. Does innate food→eat weight survive? Does the net signed input to
     `act_eat` become negative despite `can_see_food=100`?
  2. Why does transformer `act_move` fall below 45 and then to 0?
     Distinguish negative learned weights from inhibition by other active
     motor neurons and altered input dynamics.
  3. Compare off and linear to locate **shared feeding failure** versus
     **transformer-only motor shutdown**. Record timings/weights and
     potential causal pathways; don't attribute causation on correlation.
  4. Add actual results, honest uncertainty and next falsifiable experiment
     to `docs/brain_growth.md` and this HANDOFF. Commit `[skip ci]`
     for documentation-only changes.
  5. Only if the mechanism is established, plan a **controlled intervention**
     testing it; do not simply force actions, raise caps, change neural
     rules or feed the squid for free. Interventions must be flagged
     as artificial and excluded from earned-feeding metrics.

## Other research: seed 222 preserved; population gain NOT replicated

- Run 9 (12-seed calm-world replication) **did not replicate** the
  transformer feeding advantage across the population. Transformer
  mean 41.6 came mostly from one exceptional seed: **222 ate 463**,
  while the other 11 transformer seeds averaged **3.3 foods** against
  off **3.9** and linear **2.0** (excl. 222 paired t≈1.67, p≈0.13).
  No general advantage established. See `docs/predictive_cognition.md`
  Results III.
- Seed 222 remains a fascinating *single-organism existence proof*:
  463 foods in training, 5/5 frozen delayed-consequence trials
  (latency 2), 18 adaptation and 131 frozen-retention foods, 696
  Hebbian updates and 73 synapses formed from predictive sensors.
- The **original pre-relief-fix seed-222 organism is preserved** at
  `experiments/results/squid_222/`: `brain_222.json` (45 neurons),
  `predictive_cortex_222.json`, `cortex_report_222.json`,
  `metadata.json`. Run 15 (`0059733f` / `2e30b6d3`) **reproduced
  all 24 strict fields** bit-for-bit against run 9; the stochastic
  fields also matched. Rebuild script:
  `experiments/save_special_squid.py`. The saved specimen is a
  historical research artefact; don't overwrite with later engine
  behaviour or mistake it for evidence of population-level performance.

## Files and research operations

- Study design and detailed record: `docs/brain_growth.md`;
  predictive-cognition series: `docs/predictive_cognition.md`;
  run19 visualisation: `docs/figures/run19_growth_study.svg`.
- Experiment scripts: `experiments/growth_experiment.py`,
  `experiments/predictive_cognition_experiments.py`,
  `experiments/save_special_squid.py`; workflow:
  `.github/workflows/predictive-cognition.yml`.
- CI commits publish under `ci-logs/<number>/` and usually
  `experiments/results/`, using `[skip ci]`. Check test logs *and*
  job conclusion; the publish step can run even after tests fail.
- Obtain repository files through the GitHub **file API**, not a generic
  raw-web-page reader, which previously corrupted a large Python
  source file in run 16. Fetch narrow result files rather than
  multi-megabyte experiment JSON. Check file SHA before edits so
  concurrent commits aren't overwritten.
- Relevant recent branch ledger (oldest → newest, before this handoff):
  `66d1a673` run13 publish;
  `f580e2f8` run13 verdict;
  `fec24337` anxiety repair;
  `3fb9c7b8` run18 publish;
  `7071cdd2` run19 launch;
  `8d28329d` run19 publish;
  `4acbf117` run19 chart;
  `62696c40` run19 documentation;
  `f76c2e16` formatting;
  `379991eb` run20 probe;
  `c75a0f72` run20 publish;
  `8dd2ff06` run20 documentation;
  `db7f7e32` run21 synaptic diagnostic launch.
