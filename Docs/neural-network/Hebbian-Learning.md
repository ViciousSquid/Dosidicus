# Synaptic plasticity

Dosidicus does not use backpropagation. It learns with a biologically-inspired
correlation rule, blended with spike-timing, modulated by outcome — a
three-factor rule. There is exactly one implementation of it,
[`src/plasticity.py`](../../src/plasticity.py), committed by
`BrainWidget.perform_hebbian_learning()`. The headless trainer calls the same
engine.

---

## 1. Evidence is accumulated every tick

`PlasticityEngine.observe()` runs once per simulation tick from
`propagate_activations()`. It accumulates running sums for a true covariance
over the window, and feeds the same tick to the spike tracker.

This matters because the squid learns on two timescales that a snapshot cannot
bridge: drives take 30–60 s to move ten points, while event neurons
(`can_see_food`, `is_eating`, `is_startled`) flip in a single tick and are on
for roughly 2 % of the time. A sampler that looked at the network once every
30 s caught **none** of the ticks where `can_see_food` was on, so the neurons
carrying what actually happened to the squid were structurally excluded from
learning.

The commit interval (`[Hebbian] learning_interval`, default 20 s) is therefore
a pacing choice, not a correctness one.

## 2. The rule

For each committed pair:

```
Δw  =  lr · r(a₁, a₂)                     (Hebbian term)
Δw  =  (1−β)·Δw_hebb + β·Δw_stdp·lr       (when spike timing has an opinion)
w'  =  clamp(w + Δw − w·decay,  −1, +1)
```

* **`r` is the Pearson correlation** between the two neurons over the window,
  against each neuron's own mean rather than a fixed midpoint. Pairs that vary
  together strengthen; pairs that vary oppositely go **negative**; unrelated
  pairs decay to zero instead of saturating. A neuron held at a constant has no
  variance and therefore teaches nothing, which is correct — you cannot learn
  from an invariant.
* **Weights are signed.** An avoidance behaviour ("why is yours afraid of
  poop?") *is* an inhibitory synapse. The old rule used `lr · a₁ · a₂`, which
  is never negative, so no amount of experience could produce one.
* **With `base_learning_rate == weight_decay`** a synapse converges to exactly
  the correlation between its endpoints, which makes every weight in the
  network readable as a statement about the squid's experience.
* **New neurons learn faster** while they bed in
  (`new_neuron_lr_multiplier`, default 2.0).

Spike timing is blended **only where it has an opinion**. STDP is silent for
most pairs on most cycles, and averaging its zero in regardless would drag every
estimate toward the middle and break the convergence property above.

## 3. Direction

A sensor may be a learning **source** but never a **target**: the world
overwrites it every tick, so a synapse pointing into one is inert.
`PlasticityEngine.orient()` gives a new synapse a direction that can actually
do something — a network-driven neuron via propagation, or a core drive via
modulation — and skips the pair entirely if neither end qualifies.

An existing edge always keeps its direction.

## 4. Coverage

Pairs are ranked by the strength of the evidence, not by a snapshot, and the
engine commits `max(min_pairs_per_cycle, half the candidate pool)` of them per
cycle, capped at 64. A recently-committed pair is deprioritised but not exiled.
At the old fixed two pairs per cycle, a synapse in a 20-neuron brain updated
once every 47 minutes — the more the brain grew, the less each synapse learned.

## 5. Where else weights change

Plasticity is not the only mechanism, but it is the only *correlational* one.
The complete set, all of which write through `BrainWidget.apply_weight_change()`
and all of which are distinguishable in the ledger:

| Mechanism | What it means |
|-----------|---------------|
| `hebbian` | they kept happening together |
| `stdp` | one reliably fired just before the other |
| `causal_reward` | an action it took led to a result worth repeating |
| `consolidation` | it was replayed during sleep |
| `neurogenesis` | a new neuron was wired in |
| `reflex` | an innate reflex fired (eating, illness, cleaning, curiosity) |
| `designer` | you wired it by hand |
| `prune` | it never amounted to anything and was removed |

## 6. Configuration

`[Hebbian]` in `config.ini` is read by `LearningConfig` and converted by
`PlasticityConfig.from_learning_config()`. Every key in that section takes
effect.

## 7. Seeing it

The **Learning** tab shows each committed change as a card carrying the
mechanism, the measured correlation, the sample count and the LTP/LTD badge
when spike timing contributed — all read from the provenance ledger, which is
the record the mechanism itself wrote. It does not diff its own cached copy of
the weights, which is what it used to do and why it could never say *why*
anything changed.

The **Knowledge** tab turns the same record into plain English.
