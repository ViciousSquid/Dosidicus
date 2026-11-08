# Predictive cognition experiments

Protocol, code and results for the research question this branch exists
to answer: **can a small transformer provide predictive cognition that
Dosidicus's existing plasticity, neurogenesis and memory systems let the
organism continually learn from?**

The runner is `predictive_cognition_experiments.py`. It uses the real
headless trainer and the real brain, no mocks, no scripted behaviours.

## Conditions

| condition | what it is |
|---|---|
| `off` | the baseline engine, untouched. The control of record. |
| `linear` | an exponential-smoothing temporal predictor (per-channel EMA + a decaying trace of the last seen food direction). Same interface, same senses, same telemetry as the transformer - the "is it the plumbing or the sequence modelling?" control. |
| `transformer` | 2 layers, 4 heads, 64-dim, causal self-attention over the squid's experience, trained on windows of its own recent history. |

Conditions differ in nothing else: same seeds, same scenario, same
engine, same brain.

## Training phase

Every condition trains for 24,000 ticks on the same delayed-reward
contingency: **a startle every 700 ticks, followed 16 ticks later by
food appearing within sight of the squid (0.2 east of wherever it is
when the timer fires).** Food must still be seen, swum to and eaten;
placing it is an environmental act, not a reward.

Run-6 post-mortem: the original world fired a startle every 150 ticks,
which pinned anxiety at 100 and left the behavioural metrics no dynamic
range, and placed food at a fixed far spot that was almost never inside
the squid's 0.32 sight radius, so the contingency barely existed in
its own percept stream. Both confounds are fixed here.

## Held-out evaluations

Scored OUTSIDE the squid (the squid itself only ever receives unsigned
0-100 sensor values):

1. **Object permanence.** The squid watches food, then is teleported far
   out of sight of it. Over 30 blind ticks we measure the cosine
   alignment between the prediction senses' implied direction and the
   food's true direction, the coverage (fraction of ticks with a
   non-silent prediction), and the time to eat once the food is
   re-sighted (frozen brain).
2. **Delayed consequences.** A held-out schedule of the training
   contingency's structure. Does `pred_food_ahead` rise between the
   startle and the food's appearance, in an early (t0+1..t0+7) and a
   late (t0+8..t0+14) window, before the food exists? How quickly is
   the food eaten?
3. **Adaptation.** A 1,500-tick stress phase (5% startle chance) with
   learning live: escape ratio, anxiety, feeding.
4. **Retention.** 2,500 ticks with a frozen brain and ordinary food
   spawning: does the feeding behaviour learned during training survive?
5. **Telemetry and overhead.** Per-channel-group prediction MAE,
   action top-1 accuracy, ticks/sec per condition, inference and
   training wall-clock, and the synapses the host network grew FROM the
   prediction sensors.

## Running

From the repository root (numpy only; no Qt, no torch):

```bash
python experiments/predictive_cognition_experiments.py --quick   # smoke: 2 seeds
python experiments/predictive_cognition_experiments.py --full    # 6 seeds x 24k ticks
```

Results are written to `experiments/results/full_results.json` (full)
or `experiments/results/quick_results.json` (quick) and a markdown
summary is printed. GitHub Actions runs the quick mode on every push to
this branch (`.github/workflows/predictive-cognition.yml`) and the full
mode when the pushed commit message contains `[full]`.

## Integrity rules

- Identical seeds and tick counts; the transformer seed follows the run
  seed.
- The transformer sees only the squid's perception: drives, senses,
  position, currently-visible egocentric food direction, its own actions
  and its own neural activations. Food it cannot see does not exist in
  its input.
- Scoring may read the cortex's telemetry from outside; the squid cannot.
- Failures are reported as failures. See `docs/predictive_cognition.md`
  for the actual results, including what did not work.
