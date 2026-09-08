#### Responsibilities

* Builds the multi-tab window (Network, Learning, Memory, Decisions, Statistics, …).
* Hosts the [BrainWidget](../source-reference/brain_widget.py.md) in the “Network” tab.
* Exposes buttons, sliders, tables to stimulate neurons, export data, change learning rate, force a learning cycle, etc.
* Persists / loads the whole brain state (weights, positions, neurogenesis history) to JSON.
* Owns the [BrainWorker](../source-reference/brain_worker.py.md) thread instance (wraps the one inside BrainWidget) and restarts it if it crashes.
* Bridges between the squid logic ([tamagotchi_logic](../source-reference/tamagotchi_logic.py.md)) and the brain widget:


 – every few seconds it copies the squid’s current `hunger`, `happiness`, `anxiety`… into the widget’s state so the network mirrors the squid.

 – when the network learns new weights, the squid can query them for [decision-making](../engine/Decision-Engine.md).



#### Key internal objects

* `self.brain_widget` – canvas widget ([brain_widget.py](../source-reference/brain_widget.py.md))
* `self.tabs` – QTabWidget with all the inspector tabs
* `self.config_manager` – central place for thresholds, intervals, colours, etc.
* `self.tamagotchi_logic` – reference to the actual pet simulation (runs in the main game loop)