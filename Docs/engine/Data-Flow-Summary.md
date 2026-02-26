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
| [**BrainWorker**](../source-reference/brain_worker.py.md) | Hebbian learning, Neurogenesis | Signals → BrainWidget |
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

2. **Processing Stage**
   - [`BrainWidget`](../source-reference/brain_widget.py.md) updates state dictionary
   - [`BrainWorker`](../source-reference/brain_worker.py.md) performs Hebbian learning (weight updates)
   - [`BrainWorker`](../source-reference/brain_worker.py.md) checks [neurogenesis](../neural-network/Neurogenesis.md) triggers

3. **Output Stage**
   - [`NeuronOutputMonitor`](../source-reference/brain_neuron_outputs.py.md) checks activation thresholds
   - Fires output hooks → game behaviours
   - Actions: `flee`, `seek_food`, `sleep`, `change_colour`, etc.

4. **Rendering Stage**
   - [`BrainRenderWorker`](../source-reference/brain_render_worker.py.md) receives state snapshot
   - Renders to offscreen QImage
   - Main thread blits cached image
