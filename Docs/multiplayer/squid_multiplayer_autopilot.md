### Remote Squid Control

(`squid_multiplayer_autopilot.py`)

When your squid visits another instance, it's not directly controlled by the other player. Instead, the `RemoteSquidController` class in `squid_multiplayer_autopilot.py` takes over.
This is an AI autopilot that simulates your squid's behavior according to predefined patterns (exploring, seeking food, interacting with objects, etc.). The controller makes decisions based on:

The initial state of your squid when it crossed the boundary
A random "personality" for the visit
The environment of the other tank (available food, rocks, etc.)

The flow works like this:

Your squid hits a boundary and sends a `squid_exit` message
The other instance receives this message and:

Creates a visual representation of your squid
Creates a RemoteSquidController to manage its behavior


The autopilot controls your squid in the other tank
After a random amount of time (or when the controller decides it's met its goals like stealing rocks), it initiates a return
When your squid returns, any experiences or stolen items are synchronized back

This autopilot system allows for autonomous interaction between instances without requiring direct player control. Your squid effectively has a "life of its own" while visiting other tanks.


# RemoteSquidController Autopilot System

The `RemoteSquidController` class in `squid_multiplayer_autopilot.py` implements an autopilot system that governs the behavior of remote squids in a multiplayer Tamagotchi-like game. These squids are visiting from other players' game instances and operate autonomously in a foreign environment. The autopilot manages their movement, interactions, and decision-making, simulating natural squid behavior while allowing for unique actions like stealing rocks. Below is a detailed explanation of how the autopilot works.

---

## Overview

The `RemoteSquidController` is instantiated for each remote squid entering a player's game instance. It uses a state machine to control the squid's behavior, transitioning between states like exploring, feeding, interacting, and returning home. The autopilot relies on the game’s graphics scene to detect objects (e.g., food, rocks) and uses predefined rules to decide actions based on probabilities, timers, and environmental conditions.

**Key features:**
- **State-based behavior**: The squid operates in one of four states: `exploring`, `feeding`, `interacting`, or `returning`.
- **Autonomous decision-making**: Decisions are made at regular intervals (every 0.5 seconds) with some randomness for natural movement.
- **Object interaction**: Squids can eat food, interact with rocks, or steal rocks to bring back to their home instance.
- **Time-limited visits**: Squids stay for a random duration (1–3 minutes) before returning home.
- **Debug mode**: Provides verbose logging for troubleshooting.

---

## Key Components and Initialization

When a remote squid enters a foreign instance, the `RemoteSquidController` is initialized with:
- **`squid_data`**: A dictionary containing the squid’s initial state (e.g., position, direction, color, hunger, happiness).
- **`scene`**: The PyQt5 graphics scene, used to detect and interact with objects like food and rocks.
- **`debug_mode`**: A boolean flag for enabling detailed logs (default: `False`).

**During initialization:**
- The squid’s data is copied to avoid reference issues.
- Default window dimensions (1280x900) are set if not provided.
- A random visit duration (`max_time_away`, 60–180 seconds) is assigned.
- The squid starts in the `exploring` state, with a random number of rocks it can steal (1–3).
- Movement parameters are set: speed (`move_speed = 5`), direction change probability (`direction_change_prob = 0.02`), and decision interval (`decision_interval = 0.5` seconds).

**Example debug output at initialization:**
```
[AutoPilot] Initialized for squid at (x, y)
[AutoPilot] Will return home after 120 seconds
[AutoPilot] Home direction: left
```

---

## State Machine and Behavior

The autopilot operates using a state machine, with the `update` method driving behavior updates at regular intervals. The squid makes decisions every 0.5 seconds, but continues moving between decisions to maintain smooth motion. The states and their behaviors are:

### 1. Exploring (`exploring`)

- **Purpose**: The squid moves randomly to explore the environment.
- **Behavior**:
  - Moves in the current direction (left, right, up, or down) at a speed of 5 pixels per update.
  - Has a 2% chance (`direction_change_prob`) to randomly change direction, creating natural wandering.
  - Periodically checks for nearby food (10% chance) or rocks (5% chance) within detection ranges (300 pixels for food, 200 for rocks).
  - If food is found, transitions to `feeding` state; if a rock is found, transitions to `interacting` state.
- **Implementation**: The `explore` method handles movement and object detection using `find_nearby_food` and `find_nearby_rock`.

### 2. Feeding (`feeding`)

- **Purpose**: The squid moves toward and consumes food.
- **Behavior**:
  - Targets the closest food item found during exploration.
  - Moves toward the food’s position using `move_toward`, prioritizing the larger axis (horizontal or vertical) for direction.
  - If the squid is within 50 pixels of the food, it “eats” it:
    - Removes the food from the scene.
    - Increments `food_eaten_count`.
    - Reduces hunger (`hunger - 15`) and increases happiness (`happiness + 10`).
  - If the food is no longer valid (e.g., eaten by another squid), reverts to `exploring`.
- **Implementation**: The `seek_food` method manages movement and eating, with `eat_food` handling consumption.

### 3. Interacting (`interacting`)

- **Purpose**: The squid interacts with rocks, with a chance to steal them.
- **Behavior**:
  - Targets the closest rock found during exploration.
  - Moves toward the rock using `move_toward`.
  - If within 50 pixels, the squid interacts:
    - Increments `rock_interaction_count` and boosts happiness (`happiness + 5`).
    - If the rock is locally owned (not remote) and the squid hasn’t reached its stealing limit (`max_rocks_to_steal`), it has a 40% chance to steal the rock:
      - Sets `carrying_rock = True` and `stealing_phase = True`.
      - Hides the rock in the scene and increments `rocks_stolen`.
      - If the stealing quota is met, transitions to `returning`.
  - After interaction (or if no steal occurs), reverts to `exploring`.
- **Implementation**: The `interact_with_object` method handles movement, interaction, and stealing logic.

### 4. Returning (`returning`)

- **Purpose**: The squid heads back to its home instance.
- **Behavior**:
  - Triggered when the visit duration (`time_away`) exceeds `max_time_away` or the stealing quota is met.
  - Determines the home direction using `determine_home_direction` (opposite of entry direction or closest boundary if unknown).
  - Moves toward the boundary corresponding to `home_direction` (e.g., left edge for `left`) with slight randomness to avoid straight-line movement.
  - Tracks distance traveled (`distance_traveled += move_speed`).
  - When within 20 pixels of the boundary (`is_at_boundary`), the squid is considered to have exited, and the controller logs a summary of activities (food eaten, rocks interacted with, rocks stolen, distance traveled).
- **Implementation**: The `return_home` method manages movement to the boundary, with `is_at_boundary` checking for exit conditions.

---

## Movement Mechanics

The autopilot uses two primary movement methods:
- **`move_in_direction(direction)`**: Moves the squid in the specified direction (left, right, up, down) by `move_speed` (5 pixels), ensuring it stays within window bounds (10 pixels from edges).
- **`move_toward(target_x, target_y)`**: Moves toward a target position by prioritizing the larger axis (horizontal or vertical) and calling `move_in_direction`.

Movement is smooth because the squid continues moving between decision intervals, only changing direction or state during decision points.

---

## Object Detection

The autopilot interacts with the game’s graphics scene to detect objects:
- **`find_nearby_food`**:
  - Scans the scene for food items (identified by filenames containing “food,” “sushi,” or “cheese” or a `category` of “food”).
  - Returns the closest food within 300 pixels, if any.
- **`find_nearby_rock`**:
  - Scans for rocks (identified by `category` of “rock” or “rock” in filename).
  - Returns the closest rock within 200 pixels, if any.
- **Vision Range**: The `is_in_vision_range` method checks if an item is within 800 pixels, though this is less frequently used.

These methods rely on `get_food_items_from_scene` and `get_rock_items_from_scene`, which filter scene items based on attributes like `filename` or `category`.

---

## Rock Stealing Mechanic

A unique feature is the ability to steal rocks:
- The squid is assigned a random stealing limit (`max_rocks_to_steal`, 1–3) at initialization.
- During `interacting`, if a rock is local (not remote) and the stealing limit isn’t reached, there’s a 40% chance to steal:
  - The rock is hidden (`setVisible(False)`), and `rocks_stolen` is incremented.
  - The squid’s `carrying_rock` flag is set, and its status is updated to “stealing rock.”
- If the stealing quota is met, the squid immediately transitions to `returning`.
- Stolen rocks are later recreated in the squid’s home instance (handled by `main.py`’s `create_stolen_rocks`).

---

## Time Management and Returning Home

- The squid tracks `time_away` (seconds spent in the foreign instance) using `delta_time` calculated in `update`.
- When `time_away > max_time_away`, the squid transitions to `returning`.
- The `determine_home_direction` method sets the exit direction:
  - Uses the opposite of the entry direction (e.g., entered from left → exit via right).
  - If entry direction is unknown, chooses the closest boundary based on the squid’s position.
- Upon reaching the boundary, the controller logs a summary via `get_summary`, which includes:
  - Time away
  - Food eaten
  - Rock interactions
  - Rocks stolen
  - Distance traveled
  - Final state

---

## Integration with `main.py`

The autopilot is tightly integrated with the `MultiplayerPlugin` in `main.py`:
- **Instantiation**: When a squid exits another instance (via a `network_squid_exit` message), `main.py` creates a `RemoteSquidController` in `_setup_controller_immediately` or `_process_pending_controller_creations`.
- **Updates**: The `update_remote_controllers` method in `main.py` calls the controller’s `update` method every 50ms (20 FPS), passing `delta_time` for smooth movement.
- **Visuals**: The controller updates the squid’s position in `squid_data`, and `main.py` synchronizes the visual representation (`remote_squids[node_id]['visual']`) with this data.
- **Return Handling**: When a squid reaches a boundary, `main.py`’s `handle_remote_squid_return` triggers a fade-out animation and sends a `squid_return` message with the activity summary. The home instance’s `handle_squid_return` applies the effects (e.g., creates stolen rocks, updates squid stats).

---

## Debugging and Logging

When `debug_mode` is enabled, the autopilot provides detailed logs for:
- Initialization details (position, max time away, home direction).
- State transitions (e.g., spotting food, switching to feeding).
- Movement changes (direction changes, boundary reaching).
- Object interactions (eating food, stealing rocks).
- Final summary upon returning.

The `debug_autopilot_status` method in `main.py` prints the current state of all controllers, including position, direction, time away, and activities.

---

## Example Flow

1. A squid enters from the left (`entry_direction = 'left'`) with `max_time_away = 120` seconds and `max_rocks_to_steal = 2`.
2. It starts in `exploring`, wandering randomly.
3. After 10 seconds, it spots food (within 300 pixels), transitions to `feeding`, moves to the food, and eats it (`food_eaten_count += 1`).
4. Later, it finds a rock, transitions to `interacting`, and steals it (40% chance, `rocks_stolen = 1`).
5. After 80 seconds, it finds another rock but doesn’t steal it (random chance fails).
6. At 120 seconds, it transitions to `returning`, determines `home_direction = 'right'` (opposite of entry), and moves to the right boundary.
7. Upon reaching the boundary, it logs a summary (e.g., 1 food eaten, 2 rocks interacted with, 1 rock stolen) and exits.
8. `main.py` sends a `squid_return` message, and the home instance creates the stolen rock and updates the squid’s stats.

---

## Key Methods

- **`__init__`**: Initializes the controller with squid data, scene, and parameters.
- **`update`**: Main method driving state transitions and behavior updates.
- **`explore`**: Handles random movement and object detection.
- **`seek_food`**: Manages movement toward food and eating.
- **`interact_with_object`**: Handles rock interactions and stealing.
- **`return_home`**: Manages movement to the home boundary.
- **`find_nearby_food`/`find_nearby_rock`**: Detects nearby objects.
- **`move_in_direction`/`move_toward`**: Controls movement mechanics.
- **`get_summary`**: Generates activity summary upon returning.
