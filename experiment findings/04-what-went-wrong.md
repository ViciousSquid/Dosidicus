# 04 — What went wrong

Six artefacts that produced confident, wrong answers before being caught. They
are recorded because each one was, at the time, indistinguishable from a
result — and because anyone extending this work will meet the same class of
problem.

The common shape: **the apparatus was answering the question instead of the
squid.**

---

## 1. The false positive that was nearly published

**The worst one.** The drive measure — how hard `act_eat` is driven while the
food is hidden — was first run on **seed 7**:

```
eval: learning vs frozen control: 64% vs 42% (+22 pp), p < 0.001
```

Clean, large, highly significant, and it matched the hypothesis. It was about to
be written up as the result, and a test was drafted asserting it.

Then **seed 2**, same code, same settings:

```
eval: learning vs frozen control: 37% vs 39% (-1 pp), p = 0.68
```

Nothing. Had the seeds come up in the other order, the conclusion drawn from a
single run would have been the opposite one.

**A single run of this experiment is one animal, and one animal is not a
result.** A single seed hands you a significant effect about as often as the
significance level says it will.

Three changes came out of this:

- `replicate()` and the `--seeds` / `--seed-list` flags, which run the paired
  design over several seeds and **pool the trials** (pooling trials, not
  averaging p-values — a mean of p-values is not a p-value);
- the test suite asserts only the *null* (which replicates every time) and the
  *mechanism* (which is guaranteed by construction), **never** a single seed's
  effect size;
- the per-seed column is printed in every replication report, so the spread is
  visible rather than buried in a pooled average.

The drive effect did survive pooling, and is reported in
[`03-results.md`](03-results.md). But it is believable because it pools over ten
seeds, not because seed 7 was convincing.

## 2. Scoring omissions as errors — an apparent *below-chance* result

Early runs came back at **13–20%** accuracy against a 33.3% chance rate. A squid
reliably *worse* than guessing is a striking result and an implausible one.

It was arithmetic. The squid reached a cup on only ~60% of trials, and the other
40% were being counted as wrong answers:

```
0.60 × 0.33 ≈ 0.20
```

Exactly the number observed. Accuracy is now **hits / committed**, with
omissions reported separately, and `omission_bias()` checks that whether the
squid plays is unrelated to which cup was baited — the assumption that makes the
drop legitimate.

## 3. The shuffle was too short to see — a second below-chance artefact

With the shuffle phase at 3 ticks, the squid was still sitting at the
**pre-shuffle** location when the choice opened, and went straight back to it.
Since a random permutation leaves a given cup in place only 1/3 of the time,
this looked like a systematic bias.

The shuffle runs long enough (16 ticks) for the squid to be able to watch where
its cup went. This is not a convenience: it is what makes a shell game solvable
in principle rather than a pure guess, and therefore what makes the null
meaningful.

## 4. The squid standing on the answer — an apparent *above-chance* result

The opposite artefact, and the one that mattered most. The squid spends the bait
and shuffle phases swimming *towards* the baited cup, so when the food vanishes
it is already there. Picking the nearest cup then scores far above 1/3 while
knowing nothing.

The obvious fix — engineer the proximity away — was wrong, because the random
walk diffuses far too slowly to wash the correlation out inside a trial
(~22 px/tick with `p = 0.20` of turning, against a 500 px cup spacing; covering
that distance takes hundreds of ticks). Suppression was not available.

So it is **controlled for** instead, three ways:

- the **start-position rule**: the choice opens only once the squid is clear of
  every cup, the same rule for all three;
- the **`started_clear` flag**: trials are scored split by whether that
  succeeded, so the residue is measured;
- the **learning-disabled control arm**: the free gift is present in both arms,
  so only the difference counts.

This is the single strongest argument for the control arm. In replication B the
frozen control's own training block scored 40.9%, "above chance" at p = 0.021,
having learned precisely nothing.

## 5. Measuring a dying animal

Long runs were producing `act_eat` readings of 0.0 through entire evaluation
blocks. The cause was not the network:

```
hunger 100   anxiety 100   sleepiness 90   act_collapse 100
```

`HeadlessSquid.update()` raises sleepiness and never lowers it (the recovery
lives in `TamagotchiLogic.update_simulation`, which the headless harness does not
run), and it has **no anxiety decay at all**. Over dozens of multi-minute trials
the squid starved, never slept, and finished pinned at anxiety 100 in a collapse
that inhibits every voluntary action it has. Meanwhile neurogenesis, doing its
job, grew 14 emergency neurons wired at ±0.8 into everything — which swamped the
effect being measured.

Two separate readings were wrong as a result:

- the drive measure was reading **how tired the squid was**, because sleep
  gating holds `act_eat` at zero;
- the drive measure was also **saturating at 100** in other runs, because a
  squid that only eats when it guesses right gets hungry enough to pin
  `hunger → act_eat`.

Fixed with explicit between-trial husbandry — rest before sleepiness reaches the
level where a trial could push it past 90, maintenance feeding to keep the
measure off both floor and ceiling, cleaning, and anxiety relaxing toward the
model's own resting value when needs are met. None of it happens inside a trial,
so none of it enters the contingency being tested.

`--no-growth` was added to isolate plasticity from structural growth. Both modes
work; the reported results use `--no-growth` so the measurement is about
learning rather than about emergency neurogenesis.

## 6. The experiment was not reproducible at all

Two runs with the same seed gave different answers. `decision_engine.select_action`
draws its tie-breaking jitter from the **global** `random` module, so seeding
only the world's own `random.Random(seed)` left the run at the mercy of whatever
had consumed the global stream beforehand — including, in the test suite, which
tests had run first.

`CupWorld.__init__` now seeds the global module too, following the convention
`HeadlessSimulation` already established for the same reason.

This one is worth flagging beyond this experiment: **any** study using
`select_action` and expecting reproducibility has to seed the global RNG.

---

## Two near-misses in the process, not the experiment

**A test asserting something known to be false.** A test was written asserting
that the frozen control arm's drive does not drift. The replication then found
it drifting significantly in **one seed out of five** — about what a 5% threshold
buys you. The test now asserts the control's *mechanical* guarantee (every
synaptic write was refused, so it cannot have learned) rather than a statistical
outcome that is only usually true.

**A regression that was not one.** A full-suite run reported
`test_transparency.py::test_regulator_wiring_keeps_both_directions` failing. That
test calls `inspect.getsource(BrainWidget.apply_weight_change)` — which resolves
to `src/neural_provenance.py`, a file being edited *while the suite ran*.
`linecache` handed it stale line offsets and it extracted the wrong block of
text. A clean run passed. **Do not edit source files while a test suite is
running**, particularly in a codebase whose tests assert on source text.
