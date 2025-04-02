# Technical Overview: Brain Window

This module implements a neural network visualization and interaction system for a digital pet squid using PyQt5. It provides a window into the squid's "brain" with visual representations of neurons, their connections, and learning processes.

## Core Components

### 1\. BrainWidget Class

The main visualization widget that displays the neural network and handles interactions.

### ` __init__(self) `

Initializes the brain widget with:

*   Neuron positions and connections

*   State variables (hunger, happiness, etc.)

*   Neurogenesis tracking system

*   Visualization settings

### `update\_state(self, new\_state)`

Updates the brain's state with new values and triggers visualization updates.

Parameters: new_state (dict) - Dictionary containing new state values

###`check_neurogenesis(self, state)`

Checks conditions for creating new neurons based on novelty, stress, and reward thresholds.

Parameters: state (dict) - Current brain state

Returns: bool - True if any neurons were created

### `paintEvent(self, event)`

Handles all drawing operations for the widget, including:

*   Neurons (circles, squares, triangles)
*   Connections between neurons
*   Weight values
*   Highlights for new neurons

### `update_weights(self)`

Randomly adjusts connection weights between neurons when not frozen.

### 2\. SquidBrainWindow Class

The main application window that contains the brain visualization and various control tabs.

### ` __init\__(self, tamagotchi\_logic, debug\_mode=False)`

Initializes the main window with:

*   Reference to the tamagotchi logic
*   Debug mode flag
*   Various timers for updates
*   Tab-based interface

### `update\_brain(self, state)`

Main method for updating the brain visualization with new state data.

Parameters: state (dict) - Complete brain state dictionary

### `perform_hebbian_learning(self)`

Implements Hebbian learning ("neurons that fire together wire together") by:

1.  Identifying active neurons
2.  Selecting random pairs of active neurons
3.  Updating their connection weights
4.  Logging the changes

### `update_connection(self, neuron1, neuron2, value1, value2)`

Updates the weight between two neurons based on their activation levels.

Parameters: neuron1, neuron2 (str) - Names of the neurons

Parameters: value1, value2 (float) - Activation levels (0-100)

## Key Features

### Neurogenesis System

The brain can grow new neurons under certain conditions:

*   **Novelty:** When exposed to new experiences
*   **Stress:** During prolonged stressful situations
*   **Reward:** After receiving positive reinforcement

New neurons are visually distinct (triangular) and have default connections.

### Visual Representation

The brain visualization includes:

*   **Original neurons:** Circles (basic needs) and squares (complex states)
*   **New neurons:** Triangles (color-coded by type)
*   **Connections:** Colored lines (green=positive, red=negative)
*   **Weights:** Displayed at connection midpoints

### Interactive Features

*   **Neuron dragging:** Rposition neurons with mouse
*   **Stimulation:** Manual input of state values via dialog
*   **Training:** Capture and apply Hebbian learning
*   **Freezing:** Temporarily stop weight changes

### Information Tabs

The interface provides multiple tabs for different aspects:

| Tab | Purpose |
| --- | --- |
| Network | Main brain visualization and controls |
| Memory | Short-term and long-term memory display |
| Personality | Personality traits and care tips |
| Learning | Weight change history and analysis |
| Thinking | Decision-making process visualization |

## Important Data Structures

### Brain State

The core state dictionary contains:

*   `hunger`, `happiness`, `cleanliness`, `sleepiness` (0-100)
*   `satisfaction`, `anxiety`, `curiosity` (0-100)
*   Boolean flags: `is_sick`, `is_eating`, `is_sleeping`
*   Movement: `direction`, `position`

### Neurogenesis Data

Tracks neuron creation:

*   `novelty_counter`: Count of novel experiences
*   `new_neurons`: List of created neurons
*   `last_neuron_time`: Timestamp of last creation

### Connection Weights

Stored as a dictionary with tuple keys (neuron pairs) and float values (-1 to 1):

`{
    ("hunger", "satisfaction"): 0.75,
    ("happiness", "cleanliness"): 0.32,
    ...
}`

### Implementation Notes

*   The system uses PyQt5 for visualization and Qt's signal/slot mechanism for updates
*   Neuron positions are stored as (x,y) tuples in `neuron_positions`
*   The Hebbian learning timer runs every 2 seconds by default
*   Debug mode provides additional console output

## Integration Points

The module integrates with the main tamagotchi system through:

*   `tamagotchi_logic` reference for state updates
*   Memory manager access for memory tab updates
*   Personality system for trait-specific behaviors
