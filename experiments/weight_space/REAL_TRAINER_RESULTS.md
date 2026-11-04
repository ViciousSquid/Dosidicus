# Real Dosidicus trainer: action–outcome learning and weight-only transfer

**Study date:** 4 November 2026  
**Status:** The headless trainer has been corrected to couple neural actions to consequences. **No validated general intelligence gain has yet been established.** The original birth-weight profile shows a modest, variable benefit from learned weights; the three-edit profile is not a demonstrated improvement.

This study runs the repository's **real `HeadlessSimulation` and `HeadlessBrain`**, not the separate illustrative `closed_loop.py` tank. The model still simplifies much of the graphical Dosidicus game's physics, ecology and social interactions.

## What was broken

Before the change, `headless/headless_trainer.py::_update_environment()` automatically called `squid.feed()` with a fixed 10% probability whenever food was visible. That action required **no selected `act_eat` neuron**. Body position also drifted randomly while neural action selection was not consulted. Consequently, a score based on meals could be high for a brain that had learned absolutely nothing about food.

A second issue affected causal credit: manually scripted `feed`, `clean`, or `set_state` events could change the organism's drives inside an outstanding action–outcome window, potentially giving an unrelated preceding action undeserved credit.

## Exact implementation

1. **Neural action drives the headless body.** Each simulation tick follows body ageing → environment event → local percepts → real `HeadlessBrain.propagate` → shared `src.decision_engine.select_action(jitter=False)` → body actuator. Feeding occurs only when `eating` is the selected action and visible food is within bite distance after movement; the squid approaches food in small steps. Food beyond the 0.32 normalised-unit sight radius cannot stimulate `can_see_food`.
2. **Body movement is no longer an unobserved random override.** The normal resting `act_move` pathway permits wandering; a true blank, motor-free brain stays still. `act_flee` controls flight and can end a simulated startle. Sleeping requires a learned `act_rest` or innate `act_collapse`, and its finite sleep period ends rather than silently restarting.
3. **Action-caused state changes remain visible to learning.** `causal_learning.on_action()` receives the pre-outcome neural state; the next propagation exposes the resulting drives and sensors to the existing correlation, STDP and causal-outcome mechanisms.
4. **External intervention is not evidence of intelligence.** Scripted feeding is counted separately as `manual_feedings`, not `food_eaten`. Causal windows whose evidence is corrupted by manual state changes are discarded with a persisted audit counter and reason; settled knowledge and synaptic weights remain untouched.
5. **Frozen evaluation is explicit.** `TrainingConfig.learning_enabled=False` stops plasticity observations, Hebbian commits, sleep consolidation and neurogenesis during tests. It does not replace neural propagation with a lookup table.
6. **A/B comparisons transfer only directed synaptic weights** to a new brain of identical architecture. The simulated body, personality draw, environment event seed and evaluation run are freshly initialised for every paired observation; no learned causal episode history is copied. Existing save files and default-branch weights are not rewritten.

Relevant code:

- [headless/headless_trainer.py](../../headless/headless_trainer.py)
- [src/portable_brain.py](../../src/portable_brain.py)
- [src/causal_learning.py](../../src/causal_learning.py)
- [tests/test_headless_causal_training.py](../../tests/test_headless_causal_training.py)
- [experiments/weight_space/trainer_transfer.py](trainer_transfer.py)

## Native training/transfer protocol

Two starting weight sets:

- **Original:** reconstitute the exact 3.2.0 source weights; this branch contains the earlier three-edit experiment, so the control explicitly reverses it.
- **Three-edit:** the edited birth weights, already shown not to improve the preceding toy-world benchmark reliably.

For each profile, three training seeds **11, 29, 53**, each for **450 simulation ticks**, with normal Hebbian/STDP/causal learning enabled and neurogenesis disabled to isolate synaptic learning.

Next, evaluate paired untrained and weights-only-transferred brains, 300 ticks per episode, for three fresh evaluation seeds **10001, 10033, 10061** in each of three regimes:

| Test world | Food spawn chance/tick | Startle chance/tick |
| --- | ---: | ---: |
| Balanced | 0.025 | 0.005 |
| Scarce | 0.008 | 0.005 |
| Stress | 0.025 | 0.035 |

