from enum import Enum, auto
import random

# --- Enums ---
class NeuronType(Enum):
    INPUT = auto()
    OUTPUT = auto()
    HIDDEN = auto()
    CORE = auto()
    SENSOR = auto()
    CONNECTOR = auto()
    CUSTOM = auto()  # New: User-created custom neurons

# --- Visual Constants ---
CORE_NEURON_RING_COLOR = (255, 215, 0)
INPUT_SENSOR_RING_COLOR = (100, 149, 237)
CUSTOM_NEURON_RING_COLOR = (180, 180, 180)
CONNECTOR_COLOR = (0, 0, 0)
PROTECTED_RING_WIDTH = 3
NORMAL_RING_WIDTH = 2
DEFAULT_LAYER_HEIGHT = 120
DEFAULT_LAYER_SPACING = 150

# Custom neuron visual settings
CUSTOM_NEURON_COLOR = (147, 112, 219)  # Medium purple - distinctive for custom neurons
CUSTOM_NEURON_SHAPE = 'pentagon'  # Pentagon shape for custom neurons

DEFAULT_COLORS = {
    'core': (150, 150, 220),
    'required': (100, 180, 100),
    'input': (100, 200, 150),
    'output': (220, 150, 150),
    'hidden': (180, 180, 200),
    'sensor': (150, 200, 220),
    'connector': (0, 0, 0),
    'custom': CUSTOM_NEURON_COLOR,  # New: Custom neuron color
}

LAYER_COLORS = {
    'input': {'fill': (200, 255, 200, 80), 'border': (150, 220, 150, 120)},
    'output': {'fill': (255, 200, 200, 80), 'border': (220, 150, 150, 120)},
    'hidden': {'fill': (230, 230, 255, 80), 'border': (200, 200, 240, 120)}
}

# --- Logic Constants ---
CORE_NEURONS = {
    "hunger": (127, 81), "happiness": (361, 81), "cleanliness": (627, 81),
    "sleepiness": (840, 81), "satisfaction": (271, 380), "anxiety": (491, 389),
    "curiosity": (701, 386),
}
MANDATORY_SENSOR = {"can_see_food": (50, 200)}
REQUIRED_NEURONS = {**CORE_NEURONS, **MANDATORY_SENSOR}
CORE_NEURON_NAMES = list(CORE_NEURONS.keys())
REQUIRED_NEURON_NAMES = CORE_NEURON_NAMES + ["can_see_food"]

INPUT_SENSORS = {
    "external_stimulus": (50, 50), "plant_proximity": (50, 250),
    "threat_level": (50, 350), "pursuing_food": (150, 50),
    "is_sick": (150, 150), "is_fleeing": (150, 250),
    "is_eating": (150, 350), "is_sleeping": (250, 50),
    "is_startled": (250, 150),
}

BINARY_NEURONS = {
    'can_see_food', 'is_eating', 'is_sleeping', 'is_sick',
    'pursuing_food', 'is_fleeing', 'is_startled', 'external_stimulus'
}

# Neurogenesis prefixes - neurons created by the neurogenesis system
NEUROGENESIS_PREFIXES = {'stress_', 'novelty_', 'reward_', 'connector_'}

def is_core_neuron(name): return name in CORE_NEURONS
def is_required_neuron(name): return name in REQUIRED_NEURONS
def is_input_sensor(name): return name in INPUT_SENSORS
def is_binary_neuron(name): return name in BINARY_NEURONS
def is_protected_neuron(name): return is_required_neuron(name)

def is_neurogenesis_neuron(name):
    """Check if a neuron was created by the neurogenesis system."""
    return any(name.startswith(prefix) for prefix in NEUROGENESIS_PREFIXES)

def is_custom_neuron(name):
    """
    Check if a neuron is a user-created custom neuron.
    Custom neurons are those that are:
    - Not core neurons
    - Not required neurons (including can_see_food)
    - Not input sensors
    - Not created by neurogenesis (stress_, novelty_, reward_, connector_)
    """
    if is_core_neuron(name):
        return False
    if is_required_neuron(name):
        return False
    if is_input_sensor(name):
        return False
    if is_neurogenesis_neuron(name):
        return False
    return True

