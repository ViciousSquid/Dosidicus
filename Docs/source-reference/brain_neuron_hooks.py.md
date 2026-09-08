#### brain_neuron_hooks.py
The **sensory input** system that bridges game events to neuron activations. It maintains a registry of handler functions that calculate activation values for input neurons based on the current game state. This is where environmental awareness enters the neural network—when the squid sees food, gets startled, or detects a nearby plant, these hooks translate those game conditions into numerical activations that propagate through the network.

#### Handler Registry:

* Maps neuron names to calculation functions
* Built-in handlers for: `external_stimulus`, `can_see_food`, `plant_proximity`, `threat_level`, `is_eating`, `is_sleeping`, `is_fleeing`, `is_startled`, `pursuing_food`, `is_sick`

#### Plugin Integration:

* `register_handler(name, callable)` — allows plugins to add custom input neurons
* `unregister_handler(name)` — removes custom handlers (built-ins protected)
* Merges plugin handlers with built-in ones at runtime

#### Event Tracking:

* Maintains `event_tracker` dictionary for temporal calculations
* Tracks window resizes, object spawns, user interactions with decay over time
* `update_decay()` — decays event intensities each simulation tick

#### Key Method:

* `get_input_neuron_values()` — returns current activation values for all registered input sensors