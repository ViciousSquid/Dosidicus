# Exploratory 144-state robustness sweep

**Status:** Completed and verified. **Result: meaningful trade-offs, including a regression in a no-threat feeding state.** This is a descriptive sweep run **after** the predeclared 704-paired-trial experiment, and is **not** an independent holdout validation.

- Workflow: [successful Actions run #41744722860](https://github.com/ViciousSquid/Dosidicus/actions/runs/41744722860)
- Tested commit: `0f5b817f21f11b24044f37f3499a22006b4826f6` (code change from preceding success: only new sweep and CI)
- Full JSON of all 144 input combinations and both networks' action activations: [workflow artefact](https://github.com/ViciousSquid/Dosidicus/actions/runs/41744722860/artifacts/13283285729)
- Reproduction: `python -m experiments.weight_space.grid_scan --json experiments/weight_space/grid_results.json`

## Method

Sweep the Cartesian product:

- Threat level: **0, 15, 30, 50, 75, 100** (six levels)
- Anxiety: **20, 50, 80, 95** (four)
- Hunger: **40, 80, 95** (three)
- Food visibility: **0 or 100** (two)

6 × 4 × 3 × 2 = **144 distinct paired snapshots**, no random noise, with 32 iterations of Dosidicus's actual shared neural propagation from identical starting states. All four combinations of feeding/fleeing threshold flags are counted per network:

- **Eat**: eating above threshold, fleeing below threshold
- **Flee**: fleeing above threshold, eating below threshold
- **Both**: both above threshold
- **Neither**: neither eating nor fleeing above threshold. **This does not mean the squid is immobile**: its locomotion or other actions may remain active. These four categories describe *only* the two measured actions.

This sweep is *exploratory*: it has no imposed correctness labels or reward. Consequently differences are **descriptive**, not a new intelligence score.

## All observed per-stratum outcomes

Each stratum contains **12 snapshots**, one for each anxiety/hunger combination. Counts are ordered Eat / Flee / Both / Neither.

| Threat | Food visible | Original | Edited |
| ---: | :---: | :---: | :---: |
| 0 | No | 0 / 0 / 0 / 12 | 0 / 0 / 0 / 12 |
| 0 | Yes | **11 / 0 / 0 / 1** | **10 / 0 / 0 / 2** |
| 15 | No | 0 / 0 / 0 / 12 | 0 / 0 / 0 / 12 |
| 15 | Yes | 10 / 0 / 0 / 2 | 8 / 0 / 0 / 4 |
| 30 | No | 0 / 0 / 0 / 12 | 0 / 0 / 0 / 12 |
| 30 | Yes | 10 / 0 / 0 / 2 | 8 / 0 / 0 / 4 |
| 50 | No | 0 / 0 / 0 / 12 | 0 / 3 / 0 / 9 |
| 50 | Yes | 9 / 0 / 0 / 3 | 6 / 2 / 0 / 4 |
| 75 | No | 0 / 0 / 0 / 12 | 0 / 6 / 0 / 6 |
| 75 | Yes | 8 / 0 / 0 / 4 | 1 / 6 / 0 / 5 |
| 100 | No | 0 / 0 / 0 / 12 | 0 / 6 / 0 / 6 |
| 100 | Yes | 8 / 0 / 0 / 4 | 0 / 6 / 0 / 6 |

## Transition summary (all 144 paired cases)

| Original → edited | Number of cases |
| --- | ---: |
| Neither → Neither | 68 |
| Eat → Eat | 33 |
| Neither → Flee | 20 |
| Eat → Flee | 9 |
| **Eat → Neither** | **14** |
| All other transitions | 0 |

**Positive:** 20 formerly non-fleeing/uneating states acquired flight, and 9 former feeding states instead activated flight. Most of these occur at elevated threat, which was the intended behavioural direction.

**Negative:** 14 former feeding states no longer activated *either* eating or flight. Some of these are low-threat states where feeding may be preferable.

**Concrete no-threat regression:** With threat **0**, anxiety **80**, hunger **40**, and visible food **100**, the original network produced eating activation **38.13645** (threshold 38, so it could eat); the experimental network produced **36.80028** (below threshold). Meanwhile fleeing increased from **3.30499** to **15.45197** (still below its threshold 50). In this stationary snapshot, an anxious squid with food available loses the opportunity to eat **despite no threat**.

This is a *real neural-threshold regression on the broader sweep*, not an error in the CI run or a reason to relabel this test.

**Another potential drawback:** At threat 100 with visible food, the candidate is classified as Flee in only **6/12** cases and Neither in **6/12**. It is therefore not a reliable universal threat response. In those Neither cases, locomotion may remain active; the grid does not simulate escape or freezing.

## Interpretation and disposition

The predeclared suite's results remain valid **for its chosen cases**: 253 → 349 correct development responses and 256 → 352 holdout responses. The new grid demonstrates that **passing a narrow set of bespoke threshold probes does not establish generally better behaviour**. Some apparently harmless high-anxiety or weak-threat states suffer reduced feeding.

The edit should **remain experimental and should not be merged to the release branch** without resolving these cases and validating them in a real action-coupled environment. A next candidate should be treated as a **new hypothesis**, with newly chosen, untouched evaluation states/seeds; reusing the now-inspected holdout would not provide an independent validation. Recommended follow-on: ablate the three edits individually, explore state-dependent threat/feeding mediation or recurrent inhibition, then test longitudinal learning and survival in a closed-loop environment. Preserve this negative result in all subsequent comparisons.
