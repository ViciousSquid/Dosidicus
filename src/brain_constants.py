"""
brain_constants.py - Shared constants for Dosidicus-2 brain system

This file defines the canonical neuron categories used across:
- brain_widget.py
- brain_tool.py  
- brain_designer.py
- brain_neuron_hooks.py

Import from here to ensure consistency.
"""

# =============================================================================
# REQUIRED NEURONS - Mandatory for all brain designs
# These 8 neurons MUST exist in any valid Dosidicus brain.
# =============================================================================

# Core stat neurons - positions match brain_widget.py's original_neuron_positions
CORE_NEURONS = {
    "hunger": (127, 81),
    "happiness": (361, 81),
    "cleanliness": (627, 81),
    "sleepiness": (840, 81),
    "satisfaction": (271, 380),
    "anxiety": (491, 389),
    "curiosity": (701, 386),
}

# can_see_food is MANDATORY - the squid must be able to see food
# This is separate from optional sensors because it's required for basic functionality
MANDATORY_SENSOR = {
    "can_see_food": (50, 200),
}

# All required neurons combined (7 core + 1 mandatory sensor)
REQUIRED_NEURONS = {**CORE_NEURONS, **MANDATORY_SENSOR}

# Ordered list for consistent iteration
CORE_NEURON_NAMES = [
    "hunger", "happiness", "cleanliness", "sleepiness",
    "satisfaction", "anxiety", "curiosity"
]

REQUIRED_NEURON_NAMES = CORE_NEURON_NAMES + ["can_see_food"]

# =============================================================================
# INPUT SENSORS - Optional neurons that receive values from game state
# These neurons get their activation from BrainNeuronHooks, not from
# neural propagation. They represent environmental/state observations.
# NOTE: can_see_food is NOT here - it's in REQUIRED_NEURONS
# =============================================================================
INPUT_SENSORS = {
    "external_stimulus": (50, 50),      # Environmental changes (resize, interactions)
    "plant_proximity": (50, 250),       # Distance to nearest plant decoration
    "threat_level": (50, 350),          # Computed from anxiety + startle state
    "pursuing_food": (150, 50),         # Currently chasing food
    "is_sick": (150, 150),              # Sickness state
    "is_fleeing": (150, 250),           # Currently fleeing
    "is_eating": (150, 350),            # Currently eating
    "is_sleeping": (250, 50),           # Currently sleeping
    "is_startled": (250, 150),          # Startled state
}

# Tuple for compatibility with brain_neuron_hooks.py (includes can_see_food)
DEFAULT_INPUT_SENSORS = (
    'external_stimulus',
    'can_see_food',  # Listed here for hooks compatibility but it's mandatory
    'plant_proximity',
    'threat_level',
    'pursuing_food',
    'is_sick',
    'is_fleeing',
    'is_eating',
    'is_sleeping',
    'is_startled',
)

# =============================================================================
# BINARY NEURONS - Neurons that should display as on/off (0 or 100)
# These use bright green/red coloring instead of gradient heat maps.
# =============================================================================
BINARY_NEURONS = {
    'can_see_food',
    'is_eating',
    'is_sleeping',
    'is_sick',
    'pursuing_food',
    'is_fleeing',
    'is_startled',
    'external_stimulus',  # Usually high/low, treat as binary-ish
}

# =============================================================================
# EXCLUDED NEURONS - Status neurons that exist but aren't visualized normally
# These are tracked in brain state but not shown in the main visualization.
# =============================================================================
EXCLUDED_NEURONS = [
    'is_sick',
    'is_eating', 
    'pursuing_food',
    'direction',
    'is_sleeping'
]

# =============================================================================
# VISUAL STYLE CONSTANTS - For consistent rendering across tools
# =============================================================================

# Ring colors for neuron types
CORE_NEURON_RING_COLOR = (255, 215, 0)      # Gold
INPUT_SENSOR_RING_COLOR = (100, 149, 237)   # Cornflower blue
CUSTOM_NEURON_RING_COLOR = (180, 180, 180)  # Gray

# Ring widths
PROTECTED_RING_WIDTH = 3
NORMAL_RING_WIDTH = 2

# Default neuron colors by type
DEFAULT_COLORS = {
    'core': (150, 150, 220),      # Soft purple
    'input': (100, 200, 150),     # Soft green  
    'output': (220, 150, 150),    # Soft red
    'hidden': (180, 180, 200),    # Neutral
    'sensor': (150, 200, 220),    # Soft blue
}

# =============================================================================
# LAYER DEFAULTS
# =============================================================================
DEFAULT_LAYER_HEIGHT = 120
DEFAULT_LAYER_SPACING = 150

LAYER_COLORS = {
    'input': {
        'fill': (200, 255, 200, 80),
        'border': (150, 220, 150, 120)
    },
    'output': {
        'fill': (255, 200, 200, 80),
        'border': (220, 150, 150, 120)
    },
    'hidden': {
        'fill': (230, 230, 255, 80),
        'border': (200, 200, 240, 120)
    }
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def is_core_neuron(name: str) -> bool:
    """Check if a neuron name is a core stat neuron (7 stats)."""
    return name in CORE_NEURONS

def is_required_neuron(name: str) -> bool:
    """Check if a neuron is required (core + can_see_food)."""
    return name in REQUIRED_NEURONS

def is_input_sensor(name: str) -> bool:
    """Check if a neuron name is an optional input sensor."""
    return name in INPUT_SENSORS

def is_any_sensor(name: str) -> bool:
    """Check if a neuron receives values from hooks (including can_see_food)."""
    return name in INPUT_SENSORS or name in MANDATORY_SENSOR or name in DEFAULT_INPUT_SENSORS

def is_binary_neuron(name: str) -> bool:
    """Check if a neuron should display as binary (on/off)."""
    return name in BINARY_NEURONS

def is_protected_neuron(name: str) -> bool:
    """Check if a neuron is protected (cannot be deleted or renamed)."""
    return is_required_neuron(name)

def get_neuron_category(name: str) -> str:
    """Get the category of a neuron: 'core', 'required', 'sensor', or 'custom'."""
    if is_core_neuron(name):
        return 'core'
    elif name == 'can_see_food':
        return 'required'
    elif is_input_sensor(name):
        return 'sensor'
    else:
        return 'custom'

def get_all_standard_neurons() -> dict:
    """Get all standard neurons (required + optional sensors) with positions."""
    result = dict(REQUIRED_NEURONS)
    result.update(INPUT_SENSORS)
    return result

def get_missing_required(existing_neurons: set) -> list:
    """Get list of required neurons not in the given set."""
    return [name for name in REQUIRED_NEURONS if name not in existing_neurons]