

# Squid Class Technical Overview

The Squid class represents the main character in the Dosidicus application, a virtual pet simulation with complex behaviors and personality traits.

## Class Overview

The Squid class is a PyQt5-based implementation that handles:

*   Visual representation and animation
*   Movement and navigation
*   Decision making based on needs and personality
*   Interaction with environment (food, decorations)
*   State management (hunger, happiness, etc.)

## Core Attributes

| Attribute | Type | Description |
| --- | --- | --- |
| ui  | UserInterface | Reference to the main UI component |
| tamagotchi\_logic | TamagotchiLogic | Reference to the main game logic |
| memory\_manager | MemoryManager | Handles memory storage and retrieval |
| mental\_state\_manager | MentalStateManager | Manages emotional states |
| personality | Personality (Enum) | The squid's personality type (TIMID, GREEDY, STUBBORN) |
| health, hunger, happiness, etc. | int (0-100) | Various state attributes |

## Key Methods

### Initialization and Setup

```
def __init__(self, user_interface, tamagotchi_logic=None, personality=None, neuro_cooldown=None):
    # Initializes the squid with default values and sets up UI components
```

### Movement and Navigation

```
def move_squid(self):
    # Handles the squid's movement based on current direction and animation speed
```

```
def move_towards(self, x, y):
    # Moves the squid towards a specific coordinate
```

```
def change_direction(self):
    # Randomly changes the squid's movement direction
```

### Decision Making

```
def make_decision(self):
    # The main decision-making function that determines the squid's behavior
```

```
def _make_timid_decision(self, current_state):
    # Personality-specific decision making for timid squids
```

```
def _make_greedy_decision(self, current_state):
    # Personality-specific decision making for greedy squids
```

### Food Interaction

```
def eat(self, food_item):
    # Handles eating behavior and applies effects
```

```
def get_visible_food(self):
    # Returns food items within the squid's vision cone
```

```
def is_in_vision_cone(self, x, y):
    # Determines if a point is within the squid's field of view
```

### Environment Interaction

```
def push_decoration(self, decoration, direction):
    # Pushes a decoration with animation
```

```
def organize_decorations(self):
    # Organizes nearby decorations (personality-specific behavior)
```

### State Management

```
def go_to_sleep(self):
    # Puts the squid to sleep
```

```
def wake_up(self):
    # Wakes the squid up
```

```
def load_state(self, state):
    # Loads a saved state
```

## Detailed Method Explanations

### make\_decision()

The core decision-making method that determines the squid's behavior based on:

*   Current needs (hunger, sleepiness, etc.)
*   Personality traits
*   Environmental factors
*   Neurogenesis state (brain development)

Implements a hierarchical decision system that checks conditions in priority order.

### move\_squid()

Handles the squid's movement with several key features:

*   Respects animation speed settings
*   Handles sleeping state differently (moves downward)
*   Implements food pursuit behavior when food is visible
*   Changes direction at screen boundaries
*   Updates visual representation (animation frames)

### eat()

Complex food consumption behavior that:

*   Applies different effects based on food type
*   Triggers personality-specific reactions
*   Starts digestion/poop timer
*   Manages memory of eating events
*   Updates multiple status attributes

## Personality System

The squid implements distinct personality types that modify behavior:

*   **TIMID**: More cautious, avoids risks
*   **GREEDY**: Focused on food, eats more
*   **STUBBORN**: Prefers specific foods, resistant to change

Personality affects decision making through specialized methods (\_make\_\*\_decision).

## Vision System

The squid has a limited field of view implemented with:

*   80-degree view cone (view\_cone\_angle)
*   Visualization capability (toggle\_view\_cone())
*   Food prioritization within view (get\_visible\_food())

## Animation System

The visual representation uses:

*   Frame-based animation (current\_frame)
*   Direction-specific sprites
*   Sleeping state animation
*   Adjustable animation speed

## State Management

The squid maintains numerous state variables:

| Variable | Range | Description |
| --- | --- | --- |
| hunger | 0-100 | Need for food |
| happiness | 0-100 | Overall contentment |
| cleanliness | 0-100 | Clean/dirty state |
| sleepiness | 0-100 | Need for sleep |
| satisfaction | 0-100 | Recent positive experiences |
| anxiety | 0-100 | Stress level |
| curiosity | 0-100 | Desire to explore |

## Interaction System

The squid interacts with its environment through:

*   Food consumption (eat())
*   Decoration manipulation (push\_decoration())
*   Personality-specific behaviors (organize\_decorations())
*   Visual feedback (show\_eating\_effect())

**Note:** The Squid class demonstrates a sophisticated virtual pet implementation with complex behavior patterns, personality-driven decision making, and rich environmental interactions.
