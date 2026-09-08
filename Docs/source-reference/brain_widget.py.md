### brain_widget.py
This is the main neural network visualization and coordination hub. It serves as the central controller that owns the authoritative brain state, coordinates background worker threads, and integrates all the subsystems that make the neural network function. Everything flows through this widget—stat updates from the game, rendering requests, learning signals, and neurogenesis events all converge here before being dispatched to the appropriate handlers.

#### Core State Management:

* Maintains the authoritative `state` dictionary with all neuron activations (hunger, happiness, anxiety, etc.)
* Manages `weights` dictionary for connection strengths between neurons
* Tracks `neuron_positions` for [visualization](../brain-tool/Network-Tab.md) layout

#### Worker Coordination:

* Receives an external [`BrainWorker`](../source-reference/brain_worker.py.md) via `set_brain_worker()` (avoids duplicate thread creation)
* Owns a [`BrainRenderWorker`](../source-reference/brain_render_worker.py.md) for offscreen rendering
* Coordinates signal/slot connections between workers and UI

#### Subsystems Integrated:

* [`EnhancedNeurogenesis`](../neural-network/Neurogenesis.md) for dynamic neuron creation
* [`ExperienceBuffer`](../neural-network/Experience-Buffer.md) for tracking learning experiences
* `EnhancedBrainTooltips` for hover information
* Theming with animation styles (Vibrant, Subtle, etc.)
* Brain state bridge for [designer](../brain-tool/Brain-Designer.md) synchronization

#### Key Methods:

* `update_brain_state(stats_dict)` — main entry point for stat updates from the game
* `set_brain_worker()` — accepts external [worker](../source-reference/brain_worker.py.md) instance
* `export_brain_state_for_designer()` — syncs state with the Brain Designer tool