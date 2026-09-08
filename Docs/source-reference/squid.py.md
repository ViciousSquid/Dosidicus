`squid.py` file defines the Squid class, integrating various functionalities to simulate a living creature. It handles its own visual rendering and animation, calculates its movement, makes decisions based on its internal states and personality, and interacts with objects like food and decorations.

#### Core Responsibilities:

* **Physical Simulation**: Handles movement, animation frames, collision with boundaries, and "Inking" behaviors.
* **Internal State**: Tracks "Needs" (Hunger, Happiness, etc.) and "Goal Neurons" (Satisfaction, Anxiety, Curiosity).
* **Interaction Engine**: Manages picking up/throwing rocks, eating food, and reacting to other squids in a multiplayer environment.
* **Perception**: Acts as the primary interface for the VisionWorker, translating raw geometric vision data into behavioral triggers.

#### Key Functions:

* `update_view_direction()` - Makes the squid "scan" the tank; includes a "Hunger Bias" that forces it to look toward food.
* `eat()` - Processes food consumption, applies stat changes, and starts the "Poop Timer".
* `check_boundary_exit()` - Detects if the squid has swum off-screen to transition to a neighbour's tank in multiplayer mode.
* `startle_awake()` - Handles the logic for a rude awakening, including anxiety spikes and potential ink cloud creation.

#### Key internal objects:
* `self.mental_state_manager` – boolean flags + cooldowns
* `self.memory_manager` – short-term & long-term memory lists
* `self._decision_engine` – Q-learning / weight-based action picker
* `self.statistics` – personal lifetime counters (age, food eaten, rocks thrown…)