Nine matched pairs per regime and profile. All evaluation pathways have **learning disabled**.

Instead of a weighted “IQ score”, measure **real meals earned, health remaining, unavoided startle ticks, flight actions, escaped startles, food pursuit and visible-food exposure**. Values below are *mean differences, trained minus untrained*, across nine pairs. Positive food and health changes are desirable; negative unavoided startle changes are desirable.

## Verified observations

| Starting weights | World | Δ meals | Δ health | Δ unavoided startle ticks |
| --- | --- | ---: | ---: | ---: |
| Original | Balanced | +0.333 | −0.500 | +0.667 |
| Original | Scarce | −0.111 | +0.500 | −0.667 |
| Original | Stress | **+0.222** | **+2.667** | **−3.556** |
| Three-edit | Balanced | +0.444 | −0.083 | +0.111 |
| Three-edit | Scarce | +0.111 | 0.000 | 0.000 |
| Three-edit | Stress | 0.000 | −0.250 | +0.333 |

The original brain's learned weights provide a **small improvement in the stress regime** under these seeds, but the effect is not uniform across regimes or metrics. The earlier three-weight modification is **not a reliable improvement** and under stress performs worse after learning on the health and unavoided-startle measures.

Training generated dozens of real synaptic changes per brain: in the recorded three original-profile training runs **52–67 directed edges changed**, with **29–46 Hebbian updates** and **60–78 closed causal episodes**. However, the **number of changed edges is not an intelligence measure**. It is only evidence that the learning machinery executed.

A run of 450 training ticks and only nine paired evaluation trials per regime is a **smoke-scale experimental sample**. It cannot establish a stable effect size, long-term survival advantage, generalisation, or emergent cognition. Different worlds and seeds may reverse the result.

## Reproduce exactly

On the [experimental branch](https://github.com/ViciousSquid/Dosidicus/tree/experiment/newborn-weight-space-2026-11), from the repository root:

```bash
python -m pip install numpy pytest PyQt5 Pillow platformdirs
QT_QPA_PLATFORM=offscreen python -m pytest -q \
  tests/test_headless_training.py \
  tests/test_headless_causal_training.py \
  tests/test_headless_trainer_transfer.py \
  tests/test_weight_space_experiment.py \
  tests/test_weight_space_closed_loop.py

python -m experiments.weight_space.trainer_transfer \
  --json experiments/weight_space/trainer_transfer_results.json
```

The experimental branch's GitHub Actions workflow runs these tests and writes **all paired per-seed results as JSON**, plus the preceding static probes, grid and toy-world results, into one build artefact. The most recent successful run's exact commit and artefact should be used; do not relabel scores from one implementation as if they were produced by another.

## Limitations and further experimental design

- The headless aquarium is still small and uses simplified movement and startle physics; its fitness metrics must not be conflated with the full game.
- The environment has no explicit spatial predator with line-of-sight, attack range, occlusion or realistic flee trajectories; a “successful escape” is defined as ending a simulated startle. Real antipredator intelligence requires a spatial adversary.
- Although network decisions now affect future states, the trainer still omits rocks, dynamic plants, social encounters and multiplayer causal learning.
- The initial weights and the trained weights affect future *perception* through movement. That is desirable feedback, but it makes later event histories diverge, so common RNG seeds do not mean identical future percepts.
- Exploration into currently unwired action neurons—such as voluntary rest, play and shelter—has not yet been demonstrated. Without meaningful experiences and affordances, these skills cannot be certified as learned.
- Long-term neurogenesis, consolidation ablations, cross-squid personality generalisation and full desktop/Android simulation remain untested.
- The initial three-weight experiment's original positive threshold score was misleading in the absence of consequence-coupled action evaluation; retain [RESULTS.md](RESULTS.md), [GRID_RESULTS.md](GRID_RESULTS.md) and [CLOSED_LOOP_RESULTS.md](CLOSED_LOOP_RESULTS.md) as historical record.

**Disposition:** Corrected causal learning infrastructure, a reproducible paired test, and a narrowly positive observation in one stress regime. **Not sufficient evidence that Dosidicus is now smarter.** The edits to innate threat reflexes must stay out of the production branch until broader, longitudinal tests demonstrate actual adaptive benefit.
