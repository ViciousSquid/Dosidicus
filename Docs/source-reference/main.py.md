### The Simulation Loop (main.py)
The simulation loop is driven by a QTimer from the PyQt5 framework, which "ticks" at a consistent rate. Each tick represents one frame of the simulation.

The loop has two key responsibilities:

**State Update**: On each tick, it calls the `update_game_state()` method. This function is responsible for everything that changes over time without direct user input. This includes:

* Decrementing the squid's needs (hunger, cleanliness, etc.).

* Calling the neural network to get the squid's next autonomous action.

* Executing the squid's chosen action (e.g., moving, interacting with an object).

* Updating animations.

**Rendering**: After the state has been updated, the loop tells the GUI to repaint itself, ensuring that the user always sees the most current state of the simulation.