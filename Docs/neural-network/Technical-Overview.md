# Neural network technical overview

<img width="598" height="296" alt="image" src="https://github.com/user-attachments/assets/da9c7b03-9953-4892-9417-17d429d9a2fe" />

The network is a single-plane, sparsely-connected graph that grows through
capability-driven neurogenesis. There is no backpropagation and no training
phase; the squid learns while it lives.

Every neural mechanism has exactly one implementation, and every change any of
them makes is recorded with its reason.

| Mechanism | Lives in | Driven from |
|-----------|----------|-------------|
| Forward propagation | `src/propagation.py` | `BrainWidget.propagate_activations()`, once per tick |
| Synaptic plasticity (Hebbian + STDP) | `src/plasticity.py` | `BrainWidget.perform_hebbian_learning()`, on the commit cycle |
| Spike timing | `src/stdp.py` | `PlasticityEngine.observe()`, every tick |
| Action → consequence learning | `src/causal_learning.py` | `ActionOutcomeLedger.on_tick()`, every tick |
| Sleep consolidation | `src/consolidation.py`, `src/sleep_consolidation.py` | `ConsolidationManager.on_tick()`, every tick |
| Capability diagnosis | `src/capability.py` | `CapabilityMonitor.evaluate()`, on the neurogenesis timer |
| Structural growth | `src/neurogenesis.py` | `BrainWidget.check_neurogenesis_triggers()` |
| Provenance | `src/neural_provenance.py` | every one of the above |

The headless trainer imports the same modules, so a brain trained without the
GUI behaves identically inside it.

### One clock

Four of those mechanisms are paced in seconds: how long a deficit must persist,
how long an action's consequence is watched, how long after growing one neuron
another may be grown, and — most of all — how long ago a neuron fired. Each of
them reads a `clock` attribute that defaults to the wall clock and that the
headless trainer and the test harness replace with simulated seconds.

Without that, a trainer stepping 1 500 ticks per real second presented every
spike as arriving under a millisecond after the last, far inside any plausible
timing window, so STDP computed a delta of exactly zero for every synapse and a
brain trained without the GUI had no spike timing in it at all. The same clock
substitution is what makes the behavioural experiments in
`tests/test_organism.py` mean anything: a squid can live an hour in a tenth of
a second and every pacing rule still means what it says.

---

## 1. Architecture

The network starts with 7 core drive neurons plus the mandatory `can_see_food`
sensor:

* **Basic needs**: `hunger`, `happiness`, `cleanliness`, `sleepiness`
* **Complex states**: `satisfaction`, `anxiety`, `curiosity`

Activations run 0–100 and weights run −1 … +1. How much a neuron *contributes*
is its distance from **its own resting level**, which is not the same number
for every neuron: a drive rests at 50 and ranges ±50 either side of it, while a
sense organ rests at **zero** — "I cannot see any food" is a sensor with nothing
to report. `propagation.signal_of()` is the one place that distinction is made,
and everything that reads an activation as a contribution goes through it.

Subtracting 50 from a sensor made *not* seeing food a signal of −50: as loud as
seeing food and pointing the other way, so a squid born with
`can_see_food → happiness +0.5` was made actively unhappy by the absence of
food, every tick of its life.

Every squid hatches with the same instincts, listed once in
`brain_constants.INNATE_CONNECTIONS` and written through the recorded write
path with mechanism `innate`, so even a newborn brain can explain itself. The
game used to build one out of 40% random connections at random weights while
the headless trainer used a fixed table, which meant two squid of the same
species were born with different instincts and "the same squid, raised
differently" was not a comparison anyone could make.

Four roles decide what may write a neuron (`src/brain_constants.py`,
`src/propagation.py`):

| Role | Written by | May a synapse point at it? |
|------|-----------|----------------------------|
| **Pure input** (sensors) | the world, via `BrainNeuronHooks` | No — the world overwrites it every tick, so the synapse would be inert |
| **Core drive** | the squid model | Yes — via modulation (see §4) |
| **Network-driven** (grown, Designer, connector) | forward propagation | Yes |
| **Externally driven** (action representations) | what the squid is currently doing, via `ExternallyDriven.drive_external_neurons()` | No — same reason as a sensor |

## 2. Forward propagation

One timestep, for every network-driven neuron, from a single consistent
snapshot so all neurons step together:

```
target = 50 + Σ (activation[src] − 50) · weight · strength
new    = old + (target − old) · smoothing        clamped to 0 … 100
```

`strength` is the per-neuron multiplier a grown neuron accumulates when
neurogenesis deepens it instead of duplicating it (capped at 4.0).

## 3. Learning

See [Hebbian Learning](Hebbian-Learning.md) for the rule and
[STDP](STDP.md) for the spike-timing term. In summary:

* co-activation is accumulated **every tick** and committed on a cycle, so a
  one-second event is not invisible;
* the Hebbian term is a **signed correlation**, so aversions are learnable;
* spike timing is blended in where it has an opinion;
* an action's outcome is broadcast back along the **eligibility traces** laid
  down when the spikes happened — the third factor, and the squid's route from
  correlation to causation;
* sleep replays the day's strongest co-activations and prunes what never
  amounted to anything.

## 4. From synapse to behaviour

Propagation deliberately never overwrites a core drive — the squid model owns
those, and two writers would fight. But a brain that cannot touch its own
physiology cannot express what it learned, and a default eight-neuron brain
contains nothing *but* sensors and drives.

So learned synapses pointing at a drive act as a **modulation**:
`compute_neural_modulation()` sums `(source − 50)/100 · weight` per drive and
returns a small per-tick delta. A squid whose experience taught it
`can_see_food → anxiety` becomes anxious at the sight of food; one that learned
`can_see_food → happiness` brightens instead. Same stimulus, opposite response,
because they lived different lives.

Each synapse's contribution is recorded, which is how the Knowledge tab can say
how a learned association has actually affected behaviour rather than asserting
that it must have.

## 5. Structural growth

See [Neurogenesis](Neurogenesis.md). A neuron is grown when the network has a
**persistent functional deficiency** — something it cannot represent, regulate
or express — that ordinary learning has already failed to fix. Never because an
event occurred.

## 6. Stability and pruning

* **Connection pruning** removes synapses whose absolute weight stays below a
  threshold, with connectors and young neurons immune.
* **Sleep pruning and down-scaling** apply synaptic homeostasis: everything is
  scaled back overnight and only what was replayed comes out ahead.
* **Neuron pruning** removes the lowest-utility grown neuron when the network
  nears its ceiling, scoring on utility, recency, uniqueness of specialisation
  and total synaptic weight.

Every removal is recorded with its reason.

## 7. Transparency

Transparency is an architectural requirement, not a debugging feature. Every
weight change and every neuron birth goes through one recorded write path -
`neural_provenance.RecordedSynapses`, which the game's BrainWidget, the headless
trainer and every test double all inherit, so "record every change" cannot be
true in one and quietly false in another. The inspection tools read that record
rather than reconstructing an approximation of it:

```python
brain_widget.explain_weight(("can_see_food", "satisfaction"))
brain_widget.explain_neuron("anxiety_reduction")
brain_widget.what_do_you_know("food")
```

The same data drives **Brain Tool → Knowledge**, the **Learning** tab and the
**Neuron Laboratory**, and it is saved with the squid — so a save file really is
a cognitive history.
