# Verified closed-loop results — are the edited squids smarter?

**Conclusion: No general improvement demonstrated.** Directly changing three birth weights dramatically improved a stationary, hand-labelled reflex test, but **did not materially improve survival, feeding, escapes or health** in the action-coupled proxy aquarium. The base profile also transferred learned synaptic weights more successfully than every edited profile in these four transfer episodes.

The result is a **negative research result**. Do not merge the three experimental default-weight edits into `3.2.0_LatestVersion`.

## Evidence

- Successful CI: [run #41745949421](https://github.com/ViciousSquid/Dosidicus/actions/runs/41745949421), [tested implementation](https://github.com/ViciousSquid/Dosidicus/commit/c19061f6fcef4e4bb7e35c3af4b933002038173a)
- **50 passed, 108 subtests passed** (existing mechanism suite plus experiment tests)
- [Exact machine-readable JSON for every episode and profile, plus original probe/grid results](https://github.com/ViciousSquid/Dosidicus/actions/runs/41745949421/artifacts/13284790129)
- Experiment: `experiments/weight_space/closed_loop.py`
- Methodology and limitations: [CLOSED_LOOP.md](CLOSED_LOOP.md)

### Fresh-brain performance (untrained; paired evaluation worlds)

Mean values across the **16 episodes per split**: four worlds × four event seeds, maximum 250 simulated seconds per episode.

| Profile | Development score | Holdout score | Development survival ticks | Holdout survival ticks |
| --- | ---: | ---: | ---: | ---: |
| Original 3.2.0 | **−7.96** | 26.65 | 151.2 | 196.9 |
| Three-edit hypothesis | −8.21 | **26.84** | 151.5 | 196.9 |
| Threat-only hypothesis | −7.57 | 26.65 | 152.2 | 196.9 |
| Moderate hypothesis | −7.75 | 26.68 | 152.5 | 197.0 |

The mixed-sign score is a **hand-defined proxy reward**, not a general cognitive score. The differences are extremely small, with essentially identical feeding and health outcomes; a small change in score is **not proof of a useful improvement**.

### Actual food, flight and escape decisions

| Metric (all 16 development episodes) | Original | Three-edit | Threat-only | Moderate |
| --- | ---: | ---: | ---: | ---: |
| Meals actually eaten | 44 | 44 | 44 | 44 |
| Flee actions | 0 | 0 | 1 | 1 |
| Successful escapes | 0 | 0 | 1 | 1 |

**Holdout (all 16 episodes): every profile ate exactly 53 meals and selected fleeing zero times.** In the development environment the three-edit profile never fled either.

The single-tick startle pulse plus smoothed neural activation and a firing threshold of 50 is one plausible mechanism for this nonresponse. There is also a sign interaction: anxiety below its 50-point resting level contributes *negatively* through the positive anxiety→flee synapse, and the three-edit profile magnifies that effect. These are engineering hypotheses to investigate in the live game, not a proved explanation for every trajectory.

**Interpretation:** The edit mainly changed stationary steady-state activation under sustained inputs, while actual world stimuli change before the network reaches that state. The behaviour measured in the original 11 threshold probes does not translate into real decisions under short threats.

### Learning transfer: isolated learned synapses

A separate arm runs four training episodes per brain, across all four worlds, calls the *real* Hebbian/STDP commit and causal-learning machinery, and then evaluates a different, unseen event stream with **frozen plasticity**. To distinguish learned synapses from other retained state, each trained network's weights are also copied into a fresh, otherwise untrained `HeadlessBrain` with no episodic memories. An untrained brain of the *same* starting profile runs the exact same transfer seed.

Mean score over **four transfer seeds**:

| Profile | Untrained | After weights-only transfer | Gain attributable to copied weights | Average learned updates |
| --- | ---: | ---: | ---: | ---: |
| Original | 28.58 | **46.80** | **+18.23** | 274.5 |
| Three-edit | 28.30 | 44.55 | +16.25 | 263.75 |
| Threat-only | 28.58 | 31.20 | +2.63 | 278.25 |
| Moderate | 28.30 | 41.55 | +13.25 | 277.75 |

This is genuine evidence that **learning can change behaviour through retained weights** in this simplified environment. But it is *not* reliable evidence of increased general intelligence. In fact the original weights have the best average transfer performance of the four candidates.

**Per-seed caution:** Much of the apparent original-brain advantage is a single favourable transfer episode, seed **37**, where the trained original ate **28 meals**, versus **4** when untrained, with an objective score rising from **25.6 to 95.5**. Other original transfer seeds were **70.0→70.0**, **26.9→28.4**, and **−8.2→−6.7**. Four seeds are far too few for a broad claim about generalisation.

After frozen evaluation, the trained and weights-only brain scores were identical for every profile here; that is consistent with the observed transfer gain being carried by weights, not a latent nonweight state in this specific test.

## Methodological corrections made before the final rerun

- The first workflow failed because PyQt5 wasn't installed for an existing test; CI dependencies were fixed.
- Early versions of the action-coupled simulator counted `attacks_suffered` as zero even when damage was delivered. The counter was corrected and the entire experiment rerun.
- The first “evaluation” mode still called `observe_for_learning` inside `HeadlessBrain.propagate`, so learning might have continued during the supposed frozen transfer. The final implementation suppresses learning observations during non-learning runs.
- The final version **adds an independently initialised untrained control and a clean weight-only transfer brain**, making the weight contribution identifiable.
- The first static sweep proved a no-threat feeding regression, which is preserved in [GRID_RESULTS.md](GRID_RESULTS.md), not concealed by the positive bespoke probe scores.

## What this establishes, and what it does not

It establishes that the initial direct weight-edit idea **failed a more relevant behavioural test**. It also establishes a **testable learning effect** (positive average weight-only transfer in the toy aquarium, uneven across seeds), and exposes a likely sensor→motor response-time bottleneck.

It does **not** establish that any candidate is generally smarter, that learned responses generalise reliably across unseen ecology, that real squid survive longer, that long-term neurogenesis is effective, that physical navigation is better, or that the weight changes should ship.

### Recommended engineering work from the negative result

1. **Repair the headless training environment's causal coupling.** Today `headless/headless_trainer.py::_update_environment` awards meals with a random 10% probability *regardless* of whether the actual brain chose eating. A trainer that does not route its real action decisions into consequences cannot reliably optimise intelligence.
2. **Investigate action firing latency** in the real game and trainer (startle pulses, target smoothing, lateral inhibition, thresholds). Determine whether a sustained dangerous stimulus ever produces actual flight *before* damage, not only after 32 artificially stationary neural steps.
3. **Test real experiential learning and transfer** across many more seeds, including reward contingencies, exploration, feeding, sheltering and social encounters, with ablations of Hebbian plasticity, causal outcome credit, consolidation and neurogenesis.
4. Only **after** behaviour and evaluation are trustworthy, attempt targeted weight-space optimisation or structural neurogenesis, using development/test/untouched-holdout regimes and preserving full provenance for every edited connection.

**Bottom line:** The original profile is the strongest of these four for the measured learning-transfer proxy. No replacement newborn-weight profile is endorsed. The experiment and all negative results remain in the separate branch.
