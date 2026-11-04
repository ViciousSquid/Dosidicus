# Dosidicus newborn weight-space experiment — November 2026

**Status:** Experimental; **not yet a validated intelligence improvement**. This branch was made from `3.2.0_LatestVersion`. It changes only the newborn's threat-related synapses; ordinary saved/learned brains are not migrated.

The point of this experiment is to test whether a tiny, direct edit to the *weights of the actual neural network* makes the newborn's action bank resolve a high-threat/food conflict more appropriately, without compromising safe feeding, sleep or basic behaviour. It is **not** a reproduction of the GPT/Qwen paper or a full proof of smarter animals.

## Latest milestone — real trainer learning is now action-coupled

The headless trainer now routes decisions from the **actual shared neural network** into feeding, food approach, movement, startle avoidance, health and sleep. Exogenous `feed`/`clean`/`set_state` interventions cancel pending causal credit, preventing a scripted reward from being claimed as the squid's own learning. Paired evaluation can now freeze every recorded synaptic learning step and transfer only directed weights into a fresh brain.

**[Read the full implementation, test protocol, per-world learning outcomes and limitations](REAL_TRAINER_RESULTS.md)**. [Successful GitHub CI run](https://github.com/ViciousSquid/Dosidicus/actions/runs/41747621480) verified **63 tests and 124 subtests**, and published the [complete raw experiment artefact](https://github.com/ViciousSquid/Dosidicus/actions/runs/41747621480/artifacts/13283539696).

After 450 simulated training ticks, the original newborn profile's learned synapses improved health by **+2.67** and reduced unavoided startle exposure by **3.56 ticks** per 300-tick evaluation episode in the deliberately stressful headless world; however, the effects were small, variable and not consistently positive in balanced or food-scarce worlds. The original profile still cannot be said to be generally smarter. The three-weight edited profile did **not** demonstrate a reliable benefit.

The original weight-space work remains useful as a *negative result*: action-readiness thresholds are not a substitute for behaviour and causal learning.

## Final outcome — direct edits did NOT demonstrate smarter squids

After a separate action-coupled test of actual neural decisions changing food, injury, health, threat escape and later states, the original three-weight edit **failed to produce a meaningful behavioural improvement**. Across 16 holdout episodes per profile, both original and edited ate the same **53 meals**, neither selected a single flight action, and their average survival was effectively identical.

When learning was enabled and learned weights were copied into a fresh brain for an unseen episode, the **original profile's mean transfer score was 46.80 versus 44.55 for the three-edit profile** (four small transfer samples; not a general benchmark). Neither is evidence that one squid is broadly smarter.

**[Read the final closed-loop negative result and actual weight-transfer analysis](CLOSED_LOOP_RESULTS.md)**, followed by the [full causal-world methodology](CLOSED_LOOP.md). The first static probe scores below are narrow threshold metrics, **not** an intelligence result.

## Research hypothesis

Original innate wiring drives eating from `can_see_food` (+0.85), flight from `threat_level` (+0.55), and flight from `anxiety` (+0.25). Because the eating threshold is 38 and the flight threshold 50, it is possible for food to be above its action threshold while sustained threat still leaves flight below threshold.

The hypothesis is that stronger threat/anxiety-to-flight excitation, paired with a modest negative threat-to-feeding edge, will make the *network* choose appropriate threshold responses for specified danger states without hard-coded behavioural if/else rules.

### Complete directed-synapse change log

| Source → target | 3.2.0 baseline | Candidate branch | Intended effect |
| --- | ---: | ---: | --- |
| `threat_level → act_flee` | +0.55 | **+1.00** | Strengthen sustained danger signal |
| `anxiety → act_flee` | +0.25 | **+0.65** | Anxiety corroborates danger |
| `threat_level → act_eat` | Absent | **−0.55** | Suppress feeding under high threat |

Everything else is unchanged, including the original action competition and sleep gates, activation thresholds, decay/smoothing, Hebbian/STDP learning, neurogenesis, output bindings and newborn motor population. All edited weights are within the existing [−1, +1] synaptic limits. The three edits are in `src/brain_constants.py` only; they flow through the existing provenance-aware `RecordedSynapses.apply_weight_change` at birth.

**Important:** These are working *birth priors*, not immutable rules. Their downstream learned values can still change. The code does not edit an existing squid's brain or erase any saved weights.

## A/B methodology (predeclared)

The runner is `experiments/weight_space/experiment.py`. Its control and candidate are separately constructed `HeadlessBrain(TrainingConfig(neurogenesis_enabled=False))` objects. The candidate starts from the new innate table; the control restores the **two exact original weights** and removes the **one newly introduced edge** using the recorded synapse mutation path.

A structural assertion establishes that **exactly these three directed edges differ**. Both conditions use the same newborn neurons and action competition network.

Each trial imposes the same sensory/drive snapshot on both brains, then performs **32 synchronous updates with the real shared `src.propagation.propagate` function**. It tests the action-neuron activations against the existing `ACTION_FIRING_THRESHOLDS`.

Dosidicus's transfer function is based on:

```text
input(target) = sum(signal(source) * weight(source,target))
target_level  = resting_level(target) + input(target)
next_level    = clamp(old + 0.5 * (target_level - old), 0, 100)
```

Normal core drives have a baseline of 50; input sensors rest at zero and contribute half their 0–100 level. The existing recurrent lateral inhibition between actions remains active.

These are neural **action-readiness** probes. They do *not* step the squid's body, cause food acquisition, or model threat escape. This distinction is essential.

### Cases and expectations

| Probe | Required threshold crossing(s) | Category |
| --- | --- | --- |
| safe_hungry_food | Eat yes; flee no | Safeguard |
| safe_content_food | Eat yes; flee no | Safeguard |
| safe_nothing_visible | Eat no; flee no | Safeguard |
| mild_threat_food | Eat yes; flee no | Safeguard |
| anxiety_without_threat | Eat no; flee no | Safeguard |
| high_threat_with_food | Eat no; flee yes | Target |
| moderate_threat_with_food | Eat no; flee yes | Target |
| sustained_threat_without_food | Eat no; flee yes | Target |
| startle_without_food | Flee yes | Reflex safeguard |
| sleep_blocks_feeding | Eat no; flee no | Sleep safeguard |
| exhaustion_collapse | Collapse yes | Homeostasis safeguard |

There are **11 distinct scenarios**, each with **32 deterministic perturbations per split**:

- Development seeds: 0–31
- Independent holdout seeds: 10000–10031
- Total: 352 *paired trials* per split, 704 paired trials overall
- The same trial conditions are used for both networks
- Nonzero hunger, anxiety, sleepiness and threat readings receive deterministic ±3 uniform jitter (clamped 0–100)
- Binary senses remain strictly on/off; no injected stochastic neural noise
- No trained, pre-existing networks are compared; neither condition undergoes learning or neurogenesis during the probes

**Acceptance criteria, defined before examining results:** In each split, the candidate's total number of passes must strictly exceed the original's; **no individual safeguard or danger probe may regress**; and at least one danger probe must strictly improve. These are narrow engineering gates, *not a claim of general intelligence or improved biological survival*.

The runner publishes the full results including exact weights, Python/NumPy versions, GitHub commit SHA, exact seed lists, counts, case expectations and **mean action-neuron activations**.

## Reproduction instructions

From the repository root, using Python 3.11 or newer:

```bash
python -m pip install numpy pytest
python -m pytest -q tests/test_headless_training.py tests/test_weight_space_experiment.py
python -m experiments.weight_space.experiment --json experiments/weight_space/results.json
```

Run from the checkout's repository root so the `src` module is importable. A nonzero status means a test or predeclared experiment gate has failed, not that it should be silently ignored.

GitHub Actions workflow: `.github/workflows/weight-space-experiment.yml`. It runs on pushes to this branch and is also manually dispatchable. Its `newborn-weight-space-report` artefact contains the complete JSON report if the report step executes.

## Results and audit record

**GitHub Actions run:** [Newborn weight-space experiment](https://github.com/ViciousSquid/Dosidicus/actions/workflows/weight-space-experiment.yml?query=branch%3Aexperiment%2Fnewborn-weight-space-2026-11).

**VERIFIED RESULTS:** The [successful CI run](https://github.com/ViciousSquid/Dosidicus/actions/runs/41744349842) executed **46 tests and 108 subtests**, then ran the full paired protocol at commit `850f833281f15a3cdfedfb63f2cc06c374bdd546`.

| Split | Baseline | Edited | Net improvement |
| --- | ---: | ---: | ---: |
| Development (352 paired trials) | 253 correct | 349 correct | **+96** |
| Holdout (352 paired trials) | 256 correct | 352 correct | **+96** |

The three target-threat probes improved from **0/32 to 32/32 each** in both splits; safety scenarios had no observed regressions. The exhaustion-collapse check still failed **3/32 development trials in both brains** (unrelated to the edit). An important caution: anxiety without threat boosted mean flee activation from approximately 11 to 29, although it remained below the threshold in these trials.

**[Read the complete per-probe results, activation values, observed failures and interpretation in RESULTS.md](RESULTS.md).** The [raw JSON artefact](https://github.com/ViciousSquid/Dosidicus/actions/runs/41744349842/artifacts/13282437823) contains machine-readable seeds and values; its retention depends on GitHub settings. These scores demonstrate performance on specified threshold probes, **not greater general intelligence or actual survival**.

| Test | Observed status |
| --- | --- |
| Three source-level changes | Implemented in the experimental branch |
| Exact-edge invariant | Automated test provided |
| Original neuro-mechanism test suite | CI executes `tests/test_headless_training.py` |
| Development-seed A/B | Workflow report |
| Holdout-seed A/B | Workflow report |
| Whole-life survival and food acquisition | **Not measured** |
| Learning quality or speed | **Not measured** |
| Neurogenesis and personality development | **Not measured** |
| Mac/Windows/Android live game performance | **Not measured** |

Do not substitute a hypothetical score for a missing or failed CI result. Unexpected failures are scientific outcomes and should be reported explicitly rather than changing the acceptance criteria post hoc.

## Exploratory robustness sweep: a substantive negative finding

After the preregistered test, a separate **144-state unlabelled grid** varied six threat levels, four anxiety levels, three hunger levels and food visibility. It found **14 states** that moved from eating to neither eating nor fleeing; one had **zero threat**. Specifically, with threat 0, anxiety 80, hunger 40, food visible, eating fell from **38.13645** to **36.80028**, crossing below the eating threshold of 38. This is a **regression** not covered by the original safeguards. The grid also identified 20 transitions from neither to flee and 9 transitions from eat to flee. At maximum threat with visible food, only six of twelve candidate states activated flight.

**[Complete sweep methodology, all 144-case aggregate outcomes, exact regression and source JSON: GRID_RESULTS.md](GRID_RESULTS.md).**

The strong result on the predefined cases must therefore not be summarised as an unconditional improvement in intelligence or even in feeding/flight policy. This version is **not suitable for merging into the production default**. Any new tuning after this observed regression must use fresh evaluation states; the previously inspected holdout is no longer untouched.

## Interpretation and threats to validity

1. The tests ask whether activation levels meet **human-defined desired thresholds** on a narrow family of states; satisfying them is *not* proof of intelligence or generalisation.
2. The headless trainer's world does not fully close the causal loop from the action-bank's chosen action to the next environment/body state. Therefore food-eaten, survival time or stress in an ordinary headless run **cannot validly be presented as causal evidence of a smarter neural policy** without further work.
3. The 32 steps per probe are stationary sensory snapshots. In the game, the world and squid change on each tick. Plasticity, STDP, consolidation, neurogenesis, pruning and social interactions are not covered.
4. A larger threat gain could cause *false alarms*. Inhibiting feeding in moderate threat could also cause a squid to do neither eating nor fleeing. The test cases are not comprehensive.
5. The seeds represent perturbed inputs for the *same two fixed networks*, not 32 independently evolved brains; an observed pass-rate increase is not a statistical estimate of general game performance.
6. The candidate was hand-designed, not optimised by gradients, reinforcement learning or an automatic weight-search algorithm. No new concepts or learned behaviours were installed.
7. The three-weight intervention is deliberately small to isolate its effect, but separate one-edge and two-edge ablations would be needed to attribute the improvement among the three edits.

## Required next stage before production

Build a truly closed-loop test in which action neurons control movement, feeding and threat avoidance, compare baseline and candidate with common random seeds over long simulation lives, retain learned-weight provenance, measure new skill acquisition and memory, run hostile and unfamiliar environmental regimes, perform three-edge ablations, then validate desktop and Android. Test that this stronger newborn prior doesn't crowd out experience-driven learning.

**Reversibility:** Switch back to `3.2.0_LatestVersion` to recover the original innate tables. No existing saves are migrated or modified by this experiment. Do **not** merge these weights into the production branch on the strength of static probes alone.
