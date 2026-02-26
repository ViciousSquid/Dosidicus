#### designer_window.py
This is the primary application shell for the neural network Designer.

#### Core Responsibilities:
* **Application Orchestration**: Manages the main window, menus, toolbars, and the splitter layout containing the canvas and property panels.
* **State Management**: Holds the active `BrainDesign` instance and coordinates "Undo/Redo" style refreshes across all sub-panels.
* **Live Game Bridge**: If the game is running, it allows the user to "Sync from Game" (import the current brain) or "Push to Game" (export the design to the live squid).
* **Network Generation**: Provides entry points for "Chaos Mode" or preset-based automated network generation using the `SparseNetworkGenerator`.

#### Key Functions:

* `setup_ui()` - Initializes the `BrainCanvas` and the vertical tabbed panels (Layers, Sensors, Properties, Connections, Outputs).
* `push_to_game()` - Converts the visual design into a format the game understands and sends it via the `brain_state_bridge`.
* `instant_random_generate()` - Triggers an instant "Chaos" shuffle of neuron positions and randomizes connections.
* `load_from_brain_widget_state()` - Allows the editor to be opened mid-game by importing the current state of the squid's brain.

#### Key internal objects:
`ScrollingTicker`: A specialized UI widget that scrolls rich-text help messages and shortcuts.
`BrainDesignerWindow`: The `QMainWindow` class that coordinates the canvas, side panels, and the bridge to the live game.