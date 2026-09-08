#### brain_neuron_outputs.py
**output system** that bridges neuron activations to game behaviours (bindings)

When neurons fire above configurable thresholds, this system triggers corresponding game actions (hooks) like fleeing, seeking food, or changing colour. It completes the sensorimotor loop—inputs flow in through hooks, propagate through the network, and outputs emerge here to drive the squid's behaviour.

#### NeuronOutputBinding Dataclass:

* Binds a neuron to an output hook with threshold, trigger mode, and cooldown
* Trigger modes: `THRESHOLD_RISING`, `THRESHOLD_FALLING`, `THRESHOLD_ABOVE`, `THRESHOLD_BELOW`, `ON_CHANGE`
Serializable to/from dict for save/load support

#### Standard Output Hooks:

* Movement: `flee`, `seek_food`, `seek_plant`, `approach_rock`, `wander`
* Actions: `throw_rock`, `pick_up_rock`, `ink_cloud`, `eat`, `change_color`
* State Changes: `sleep`, `wake`, `startle`, `calm`
* Stat Modifications: `boost_happiness`, `boost_curiosity`, `reduce_anxiety`

#### NeuronOutputMonitor Class:

* `monitor(activations)` — checks all bindings against current values, fires those meeting conditions
* Respects cooldown timers to prevent rapid-fire triggering
* Integrates with plugin system's hook dispatcher
* Includes floating `NeuronLogWindow` for debugging fired outputs