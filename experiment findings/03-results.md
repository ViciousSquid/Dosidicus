# 03 — Results

All figures come from the raw logs in [`data/`](data/), each of which records
the command that produced it. Settings throughout: 30 no-information trials, 50
training, 50 frozen evaluation, per seed, per arm, with neurogenesis off.

Two independent five-seed replications. Replication A's seeds were chosen during
exploratory work; replication B's are a consecutive block picked afterwards
precisely so they could not have been selected for their answer.

---

## Replication B — seeds 200–204

```bash
python headless/cup_experiment_runner.py --seed 200 --seeds 5 --naive 30 --train 50 --eval 50 --no-growth
```

### Per seed — eval block, learning arm vs frozen control

| seed | which cup | drive under occlusion |
|---:|---|---|
| 200 | +3.5 pp (p=0.75) | +4 pp (p=0.17) |
| 201 | +16.2 pp (p=0.18) | **+15 pp (p<0.001)** |
| 202 | −11.3 pp (p=0.31) | **+29 pp (p<0.001)** |
| 203 | +9.1 pp (p=0.42) | **+26 pp (p<0.001)** |
| 204 | +9.9 pp (p=0.40) | **+22 pp (p<0.001)** |

Note the spread. Seed 200 and seed 202 differ by 25 points on the drive measure,
same code, same settings.

### Pooled over every trial

| arm | block | correct | rate | 95% CI | vs 1/3 |
|---|---|---:|---:|---|---|
| learning | naive | 30/99 | 30.3% | 22.1–40.0% | p=0.77 |
| learning | train | 70/180 | 38.9% | 32.1–46.2% | p=0.068 |
| learning | **eval** | 73/176 | **41.5%** | 34.5–48.9% | p=0.015 |
| control | naive | 30/99 | 30.3% | 22.1–40.0% | p=0.77 |
| control | train | 72/176 | 40.9% | 33.9–48.3% | p=0.021 |
| control | **eval** | 66/181 | **36.5%** | 29.8–43.7% | p=0.21 |

**Read the control's training row before reading anything else.** It scores
40.9%, "above chance" at p = 0.021 — with plasticity frozen throughout. It
learned nothing. That is the apparatus, and it is why the verdict below is a
comparison between arms and not a distance above 1/3.

The no-information baseline lands at **30.3%**, comfortably containing 1/3. The
apparatus is calibrated.

### Verdict

```
WHICH CUP
  eval: learning vs frozen control     41.5% vs 36.5%   (+5.0 pp)   p = 0.331
  eval vs no-information baseline      41.5% vs 30.3%   (+11.2 pp)  p = 0.066

DRIVE UNDER OCCLUSION
  eval: learning vs frozen control       59% vs 40%     (+19 pp)    p < 0.001
  learning arm: eval vs baseline         59% vs 26%     (+33 pp)    p < 0.001
  control arm:  eval vs baseline         40% vs 26%     (+14 pp)    p < 0.001
```

The last line is important and easy to skip: **the frozen control's drive also
rises** from its own baseline. Part of the effect is the protocol — a squid that
spends bait and shuffle phases looking at food is in a different state from one
that never saw any. The learning component is the +19 pp that survives after
both arms get the same protocol.

---

## Replication A — seeds 2, 7, 17, 43, 101

```bash
python headless/cup_experiment_runner.py --seed-list 2,7,17,43,101 --naive 30 --train 50 --eval 50 --no-growth
```

### Per seed — eval block, learning arm vs frozen control

| seed | which cup | drive under occlusion |
|---:|---|---|
| 2 | −13.3 pp (p=0.24) | −1 pp (p=0.68) |
| 7 | +16.0 pp (p=0.17) | **+10 pp (p<0.001)** |
| 17 | −11.9 pp (p=0.28) | **+16 pp (p<0.001)** |
| 43 | −7.4 pp (p=0.51) | **+11 pp (p<0.001)** |
| 101 | −17.6 pp (p=0.13) | −0 pp (p=0.94) |

### Pooled over every trial

| arm | block | correct | rate | 95% CI | vs 1/3 |
|---|---|---:|---:|---|---|
| learning | naive | 35/99 | 35.4% | 26.6–45.2% | p=0.37 |
| learning | train | 61/164 | 37.2% | 30.2–44.8% | p=0.17 |
| learning | **eval** | 63/184 | **34.2%** | 27.8–41.4% | p=0.42 |
| control | naive | 35/99 | 35.4% | 26.6–45.2% | p=0.37 |
| control | train | 64/175 | 36.6% | 29.8–43.9% | p=0.20 |
| control | **eval** | 74/179 | **41.3%** | 34.4–48.7% | p=0.015 |

