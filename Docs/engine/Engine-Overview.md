## `S`imulated `T`amagotchi `R`eactions via `I`nferencing and `N`eurogenesis `(STRINg)`

🧠 Read the [Cognitive Sandbox Manifesto](https://github.com/ViciousSquid/Dosidicus/wiki/Cognitive-Sandbox-Manifesto-%7C-Artificial-Life-and-Transparent-Neural-Systems): On Artificial Life and Transparent Neural Systems

## Simulation engine overview:

The architecture of Dosidicus is a "Bottom-Up" sensory system where raw environmental data is distilled into neural inputs, which are then filtered through the squid's [personality](https://github.com/ViciousSquid/Dosidicus/wiki/Personality) to produce behavior.

**brains**: small neural networks ([custom **json** format](https://github.com/ViciousSquid/Dosidicus/tree/2.6.1.2_tattoo/headless#brain-json-format)) with **applied inputs**, **learning**, **memories** and **neuron growth**.  

* Default networks are [biologically-inspired](https://github.com/ViciousSquid/Dosidicus/wiki/Brain-Designer#generate-sparse-network) semi-random single layers with **8 core neurons**

### * **No Tensorflow, No Pytorch**
* Rejects the standard "black box" approach in favour of transparent, biologically inspired learning.
* [decision engine](https://github.com/ViciousSquid/Dosidicus/wiki/Decision-Engine) is **entirely neural network driven**

---------------------


### 1. Brain Data Structure (NumPy core)
Every squid brain is stored as:

* `neurons`: `np.ndarray` shape `(n_neurons,)` — activation values (float32, clamped 0–1)
* `weights`: `np.ndarray` shape `(n_neurons, n_neurons)` — connection strengths (float32)
* `thresholds`: `np.ndarray` shape `(n_neurons,)` — firing threshold per neuron
* `types`: `np.ndarray` shape `(n_neurons,)` — sensor / hidden / motor flags (int8)

Starts with exactly 8 randomly wired neurons (sparse connectivity via `np.random.rand() < density`).

All of this is saved/loaded via custom JSON + NumPy `save/load` for the arrays.

### 2. Forward pass (inference) — pure NumPy vectorized

```Python
# Inside the step() loop
inputs = sensory_vector  # e.g. hunger, touch, visual, etc. (also np.array)
net_input = np.dot(weights.T, neurons) + inputs
activations = np.tanh(net_input - thresholds)   # or sigmoid / ReLU
neurons = np.clip(activations, 0.0, 1.0)
```

#### One matrix multiply + one vectorized non-linearity → the entire mind “thinks” in <1 µs.

### 3. Hebbian learning (the rewiring)
After every step (or every few steps):

```python
# Classic Hebbian + decay
delta_w = learning_rate * np.outer(neurons, neurons)   # Hebb’s rule: “cells that fire together wire together”
weights += delta_w
weights *= decay_factor                            # forget unused connections
np.clip(weights, -1.0, 1.0, out=weights)           # bound
```

This is the entire plasticity rule. No backprop, no gradients — just outer product (pure NumPy, blazing fast).

### 4. Neurogenesis (structural growth)
When a neuron’s “growth pressure” (accumulated activity + dopamine-like signal) exceeds threshold:

```python
new_neuron_count = 1
new_size = neurons.shape[0] + new_neuron_count

# Grow every matrix in one go
neurons = np.pad(neurons, (0, new_neuron_count), mode='constant')
thresholds = np.pad(thresholds, (0, new_neuron_count), constant_values=default_threshold)
weights = np.pad(weights, ((0, new_neuron_count), (0, new_neuron_count)), mode='constant')
```

Random weak connections are added to the new row/column. This is why your squids literally get “bigger brains” over time and why every save file is a unique cognitive history.

### 5. Dual memory system

* Short-term: rolling buffer of last N activations (`np.array` deque-like)
* Long-term: periodic consolidation into weights + a separate episodic memory array (experience buffer) that can be replayed for offline Hebbian updates.


-----------------------------------------

## Read Next: [Data flow Summary](https://github.com/ViciousSquid/Dosidicus/wiki/Data-Flow-Summary) overview

#### Further engine studies:

- [Decision Engine](https://github.com/ViciousSquid/Dosidicus/wiki/Decision-Engine)
- [Brain Widget](https://github.com/ViciousSquid/Dosidicus/wiki/brain_widget.py)
