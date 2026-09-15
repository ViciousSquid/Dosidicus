# 05 — Limitations

What this experiment does **not** show, and what would change the conclusion.

---

## On the null (cup choice)

**It is a limitation of this architecture, not of neural networks, or of squid,
or of learning.** The scope of the claim is: *this* input space and *this* output
space cannot represent which of three cups holds the food. Anything beyond that
is not supported by these data.

**It is not a failure of training.** No amount of further training would change
it, because it is a statement about what the network can represent rather than
about the values of its weights. Running more trials would be a waste.

**The task was solvable in principle.** The bait is visible during the shuffle,
so a system that could track the cup would score above chance. The null is about
the squid, not about an impossible task.

**A ceiling this experiment cannot rule out.** The squid also never *approaches*
better than chance, so the null covers the whole
perception → representation → action chain at once. It does not separate "cannot
represent the location" from "cannot act on a representation it has". The audit
argues both fail, but the experiment tests them jointly.

**What would falsify it:** the learning arm's frozen evaluation beating the
frozen control by a margin that replicates across seeds. The test suite has a
tripwire for this and points at the documented finding, so a future change that
makes the task learnable will show up as a test failure rather than going
unnoticed.

## On the positive result (drive under occlusion)

This is the weaker of the two findings and should be cited with care.

**It is statistically strong pooled and highly variable per seed.** See the
per-seed columns in [`03-results.md`](03-results.md). Three of ten seeds show
essentially nothing (−1, −0 and +4 points), and the two replications' pooled
estimates differ by a factor of nearly three (+7 pp and +19 pp). The pooled estimate is the result; no individual run is.

**Part of the rise is the protocol, not learning.** The frozen control's own
drive also rises from its no-information baseline. A squid that spends bait and
shuffle phases looking at food is in a different state from one that never saw
any. This is exactly why the headline is learning-arm-vs-control (both get the
same protocol) rather than eval-vs-baseline — but it means the *absolute* rise
overstates the learning component.

**The control arm's drive drifted significantly in one seed of the first five.**
About what a 5% threshold buys you, and a reason to treat single-seed drive
results — in either direction — as uninformative.

**"Follow the food" is a generous reading.** What is measured is that
food-seeking drive survives occlusion better after training. That is persistence
of an appetitive state, not memory of a location, and it should not be described
as the squid remembering where the food went.

**Not traced to specific synapses.** The provenance ledger records every weight
change and the trials carry the deltas, but no analysis identifies *which*
pathway carries the effect. "Plasticity did it, and here is the ledger" is
established; "this synapse did it" is not.

## On the apparatus

**The body is a model.** Vision, decisions, learning and reward are the shipping
code, but the headless body is modelled on `Squid.move_squid` rather than being
it. Boundary handling, speed multipliers and the drive-priority system are
simplified. The game-side tests cover the real path for the claims that depend
on it (hiding, revealing, eating, no leakage), but the *statistics* come from the
modelled body.

**Omission rates are high** — 28–45% of trials, higher in the no-information arm
where nothing draws the squid towards the cups. Omissions are shown to be
unrelated to the answer, so the scoring is sound, but a third of the data is
being dropped and a more engaged animal would give tighter intervals.

**Husbandry is a designed part of the protocol**, and different husbandry could
give different drive numbers — the measure is sensitive to hunger, which is what
maintenance feeding controls. The cup-choice null is not sensitive to this.

**Results are reported with neurogenesis off** (`--no-growth`). With growth on
the architecture still works and the cup null is unchanged, but emergency
neurogenesis under stress adds neurons wired at ±0.8 into everything, which
dominates the drive measure. That is a real property of the architecture, not
noise to be discarded — it is simply not what these runs were measuring.

**One retention interval.** 20 ticks, chosen so a trial cannot be won by
coasting. `--delay` varies it, but no systematic sweep was run, so "accuracy as
a function of retention interval" is unmeasured.

**Three cups, one geometry, one personality distribution.** No variation in cup
count, spacing, or squid personality was tested.

## Not verified

**The game UI was never watched on a real display.** It was driven end to end
headlessly — menu action, trial, hide, reveal, eat — and twelve tests cover the
behaviour. The *visuals* (cup rendering, lift animation, ghost marker) are
unconfirmed by eye.

## Worth doing next

- A retention-interval sweep — the cleanest demonstration that any apparent
  competence is proximity rather than memory.
- Trace the drive effect to specific synapses through the provenance ledger.
- Run the statistics through the game-side body to check the modelled body is
  not carrying the result.
- More seeds on the drive measure; ten is thin for an effect this variable.
