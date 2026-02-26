View source: [tamagotchi_logic.py](https://github.com/ViciousSquid/Dosidicus/blob/2.6.1.2_LatestVersion/src/tamagotchi_logic.py) version 2.6.1.2

A **god-object** serving as the central game logic controller. Its primary purpose is to manage the core simulation loop, handle the squid's behaviour and needs, facilitate interactions with the environment, and integrate various game systems, including the neural network, memory, and save/load functionalities.


#### Responsibilities
* Owns the live pet simulation loop (`hunger`, `happiness`, `sickness`, `sleep`, etc.).
* Spawns and manages world objects: food, poop, decorations, rocks.
* Runs every-frame update (movement, collisions, timers, cooldowns).
* Handles user actions: feed, clean, medicine, speed changes, window resize.
* Coordinates save / load of the entire game state (squid, memories, decorations, brain).
* Hosts the [plugin](../engine/Plugin-System.md) system (achievements, multiplayer, etc.) and fires hooks.
* Owns statistics & scoring (distance swam, food eaten, startles, ink clouds…).
* Bridges pet ← → brain:
1. – copies squid stats into the neural network so the network mirrors the pet.
2. – reads learned weights back from the network to influence future decisions.


#### Key internal objects
* `self.squid` – the pet instance ([squid.py](../source-reference/squid.py.md))
* `self.brain_window` – the debug UI ([brain_tool.py](../source-reference/brain_tool.py.md))
* `self.food_items` / `poop_items` / `rock_items` – lists of QGraphicsItems
* `self.neurogenesis_triggers` – counters that tell the brain when to grow new neurons
* `self.plugin_manager` – loads & runs plugins (multiplayer, achievements, …)


----------------------------------

* `TamagotchiLogic.__init__()` constructs the Squid and keeps a reference.
* Squid receives a back-reference (`self.tamagotchi_logic`) so it can:
1. – ask for nearby decorations / food
2. – tell the logic when it threw a rock (for RL reward)
3. – trigger plugin hooks

#### Data flow every frame:
* `TamagotchiLogic.update_simulation`()
* → calls `squid.move_squid`()
* → copies `squid.hunger` / `happiness` / `anxiety` … into a dict
* → sends dict to `brain_window.update_brain`() (neural network)
* Neural network learns, may create new neurons, returns updated weights.
* `TamagotchiLogic` reads those weights and/or calls `squid.make_decision`() which uses them.
* Save / load
* `TamagotchiLogic.save_game`() asks `squid.save_state`() for the pet slice, then bundles it with brain data, memories, decorations, achievements.
On load the reverse happens; afterwards `sync_state_from_squid`() is called so the squid remains the single source of truth for core stats.

#### Plugin hooks:
Any time a Squid property changes (via its setters) it fires tamagotchi_logic.plugin_manager.trigger_hook("on_hunger_change", …)
so plugins (achievements, multiplayer, etc.) can react.