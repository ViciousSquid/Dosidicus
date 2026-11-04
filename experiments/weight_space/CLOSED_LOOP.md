# Can direct weight editing make Dosidicus smarter?

## Correcting the original question

The first version of this project changed **three threat reflex synapses**. It improved agreement with 11 human-defined threshold probes but produced a no-threat feeding regression on a separate 144-state sweep. **That was not evidence that the squid became smarter.** This follow-up investigates *consequential choice* and *learning transfer* instead of counting action-neuron threshold crossings.

It is an experiment on Dosidicus's actual numerical neural machinery with a **simplified action-coupled tank**, *not* the graphical game. It must not be promoted to release solely on the basis of toy-world scores.

## Why the existing trainer does not test intelligence

In `headless/headless_trainer.py`, the default simulation's `_update_environment` method does this:

```python
if self.squid.food_visible and random.random() < 0.1:
    self.squid.feed()
    self.stats['food_eaten'] += 1
```

The food counter can increase whether or not the network fires `act_eat`. Its position and motion are updated independently of action selection. Thus the old trainer's feeding statistic is a poor fitness metric for weight-space programming. A test of network intelligence needs **actions to cause consequences that alter the next inputs**.

## New experiment: `closed_loop.py`

- Uses `HeadlessBrain` with its original network and `src.decision_engine.select_action`, not a separate invented action policy.
- Every simulated second advances the real clock, calls `brain.update_state`, calls `brain.propagate()` (and therefore the shared `src.propagation` transfer function), and calls `select_action(..., jitter=False)`.
- The chosen `eating` action consumes visible food, reduces hunger and replenishes health. **No eating action, no food**.
- The chosen `fleeing` action can escape an active predator; failure and nonflight incur damage. Flight without a predator costs food/energy.
- Hunger, anxiety, sleepiness, health, visibility and threat change over time, including as a consequence of neural decisions, feeding back to the network.
- A real learned `sleeping` action or collapse reflex activates a short simulated rest episode. Involuntary collapse carries a recorded penalty.
- Four environment regimes vary food availability, attack rate and false-alarm frequency. Every profile sees the same seeded distribution of external events.
- With `learn=True`, each tick uses the real plasticity observation path; every 30 ticks calls `HeadlessBrain.perform_hebbian_learning`, then sleep consolidation. Training episode weights persist across worlds. Neurogenesis is **disabled** in this first controlled study to isolate synapse learning.
- Evaluation uses fresh brains and held-out world event seeds. A separate **learning-transfer** arm first trains the same brain in multiple worlds, then resets activation state while preserving its learned weights and evaluates in an unseen episode. These two arms must not be conflated.

## Candidate birth-weight profiles

| Connection | Original | Previous edit | Threat-only | Moderate |
| --- | ---: | ---: | ---: | ---: |
| Threat → Flee | 0.55 | 1.00 | 1.00 | 0.90 |
| Anxiety → Flee | 0.25 | 0.65 | 0.25 | 0.35 |
| Threat → Eat | absent | −0.55 | absent | −0.20 |

The previous edit is the actual three-weight change in the experimental branch's `brain_constants`. The runner **restores original weights for controls** and applies the other candidate profiles only to in-memory brains, via `apply_weight_change` / `remove_weight` with provenance. It does not change anyone's existing saved animals.

## Predeclared simulation protocol

Four worlds (`balanced`, `scarce_food`, `dangerous`, `false_alarms`) with fixed, documented probabilities for food, predators, noise. Simulated food persists 13 ticks; predators last up to 7 ticks. These are *model assumptions*, not measured Dosidicus-world parameters.

- Training seeds: `11, 23, 37, 51`; 200 ticks/world, per brain, learning enabled
- Development evaluation seeds: `1009, 1021, 1033, 1051`; 250 ticks/world, learning disabled
- Independent evaluation seeds: `4001, 4013, 4027, 4051`; 250 ticks/world, learning disabled
- Transfer evaluation seeds: `80011, 80023, 80037, 80051`; after training, 250 ticks in balanced world

**Observables:** ticks survived, remaining health, meals actually eaten, injury amount, successful predator escapes, unnecessary flight, starvation time, collapse count, and actions chosen. No subjective desired-action labels are used.

The *illustrative* weighted score is:

```text
100 × ticks_alive / max_ticks
+ 3 × food_eaten
+ 1 × successful_escapes
− 0.75 × damage
− 0.12 × false_flees
− 0.18 × hunger_above_85_ticks
− 0.50 × collapses
```

This is an explicit convenience metric, **not a validated intelligence metric** or a welfare model. Publish the underlying observables, not just the score.

**A genuine positive result would require** repeatable gains in survival and food acquisition (without unacceptable false alarms), robustness across all four regimes, and no decline in learning transfer on previously unseen event streams. A better composite score by itself is insufficient. Until a full-game replication, none of this establishes general intelligence.

## Reproduce

From the branch's repository root:

```bash
python -m pip install numpy pytest PyQt5 Pillow platformdirs
QT_QPA_PLATFORM=offscreen python -m pytest -q tests/test_headless_training.py tests/test_weight_space_closed_loop.py
python -m experiments.weight_space.closed_loop --json experiments/weight_space/closed_loop_results.json
```

Workflow: `.github/workflows/weight-space-experiment.yml` saves `closed_loop_results.json` alongside the earlier threshold-probe report and 144-state sweep.

## Scientific limitations and unresolved issues

1. This is still a **minimal tank model**, with synthetic predators, food and injury logic. It omits full geometry, proximity, pursuit, positioning, decoration play, multi-squid social interaction, reproduction, network visits and actual render/UI.
2. A predator attack is synthetic, with hand-set probabilities and consequences. A weight profile can exploit this model and fail in the real game.
3. Environmental draws are common-random-number seeded, but different actions change future state and thus diverge the histories; this is **intended causal feedback**, not evidence of identical trajectories.
4. Most actions are available, but `act_play` and `act_shelter` have no ecological affordances in this tank. This does not test whether the squid learns new skills or learns to plan.
5. The network retains learned synapses between training worlds, but the training stage is small, and Hebbian correlation does not necessarily optimise survival. **A high synaptic-update count is not proof of useful learning.**
6. The transfer arm tests post-training behaviour but does not automatically compare each trained brain to an *untrained matched brain on the identical transfer episode*. That comparison is needed before attributing transfer performance to learning.
7. `select_action(jitter=False)` removes selection noise to isolate weight effects; live gameplay has noise and may respond differently.
8. Some action binding cooldowns and bodily animation delays are simplified. No multi-agent adversarial dynamics are included.
9. **Do not rewrite this study's evaluation rules in response to poor results.** If a better weight profile is designed after reviewing them, it requires a new held-out study and a recorded hypothesis.

## Disposition

Evidence of actual adaptive intelligence requires **closed-loop behavioural success**, **measurable changes caused by learning**, **successful transfer to unfamiliar situations**, and real-game validation. The test supplies a more defensible starting point than the previous threshold-only study, but its outputs must be checked and documented, including negative results, before calling Dosidicus smarter.
