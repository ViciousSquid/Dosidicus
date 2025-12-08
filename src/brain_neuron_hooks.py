# brain_neuron_hooks.py
import math
import random
import time
from typing import Dict, Callable, Any

class BrainNeuronHooks:
    """
    Generic system for wiring input neurons to actual game events.
    Keeps tamagotchi_logic clean by encapsulating all neuron calculation logic.
    """
    
    def __init__(self, tamagotchi_logic):
        self.logic = tamagotchi_logic
        
        # Registry mapping neuron names to their calculation functions
        self.handlers: Dict[str, Callable] = {
        'external_stimulus': self.calculate_external_stimulus,
        'can_see_food': self.calculate_can_see_food,
        'plant_proximity': self.calculate_plant_proximity,
        'threat_level': self.calculate_threat_level,
        'pursuing_food': self.calculate_pursuing_food,
        'is_sick': self.calculate_is_sick,
        'is_fleeing': self.calculate_is_fleeing,
        'is_eating': self.calculate_is_eating,
        'is_sleeping': self.calculate_is_sleeping,
    }
        
        # Environmental event history for temporal calculations
        self.event_tracker = {
            'last_window_resize_time': 0,
            'window_resize_magnitude': 0,
            'new_object_appeared': False,
            'last_user_interaction_time': 0,
            'interaction_intensity': 0,
            'last_food_spawn_time': 0,
            'last_poop_spawn_time': 0,
        }
    

    # ------------------------------------------------------------

    def calculate_pursuing_food(self) -> float:
        """Return 100.0 if squid is pursuing food, 0.0 otherwise."""
        if not hasattr(self.logic, 'squid'):
            return 0.0
        return 100.0 if getattr(self.logic.squid, 'pursuing_food', False) else 0.0

    def calculate_is_sick(self) -> float:
        """Return 100.0 if squid is sick, 0.0 otherwise."""
        if not hasattr(self.logic, 'squid'):
            return 0.0
        return 100.0 if getattr(self.logic.squid, 'is_sick', False) else 0.0

    def calculate_is_fleeing(self) -> float:
        """Return 100.0 if squid is fleeing, 0.0 otherwise."""
        if not hasattr(self.logic, 'squid'):
            return 0.0
        return 100.0 if getattr(self.logic.squid, 'is_fleeing', False) else 0.0


    # =========================================================================
    # PUBLIC API - Called from tamagotchi_logic.py
    # =========================================================================

    
    
    def get_input_neuron_values(self) -> Dict[str, float]:
        """
        Calculate activation values for all registered input neurons.
        Returns: {neuron_name: activation_value}
        """
        if not hasattr(self.logic, 'brain_window') or not self.logic.brain_window:
            return {}
        
        brain_widget = self.logic.brain_window.brain_widget
        input_values = {}
        
        # Get neuron configurations
        config = getattr(brain_widget, 'config', {})
        neurons_config = config.get_neurogenesis_config().get('neurons', {})
        
        for neuron_name in brain_widget.neuron_positions.keys():
            # Skip core stat neurons
            if neuron_name in ['hunger', 'happiness', 'cleanliness', 'sleepiness', 
                              'satisfaction', 'anxiety', 'curiosity']:
                continue
            
            # Check if neuron is marked as input type OR has a handler
            neuron_cfg = neurons_config.get(neuron_name, {})
            if neuron_cfg.get('type') == 'input' or neuron_name in self.handlers:
                # Call handler if exists, otherwise default background noise
                if neuron_name in self.handlers:
                    input_values[neuron_name] = self.handlers[neuron_name]()
                else:
                    input_values[neuron_name] = random.uniform(5, 10)
        
        return input_values
    
    def on_window_resize(self, width_change: int, height_change: int, new_size: tuple):
        """Track window resize events for external_stimulus neuron."""
        magnitude = math.sqrt(width_change**2 + height_change**2)
        self.event_tracker['window_resize_magnitude'] = min(100, magnitude / 10)
        self.event_tracker['last_window_resize_time'] = time.time()
    
    def on_object_spawned(self, object_type: str):
        """Track when new objects appear in the environment."""
        self.event_tracker['new_object_appeared'] = True
        
        # Set interaction intensity based on object type
        intensity_map = {
            'food': 30,
            'decorations': 20,
            'poop': 10,
        }
        self.event_tracker['interaction_intensity'] = intensity_map.get(object_type, 15)
        self.event_tracker['last_user_interaction_time'] = time.time()
    
    def on_user_interaction(self, action: str):
        """Track user interactions (feeding, cleaning, etc.)."""
        self.event_tracker['last_user_interaction_time'] = time.time()
        
        intensity_map = {
            'feed': 40,
            'clean': 60,
            'medicine': 70,
            'rock_test': 50,
        }
        self.event_tracker['interaction_intensity'] = intensity_map.get(action, 30)
    
    def update_decay(self):
        """Decay environmental trackers each simulation tick."""
        self.event_tracker['window_resize_magnitude'] *= 0.95
        self.event_tracker['interaction_intensity'] *= 0.90
    
    # =========================================================================
    # HANDLER FUNCTIONS - Specific neuron calculations
    # =========================================================================
    
    def calculate_external_stimulus(self) -> float:
        """
        Calculate activation for external_stimulus neuron based on recent environmental changes.
        Returns value between 0-100.
        """
        tracker = self.event_tracker
        current_time = time.time()
        
        # Start with baseline environmental noise
        activation = random.uniform(5, 15)
        
        # Add contribution from window resize events
        if tracker['window_resize_magnitude'] > 0:
            time_since_resize = current_time - tracker['last_window_resize_time']
            decay_factor = max(0, 1 - (time_since_resize / 10.0))
            activation += tracker['window_resize_magnitude'] * decay_factor
        
        # Add contribution from new objects
        if tracker['new_object_appeared']:
            activation += 30
            tracker['new_object_appeared'] = False  # Reset after one tick
        
        # Add contribution from user interactions
        if tracker['interaction_intensity'] > 0:
            time_since_interaction = current_time - tracker['last_user_interaction_time']
            decay_factor = max(0, 1 - (time_since_interaction / 5.0))
            activation += tracker['interaction_intensity'] * decay_factor
        
        return max(0, min(100, activation))
    
    def calculate_can_see_food(self) -> float:
        """Return 100.0 if food is visible in vision cone, 0.0 otherwise."""
        if not hasattr(self.logic, 'food_items') or not self.logic.food_items:
            return 0.0
        
        # Check if any food is visible using the squid's vision system
        visible_food = self.logic.squid.get_visible_food()
        return 100.0 if visible_food else 0.0
    
    def calculate_plant_proximity(self) -> float:
        """Calculate activation based on distance to nearest plant decoration."""
        if not hasattr(self.logic, 'user_interface'):
            return 0
        
        squid_x, squid_y = self.logic.squid.squid_x, self.logic.squid_y
        min_distance = float('inf')
        
        # Scan scene for plant decorations
        for item in self.logic.user_interface.scene.items():
            if hasattr(item, 'category') and item.category == 'plant':
                plant_pos = item.sceneBoundingRect().center()
                dist = math.hypot(plant_pos.x() - squid_x, plant_pos.y() - squid_y)
                min_distance = min(min_distance, dist)
        
        # Convert to activation (closer = higher)
        max_range = 300
        return max(0, 100 - (min_distance / max_range * 100))
    
    def calculate_threat_level(self) -> float:
        """Calculate activation based on current anxiety and startle state."""
        if not hasattr(self.logic, 'squid'):
            return 0
        
        # Base threat on anxiety
        threat_level = self.logic.squid.anxiety
        
        # Increase if startled or fleeing
        if getattr(self.logic.squid, 'is_fleeing', False):
            threat_level = min(100, threat_level + 30)
        
        # Add random fluctuation
        threat_level += random.uniform(-5, 5)
        
        return max(0, min(100, threat_level))
    
    def calculate_is_eating(self) -> float:
        """Return 100.0 if squid is eating, 0.0 otherwise."""
        if not hasattr(self.logic, 'squid'):
            return 0.0
        return 100.0 if getattr(self.logic.squid, 'is_eating', False) else 0.0

    def calculate_is_sleeping(self) -> float:
        """Return 100.0 if squid is sleeping, 0.0 otherwise."""
        if not hasattr(self.logic, 'squid'):
            return 0.0
        return 100.0 if getattr(self.logic.squid, 'is_sleeping', False) else 0.0



DEFAULT_INPUT_SENSORS = (
    'external_stimulus',
    'can_see_food',
    'plant_proximity',
    'threat_level',
    'pursuing_food',
    'is_sick',
    'is_fleeing',
    'is_eating',
    'is_sleeping',
)