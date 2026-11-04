# Research: discovering a voluntary action from experience

**Branch:** `research/learned-actions-and-credit-20261104`  
**Base:** 3.2.1.0_Latest (now superseded as the repo default)  
**Date:** 4 November 2026  
**Status:** Experimental, default-off. **Not suitable for merging into the GUI/mobile game without further tests.**

## Hypothesis

The newborn brain has output neurons for play (`act_play`), shelter (`act_shelter`) and *voluntary* rest (`act_rest`), but no excitatory birth wiring into them. A purely correlation-based plasticity rule struggles to discover an output that has never fired; there is no co-activation evidence from an action the squid has not tried.

We test whether **endogenous motor exploration followed by real outcome-gated synaptic learning** can discover at least one useful, situation-sensitive voluntary action while preserving the existing network's innate reflexes and action selection.

This is not an "if tired, sleep" rule. A short stochastic spike enters an existing motor neuron; the **normal** `src.decision_engine.select_action` chooses whether that motor wins against the others. The body then follows its chosen action. Only after the **actual causal outcome window** closes can repeated evidence wire ordinary synapses.

## Code

- `src/action_discovery.py`: experimental motor-probe and post-outcome synapse learner
- `src/portable_brain.py`: opt-in `TrainingConfig.action_discovery_rate`, default **0.0**, and `action_discovery_teaching`
- `headless/headless_trainer.py`: routes optional probes through the existing brain → selector → body → causal-ledger path
- `src/neural_provenance.py`: distinct provenance mechanism `causal_motor_discovery`
- `tests/test_action_discovery.py`: positive and negative causal tests
- `experiments/action_discovery/evaluate.py`: learning, probe-only placebo, and no-probe controls
- `experiments/action_discovery/specificity.py`: **the primary evaluation**, including rested/medium/tired counterexamples
- `.github/workflows/action-discovery-research.yml`: runs all three control arms and uploads raw JSON

The baseline `3.2.0.0` headless correctness backport is **separate**. No motor-discovery code was ported to it.

## Learning algorithm

1. At a configurable probability, attempt a **short motor-neuron impulse** into one of the currently unwired actions. Do not attempt this when the brain already intends to flee, eat, or collapse, or when the squid is sleeping. The impulse is *not* a direct body action.
2. The normal network arbitrates. Only when the trial wins is a causal episode attached to the attempted motor and its pre-action cue/state.
3. The ordinary headless environment applies consequences. Resting lowers sleepiness across future ticks; an unsuccessful shelter or play attempt cannot create a fictitious reward.
4. Once the real `ActionOutcomeLedger` has closed the episode, calculate a **baseline-corrected physiological outcome**. Reducing an already comfortable need is not a valuable outcome merely because its numeric stat decreases. The reward is weighted by the *initial unmet need* above 50; this generic homeostatic score is an objective function, **not a rule selecting an action**.
5. A specific cue can become associated with the motor only after at least **3 cue-present trials and 2 cue-absent trials**, and only if (i) the positive-cue mean benefit is meaningful and (ii) the *difference in outcomes* between cue-present and cue-absent trials exceeds the evidence threshold. A cue always present during good outcomes (e.g., an otherwise clean tank) no longer qualifies.
6. A qualifying association creates or strengthens a normal directed `cue → act_* ` synapse through `brain.apply_weight_change()` with the original causal episode ID, trial counts, benefit contrast and descriptive provenance. It is not injected as a rule into `DecisionEngine`.
7. The probe controller relinquishes a learned action only when its synaptic input at the **current** sensor/drive values could actually fire the motor. An edge at 0.30 that still leaves `act_rest` below threshold is not treated as an acquired skill.
8. A scripted environment/user intervention cancels outstanding attribution windows. Cancelled probes are dropped without synaptic updates. Settled episodes are processed incrementally rather than repeatedly scanning the full historical ring.

The research still has hand-designed exploration-rate, reward-scale, homeostatic set point, minimum evidence and firing thresholds; "emergent" here means the **association between situation and behaviour is learned**, not that its reinforcement objective or motor repertoire appeared without design.

## Controlled training

All arms use the **exact original 3.2.0 innate synaptic prior** reconstructed by `experiments.weight_space.trainer_transfer.new_simulation(..., "original")`. The older three threat-reflex edits inherited by this research branch are *reversed in the experiment's brain construction*.

| Training arm | Spontaneous motor probes | Outcome-gated direct cue→motor teaching | Ordinary Hebbian/STDP |
|---|---|---|---|
| Ordinary learning | Off | Off | On |
| Motor probes only (placebo) | On | Off | On |
| Motor probes + teaching | On | On | On |

