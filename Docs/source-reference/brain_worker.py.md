_Not to be confused with [brain_render_worker.py](../source-reference/brain_render_worker.py.md)_

#### brain_worker.py
A background QThread dedicated to handling computationally expensive brain logic that would otherwise block the UI. It operates on cached snapshots of brain state, processes tasks from a thread-safe queue, and emits results back to the main thread via signals. This separation keeps the simulation responsive even during complex Hebbian learning calculations or neurogenesis evaluations.

#### Task Queue System:

* Uses thread-safe `Queue` for task dispatch
* Processes three task types: [`neurogenesis`](../neural-network/Neurogenesis.md), [`hebbian`](../neural-network/Hebbian-Learning.md), `state_update`
* Supports pause/resume for game state changes

#### Neurogenesis Checks:

* Evaluates stress/novelty/reward triggers against configurable thresholds
* Emits `neurogenesis_result` signal with creation recommendations
* Handles emergency stress neuron creation when anxiety exceeds 90

#### Hebbian Learning:

* Selects top-k neuron pairs based on co-activation scores
* Includes anti-loop mechanisms (randomization, cooldown penalties on recently-used pairs)
* Can create new connections between previously unconnected co-active neurons
* Emits weight updates back to main thread for application

#### State Decay Processing:

* Applies temporal decay toward baseline for non-input neurons
* Adds small random noise for organic feel
* Propagates connection effects through the network