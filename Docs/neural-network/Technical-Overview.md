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

---

## 1. Architecture

The network starts with 7 core drive neurons plus the mandatory `can_see_food`
sensor:

* **Basic needs**: `hunger`, `happiness`, `cleanliness`, `sleepiness`
* **Complex states**: `satisfaction`, `anxiety`, `curiosity`

Activations run 0–100 with **50 as the neutral baseline**, so a silent input
contributes nothing and a negative weight is genuinely inhibitory. Weights run
−1 … +1.

Three roles decide what may write a neuron (`src/brain_constants.py`):

| Role | Written by | May a synapse point at it? |
|------|-----------|----------------------------|
| **Pure input** (sensors) | the world, via `BrainNeuronHooks` | No — the world overwrites it every tick, so the synapse would be inert |
| **Core drive** | the squid model | Yes — via modulation (see §4) |
| **Network-driven** (grown, Designer, connector) | forward propagation | Yes |

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
weight change and every neuron birth goes through one recorded write path, and
the inspection tools read that record rather than reconstructing an
approximation of it:

```python
brain_widget.explain_weight(("can_see_food", "satisfaction"))
brain_widget.explain_neuron("anxiety_reduction")
brain_widget.what_do_you_know("food")
```

The same data drives **Brain Tool → Knowledge**, the **Learning** tab and the
**Neuron Laboratory**, and it is saved with the squid — so a save file really is
a cognitive history.