Each arm trains **four brains**, using seeds 11, 29, 53 and 71. Each brain gets 32 training bouts × 32 simulation ticks = **1,024 ticks**. The controlled fatigue curriculum alternates **94, 22, 94, 65** sleepiness to expose rest as both useful and unnecessary. At the start of each bout the environment sets the body state and explicitly cancels open causal windows; these interventions cannot be credited as neural successes.

The motor exploration rate is **0.45 per eligible tick** in the experiment. This is deliberately high to stress-test whether a skill can emerge, **not** a recommended real-time frequency.

All trained brains retain the rest of the normal Hebbian, STDP and causal learning; neurogenesis is disabled to isolate synaptic learning.

## Proper evaluation: no collapse mistaken for voluntary sleep

Only learned directed weights are transferred into a clean, frozen brain; no body state, causal history, ongoing motor impulse, or motor-learning controller is copied. Evaluation is 48 ticks, four held-out seeds **101, 103, 107, 109**, all paired with the four training seeds.

Crucially, *being asleep* is not evidence that `act_rest` was learned: the squid can also fall asleep through its **innate, involuntary `act_collapse` reflex**. The evaluation counts only an **awake → voluntarily sleeping** transition with status `sleeping`. This corrects an earlier misleading tally that counted subsequent sleep ticks after collapse as voluntary rest.

### Verified results (16 frozen episodes per arm per initial fatigue level)

| Arm | Well rested (sleepiness 22) | Moderate (65) | Very tired (94) |
|---|---:|---:|---:|
| Ordinary learning | 0/16 | 0/16 | 0/16 |
| Motor probes only | 0/16 | 0/16 | 0/16 |
| Motor probes + outcome teaching | **0/16** | **0/16** | **16/16** |

The teaching arm learned a mean `sleepiness → act_rest` weight of **+0.986** across the four trained brains. No positive `cleanliness → act_rest` pathway appeared in the recorded learned connections after adding the cue-absent control. The earlier test without that control had falsely learned cleanliness as a reason to sleep. This is an actual correctness improvement in causal credit, not merely a better scalar training score.

**Interpretation:** Across the predeclared simulated samples, the mechanism learned a previously unwired voluntary rest action **in a high-fatigue context** and did not express that action when rested or moderately tired. The probe-only placebo did not acquire that action. This is a **narrow, encouraging learning result**.

**It is not proof of general intelligence or a production-ready pet.** All episodes share one simplified headless simulator, a hand-authored rest payoff, a small number of training seeds, and the same general training curriculum. The response does not yet extend to moderate fatigue, actual 3D/2D path planning, rocks, plants, threats, multiplayer or longer-term aging.

## Reproduce

From the checkout root, with the engine dependencies installed:

```bash
QT_QPA_PLATFORM=offscreen python -m pytest -q \
  tests/test_headless_training.py \
  tests/test_headless_causal_training.py \
  tests/test_action_discovery.py

python -m experiments.action_discovery.evaluate \
  --json experiments/action_discovery/results.json

python -m experiments.action_discovery.specificity \
  --json experiments/action_discovery/specificity_results.json
```

The GitHub Actions workflow uploads both raw JSON files, including every seed and the actual learned `act_rest` input synapses, so these aggregated numbers can be independently audited.

## Next evidence needed

1. **Transfer beyond the training curriculum:** varied durations, recovery rates, initial health, different environmental conditions, and longer evaluation horizons. The current 16/16 may be fragile against changes to these.
2. **Other learned actions:** play needs actual rocks and an independently measured outcome; shelter needs plants, spatial approach and external threat relief. Do not claim learned play or shelter until their actions have physical consequences and pass placebo controls.
3. **Open-loop versus closed-loop ablations:** separately disable ordinary Hebbian/STDP learning, neurogenesis and reward teaching to understand which mechanism is responsible and whether the combination stays stable.
4. **Real game integration:** test the live PyQt5 and Android action-to-body paths before enabling anything in production. None of the new motor-learning logic is enabled in the GUI or mobile app.
5. **Safety against compulsive behaviour:** demonstrate it never learns to rest excessively, neglect food, or ignore an actual threat; count *action initiations*, never duration under an involuntary sleeping status.

**Decision:** keep the feature opt-in on this research branch. Preserve the successful behaviour-learning experiment, but do not merge it to `3.2.0.0` or enable it by default.
