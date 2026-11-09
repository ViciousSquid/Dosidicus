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
  telemetry and per
sistence.

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
**only while learning is enabled** - a frozen evaluation free
zes the
transformer too, though its predictions still flow. While the squid
sleeps, `sleep_replay()` runs bounded extra offline replay steps over
the buffer, the transformer's analogue of the consolidation the rest of
the brain already performs. The transformer's gradients never touch
the squid's synapses and the squid's learning rules never touch the
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
conditions, 12 seeds each (run 9; earlier runs used 6), 24,000 training
ticks on a delayed-reward contingency (a startle, then food 16 ticks
later, placed within sight of the squid; ambient random startles are
silenced during training - see Results II for the world's history),
followed by
held-out evaluations: object permanence, delayed-consequence
anticipation, stress adaptation, retention of learned feeding behaviour,
prediction telemetry and wall-clock overhead. Everything runs through
the real headless trainer with reproducible seeds; the transformer never
receives information the squid has not perceived.

CI: `.github/workflows/predictive-cognition.yml` runs the unit suite
and the quick experiment on every push to this branch, and the full
experiment
 on `workflow_dispatch` or when the head commit message
carries `[full]`. Every run publishes its logs and raw result JSON to
`ci-logs/<run>/` and `experiments/results/` on this branch.

## Results

*Every number below is measured, from the runs this branch's CI actually
executed: the full run is 3 conditions x 6 seeds x 12,000 training ticks
(workflow run 6, commit `ce53125f`); the smoke run is 2 seeds x 1,500
ticks (run 5). Raw JSON: `experiments/results/full_results.json` and
`quick_results.json` on this branch. The run that produced the full
numbers also passed all 35 predictive tests and all 51 baseline tests
(123 subtests). Failures and overhead are reported as measured.*

### Headline table (means over 6 seeds, full run)

| metric | off | linear | transformer |
|---|---|---|---|
| train: food eaten | 2.667 | 2.833 | 2.000 |
| train: escape ratio | 0.012 | 0.026 | 0.015 |
| train: neurons created | 14.5 | 15.8 | 15.3 |
| train: ticks/sec | 285.9 | 210.1 | 154.8 |
| object permanence: alignment | - | 0.853 | -0.080 |
| object permanence: coverage | - | 0.883 | 0.983 |
| delayed consequence: pred_food_ahead rise | - | 0.000 | -1.027 |
| delayed consequence: eat rate (held-out) | 0.000 | 0.000 | 0.000 |
| adaptation: escape ratio | 0.000 | 0.000 | 0.000 |
| retention: food eaten (frozen, 2500 ticks) | 0.000 | 0.000 | 0.000 |
| prediction: action top-1 | - | 0.991 | 0.957 |
| synapses grown from predictions | - | 64.3 | 64.3 |

Metrics shown as `-` are undefined for the off control, which has no
prediction senses by design. The smoke run (2 seeds) agrees
directionally with every row.

### What worked

**The transformer really learned its experience.** Loss EMA settled at
0.005-0.006 after 374 gradient steps (plus up to 40 sleep-replay steps
on nights the squid slept). Held-out prediction error (MAE per channel
group), transformer vs the linear control:

| channel group | linear | transformer |
|---|---|---|
| drives | 0.0005 | 0.0122 |
| flags | 0.0115 | 0.0085 |

| senses | 0.0948 | 0.0918 |
| position | 0.0066 | 0.0223 |
| food | 0.0086 | 0.0146 |
| action | 0.0026 | 0.0076 |
| neural (own activity) | 0.0030 | 0.0073 |

The transformer beat the smoothing control on the discrete state flags
and on the raw senses; exponential smoothing is a genuinely strong
baseline for one-step-ahead prediction of slow continuous channels
(drives, position) and it won those. Both predictors anticipated the
squid's own next action well (top-1: 0.991 linear, 0.957 transformer).

**The brain really wired itself to the predictions.** In every
linear- and transformer-mode run, plasticity grew about 64 synapses
whose source is a prediction sensor, and zero synapses into them, as
the sensor interface forbids. Examples from the trained runs:
`pred_food_east -> act_eat` (+0.33, transformer seed 11),
`pred_threat_soon -> act_move` (-1.0, linear seed 11). Neurogenesis ran
comparably in all three conditions (14.5 / 15.8 / 15.3 neurons created).

**Compatibility held.** Off-mode runs the baseline path; all baseline
tests passed on every CI run of this branch; saves and the vanilla brain
export still work; the transformer needs only NumPy. The full
18-population experiment finished in under 20 minutes of CI time.

### What failed

**No behavioural benefit was demonstrated, for any condition.** The
behavioural metrics are at the floor everywhere: 2-3 foods eaten per
12,000 training ticks (out of ~78 placed), zero food eaten in the
frozen 2500-tick retention phase, zero eats in the held-out
delayed-consequence trials, escape ratios of 0-3%. With every
condition at the floor, no condition difference can be resolved. The
transformer population ate slightly less during training (2.0 vs 2.67 /
2.83), within seed-level noise (per-seed food eaten: off 1,6,3,1,2,3;
linear 1,3,4,1,2,6; transformer 1,2,3,1,3,2).

**Delayed-consequence anticipation did not emerge.** The transformer's
`pred_food_ahead` did not rise after a startle (change -1.03 on a 0-100
scale; the l
inear control sits saturated at 100, rise 0.000). The root
cause looks perceptual rather than a modelling failure: food was always
placed at a fixed spot in the east while the squid wanders, its sight
radius is 0.32, and only ~6 approaches happened per run - the food was
seen in a small fraction of the 78 training repetitions. As the squid
actually perceived the world, "startle, then visible food" almost never
happened, and the transformer correctly learned that startles are not
followed by visible food. The contingency has to be perceivable before
any predictor can anticipate it.

**Object permanence was unstable in the transformer.** Teleported out
of sight of food, the linear control's decaying food trace kept pointing
at it (alignment 0.853 with the true direction). The transformer's mean
alignment was -0.080, but per-seed it ranged from +0.96 to -0.89: some
seeds kept a usable spatial memory, others confidently pointed the wrong
way (coverage 0.983 - it almost always reports "food somewhere"). A
learned spatial memory must integrate the squid's own motion across the
blind window; with 374 gradient steps over 12k ticks of mostly-empty
food channels, half the seeds had not converged to that. The hand-coded
trace wins this round.

**A real telemetry bug was found by the first full run.** `delta_mae`
read exactly 0.0 in every run: each tick's new delta prediction
overwrote the pending one before its 5-tick horizon arrived, so delta
scoring never executed. Fixed in the follow-up commit (predictions now
queue in a small FIFO and are scored when their future arrives) with a
regression test that fails if the telemetry ever sticks at 0.0 again.
The bug affected telemetry only - no sensor value or behaviour depended
on it, so the run-6 results above stand; the delta MAE is reported
truthfully by CI runs that include the fix. Verified on the follow-up
run (run 7, quick experiment, commit `8cd648dc`): delta MAE 0.00003 /
0.00003 (linear, seeds 11 / 22) and 0.018 / 0.051 (t
ransformer), with
all 36 predictive and 51 baseline tests passing.

**A design confound affected all conditions equally.** The training
contingency startled the squid every 150 ticks, which kept anxiety at
its ceiling (100) for effectively the whole run, with the emergency
neurogenesis path firing constantly. Chronic stress suppressed feeding
behaviour in every population, which is the most likely reason all
behavioural metrics sit at the floor. This is a property of the
experiment's world, not of any predictor.

### Overhead (honest numbers)

- Throughput: 285.9 ticks/sec (off) -> 210.1 (linear, 0.73x) -> 154.8
  (transformer, 0.54x), measured over the full 12k-tick training runs
  on the CI runner.
- Transformer cost per 12k-tick run: 8.27 s inference + 4.10 s training
  (374 steps), plus per-tick sensor writes. The linear control costs
  ~0.13 s + ~0.22 s.
- The predictive module is off by default and costs nothing in the
  baseline engine (verified by test).

### Answer to the central research question, at this scale

The mechanism is sound: the cortex delivers learned predictions as
ordinary senses, the existing plasticity grows synapses from them (and
only from them), neurogenesis is not blocked, the original network
keeps behavioural control, and the whole thing is optional, Qt-free and
save-compatible. But no emergent cognitive benefit was demonstrated at
this scale, and the one clean spatial-memory signal came from the linear
control's hand-coded decaying trace rather than the transformer. The
binding constraints were perceptual and behavioural: the training
world's key contingency was mostly invisible to the squid, and chronic
startle stress suppressed feeding in every population, so the
behavioural measures had no dynamic range.

For a fairer next test: place the food within sight of the squid (or
relative to it), space the startles far enough apart that anxiety can
recover between them, train for more gradient steps, and evaluate
anticipation over a hori
zon longer than one tick. The infrastructure to
do all of this - seeds, held-out scenarios, per-condition telemetry,
automatic publication of results to the branch - now exists and is
verified end to end.

## Results II: the fairer world (run 8)

Commit `e7465276` implemented the recommendations above and CI executed
the full experiment again (workflow run 8: 3 conditions x 6 seeds x
24,000 training ticks, all 36 predictive and 51 baseline tests
passing). The world changes:

- food placed **within sight** (0.2 east of the squid's position at
  placement time) instead of at a fixed far spot;
- the scripted contingency startles **spaced 700 ticks** apart;
- the contingency delay lengthened to **16 ticks**, scored in an early
  (t0+1..t0+7) and a late (t0+8..t0+14) anticipation window;
- training interval halved (64 -> 32) and tick budget doubled
  (12k -> 24k): ~1,500 gradient steps per run;
- a harness bug fixed: the delayed-consequence evaluation queued its
  startle/food events but never called the event processor, so run 6's
  trials had silently run in an empty world (eat rate was structurally
  zero; the anticipation numbers of run 6 measured nothing).

### Headline table (run 8, means over 6 seeds)

| metric | off | linear | transformer |
|---|---|---|---|
| train: food eaten | 2.50 | 2.50 | 4.67 |
| train: food approaches | 5.33 | 5.50 | 9.83 |
| train: ticks/sec | 279.0 | 204.1 | 131.5 |
| object permanence: alignment | - | 0.778 | -0.193 |
| delayed consequence: rise, early window | - | 0.000 | +1.149 |
| delayed consequence: rise, late window | - | 0.000 | -0.708 |
| delayed consequence: eat rate | 0.000 | 0.000 | 0.000 |
| retention: food eaten (frozen) | 2.00 | 0.00 | 0.00 |
| prediction: action top-1 | - | 0.992 | 0.988 |
| synapses grown from predictions | - | 54.0 | 79.7 |

### What changed

**The transformer population ate more.** 4.67 vs 2.50 foods per run
(the two controls are identical), on 9.83 approaches vs ~5.4. Per-seed
against the linear contr
ol the transformer was ahead in 4 of 6 seeds
and tied in 2 (diffs +3, 0, +3, 0, +2, +5; paired t = 2.7, p = 0.04,
n = 6); against off, ahead in 4 of 6 (+2, -2, +4, 0, +3, +6; t = 2.0,
p = 0.10). This is the first behavioural separation between
conditions, in the direction the thesis predicts - but with six seeds
in one world it is suggestive, not established. It needs replication
with more seeds before it means anything.

**Genuine anticipation appeared in some seeds.** With the evaluation
bug fixed, trials now really contain a startle followed by food. The
linear control saturates `pred_food_ahead` at 100 (rise 0.000: its
decaying food trace pins the sensor). The transformer, whose baseline
sits at 53-73, raised `pred_food_ahead` in the early window in 3 of 6
seeds (+5.4, +5.4, +4.5 points) and did not in the others; means
+1.15 early, -0.71 late. The transformer predicts in a graded way the
hand-coded control structurally cannot, but the learned contingency
signal is still seed-unstable.

**Object permanence remained bimodal in the transformer.** The linear
control was stable and good (per-seed 0.57-0.86, mean 0.778). The
transformer was either excellent (+0.96, +0.97) or confidently wrong
(-0.70 to -0.89), mean -0.19. Four times the gradient budget did not
stabilise its spatial memory across seeds; the hand-coded trace still
wins this metric.

**The chronic-stress confound persisted through a different channel.**
The 700-tick spacing applies only to the scripted contingency; the
trainer's ambient random startle chance (default 0.005/tick) still
fired ~120 startles per 24k-tick run, so training saw ~150 startles
and anxiety stayed pinned at 100 in every condition (the adaptation
eval confirms: final anxiety 100 everywhere, zero feeding). The
delayed-consequence eat rate stayed 0 everywhere for the same reason:
a startled, frozen squid does not choose to eat within the 80-tick
window. The world still lacks behavioural dynamic range - the run-6
diagnosis was right a
bout the mechanism but incomplete about the
channel.

### Overhead (run 8)

Transformer: 0.47x throughput (131.5 vs 279.0 ticks/sec), 17.7 s
inference + 15.5 s training per 24k-tick run (~1,500 steps). Linear:
0.73x. Off: free.

### Where this leaves the question

The integration mechanism continues to hold (54-80 synapses grown from
predictions, zero into them, all tests green), and for the first time
a behavioural metric separates the transformer from both controls in
the predicted direction. But the world is still stress-pinned through
the ambient startle channel, the object-permanence signal is still
seed-unstable, and n = 6 is too small to trust the feeding difference.
Next test: silence the ambient random startles during training so
stress arrives only through the spaced contingency, and raise the seed
count before claiming the feeding advantage.

## Results III: the calm world, 12 seeds (run 9)

Commit `38be60ba` silenced the last stress channel and doubled the
seeds; CI executed the full experiment (workflow run 9: 3 conditions x
12 seeds x 24,000 training ticks, all 36 predictive and 51 baseline
tests passing, publish `5e4cd2f0`). The world changes:

- ambient random startles silenced entirely during training
  (`startle_chance=0`): stress arrives only through the spaced
  contingency, 35 startles per 24k run (run 8: ~150);
- the retention evaluation also runs calm;
- seeds 6 -> 12 (`[11, 22, 33, 44, 55, 66, 77, 88, 99, 111, 222, 333]`);
- CI job timeout 120 -> 180 min.

### Headline table (run 9, means over 12 seeds)

| metric | off | linear | transformer |
|---|---|---|---|
| train: food eaten | 4.08 | 1.92 | 41.58 |
| train: food approaches | 9.17 | 4.50 | 79.92 |
| train: escape ratio | 0.017 | 0.005 | 0.017 |
| train: neurons created | 12.5 | 15.7 | 15.3 |
| train: ticks/sec | 424.8 | 275.0 | 160.2 |
| object permanence: alignment | - | 0.779 | 0.543 |
| object permanence: coverage | - | 0.842 | 0.811 |
| delayed consequence: rise, early window | - | 0
.000 | -1.428 |
| delayed consequence: rise, late window | - | 0.000 | -4.925 |
| delayed consequence: eat rate | 0.000 | 0.000 | 0.083 |
| adaptation: food eaten (live learning) | 0.000 | 0.000 | 1.500 |
| retention: food eaten (frozen) | 0.000 | 0.000 | 10.917 |
| prediction: action top-1 | - | 0.996 | 0.985 |
| synapses grown from predictions | - | 56.1 | 61.4 |

### What the data says

**Run 8's feeding advantage did not survive replication.** The
transformer's mean 41.6 foods per run is real arithmetic and misleading:
one seed (222) ate 463 foods; the other eleven transformer seeds ate
36 in total (mean 3.3), between off (3.9 excluding seed 222) and
linear (2.0). Per-seed food eaten, in seed order 11..333:

| seed | off | linear | transformer |
|---|---|---|---|
| 11 | 4 | 1 | 3 |
| 22 | 15 | 3 | 2 |
| 33 | 1 | 4 | 2 |
| 44 | 2 | 0 | 1 |
| 55 | 2 | 4 | 11 |
| 66 | 3 | 0 | 2 |
| 77 | 4 | 0 | 4 |
| 88 | 2 | 2 | 2 |
| 99 | 5 | 1 | 2 |
| 111 | 3 | 7 | 6 |
| 222 | 6 | 1 | 463 |
| 333 | 2 | 0 | 1 |

Against the linear control, excluding seed 222, the transformer was
ahead in 8 seeds, behind in 3, tied in 1 (paired mean +1.27, t = 1.67,
p = 0.13; sign test 8+/3-, p = 0.23); against off it was behind in 6
of 11. No population-level feeding advantage is demonstrable in the
calm world.

**One seed did everything the thesis predicts.** Transformer seed 222
ate 463 foods on 880 approaches in training, and it is the first run of
any condition ever to eat during the frozen evaluations: all five
held-out delayed-consequence trials (latency 2 ticks, `eat_rate` 1.0),
18 foods during the 1,500-tick stress-adaptation phase, and 131 foods
in the frozen retention phase. Its `pred_food_ahead` baseline in the
held-out trials sat at 0 - its predictions were precise where the
other transformer seeds sit chronically elevated (44-87). Its Hebbian
wiring ran hot too (696 updates vs 79-212 in the other transformer
seeds), and it was the only seed whose synaptic top-5 is dominated by
food-d
irected prediction synapses. The same seed under the controls
ate 6 (off) and 1 (linear). This is the first end-to-end existence
proof of the architecture doing what it was built to do - but at 1 in
12 seeds it is a lottery ticket, not an effect.

**The calm world changed every trajectory.** The six run-8 seeds, as
transformer, ate 3.5 foods on average in run 9 (run 8: 4.67), with
paired-vs-linear diffs +2, -1, -2, +1, +7, +2: run 8's
all-non-negative pattern (+3, 0, +3, 0, +2, +5) is gone. Silencing
~120 ambient startles changes the random stream, so trajectories are
not comparable seed-by-seed; what the comparison does show is that the
run-8 advantage was not robust to the world it lived in. Two hypotheses
remain open and unseparated: run 8 was a lucky draw at n = 6, or the
transformer's edge lives specifically in noisy worlds where prediction
has more to contribute. The honest position: the population-level
feeding advantage is not established; what is established is that the
transformer's seed variance is much larger than both controls'.

**Object permanence mostly healed.** The transformer's mean alignment
rose from run 8's bimodal -0.19 to +0.54, positive in 10 of 12 seeds
(range -0.75 to +0.96); the linear control replicated its run-8 value
almost exactly (0.779 vs 0.778). In a calmer world the transformer's
spatial memory stopped confidently pointing the wrong way in most
seeds.

**Anticipation got weaker; feeding during the anticipation window
appeared.** The early-window `pred_food_ahead` rise is now mean -1.43
(positive in 6 of 12 seeds, +2.1 to +6.6; negative in 6, down to -14.4),
versus run 8's +1.15. The learned contingency signal remains
seed-unstable. But seed 222 shows what it is for: it ate in every
held-out trial within 2 ticks of the food appearing.

**Anxiety still does not recover in the adaptation eval.** Final
anxiety 100 in every seed of every condition; escape ratios ~0. The
5%-startle phase still overwhelms regulation within 1,500 ticks; t
he
eval measures the ceiling, not recovery. The only feeding during it is
seed 222's 18 foods.

**Wiring and overhead (unchanged story).** 61.4 synapses grown from
prediction sensors (linear: 56.1), zero into them; action top-1 0.985;
loss EMA ~0.0045; delta MAE 0.0009-0.0053. Transformer throughput
160.2 ticks/sec (2.65x slower than off; 23.2 s inference + 22.6 s
training per 24k-tick run); linear 275 ticks/sec (~0.8 s total).
Run 9's 36 runs finished in ~64 minutes of CI time.

### Where this leaves the question

The integration mechanism is unchanged and sound. The behavioural
evidence is now sharper and more honest: in a calm world the
transformer population does not reliably out-eat the controls; instead
it occasionally (1/12) enters a qualitatively different regime -
precise predictions, dense Hebbian wiring, feeding in frozen evals -
that neither control ever enters. Whether that regime is reachable by
training design or only by seed lottery is now the central question.
Separately, the growth study (see `docs/brain_growth.md` and
`experiments/growth_experiment.py`) opens a second front on the same
architecture: 240,000-tick lives that watch the live neuron count
against the capability monitor's decisions, to distinguish a brain
that stops growing because it is forbidden to from one that stops
because it no longer needs to.

### The supernova is preserved

Seed 222's brain no longer exists only as run-9 JSON metrics. CI runs
14-15 rebuilt it deterministically through the real trainer and
committed the organism itself to `experiments/results/squid_222/`:
its 45-neuron brain in the standard game format, its transformer's
weights, its cortex telemetry and `metadata.json` recording the
field-by-field verification of the rebuild against run 9's published
record. Run 15's verdict: **REPRODUCED** - all 24 strict fields (the
full training record, object permanence and the delayed-consequence
evaluation) match run 9 bit-for-bit: 463 foods on 880 approaches, 696
Hebbian updates, train_steps 1511, loss_ema 0.00489973, 73 synapses
grown from predictions, and a weights checksum that round-trips exactly
at 313.006211. Even the eight stochastic-tape fields matched (18 foods
in adaptation, 131 in retention on 222 approaches): run 14's only
divergence had been self-inflicted - the artifact-validation step ran
an extra simulation between training and evaluations and consumed
shared RNG; with validation moved after the evaluations, the whole
tape reproduces. The preservation pipeline is
`experiments/save_special_squid.py`, triggered by a `[save-squid]`
commit; a restored cortex resumes predicting after two ticks of fresh
experience (the experience buffer is deliberately not preserved).
