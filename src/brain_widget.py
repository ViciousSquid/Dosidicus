import sys
import csv
import os
import time
import random
import numpy as np
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtGui import QPixmap, QFont
from datetime import datetime

# Import these from your project
from .personality import Personality
from .learning import LearningConfig

class BrainWidget(QtWidgets.QWidget):
    def __init__(self, config=None, debug_mode=False, tamagotchi_logic=None):
        self.config = config if config else LearningConfig()
        if not hasattr(self.config, 'hebbian'):
            self.config.hebbian = {
                'learning_interval': 30000,  # 30 seconds in milliseconds
                'weight_decay': 0.01,
                'active_threshold': 50  # Threshold for considering a neuron active
            }
        super().__init__()

        self.excluded_neurons = ['is_sick', 'is_eating', 'pursuing_food', 'direction', 'is_sleeping']
        self.hebbian_countdown_seconds = 30  # Default duration
        self.learning_active = False  # Track if learning is active
        self.config = config if config else LearningConfig()
        self.debug_mode = debug_mode  # Initialize debug_mode
        self.is_paused = False
        self.last_hebbian_time = time.time()
        self.tamagotchi_logic = tamagotchi_logic
        
        # Initialize neurogenesis data
        self.neurogenesis_data = {
        'novelty_counter': 0,
        'stress_counter': 0,
        'reward_counter': 0,
        'new_neurons': [],
        'last_neuron_time': time.time()
        }
        
        # Ensure neurogenesis config exists
        if not hasattr(self.config, 'neurogenesis'):
            self.config.neurogenesis = {
                'decay_rate': 0.95,  # Default decay rate if not specified
                'novelty_threshold': 3,
                'stress_threshold': 0.7,
                'reward_threshold': 0.6,
                'cooldown': 300,
                'highlight_duration': 5.0
            }
            
        # Now use self.config for all configuration
        self.neurogenesis_config = self.config.neurogenesis
        self.state = {
            'neurogenesis_active': False
        }
        # Add neurogenesis visualization tracking
        self.neurogenesis_highlight = {
            'neuron': None,
            'start_time': 0,
            'duration': 5.0  # seconds
        }
        self.neurogenesis_config = {
            'novelty_threshold': 3,
            'stress_threshold': 0.7,
            'cooldown': 300  # 5 minutes (in seconds)
        }
        self.state = {
            "hunger": 50,
            "happiness": 50,
            "cleanliness": 50,
            "sleepiness": 50,
            "satisfaction": 50,
            "anxiety": 50,
            "curiosity": 50,
            "is_sick": False,
            "is_eating": False,
            "is_sleeping": False,
            "pursuing_food": False,
            "direction": "up",
            "position": (0, 0)
        }
        self.original_neuron_positions = {
            "hunger": (321, 118),
            "happiness": (588, 86),
            "cleanliness": (881, 109),
            "sleepiness": (944, 366),
            "satisfaction": (320, 560),
            "anxiety": (584, 630),
            "curiosity": (768, 564)
        }
        self.neuron_positions = self.original_neuron_positions.copy()
        self.connections = self.initialize_connections()
        self.weights = {}  # Initialize an empty dictionary for weights
        self.initialize_weights()  # Call method to populate weights
        self.show_links = True
        self.frozen_weights = None
        self.history = []
        self.training_data = []
        self.associations = np.zeros((len(self.neuron_positions), len(self.neuron_positions)))
        self.learning_rate = 0.1
        self.capture_training_data_enabled = False
        self.dragging = False
        self.dragged_neuron = None
        self.drag_start_pos = None
        self.setMouseTracking(True)
        self.show_links = True
        self.show_weights = True

        # Neurogenesis configuration
        self.neurogenesis_config = config.neurogenesis if config else {
            'novelty_threshold': 3,
            'stress_threshold': 0.7,
            'reward_threshold': 0.6,
            'cooldown': 300,
            'highlight_duration': 5.0
        }
        
        self.state['neurogenesis_active'] = False

        # Define pastel colors for each state
        self.state_colors = {
            'is_sick': (255, 204, 204),  # Pastel red
            'is_eating': (204, 255, 204),  # Pastel green
            'is_sleeping': (204, 229, 255),  # Pastel blue
            'pursuing_food': (255, 229, 204),  # Pastel orange
            'direction': (229, 204, 255)  # Pastel purple
        }

    def stop_hebbian_learning(self):
        """Stop Hebbian learning immediately"""
        self.learning_active = False
        self.hebbian_countdown_seconds = 0
        print("++ Hebbian learning stopped")

    def start_hebbian_learning(self, duration_seconds=30):
        """Start Hebbian learning with a specified duration"""
        self.hebbian_countdown_seconds = duration_seconds
        self.learning_active = True
        self.is_paused = False
        print(f"++ Hebbian learning started for {duration_seconds} seconds")

    def get_neuron_value(self, value):
        """
        Convert a neuron value to a numerical format for Hebbian learning.

        Args:
            value: The value of the neuron, which can be int, float, bool, or str.

        Returns:
            float: The numerical value of the neuron.
        """
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, bool):
            return 100.0 if value else 0.0
        elif isinstance(value, str):
            # For string values (like 'direction'), return a default value
            return 75.0
        else:
            return 0.0
        
    def update_connection(self, neuron1, neuron2, value1, value2):
        """
        Update the connection weight between two neurons based on their activation values.

        Args:
            neuron1 (str): The name of the first neuron.
            neuron2 (str): The name of the second neuron.
            value1 (float): The activation value of the first neuron.
            value2 (float): The activation value of the second neuron.
        """
        pair = (neuron1, neuron2)
        reverse_pair = (neuron2, neuron1)

        # Check if the pair or its reverse exists in weights, if not, initialize it
        if pair not in self.weights and reverse_pair not in self.weights:
            self.weights[pair] = 0.0

        # Use the correct pair order
        use_pair = pair if pair in self.weights else reverse_pair

        # Update the weight
        prev_weight = self.weights[use_pair]
        weight_change = 0.01 * (value1 / 100) * (value2 / 100)  # Normalize values to 0-1 range
        new_weight = min(max(prev_weight + weight_change, -1), 1)  # Ensure weight stays in [-1, 1] range
        self.weights[use_pair] = new_weight

        # Debugging statement to check if update_connection is being called correctly
        print(f"Updated connection between {neuron1} and {neuron2}: {prev_weight} -> {new_weight}")

    def perform_hebbian_learning(self):
        if self.is_paused:
            return

        print("Performing Hebbian learning...")
        self.last_hebbian_time = time.time()

        # Determine which neurons are significantly active (excluding specified neurons)
        current_state = self.state  # Use the current state of the brain
        active_neurons = []
        for neuron, value in current_state.items():
            if neuron in self.excluded_neurons:
                continue
            if isinstance(value, (int, float)) and value > 50:
                active_neurons.append(neuron)
            elif isinstance(value, bool) and value:
                active_neurons.append(neuron)
            elif isinstance(value, str):
                active_neurons.append(neuron)

        print(f"Active neurons: {active_neurons}")

        # Include decoration effects in learning
        decoration_memories = {}
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'squid') and hasattr(self.tamagotchi_logic.squid, 'memory_manager'):
            decoration_memories = self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories('decorations')

        if isinstance(decoration_memories, dict):
            for decoration, effects in decoration_memories.items():
                for stat, boost in effects.items():
                    if stat in self.excluded_neurons:
                        continue
                    if isinstance(boost, (int, float)) and boost > 0:
                        if stat not in active_neurons:
                            active_neurons.append(stat)
        elif isinstance(decoration_memories, list):
            for memory in decoration_memories:
                for stat, boost in memory.get('effects', {}).items():
                    if stat in self.excluded_neurons:
                        continue
                    if isinstance(boost, (int, float)) and boost > 0:
                        if stat not in active_neurons:
                            active_neurons.append(stat)

        # If less than two neurons are active, no learning occurs
        if len(active_neurons) < 2:
            print("Not enough active neurons for Hebbian learning")
            return

        # Perform learning for a random subset of active neuron pairs
        sample_size = min(5, len(active_neurons) * (len(active_neurons) - 1) // 2)
        sampled_pairs = random.sample([(i, j) for i in range(len(active_neurons)) for j in range(i + 1, len(active_neurons))], sample_size)
        
        print(f"Learning on {sample_size} random neuron pairs")

        for i, j in sampled_pairs:
            neuron1 = active_neurons[i]
            neuron2 = active_neurons[j]
            value1 = self.get_neuron_value(current_state.get(neuron1, 50))  # Default to 50 if not in current_state
            value2 = self.get_neuron_value(current_state.get(neuron2, 50))
            print(f"Updating connection: {neuron1}({value1:.1f}) - {neuron2}({value2:.1f})")
            self.update_connection(neuron1, neuron2, value1, value2)

        # Update the brain visualization
        self.update()

        # Reset the countdown after learning
        if hasattr(self, 'hebbian_countdown_seconds'):
            # Get interval from config, defaulting to 30 seconds
            if hasattr(self, 'config') and hasattr(self.config, 'hebbian'):
                interval_ms = self.config.hebbian.get('learning_interval', 30000)
            else:
                interval_ms = 30000
            self.hebbian_countdown_seconds = int(interval_ms / 1000)
            print(f"Reset countdown to {self.hebbian_countdown_seconds} seconds")


    def resizeEvent(self, event):
        """Handle window resize events - startles squid and enforces minimum size"""
        super().resizeEvent(event)
        
        # Only trigger startle if we're actually resizing (not just moving)
        old_size = event.oldSize()
        if (old_size.isValid() and 
            hasattr(self, 'tamagotchi_logic') and 
            self.tamagotchi_logic):
            
            new_size = event.size()
            width_change = abs(new_size.width() - old_size.width())
            height_change = abs(new_size.height() - old_size.height())
            
            # Only startle if change is significant (>50px)
            if width_change > 50 or height_change > 50:
                # Check if first resize
                if not hasattr(self, '_has_resized_before'):
                    source = "first_resize"
                    self._has_resized_before = True
                else:
                    source = "window_resize"
                
                self.tamagotchi_logic.startle_squid(source=source)
                
                if self.debug_mode:
                    print(f"Squid startled by {source}")
        
        # Enforce minimum window size (1280x900)
        min_width, min_height = 1280, 900
        if event.size().width() < min_width or event.size().height() < min_height:
            self.resize(
                max(event.size().width(), min_width),
                max(event.size().height(), min_height)
            )

    def closeEvent(self, event):
        """Handle window close event - save state and clean up resources"""
        if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
            # Save current brain state
            try:
                brain_state = self.save_brain_state()
                with open('last_brain_state.json', 'w') as f:
                    json.dump(brain_state, f)
            except Exception as e:
                print(f"Error saving brain state: {e}")

            # Clean up timers
            if hasattr(self, 'hebbian_timer'):
                self.hebbian_timer.stop()
            if hasattr(self, 'countdown_timer'):
                self.countdown_timer.stop()
            if hasattr(self, 'memory_update_timer'):
                self.memory_update_timer.stop()

        # Close any child windows
        if hasattr(self, '_inspector') and self._inspector:
            self._inspector.close()
        if hasattr(self, 'log_window') and self.log_window:
            self.log_window.close()

        # Accept the close event
        event.accept()

    def save_brain_state(self):
        return {
            'weights': self.weights,
            'neuron_positions': self.neuron_positions
        }

    def load_brain_state(self, state):
        self.weights = state['weights']
        self.neuron_positions = state['neuron_positions']

    def initialize_connections(self):
        connections = []
        neurons = list(self.neuron_positions.keys())
        for i in range(len(neurons)):
            for j in range(i+1, len(neurons)):
                connections.append((neurons[i], neurons[j]))
        return connections

    def initialize_weights(self):
        neurons = list(self.neuron_positions.keys())
        for i in range(len(neurons)):
            for j in range(i+1, len(neurons)):
                self.weights[(neurons[i], neurons[j])] = random.uniform(-1, 1)

    def get_neuron_count(self):
        """Returns the neuron count for display"""
        total_neurons = len(self.neuron_positions)
        # Always display 3 less neurons than actually exist
        # To account for the left side state indicators
        displayed_count = max(0, total_neurons - 3)
        return displayed_count
    
    def get_edge_count(self):
        return len(self.connections)
    
    def get_weakest_connections(self, n=3):
        """Return the n weakest connections by absolute weight"""
        return sorted(self.weights.items(), key=lambda x: abs(x[1]))[:n]

    def get_extreme_neurons(self, n=3):
        """Return neurons deviating most from baseline (50)"""
        neurons = [(k, v) for k, v in self.state.items() 
                if isinstance(v, (int, float)) and k in self.neuron_positions]
        most_positive = sorted(neurons, key=lambda x: -x[1])[:n]
        most_negative = sorted(neurons, key=lambda x: x[1])[:n]
        return {'overactive': most_positive, 'underactive': most_negative}

    def get_unbalanced_connections(self, n=3):
        """Return connections with largest weight disparities"""
        unbalanced = []
        for (a, b), w1 in self.weights.items():
            w2 = self.weights.get((b, a), 0)
            if abs(w1 - w2) > 0.3:  # Only consider significant differences
                unbalanced.append(((a, b), (w1, w2), abs(w1 - w2)))
        return sorted(unbalanced, key=lambda x: -x[2])[:n]
    
    def calculate_network_health(self):
        """Calculate network health based on connection weights and neuron activity"""
        total_weight = sum(abs(w) for w in self.weights.values())
        avg_weight = total_weight / len(self.weights) if self.weights else 0
        
        # Health is based on average connection strength (0-100 scale)
        health = min(100, max(0, avg_weight * 100))
        return health

    def calculate_network_efficiency(self):
        """Calculate network efficiency based on connection distribution"""
        if not self.connections:
            return 0
            
        # Count reciprocal connections
        reciprocal_count = 0
        for conn in self.connections:
            reverse_conn = (conn[1], conn[0])
            if reverse_conn in self.connections:
                reciprocal_count += 1
                
        # Efficiency is based on percentage of reciprocal connections
        efficiency = (reciprocal_count / len(self.connections)) * 100
        return efficiency

    def update_state(self, new_state):
        if self.is_paused:
            return
        """Update the brain state with new values, handling both Hebbian learning and neurogenesis"""
        # Update only the keys that exist in self.state and are allowed to be modified
        excluded = ['is_sick', 'is_eating', 'pursuing_food', 'direction']
        for key in self.state.keys():
            if key in new_state and key not in excluded:
                self.state[key] = new_state[key]
        
        # Initialize missing counters if they don't exist
        if 'stress_counter' not in self.neurogenesis_data:
            self.neurogenesis_data['stress_counter'] = 0
        if 'reward_counter' not in self.neurogenesis_data:
            self.neurogenesis_data['reward_counter'] = 0
            
        # Ensure neurogenesis config exists with all required parameters
        if not hasattr(self.config, 'neurogenesis'):
            self.config.neurogenesis = {}
        if 'decay_rate' not in self.config.neurogenesis:
            self.config.neurogenesis['decay_rate'] = 0.95  # Default decay rate
        
        # Track neurogenesis triggers if they exist in the new state
        neurogenesis_triggers = {
            'novelty_exposure': new_state.get('novelty_exposure', 0),
            'sustained_stress': new_state.get('sustained_stress', 0),
            'recent_rewards': new_state.get('recent_rewards', 0)
        }
        
        # Apply weight decay to prevent weights from growing too large
        current_time = time.time()
        if hasattr(self, 'last_weight_decay_time'):
            if current_time - self.last_weight_decay_time > 60:  # Decay every minute
                for conn in self.weights:
                    decay_factor = 1.0 - self.config.hebbian.get('weight_decay', 0.01)
                    self.weights[conn] *= decay_factor
                self.last_weight_decay_time = current_time
        else:
            self.last_weight_decay_time = current_time
        
        # Update weights based on current activity
        self.update_weights()
        
        # Check for neurogenesis conditions if we have a Hebbian learning reference
        if hasattr(self, 'hebbian_learning') and self.hebbian_learning:
            # Check if neurogenesis should occur
            if self.hebbian_learning.check_neurogenesis_conditions(new_state):
                # Determine which trigger was strongest
                strongest_trigger = max(
                    ['novelty', 'stress', 'reward'],
                    key=lambda x: neurogenesis_triggers[f"{x}_exposure"] if x != 'reward' else neurogenesis_triggers['recent_rewards']
                )
                
                # Create new neuron
                new_neuron_name = self.hebbian_learning.create_new_neuron(strongest_trigger, new_state)
                
                # Update visualization
                self.neurogenesis_highlight = {
                    'neuron': new_neuron_name,
                    'start_time': time.time(),
                    'duration': self.neurogenesis_config.get('highlight_duration', 5.0)
                }
                
                # Add to tracking data
                if new_neuron_name not in self.neurogenesis_data['new_neurons']:
                    self.neurogenesis_data['new_neurons'].append(new_neuron_name)
                    self.neurogenesis_data['last_neuron_time'] = time.time()
                    
                    # Add initial state for the new neuron
                    self.state[new_neuron_name] = 50  # Mid-range activation
                    
                    # Add to connections
                    neurons = list(self.neuron_positions.keys())
                    for neuron in neurons:
                        if neuron != new_neuron_name:
                            self.weights[(neuron, new_neuron_name)] = random.uniform(-0.3, 0.3)
                            self.weights[(new_neuron_name, neuron)] = random.uniform(-0.3, 0.3)
        
        # Update the visualization
        self.update()
        
        # Capture training data if enabled
        if self.capture_training_data_enabled:
            self.capture_training_data(new_state)
        
        # Update neurogenesis counters with decay
        self.neurogenesis_data['novelty_counter'] *= self.config.neurogenesis.get('decay_rate', 0.95)
        self.neurogenesis_data['stress_counter'] *= self.config.neurogenesis.get('decay_rate', 0.95)
        self.neurogenesis_data['reward_counter'] *= self.config.neurogenesis.get('decay_rate', 0.95)
  
    def check_neurogenesis(self, state):
        """Check conditions for neurogenesis and create new neurons when triggered.
        
        Args:
            state (dict): Current brain state containing trigger values
            
        Returns:
            bool: True if any neurons were created, False otherwise
        """
        current_time = time.time()
        
        # DEBUG: Bypass all checks when forced
        if state.get('_debug_forced_neurogenesis', False):
            # Create a new neuron with a timestamp-based name
            new_name = f"debug_neuron_{int(current_time)}"
            
            # Position near center of existing network
            if self.neuron_positions:
                center_x = sum(pos[0] for pos in self.neuron_positions.values()) / len(self.neuron_positions)
                center_y = sum(pos[1] for pos in self.neuron_positions.values()) / len(self.neuron_positions)
            else:
                center_x, center_y = 600, 300  # Default center
            
            self.neuron_positions[new_name] = (
                center_x + random.randint(-100, 100),
                center_y + random.randint(-100, 100)
            )
            
            # Initialize state
            self.state[new_name] = 80  # High initial activation
            self.state_colors[new_name] = (200, 200, 255)  # Light blue for debug neurons
            
            # Create default connections
            for existing in self.neuron_positions:
                if existing != new_name:
                    self.weights[(new_name, existing)] = random.uniform(-0.5, 0.5)
                    if (existing, new_name) not in self.weights:
                        self.weights[(existing, new_name)] = random.uniform(-0.5, 0.5)
            
            # Update tracking
            self.neurogenesis_data['new_neurons'].append(new_name)
            self.neurogenesis_data['last_neuron_time'] = current_time
            
            print(f"DEBUG: Created neuron '{new_name}' at {self.neuron_positions[new_name]}")
            self.update()
            return True
        
        # Normal operation checks
        if current_time - self.neurogenesis_data['last_neuron_time'] > self.neurogenesis_config['general']['cooldown']:
            created = False
            
            # Novelty check with personality modifier
            if (state.get('novelty_exposure', 0) > 
                self.get_neurogenesis_threshold('novelty') * 
                self.get_personality_modifier(state.get('personality'), 'novelty')):
                self._create_neuron_internal('novelty', state)
                created = True
                
            # Stress check with personality modifier
            if (state.get('sustained_stress', 0) > 
                self.get_neurogenesis_threshold('stress') * 
                self.get_personality_modifier(state.get('personality'), 'stress')):
                self._create_neuron_internal('stress', state)
                created = True
                
            # Reward check
            if (state.get('recent_rewards', 0) > 
                self.get_neurogenesis_threshold('reward')):
                self._create_neuron_internal('reward', state)
                created = True
                
            return created
        return False
    
    def get_neurogenesis_threshold(self, trigger_type):
        """Safely get threshold for a trigger type with fallback defaults"""
        try:
            return self.neurogenesis_config['triggers'][trigger_type]['threshold']
        except KeyError:
            # Fallback defaults if config is missing
            defaults = {
                'novelty': 0.7,
                'stress': 0.8, 
                'reward': 0.6
            }
            return defaults.get(trigger_type, 1.0)  # High threshold if type unknown
    
    def stimulate_brain(self, stimulation_values):
        """Handle brain stimulation with validation"""
        if not isinstance(stimulation_values, dict):
            return
        
        # Only update allowed states
        filtered_update = {}
        for key in self.state.keys():
            if key in stimulation_values:
                filtered_update[key] = stimulation_values[key]
        
        self.update_state(filtered_update)

    def _create_neuron_internal(self, neuron_type, trigger_data):
        """Internal neuron creation with guaranteed success"""
        base_name = {'novelty': 'novel', 'stress': 'defense', 'reward': 'reward'}[neuron_type]
        new_name = f"{base_name}_{len(self.neurogenesis_data['new_neurons'])}"
        
        # Position near most active connected neuron
        base_x, base_y = random.choice(list(self.neuron_positions.values()))
        self.neuron_positions[new_name] = (
            base_x + random.randint(-50, 50),
            base_y + random.randint(-50, 50)
        )
        
        # Initialize state
        self.state[new_name] = 50
        self.state_colors[new_name] = {
            'novelty': (255, 255, 150),
            'stress': (255, 150, 150),
            'reward': (150, 255, 150)
        }[neuron_type]
        
        # Add to tracking
        self.neurogenesis_data['new_neurons'].append(new_name)
        self.neurogenesis_data['last_neuron_time'] = time.time()
        
        # Force immediate visual update
        self.update()
        return new_name

    def update_weights(self):
        if self.frozen_weights is not None:
            return
        for conn in self.connections:
            self.weights[conn] += random.uniform(-0.1, 0.1)
            self.weights[conn] = max(-1, min(1, self.weights[conn]))

    def freeze_weights(self):
        self.frozen_weights = self.weights.copy()

    def unfreeze_weights(self):
        self.frozen_weights = None

    def strengthen_connection(self, neuron1, neuron2, amount):
        pair = (neuron1, neuron2)
        reverse_pair = (neuron2, neuron1)

        # Check if the pair or its reverse exists in weights, if not, initialize it
        if pair not in self.weights and reverse_pair not in self.weights:
            self.weights[pair] = 0.0

        # Use the correct pair order
        use_pair = pair if pair in self.weights else reverse_pair

        # Update the weight
        self.weights[use_pair] += amount
        self.weights[use_pair] = max(-1, min(1, self.weights[use_pair]))  # Ensure weight stays in [-1, 1] range

        # Update the brain visualization
        self.update()

    
    def create_neuron(self, neuron_type, trigger_data):
        """Add after all other methods"""
        base_name = {
            'novelty': 'novel',
            'stress': 'defense',
            'reward': 'reward'
        }[neuron_type]
        
        new_name = f"{base_name}_{len(self.neurogenesis_data['new_neurons'])}"
        
        # Position near most active connected neuron
        active_neurons = sorted(
            [(k,v) for k,v in self.state.items() if isinstance(v, (int, float))],
            key=lambda x: x[1],
            reverse=True
        )
        base_x, base_y = self.neuron_positions[active_neurons[0][0]] if active_neurons else (600, 300)
        
        self.neuron_positions[new_name] = (
            base_x + random.randint(-50, 50),
            base_y + random.randint(-50, 50)
        )

        # Set highlight for visualization
        self.neurogenesis_highlight = {
            'neuron': new_name,
            'start_time': time.time(),
            'duration': 5.0
        }
        
        self.update()  # Force immediate redraw
        
        # Initialize state and connections
        self.state[new_name] = 50
        self.state_colors[new_name] = {
            'novelty': (255, 255, 150),  # Pale yellow
            'stress': (255, 150, 150),    # Light red
            'reward': (150, 255, 150)     # Light green
        }[neuron_type]
        
        # Default connections
        default_weights = {
            'novelty': {'curiosity': 0.6, 'anxiety': -0.4},
            'stress': {'anxiety': -0.7, 'happiness': 0.3},
            'reward': {'satisfaction': 0.8, 'happiness': 0.5}
        }
        
        for target, weight in default_weights[neuron_type].items():
            self.weights[(new_name, target)] = weight
            self.weights[(target, new_name)] = weight * 0.5  # Weaker reciprocal
            
        self.neurogenesis_data['new_neurons'].append(new_name)
        self.neurogenesis_data['last_neuron_time'] = time.time()
        
        return new_name

    def capture_training_data(self, state):
        training_sample = [state[neuron] for neuron in self.neuron_positions.keys()]
        self.training_data.append(training_sample)
        print("Captured training data:", training_sample)

    def train_hebbian(self):
        print("Starting Hebbian training...")
        print("Training data:", self.training_data)

        for sample in self.training_data:
            for i in range(len(sample)):
                for j in range(i+1, len(sample)):
                    self.associations[i][j] += self.learning_rate * sample[i] * sample[j]
                    self.associations[j][i] = self.associations[i][j]

        print("Association strengths after training:", self.associations)
        self.training_data = []

    def get_association_strength(self, neuron1, neuron2):
        idx1 = list(self.neuron_positions.keys()).index(neuron1)
        idx2 = list(self.neuron_positions.keys()).index(neuron2)
        return self.associations[idx1][idx2]
    
    def draw_connections(self, painter, scale):
        for conn in self.connections:
            start = self.neuron_positions[conn[0]]
            end = self.neuron_positions[conn[1]]
            weight = self.weights[conn]

            # Only draw if links are visible
            if not self.show_links:
                continue

            # Determine line color based on weight sign
            color = QtGui.QColor(0, int(255 * abs(weight)), 0) if weight > 0 else QtGui.QColor(int(255 * abs(weight)), 0, 0)

            # Determine line thickness and style based on weight magnitude
            if abs(weight) < 0.1:  # Very weak connection
                pen_style = QtCore.Qt.DotLine
                line_width = 1 * scale
            elif abs(weight) < 0.3:  # Weak connection
                pen_style = QtCore.Qt.SolidLine
                line_width = 1 * scale
            elif abs(weight) < 0.6:  # Moderate connection
                pen_style = QtCore.Qt.SolidLine
                line_width = 2 * scale
            else:  # Strong connection
                pen_style = QtCore.Qt.SolidLine
                line_width = 3 * scale

            # Create pen with appropriate style and width
            painter.setPen(QtGui.QPen(color, line_width, pen_style))
            painter.drawLine(start[0], start[1], end[0], end[1])

            # Add weight text with scaling and visibility threshold
            if self.show_weights and abs(weight) > 0.1:  # Modified this line
                midpoint = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)

                # Increase the area for drawing the weights
                text_area_width = 80
                text_area_height = 22

                # Adjust the font size based on the scale with a maximum font size
                max_font_size = 12
                font_size = max(8, min(max_font_size, int(8 * scale)))
                font = painter.font()
                font.setPointSize(font_size)
                painter.setFont(font)

                # Draw black background rectangle
                painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
                painter.drawRect(midpoint[0] - text_area_width // 2, midpoint[1] - text_area_height // 2,
                                text_area_width, text_area_height)

                # Draw the weight text on top of the black background
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))  # White text color
                painter.drawText(midpoint[0] - text_area_width // 2, midpoint[1] - text_area_height // 2,
                                text_area_width, text_area_height,
                                QtCore.Qt.AlignCenter, f"{weight:.2f}")


    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        scale_x = self.width() / 1200
        scale_y = self.height() / 600
        scale = min(scale_x, scale_y)
        painter.scale(scale, scale)

        painter.fillRect(QtCore.QRectF(0, 0, 1024, 768), QtGui.QColor(240, 240, 240))

        # Draw metrics at top
        metrics_font = QtGui.QFont()
        metrics_font.setPointSize(10)
        metrics_font.setBold(True)
        painter.setFont(metrics_font)
        
        # Calculate metrics
        neuron_count = self.get_neuron_count()
        edge_count = self.get_edge_count()
        health = self.calculate_network_health()
        efficiency = self.calculate_network_efficiency()
        
        # Draw metrics in top bar
        metrics_text = f"Neurons: {neuron_count}    Connections: {edge_count}    Network Health: {health:.1f}%"
        metrics_rect = QtCore.QRectF(0, 5, self.width(), 25)

        # Create and configure font
        metrics_font = painter.font()
        metrics_font.setPointSize(8)  # Smaller font size
        metrics_font.setBold(False)   # Remove bold
        painter.setFont(metrics_font)

        # Draw the text
        painter.setPen(QtGui.QColor(0, 0, 0))
        painter.drawText(metrics_rect, QtCore.Qt.AlignCenter, metrics_text)
        
        # Draw "Neurons" title below metrics
        title_font = painter.font()
        title_font.setPointSize(12)
        painter.setFont(title_font)
        #painter.drawText(QtCore.QRectF(0, 30, self.width(), 30), QtCore.Qt.AlignCenter, "Neurons")

        # Draw all neurons including new ones
        self.draw_neurons(painter, scale)

        # Highlight dragged neuron
        if self.dragging and self.dragged_neuron:
            pos = self.neuron_positions[self.dragged_neuron]
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 3))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(QtCore.QPointF(pos[0], pos[1]), 30, 30)
        
        # Draw highlight for recently created neurons
        self.draw_neurogenesis_highlights(painter, scale)

        if self.show_links:
            self.draw_connections(painter, scale)

        def draw_neuron_highlight(self, painter, x, y):
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 3))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(x - 35, y - 35, 70, 70)

    def draw_neurons(self, painter, scale):
        # Define original neurons from original_neuron_positions
        original_neurons = list(self.original_neuron_positions.keys())
        
        # Binary state neurons to add to far left
        binary_neurons = {
            'is_eating': (50, 300),
            'pursuing_food': (50, 400),
            'is_fleeing': (50, 500)
        }
        
        # Merge positions
        self.neuron_positions.update(binary_neurons)
        
        # Draw labels beside binary neurons
        #for name, pos in binary_neurons.items():
        #    # Draw label before drawing the neuron
        #    label_font = painter.font()
        #    label_font.setPointSize(int(8 * scale))
        #    painter.setFont(label_font)
        #    painter.drawText(pos[0] + 50, pos[1] + 10, name)
        
        # Draw all neurons that exist in current positions
        for name, pos in self.neuron_positions.items():
            if name in original_neurons:
                # Original circular/square neurons
                if name in ["hunger", "happiness", "cleanliness", "sleepiness"]:
                    self.draw_circular_neuron(painter, pos[0], pos[1], 
                                            self.state[name], name, scale=scale)
                else:
                    self.draw_square_neuron(painter, pos[0], pos[1], 
                                        self.state[name], name, scale=scale)
            elif name in binary_neurons:
                # Binary state neurons as small rectangles
                self.draw_binary_neuron(painter, pos[0], pos[1], 
                                        self.state.get(name, False), name, scale=scale)
            else:
                # Neurogenesis-created neurons (triangular)
                self.draw_triangular_neuron(painter, pos[0], pos[1], 
                                        self.state[name], name, scale=scale)
                
    def draw_binary_neuron(self, painter, x, y, value, label, color=(0, 255, 0), scale=1.0):
        # Binary state: Green for True, Red for False
        color = (0, 255, 0) if value else (255, 0, 0)
        
        painter.setBrush(QtGui.QBrush(QtGui.QColor(*color)))
        
        # Draw a smaller rectangular indicator
        painter.drawRect(x - 15, y - 15, 30, 30)
        
        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(int(6 * scale))  # Convert scale to integer
        painter.setFont(font)
        painter.drawText(x - 50, y + 30, 100, 20, QtCore.Qt.AlignCenter, label)

    def draw_circular_neuron(self, painter, x, y, value, label, color=(0, 255, 0), binary=False, scale=1.0):
        if binary:
            color = (0, 255, 0) if value else (255, 0, 0)
        else:
            color = QtGui.QBrush(QtGui.QColor(*color))

        painter.setBrush(color)
        painter.drawEllipse(x - 25, y - 25, 50, 50)

        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(x - 50, y + 30, 100, 20, QtCore.Qt.AlignCenter, label)

    def draw_triangular_neuron(self, painter, x, y, value, label, scale=1.0):
        # Determine color based on neuron type
        if label.startswith('defense'):
            color = QtGui.QColor(255, 150, 150)  # Light red
        elif label.startswith('novel'):
            color = QtGui.QColor(255, 255, 150)  # Pale yellow
        else:  # reward
            color = QtGui.QColor(150, 255, 150)  # Light green

        painter.setBrush(color)

        # Create triangle
        triangle = QtGui.QPolygonF()
        size = 25 * scale
        triangle.append(QtCore.QPointF(x - size, y + size))
        triangle.append(QtCore.QPointF(x + size, y + size))
        triangle.append(QtCore.QPointF(x, y - size))

        painter.drawPolygon(triangle)

        # Draw label with integer coordinates
        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(int(8 * scale))  # Convert to integer
        painter.setFont(font)
        painter.drawText(int(x - 30 * scale), int(y + 40 * scale),
                        int(60 * scale), int(20 * scale),
                        QtCore.Qt.AlignCenter, label)

    def show_diagnostic_report(self):
        """Show the diagnostic report dialog by accessing the brain widget"""
        if hasattr(self, 'brain_widget'):
            self.brain_widget.show_diagnostic_report()
        else:
            print("Error: Brain widget not initialized")
        
    def draw_neurogenesis_highlights(self, painter, scale):
        if (self.neurogenesis_highlight['neuron'] and 
            time.time() - self.neurogenesis_highlight['start_time'] < self.neurogenesis_highlight['duration']):
            
            pos = self.neuron_positions.get(self.neurogenesis_highlight['neuron'])
            if pos:
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 3 * scale))
                painter.setBrush(QtCore.Qt.NoBrush)
                radius = 40 * scale
                painter.drawEllipse(pos[0] - radius, pos[1] - radius, 
                                   radius * 2, radius * 2)

    def draw_square_neuron(self, painter, x, y, value, label, color=(0, 255, 0), binary=False, scale=1.0):
        if binary:
            color = (0, 255, 0) if value else (255, 0, 0)
        else:
            color = QtGui.QBrush(QtGui.QColor(*color))

        painter.setBrush(color)
        painter.drawRect(x - 25, y - 25, 50, 50)

        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(x - 50, y + 30, 100, 20, QtCore.Qt.AlignCenter, label)


    def toggle_links(self, state):
        self.show_links = state == QtCore.Qt.Checked
        self.update()

    def toggle_weights(self, state):  # Add this new method
        self.show_weights = state == QtCore.Qt.Checked
        self.update()

    def toggle_capture_training_data(self, state):
        self.capture_training_data_enabled = state

    def mousePressEvent(self, event):
        # Calculate scale factors
        scale_x = self.width() / 1200
        scale_y = self.height() / 600
        scale = min(scale_x, scale_y)
        
        # Convert click position to widget coordinates
        click_pos = event.pos()
        
        # Existing neuron dragging logic
        if event.button() == QtCore.Qt.LeftButton:
            for name, pos in self.neuron_positions.items():
                # Pass the scale to the click detection method
                if self._is_click_on_neuron(click_pos, pos, scale):
                    self.dragging = True
                    self.dragged_neuron = name
                    self.drag_start_pos = click_pos
                    self.update()
                    break

    def show_diagnostic_report(self):
        dialog = DiagnosticReportDialog(self, self.parent())
        dialog.exec_()

    def mouseMoveEvent(self, event):
        if self.dragging and self.dragged_neuron:
            delta = event.pos() - self.drag_start_pos
            old_pos = self.neuron_positions[self.dragged_neuron]
            self.neuron_positions[self.dragged_neuron] = (
                old_pos[0] + delta.x(),
                old_pos[1] + delta.y()
            )
            self.drag_start_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton and self.dragging:
            self.dragging = False
            self.dragged_neuron = None
            self.update()

    def _is_click_on_neuron(self, point, neuron_pos, scale):
        """Check if click is within neuron bounds, accounting for scaling"""
        neuron_x, neuron_y = neuron_pos
        # Scale the neuron position to match the visual representation
        scaled_x = neuron_x * scale
        scaled_y = neuron_y * scale
        # Use scaled neuron size (25 was original radius)
        return (abs(scaled_x - point.x()) <= 25 * scale and 
                abs(scaled_y - point.y()) <= 25 * scale)

    def is_point_inside_neuron(self, point, neuron_pos, scale):
        neuron_x, neuron_y = neuron_pos
        scaled_x = neuron_x * scale
        scaled_y = neuron_y * scale
        return ((scaled_x - 25 * scale) <= point.x() <= (scaled_x + 25 * scale) and 
                (scaled_y - 25 * scale) <= point.y() <= (scaled_y + 25 * scale))

    def reset_positions(self):
        self.neuron_positions = self.original_neuron_positions.copy()
        self.update()