def get_neuron_category(name):
    """Get the category of a neuron for display and logic purposes."""
    if is_core_neuron(name): 
        return 'core'
    elif name == 'can_see_food': 
        return 'required'
    elif is_input_sensor(name): 
        return 'sensor'
    elif is_neurogenesis_neuron(name):
        # Further categorize by type
        if name.startswith('connector_'):
            return 'connector'
        elif name.startswith('stress_'):
            return 'stress'
        elif name.startswith('novelty_'):
            return 'novelty'
        elif name.startswith('reward_'):
            return 'reward'
        return 'neurogenesis'
    elif is_custom_neuron(name):
        return 'custom'
    return 'hidden'

def get_missing_required(existing): 
    return [n for n in REQUIRED_NEURONS if n not in existing]

# --- Default Connections ---
DEFAULT_SENSOR_CONNECTIONS = {
    'can_see_food': [('hunger', 0.4, 1.0), ('happiness', 0.2, 0.5), ('satisfaction', 0.15, 0.2)],
    'external_stimulus': [('curiosity', 0.35, 1.0), ('anxiety', 0.15, 0.3)],
    'threat_level': [('anxiety', 0.6, 1.0), ('happiness', -0.3, 0.7), ('curiosity', -0.2, 0.4)],
    'plant_proximity': [('happiness', 0.2, 1.0), ('curiosity', 0.15, 0.5)],
    'is_sick': [('happiness', -0.5, 1.0), ('anxiety', 0.4, 0.8), ('sleepiness', 0.3, 0.6)],
    'is_fleeing': [('anxiety', 0.4, 1.0), ('curiosity', -0.3, 0.7)],
    'is_eating': [('satisfaction', 0.5, 1.0), ('happiness', 0.3, 0.8), ('hunger', -0.4, 1.0)],
    'is_sleeping': [('sleepiness', -0.5, 1.0), ('anxiety', -0.2, 0.6)],
    'is_startled': [('anxiety', 0.5, 1.0), ('curiosity', 0.2, 0.4)],
    'pursuing_food': [('hunger', 0.2, 1.0), ('curiosity', 0.25, 0.5)],
}

def get_default_connections_for_sensor(sensor_name: str) -> list:
    if sensor_name not in DEFAULT_SENSOR_CONNECTIONS:
        return []
    connections = []
    for target, weight, probability in DEFAULT_SENSOR_CONNECTIONS[sensor_name]:
        if random.random() < probability:
            connections.append((target, weight))
    return connections


# --- Custom Neuron Validation ---
def validate_custom_neuron_name(name: str) -> tuple:
    """
    Validate a custom neuron name.
    
    Returns:
        (is_valid: bool, error_message: str or None)
    """
    if not name:
        return False, "Name cannot be empty"
    
    # Normalize the name
    normalized = name.strip().lower().replace(' ', '_').replace('-', '_')
    
    # Check for reserved names
    if is_core_neuron(normalized):
        return False, f"'{name}' is a reserved core neuron name"
    
    if is_required_neuron(normalized):
        return False, f"'{name}' is a reserved required neuron name"
    
    if is_input_sensor(normalized):
        return False, f"'{name}' is a reserved sensor name"
    
    # Check for neurogenesis prefixes (warn but allow)
    for prefix in NEUROGENESIS_PREFIXES:
        if normalized.startswith(prefix):
            # Allow but it may conflict with auto-generated neurons
            return True, f"Warning: '{prefix}' prefix is used by neurogenesis system"
    
    # Check for valid characters
    import re
    if not re.match(r'^[a-z][a-z0-9_]*$', normalized):
        return False, "Name must start with a letter and contain only letters, numbers, and underscores"
    
    # Check length
    if len(normalized) < 2:
        return False, "Name must be at least 2 characters"
    
    if len(normalized) > 32:
        return False, "Name must be 32 characters or less"
    
    return True, None


def normalize_neuron_name(name: str) -> str:
    """Normalize a neuron name to standard format."""
    return name.strip().lower().replace(' ', '_').replace('-', '_')
