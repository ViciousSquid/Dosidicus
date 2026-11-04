# Verified results — newborn threat-vs-food weight edit

**Measured:** 4 November 2026, GitHub Actions Ubuntu runner, Python 3.11.17, NumPy 2.4.6.
**Source commit tested:** [850f833281f15a3cdfedfb63f2cc06c374bdd546](https://github.com/ViciousSquid/Dosidicus/commit/850f833281f15a3cdfedfb63f2cc06c374bdd546).
**Passing run:** [GitHub Actions #41744349842](https://github.com/ViciousSquid/Dosidicus/actions/runs/41744349842).
**Full machine-readable JSON and exact seeds:** [download the workflow artefact](https://github.com/ViciousSquid/Dosidicus/actions/runs/41744349842/artifacts/13282437823) (retention is governed by GitHub's artefact settings).

## Result summary

| Dataset | Baseline correct | Edited correct | Net gain |
| --- | ---: | ---: | ---: |
| Development (seeds 0–31) | 253/352 (71.88%) | 349/352 (99.15%) | +96 |
| Holdout (seeds 10000–10031) | 256/352 (72.73%) | 352/352 (100%) | +96 |
| Both combined | 509/704 (72.30%) | 701/704 (99.57%) | +192 |

These are **predeclared, deterministic action-threshold probe scores**; they do not quantify general intelligence, survival or long-term learning. Both candidate and baseline represent the same architecture and differ in exactly three newborn synapses.

The existing headless verification suite and new invariants **passed: 46 tests, 108 subtests**. The earlier CI attempts failed solely because the workflow initially omitted PyQt5, needed for an existing trainer/game parity import; the workflow was corrected and rerun successfully. Those failures were test-runner setup issues, not negative neural-behaviour comparisons.

## Per-probe pass counts

Each row represents 32 paired trials in its respective split.

| Probe | Development original → edited | Holdout original → edited |
| --- | --- | --- |
| safe_hungry_food | 32 → 32 | 32 → 32 |
| safe_content_food | 32 → 32 | 32 → 32 |
| safe_nothing_visible | 32 → 32 | 32 → 32 |
| mild_threat_food | 32 → 32 | 32 → 32 |
| anxiety_without_threat | 32 → 32 | 32 → 32 |
| high_threat_with_food | **0 → 32** | **0 → 32** |
| moderate_threat_with_food | **0 → 32** | **0 → 32** |
| sustained_threat_without_food | **0 → 32** | **0 → 32** |
| startle_without_food | 32 → 32 | 32 → 32 |
| sleep_blocks_feeding | 32 → 32 | 32 → 32 |
| exhaustion_collapse | **29 → 29** | 32 → 32 |

**Important unresolved failure:** 3/32 development probes failed the exhaustion-collapse check **in both versions**. The candidate did not cause or repair this; jitter around full sleepiness occasionally places the collapse neuron below its fixed 45-point threshold. It must not be hidden by quoting just the improved aggregate score.

## Mean action activations, before → after

Numbers are means over 32 trials. Each action is out of 100; the actual threshold comparison is done on individual trials rather than on these rounded means.

| Probe | Development (original → edited) | Holdout (original → edited) |
| --- | --- | --- |
| safe_hungry_food | eat 58.5 → 58.5; flee 0 → 0 | eat 58.3 → 58.3; flee 0 → 0 |
| safe_content_food | eat 42.6 → 42.6; flee 0 → 0 | eat 42.5 → 42.5; flee 0 → 0 |
| safe_nothing_visible | eat 12.0 → 12.0; flee 0 → 0 | eat 12.0 → 12.0; flee 0 → 0 |
| mild_threat_food | eat 56.5 → 51.6; flee 0.4 → 8.1 | eat 56.5 → 51.7; flee 0.4 → 7.9 |
| anxiety_without_threat | eat 2.8 → 0.9; flee 10.9 → 29.2 | eat 3.0 → 1.0; flee 11.0 → 29.3 |
| high_threat_with_food | eat 55.0 → 23.0; flee 31.3 → 73.2 | eat 54.9 → 23.0; flee 31.3 → 73.2 |
| moderate_threat_with_food | eat 55.7 → 31.1; flee 24.7 → 60.5 | eat 55.7 → 31.1; flee 24.6 → 60.3 |
| sustained_threat_without_food | eat 3.9 → 0; flee 35.7 → 72.6 | eat 4.0 → 0; flee 35.6 → 72.4 |
| startle_without_food | flee 84.9 → 100 | flee 84.9 → 100 |
| sleep_blocks_feeding | eat 13.6 → 13.6; flee 0 → 0 | eat 13.6 → 13.6; flee 0 → 0 |
| exhaustion_collapse | collapse 46.5 → 46.5 | collapse 46.8 → 46.8 |

### Interpretation and warning signs

1. Both splits passed the acceptance gates. The improvement is entirely concentrated in three *specifically selected threat scenarios* — not in an indiscriminate increase in the number of active actions.
2. Safe eating and sleeping retained their **binary classifications**. But the *activation margin* did change in some safeguards: under mild threat, eating weakened by roughly 4.9 points; and in anxiety without a threat, flight rose from about 11 to **29**, still below its threshold of 50. This decreased headroom is a potential false-alarm problem in states not covered by the probes.
3. Startle flight reaches 100 and may saturate; this may impede graded behaviour or subsequent learning.
4. These are stationary sensor snapshots stepped through the real neural transfer function. No body actions, food collection, predator evasion, health trajectories, synaptic plasticity, or lifespan were simulated or measured by these specific probes.
5. The labels are human-designed *desiderata*. Measuring agreement with them does not independently validate the desiderata or make a statistically valid claim about all game situations.

### Exact reproduction

```bash
python -m pip install numpy pytest PyQt5 Pillow platformdirs
python -m pytest -q tests/test_headless_training.py tests/test_weight_space_experiment.py
python -m experiments.weight_space.experiment --json experiments/weight_space/results.json
```

The raw JSON from the cited run includes exact seed lists, baseline and candidate weights, per-case unrounded mean activations (rounded in the file to five decimals), thresholds tested, and environment metadata. The README in this directory defines every test condition and the acceptance rules.

**Disposition:** Promising targeted improvement in threat/food **neural gating**, but **not ready to merge** as a generally smarter default. Next step is to build closed-loop, action-coupled survival, learning and social-behaviour experiments, followed by ablations of each of the three edits. Preserve this result even if future broader benchmarks show regressions.
