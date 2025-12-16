# brain_neuron_hooks.py
import math
import random
import time
from typing import Dict, Callable, Any, Optional

class BrainNeuronHooks:
    """
    Generic system for wiring input neurons to actual game events.
    Keeps tamagotchi_logic clean by encapsulating all neuron calculation logic.
    
    Supports plugin-registered custom neuron handlers via the plugin manager.
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
            'is_startled': self.calculate_is_startled,
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
    
    # =========================================================================
    # PLUGIN INTEGRATION
    # =========================================================================
    
    def register_handler(self, neuron_name: str, handler: Callable[[], float]) -> bool:
        """
        Register a custom handler for a neuron.
        
        Args:
            neuron_name: The name of the neuron to wire up
            handler: A callable that returns a float (0-100) activation value
            
        Returns:
            True if registered successfully, False if neuron already has a built-in handler
        """
        if neuron_name in self.handlers:
            print(f"[BrainNeuronHooks] Warning: Overwriting existing handler for '{neuron_name}'")
        
        self.handlers[neuron_name] = handler
        print(f"[BrainNeuronHooks] Registered handler for neuron: {neuron_name}")
        return True
    
    def unregister_handler(self, neuron_name: str) -> bool:
        """Remove a custom handler for a neuron."""
        if neuron_name in self.handlers:
            # Don't remove built-in handlers
            built_ins = {
                'external_stimulus', 'can_see_food', 'plant_proximity', 
                'threat_level', 'pursuing_food', 'is_sick', 'is_fleeing',
                'is_eating', 'is_sleeping', 'is_startled'
            }
            if neuron_name in built_ins:
                print(f"[BrainNeuronHooks] Cannot unregister built-in handler: {neuron_name}")
                return False
            
            del self.handlers[neuron_name]
            print(f"[BrainNeuronHooks] Unregistered handler for neuron: {neuron_name}")
            return True
        return False
    
    def get_registered_neurons(self) -> list:
        """Return list of all neurons with registered handlers."""
        return list(self.handlers.keys())
    
    def _get_plugin_handlers(self) -> Dict[str, Callable]:
        """
        Get any custom neuron handlers registered via the plugin manager.
        """
        if not hasattr(self.logic, 'plugin_manager'):
            return {}
        
        pm = self.logic.plugin_manager
        if hasattr(pm, 'get_neuron_handlers'):
            return pm.get_neuron_handlers()
        return {}

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
    
    def calculate_is_startled(self) -> float:
        if not hasattr(self.logic, 'squid'):
            return 0.0
        # Use same logic as above
        if hasattr(self.logic.squid, 'mental_state_manager') and self.logic.squid.mental_state_manager:
            return 100.0 if self.logic.squid.mental_state_manager.is_state_active('startled') else 0.0
        return 100.0 if getattr(self.logic.squid, 'status', '').lower() == 'startled' else 0.0

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
        
        # Merge plugin-registered handlers with built-in handlers
        all_handlers = {**self.handlers}
        plugin_handlers = self._get_plugin_handlers()
        all_handlers.update(plugin_handlers)
        
        for neuron_name in brain_widget.neuron_positions.keys():
            # Skip core stat neurons
            if neuron_name in ['hunger', 'happiness', 'cleanliness', 'sleepiness', 
                              'satisfaction', 'anxiety', 'curiosity']:
                continue
            
            # Check if neuron is marked as input type OR has a handler
            neuron_cfg = neurons_config.get(neuron_name, {})
            if neuron_cfg.get('type') == 'input' or neuron_name in all_handlers:
                # Call handler if exists, otherwise default background noise
                if neuron_name in all_handlers:
                    try:
                        input_values[neuron_name] = all_handlers[neuron_name]()
                    except Exception as e:
                        print(f"[BrainNeuronHooks] Error in handler for '{neuron_name}': {e}")
                        input_values[neuron_name] = 0.0
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
        # 1. Prefer the VisionWorker result (Most accurate/current)
        if hasattr(self.logic, 'latest_vision_result') and self.logic.latest_vision_result:
            return 100.0 if self.logic.latest_vision_result.can_see_food else 0.0
            
        # 2. Fallback to synchronous check (Only if worker hasn't reported yet)
        if not hasattr(self.logic, 'squid') or not self.logic.squid:
            return 0.0
            
        return 100.0 if self.logic.squid.can_see_food() else 0.0
    
    def calculate_plant_proximity(self) -> float:
        """
        Calculate activation based on squid's proximity to plant decorations.
        
        Returns:
            100.0 if squid body overlaps with any plant's bounding box (touching)
            0-99 scaled by distance to nearest plant edge if not touching
            0.0 if no plants exist
        """
        # 1. Prefer VisionWorker result for proximity (smoother/faster)
        if hasattr(self.logic, 'latest_vision_result') and self.logic.latest_vision_result:
            # The worker calculates a 0-100 proximity value automatically
            return getattr(self.logic.latest_vision_result, 'plant_proximity_value', 0.0)

        if not hasattr(self.logic, 'user_interface') or not hasattr(self.logic, 'squid'):
            return 0.0
        
        squid = self.logic.squid
        if not hasattr(squid, 'squid_item') or not squid.squid_item:
            return 0.0
        
        # Get squid's bounding rect in scene coordinates
        squid_rect = squid.squid_item.sceneBoundingRect()
        
        min_distance = float('inf')
        is_touching = False
        
        # Scan scene for plant decorations
        for item in self.logic.user_interface.scene.items():
            # Check if item has category attribute and is a plant
            if hasattr(item, 'category') and item.category == 'plant':
                plant_rect = item.sceneBoundingRect()
                
                # Check if squid overlaps with plant bounding box
                if squid_rect.intersects(plant_rect):
                    is_touching = True
                    break
                
                # Calculate distance from squid center to plant edge
                squid_center = squid_rect.center()
                
                # Find closest point on plant rect to squid center
                closest_x = max(plant_rect.left(), min(squid_center.x(), plant_rect.right()))
                closest_y = max(plant_rect.top(), min(squid_center.y(), plant_rect.bottom()))
                
                # Distance from squid center to that closest point
                dist = math.hypot(squid_center.x() - closest_x, squid_center.y() - closest_y)
                min_distance = min(min_distance, dist)
        
        # If touching any plant, return max activation
        if is_touching:
            return 100.0
        
        # If no plants found, return 0
        if min_distance == float('inf'):
            return 0.0
        
        # Scale activation by distance (closer = higher, max range ~300px)
        max_range = 300.0
        activation = max(0.0, 100.0 - (min_distance / max_range * 100.0))
        
        return activation
    
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


# Default sensors that have built-in handlers
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
    'is_startled',
)