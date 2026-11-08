# Predictive cognition: a temporal transformer as an extra sense organ

*Research module, branch `research/transformer-predictive-cognition`.*

**Central research question:** can a small transformer provide
predictive cognition while Dosidicus's existing plasticity,
neurogenesis and memory systems enable the organism to continually
learn from those predictions?

Short answer: see [Results](#results). The goal of this branch is to
investigate genuinely emergent capabilities - not to simulate
intelligence through hard-coded behaviours, and not to claim the squid
is sentient. It is a study of whether a self-modifying biological-style
network can exploit a learned predictive signal delivered as if it were
just another sense.

## 1. What was added

One new module, `src/predictive_cognition.py` (pure NumPy, no new
dependencies), plus additive wiring in the trainer and config:

- a 39-channel **observation vector** of the squid's own experience:
  7 drives, 6 state flags, 4 senses, position, the egocentric direction
  of food it can *currently* see (normalised by sight radius), the
  action it took (one-hot), and its own 8 action-neuron activations.
  Nothing the squid has not perceived ever enters this vector.
- a **TinyTransformer** (decoder-only causal self-attention, 2 layers,
  4 heads, 64-dim, learned position embeddings, GELU FFN, AdamW,
  gradient clipping, float32 throughout) with two heads:
  - *next-experience head*: predicts the full next observation
    vector;
  - *delta head*: predicts the tanh-scaled 5-tick change of
    hunger, happiness, anxiety and satisfaction.
- a **LinearPredictor** control: per-channel exponential smoothing
  plus a decaying trace of the last seen food direction. It runs through
  the identical interface so any behavioural difference is attributable
  to sequence modelling, not plumbing.
- a **PredictiveCortex** orchestrator: the experience ring buffer
  (4096 ticks), the per-tick protocol, training, sleep replay,
  telemetry and persistence.

## 2. How predictions reach the brain

The transformer's readout is translated into ten **analogue input
sensors** and registered through `brain_constants.register_input_sensor`,
the same interface plugins use:

```
pred_food_ahead, pred_food_east, pred_food_west, pred_food_south,
pred_food_north, pred_hunger_rise, pred_anxiety_rise, pred_reward_soon,
pred_threat_soon, pred_uncertainty
```

Because they are registered sensors, every existing mechanism treats
them exactly as it treats any other sense organ:

- **propagation never overwrites them** (`NON_PROPAGATED`);
- **plasticity may grow synapses FROM them but never INTO them**
  (`is_learning_target`), so the squid can learn to trust or ignore a
  prediction, but a prediction can never seize a motor neuron;
- **the capability monitor counts them in situation signatures**, so
  neurogenesis remains free to grow new circuitry in response to them;
- **the causal learner may name them as antecedent cues**.

The original network retains full behavioural control at all times. If a
prediction is useless, Hebbian decay and sleep pruning remove the
synapses that listened to it.

## 3. The per-tick protocol

In `HeadlessSimulation._simulation_step` (predictive mode only; all
no-ops when off):

1. after `brain.update_state(...)`, `cortex.begin_tick(tick, state,
   food_percept)` scores the previous prediction against what actually
   happened, records this tick's percept, predicts *this* tick from
   experience strictly before it, and writes the prediction sensors
   **before propagation** - the network acts on anticipation, not
   reaction;
2. the network propagates and selects the action exactly as before;
3. after the action, `cortex.end_tick(action, brain_state)` completes
   the experience record (action taken + the network's own
   activations) and appends it to the ring buffer.

Training runs every `predictive_train_interval` ticks (default 64),
**only while learning is enabled** - a frozen evaluation freezes the
transformer too, though its predictions still flow. While the squid
sleeps, `sleep_replay()` runs bounded extra offline replay steps over
the buffer, the transformer's analogue of the consolidation the rest of
the brain already performs. The transformer's gradients never touch the
squid's synapses and the squid's learning rules never touch the
transformer's weights.

## 4. Compatibility guarantees

- `predictive_mode='off'` (the default) registers nothing, runs
  nothing, and costs nothing: the engine is byte-identical to baseline.
- No new dependencies: NumPy only. No Qt, no torch, no import of either
  anywhere in the new code. The research workflow installs
  `numpy pytest` only.
- Existing saves load unchanged; brains trained with the cortex export
  in the standard game format (prediction sensors ride along as
  ordinary inert neurons in vanilla builds).
- Existing tests pass unchanged; `tests/test_predictive_cognition.py`
  additionally verifies the claims above against the running code,
  including a finite-difference check of every transformer gradient
  block.

## 5. Experiments

`experiments/predictive_cognition_experiments.py` (see
`experiments/README.md` for the full protocol) compares the three
conditions, 6 seeds each, 12,000 training ticks on a delayed-reward
contingency (startle, then food 8 ticks later in the east), followed by
held-out evaluations: object permanence, delayed-consequence
anticipation, stress adaptation, retention of learned feeding behaviour,
prediction telemetry and wall-clock overhead. Everything runs through
the real headless trainer with reproducible seeds; the transformer never
receives information the squid has not perceived.

CI: `.github/workflows/predictive-cognition.yml` runs the unit suite
and the quick experiment on every push to this branch, and the full
experiment on `workflow_dispatch`.

## Results

*This section is filled from the actual CI experiment runs - including
failures and overhead - not from expectations. See the workflow runs on
this branch for the raw JSON.*

- Pending first full run.
