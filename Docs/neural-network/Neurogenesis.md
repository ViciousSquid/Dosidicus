# Neurogenesis — capability-driven structural plasticity

`capability.py` decides **whether** the brain needs new structure.
`neurogenesis.py` decides **what** to grow and **how to wire it**.

## The change in v4.0

Neurogenesis used to be event-driven:

> Anxiety crossed 75, therefore grow a stress neuron.
> Curiosity crossed 70, therefore grow a novelty neuron.

That is growth as a reflex. It says nothing about whether the network needed
the neuron. A squid living a busy life grew structure it had no use for, while
a squid with a real, persistent problem grew none — and the same event was
being watched by four separate copies of the thresholds (the widget, the
worker, `HebbianLearning`, and the headless trainer), so which of them fired
first decided what the squid became.

The model now is:

> The existing network cannot usefully represent, respond to or express X, and
> that failure has persisted, so it develops structure capable of doing so.

A neuron appears because of a **persistent functional deficiency**, never
because a particular event occurred.

---

## The five deficits

`CapabilityMonitor` observes the live network every tick and re-diagnoses it on
the neurogenesis timer. Every measurement comes from the network's own state —
none of them is an event counter.

| Deficit | What is measured | What is grown |
|---------|------------------|---------------|
| **representation** | A recurring situation signature. For every neuron, the separation between its activation when the situation holds and when it does not (Cohen's *d* over streaming statistics). If **no** neuron separates the two, the brain literally cannot tell the situation apart. | A neuron wired from the sensors that define the situation, so it and nothing else fires for it. |
| **regulation** | A drive outside its comfort band for a sustained fraction of the last 240 ticks, while the corrective synaptic push into that drive is absent, below `MIN_CORRECTIVE_PUSH`, or already at the clamp. | A regulator: driven *by* the drive (and whatever predicts it), pushing back *on* it. |
| **expression** | A cue → action → outcome contingency `ActionOutcomeLedger` is confident about, with no synaptic path from the cue to the outcome of the right sign. The brain knows something it has no structure to act on. | A relay: cue → new neuron → outcome, signed by the measured effect. |
| **differentiation** | One neuron driven by two sources whose long-run correlation is strongly negative. It is being asked to stand for two incompatible situations at once, so it represents neither. | A second neuron that takes one of the two drivers over, and inherits its synapse onto the shared target. |
| **connectivity** | A neuron with no working connections. Nothing it computes can reach the rest of the brain. | A connector that bridges it back into the network. |

Comfort bands live in `capability.COMFORT_BANDS` and cover exactly the seven
core drives.

## Persistence: a deficit has to earn its neuron

A diagnosis alone is not enough. `CapabilityMonitor.actionable()` requires all
of:

* `observations >= min_observations` (default 3 separate evaluations),
* `age >= min_age` (default 20 s),
* `severity >= min_severity` (default 0.35), and
* **unresolved** — the severity has not been falling. A deficit that ordinary
  plasticity, consolidation or causal learning is already shrinking does not
  need new structure; the network is handling it, just slowly.

`EnhancedNeurogenesis._growth_blocked()` then applies the pacing rules: the
brain must have been alive for 5 s, must be under `max_neurons`, and must be
past the growth cooldown. A maximum-severity (acute) deficit may grow sooner
than the full cooldown but never instantly — there is a floor of
`max(10 s, cooldown / 4)`, so a squid with several pinned drives cannot burst
out a handful of neurons in one second.

Growth pacing reads the clock through `EnhancedNeurogenesis.clock`. The game
uses wall clock; the headless trainer substitutes simulated seconds, so the
cooldowns mean what they say when 1 500 ticks run per real second.

## Standing down

When a type cap is reached the engine deepens what already exists instead of
duplicating it: `strength_multiplier` rises by 0.5 per stand-down, capped at
`MAX_STRENGTH_MULTIPLIER` (4.0). Standing down is paced like growth, so a
capped type does not strengthen on every evaluation.

Every stand-down is recorded and shown in **Brain Tool → Knowledge → What it
can't do yet**, together with the reason.

---

## What is grown

`_create_neuron_internal()` is the only place in the project that creates a
neuron. Given a `Deficit` it:

1. maps the deficit onto one of the four structural families (`stress`,
   `novelty`, `reward`, `connector`) and one of the existing specialisations,
   so caps, colours, shapes, the Laboratory and the achievements all keep
   working;
2. chooses a name — `type_specialisation`, or an evocative one drawn from a
   pool **keyed by specialisation** when `[Neurogenesis] showmanship = True`.
   The name is chosen once, at birth. (Until v4.0 a wrapper class renamed the
   neuron *after* creation and had to migrate a dozen dictionaries to do it;
   it was also constructed and then immediately discarded, so the documented
   `showmanship` option did nothing at all.)
3. merges the **specialisation wiring** (what a neuron of this kind always
   does) with the **remedy wiring** (what this specific deficit needs) before
   writing anything, so each synapse is created once with its final value;
4. adds reciprocal links so the neuron can be driven as well as drive;
5. writes a **birth record** to the provenance ledger.

Wiring is directional and stays that way. A regulator is
`drive → regulator` excitatory **and** `regulator → drive` inhibitory; those
are two different synapses and the write path will not collapse them.

## Why does this neuron exist?

Every grown neuron carries its originating deficit, in
`FunctionalNeuron.origin_deficit` and in `CausalLedger.origins`, and both
survive save/load. Ask any of:

```python
brain_widget.explain_neuron("anxiety_reduction")
```

*Brain Tool → Knowledge → Why does this neuron exist?*

*Neuron Laboratory → double-click a neuron → “Why does this neuron exist?”*

A typical answer:

> Stress: Anxiety Regulation was grown 4 min ago because the brain could not
> pull this feeling back to a comfortable level.
> Specifically: anxiety has been outside its comfortable range for 78% of the
> last 240 ticks (currently 87), and the 1 synapse(s) that push it that way are
> already at full strength and it is still not enough.
> It was wired to pull anxiety down whenever the situations that drive it appear.
> Connections made at birth: anxiety → anxiety reduction at +0.80,
> anxiety reduction → anxiety at −0.90, …

## Pruning

`intelligent_pruning()` removes the lowest-utility neuron older than 5 minutes,
scoring on utility, activation recency, uniqueness of specialisation and total
synaptic weight. Connectors are immune. The loss is recorded in the ledger with
its reason, so a pruned neuron can still be accounted for.

## Persistence

`to_dict()` / `from_dict()` serialise every `FunctionalNeuron` (including its
originating deficit), the `ExperienceBuffer`, and the counters.
`CapabilityMonitor` serialises its streaming statistics and its live deficits
alongside them, so a loaded squid resumes its diagnosis rather than starting it
over. `ensure_all_neurons_functional()` converts legacy neurons on load, and
`SquidBrainWindow._backfill_neuron_origins()` gives a pre-v4.0 brain the best
birth record that can honestly be reconstructed — without ever overwriting a
real one.
