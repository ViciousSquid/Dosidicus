
# TamagotchiLogic Technical Documentation

## Class Overview

The `TamagotchiLogic` class is the core game logic controller for the Dosidicus digital pet application. It manages:

*   Squid behavior and state management
*   Environment interactions (food, decorations, cleanliness)
*   Game mechanics and progression
*   Brain/neural network integration
*   Save/load functionality

**Key Relationships:** TamagotchiLogic coordinates between the UI (PyQt5), Squid object, and BrainWindow to create a cohesive digital pet experience.

## Initialization and Setup

### Constructor (`__init__`)

Initializes the game controller with references to UI, Squid, and BrainWindow components.

`def __init__(self, user_interface, squid, brain_window):`

### Key Initialization Steps:

1.  Sets up neurogenesis triggers tracking
2.  Initializes Hebbian learning system
3.  Configures mental state cooldowns
4.  Sets up game timers and simulation speed
5.  Connects UI actions to methods
6.  Initializes statistics window

**Important:** The constructor ensures all required components are properly connected before loading game state.

## Core Functions

### Simulation Update (`update_simulation`)

The main game loop that updates all systems:

`def update\_simulation(self):`

*   Handles object movement (food, poop)
*   Updates squid position and state
*   Manages mental states (startle, curiosity)
*   Tracks neurogenesis triggers
*   Updates brain state

### State Management (`update_statistics`)

Updates all squid attributes and game state:

`def update\_statistics(self):`

*   Adjusts hunger, happiness, cleanliness
*   Manages sickness state
*   Updates satisfaction, anxiety, curiosity
*   Handles sleep transitions
*   Calculates points

### Brain Integration (`update_squid_brain`)

Packages squid state for brain visualization:

`def update\_squid\_brain(self):`

*   Collects all squid attributes
*   Includes position and direction
*   Adds personality information
*   Sends to BrainWindow for visualization

## Interaction Functions

### Feeding System

| Function | Description |
| --- | --- |
| `feed_squid` | Triggers food spawning (called from UI) |
| `spawn_food` | Creates food items (sushi or cheese) |
| `move_foods` | Handles food item movement |

### Cleaning System

| Function | Description |
| --- | --- |
| `clean_environment` | Initiates cleaning process |
| `update_cleaning` | Animates cleaning line and removes items |
| `finish_cleaning` | Completes cleaning and updates stats |

### Medical System

`def give\_medicine(self):`

Handles medicine administration with visual effects:

*   Cures sickness
*   Reduces happiness
*   Increases sleepiness
*   Shows needle animation
*   Forces squid to sleep

## Mental State Management

### Startle System

| Function | Description |
| --- | --- |
| `check_for_startle` | Determines if squid should be startled |
| `startle_squid` | Triggers startle state and effects |
| `end_startle` | Returns squid to normal state |

### Curiosity System

| Function | Description |
| --- | --- |
| `check_for_curiosity` | Determines if squid becomes curious |
| `make_squid_curious` | Triggers curious state |
| `curious_interaction` | Handles interactions while curious |

### Neurogenesis Tracking

`def track\_neurogenesis\_triggers(self):`

Manages counters for brain development triggers:

*   Novel object encounters
*   High stress cycles
*   Positive outcomes

## Save/Load System

### Save Function

`def save\_game(self, squid, tamagotchi\_logic, is\_autosave=False):`

Serializes game state including:

*   Squid attributes
*   Game logic state
*   Decorations
*   Brain state
*   Memory systems

### Load Function

`def load\_game(self):`

Restores game state from save file:

*   Squid attributes
*   Brain connections
*   Memories
*   Decorations
*   Game state

**Autosave:** Configured to save every 5 minutes via `start_autosave` and `autosave` methods.

## Utility Functions

### Game Management

| Function | Description |
| --- | --- |
| `game_over` | Handles end-game state |
| `reset_game` | Resets all game state |

### UI Integration

| Function | Description |
| --- | --- |
| `show_message` | Displays messages to user |
| `handle_window_resize` | Adjusts UI elements on resize |

### Simulation Control

| Function | Description |
| --- | --- |
| `set_simulation_speed` | Adjusts game speed (0-4x) |
| `update_timers` | Adjusts timer intervals based on speed |

## Conclusion

The `TamagotchiLogic` class provides a comprehensive framework for managing all aspects of the Dosidicus digital pet simulation. Its key strengths include:

*   Tight integration with neural network visualization
*   Sophisticated mental state management
*   Robust save/load system
*   Flexible simulation speed control
*   Extensive interaction systems

**Performance Note:** The class manages multiple QTimer instances which must be properly stopped/started during speed changes and game state transitions.