Here it is the **frozen control's evaluation block** that reads "above chance"
at p = 0.015, while the learning arm sits at 34.2%. Same apparatus artefact as
replication B, landing on the other arm this time.

### Verdict

```
WHICH CUP
  eval: learning vs frozen control     34.2% vs 41.3%   (-7.1 pp)   p = 0.163
  eval vs no-information baseline      34.2% vs 35.4%   (-1.1 pp)   p = 0.851

DRIVE UNDER OCCLUSION
  eval: learning vs frozen control       48% vs 40%     (+7 pp)     p < 0.001
  learning arm: eval vs baseline         48% vs 36%     (+12 pp)    p < 0.001
  control arm:  eval vs baseline         40% vs 36%     (+5 pp)     p = 0.122
```

This replication reproduced its own exploratory run **digit for digit**
(`data/exploratory-run-seeds-2-7-17-43-101.txt`), confirming the harness is
deterministic under a seed.

---

## Both replications combined — ten seeds

Trials pooled across all ten seeds, evaluation blocks:

| | learning arm | frozen control | difference |
|---|---:|---:|---|
| **which cup** | 136/360 = **37.8%** (CI 32.9–42.9%) | 140/360 = **38.9%** | **−1.1 pp, p = 0.759** |

The no-information baseline over the same ten seeds: **65/198 = 32.8%**
(CI 26.7–39.6%, p = 0.59 against 1/3). The apparatus is calibrated on 1/3 almost
exactly.

Ten seeds, 720 scored evaluation trials, and the learning arm is **1.1 points
behind** the arm that could not learn. The two replications disagree even on the
sign (−7.1 pp and +5.0 pp), which is what a null looks like.

For drive, both replications are significant in the same direction
(+7 pp and +19 pp, both p < 0.001), and seven of the ten seeds show it
individually, with no seed significant in the opposite direction.

---

## The two measures

### Which cup: no learning

Ten seeds, two independent replications, **never significant against the frozen
control in any individual seed**, and the direction is as often negative as
positive. Both pooled estimates are small and non-significant.

This was **predicted in advance** from the code, before any trial was run — see
[`01-architectural-audit.md`](01-architectural-audit.md). Nothing the world
writes into this network distinguishes one cup from another (`can_see_food` is
binary; `position` is a tuple no synapse can read), and no action the network
can take is directional. "The food is under the left cup" is not a proposition
this brain can hold, and experience cannot teach a representation the
architecture cannot form.

The experiment is therefore a **confirmed prediction**, not a failure to find an
effect. Had the learning arm beaten the control, the audit would have been
wrong — and that would have been the finding.

### Drive under occlusion: real learning

How hard `act_eat` is driven while the food is hidden, as a fraction of its
with-food-in-sight level. Unlike cup choice, this **is** an activation on an
existing neuron, reached through synapses the plasticity engine already moves.

Pooled in replication B: **+19 pp over the frozen control, p < 0.001**, measured
in a block where plasticity was frozen — so it cannot be adaptation happening
during the measurement. Seven of the ten seeds show it individually and
significantly; the other three sit at −1, −0 and +4 points, none of them
significant. **No seed shows a significant effect in the opposite direction.**

This is the full chain the experiment set out to demonstrate, running entirely
on machinery that was already there:

> visible food → experience of its location → food hidden → the squid goes on
> seeking → a correct choice is eaten through `Squid.eat` → the ordinary
> positive consequence → measurable weight change, recorded in the provenance
> ledger → still measurable when learning is frozen.

**The squid does not learn where the food went. It learns to go on wanting it
once it is gone.**

Read [`05-limitations.md`](05-limitations.md) before citing this one. It is
statistically strong pooled and highly variable per seed, and part of the
absolute rise is protocol exposure rather than learning.

---

## Supporting numbers

**Randomisation.** Across every run, a fixed strategy — "always the left cup",
"always cup B", any of them — scores 21–48% on small blocks and converges on 1/3
when pooled. No cup position or identity is exploitable.

**Omissions.** 28–45% of trials, higher in the no-information arm where nothing
draws the squid towards the cups. Play rate per baited slot varies by 5–12%,
consistent with dropout unrelated to the answer — which is what makes scoring
over played trials legitimate.

**Freezing.** Every evaluation block reports `evaluation_was_frozen: True`: the
weight dict, the ledger's change count and the neuron set are identical before
and after.

**Machinery.** Learning arms accumulate thousands of recorded weight changes
across `hebbian`, `stdp` and `causal_reward`. Control arms record `innate` only —
the synapses the squid hatched with — confirming every write was refused.

**Test suite.** 555 passed, 1 skipped, 613 subtests
([`data/test-suite-run.txt`](data/test-suite-run.txt)), including 44 experiment
controls and 12 game-path tests.
