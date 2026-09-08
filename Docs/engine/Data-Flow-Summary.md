## Data Flow Summary

### [Main Loop](../source-reference/main.py.md)

**Game Loop** → [`TamagotchiLogic`](../source-reference/tamagotchi_logic.py.md) feeds stats → `BrainWidget.update_brain_state()`

---

### Central Hub: [BrainWidget](../source-reference/brain_widget.py.md)

| Component | Description |
|-----------|-------------|
| `state` dict | Neuron activations |
| `weights` dict | Connection strengths |
| Coordinates | All subsystems |

---

### Worker Threads

| Worker | Responsibility | Output |
|--------|----------------|--------|
| [**BrainWorker**](../source-reference/brain_worker.py.md) | Retired for learning and growth — both now run on the main thread, where the state they read is authoritative | Health-check signals only |
| [**BrainRenderWorker**](../source-reference/brain_render_worker.py.md) | Offscreen painting | QImage → paintEvent |
| [**NeuronOutputMonitor**](../source-reference/brain_neuron_outputs.py.md) | Threshold checks | Hooks → Squid behaviors |

---

### Signal Flow
```
BrainWorker ──────────┐
                      │
                      ▼
                 BrainWidget ──────▶ Squid
                      ▲
                      │
BrainRenderWorker ────┘
```

---

### Complete Pipeline

1. **Input Stage**
   - [`BrainNeuronHooks`](../source-reference/brain_neuron_hooks.py.md) converts game events → neuron activations
   - Sensors: `can_see_food`, `plant_proximity`, `is_fleeing`, etc.

2. **Processing Stage**, in this order — the order matters
   - [`BrainWidget`](../source-reference/brain_widget.py.md) updates state dictionary
   - `drive_external_neurons()` writes the neurons the world owns: sensors, and
     the neurons that stand for what the squid is currently doing
   - `propagate_activations()` steps the network through `src/propagation.py`,
     the project's single transfer function
   - **then** the learning mechanisms observe: `PlasticityEngine.observe()`
     accumulates evidence every tick (`perform_hebbian_learning()` commits it
     on the cycle), and `CapabilityMonitor.observe()` and
     `ActionOutcomeLedger.on_tick()` run off the same, now fully-updated state
   - `check_neurogenesis_triggers()` asks the capability monitor what the
     network persistently cannot do

   > Evidence is gathered **after** the forward pass. Observing first paired
   > each tick's world with the *previous* tick's network, which inverted what
   > the capability monitor measures: a detector wired +0.9 from
   > `can_see_food` was recorded at its no-food value on exactly the ticks food
   > was visible, and the monitor concluded it was a detector for the *absence*
   > of food. Fixed in v5.0; that reading went from −0.51 to +1.75.

3. **Output Stage**
   - The **action neurons** compete: each is driven by propagation and inhibits
     its rivals, so behaviour is whatever survives that
     (see [Decision Engine](Decision-Engine.md))
   - [`NeuronOutputMonitor`](../source-reference/brain_neuron_outputs.py.md)
     checks each action neuron against its own firing threshold — the same
     threshold the decision engine ranks by — and rolls the reflex's
     probability where it has one (the ink cloud fires about a third of the
     time it is triggered)
   - Fires output hooks → game behaviours
   - Actions: `flee`, `seek_food`, `sleep`, `change_colour`, etc.

4. **Rendering Stage**
   - [`BrainRenderWorker`](../source-reference/brain_render_worker.py.md) receives state snapshot
   - Renders to offscreen QImage
   - Main thread blits cached image
