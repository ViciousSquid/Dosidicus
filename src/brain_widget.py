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
        neuronClicked = QtCore.pyqtSignal(str)
        self.config = config if config else LearningConfig()
        self.debug_mode = debug_mode  # Initialize debug_mode
        self.neuronClicked = QtCore.pyqtSignal(str)
        self.is_paused = False
        self.last_hebbian_time = time.time()
        self.tamagotchi_logic = tamagotchi_logic
        
        # Neural communication tracking system
        self.communication_events = {}
        self.communication_highlight_duration = 0.5
        self.weight_change_events = {}
        self.activity_duration = 0.5
        
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
        
        # Neural state initialization
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
        
        # Neuron position configuration
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
        
        # Initialize communication events for all neurons
        for neuron in self.neuron_positions.keys():
            self.communication_events[neuron] = 0
        
        # Connection and weight initialization
        self.connections = self.initialize_connections()
        self.weights = {}  # Initialize empty dictionary for weights
        self.initialize_weights()  # Populate weights
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
        
        # Visual state colors
        self.state_colors = {
            'is_sick': (255, 204, 204),  # Pastel red
            'is_eating': (204, 255, 204),  # Pastel green
            'is_sleeping': (204, 229, 255),  # Pastel blue
            'pursuing_food': (255, 229, 204),  # Pastel orange
            'direction': (229, 204, 255)  # Pastel purple
        }
        

    def set_debug_mode(self, enabled):
        """Properly handle debug mode changes"""
        old_mode = getattr(self, 'debug_mode', False)
        self.debug_mode = enabled
        
        # Only take action if mode has changed
        if old_mode != enabled:
            print(f"BrainWidget debug mode {'enabled' if enabled else 'disabled'}")
            # Force a redraw to reflect any visual changes
            self.update()

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
        current_time = time.time()
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

         # Record weight change time for both neurons
        if abs(new_weight - prev_weight) > 0.001:  # Only if significant change
            self.weight_change_events[neuron1] = current_time
            self.weight_change_events[neuron2] = current_time
            self.update()

        # Debugging statement to check if update_connection is being called correctly
        print(f"\x1b[42mUpdated connection\x1b[0m between {neuron1} and {neuron2}: \x1b[31m {prev_weight} ➡️ \x1b[32m {new_weight} \x1b[0m")

        # Record communication time for both neurons
        current_time = time.time()
        self.communication_events[neuron1] = current_time
        self.communication_events[neuron2] = current_time


    def perform_hebbian_learning(self):
        if self.is_paused:
            return

        print("  ")
        print("\x1b[44mPerforming Hebbian learning...\x1b[0m")
        self.last_hebbian_time = time.time()

        # Clean up old weight change events
        current_time = time.time()
        self.weight_change_events = {
            k: v for k, v in self.weight_change_events.items()
            if (current_time - v) < self.activity_duration
        }

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
        
        print(f">> Learning on {sample_size} random neuron pairs")

        for i, j in sampled_pairs:
            neuron1 = active_neurons[i]
            neuron2 = active_neurons[j]
            value1 = self.get_neuron_value(current_state.get(neuron1, 50))  # Default to 50 if not in current_state
            value2 = self.get_neuron_value(current_state.get(neuron2, 50))
            self.update_connection(neuron1, neuron2, value1, value2)

        # Update the brain visualization
        self.update()

        # Reset the countdown after learning
        if hasattr(self, 'hebbian_countdown_seconds'):
            # Get interval from config, defaulting to 40 seconds
            if hasattr(self, 'config') and hasattr(self.config, 'hebbian'):
                interval_ms = self.config.hebbian.get('learning_interval', 40000)
            else:
                interval_ms = 40000
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

        # Explicitly check and update binary state neurons
        if 'is_eating' in new_state:
            self.state['is_eating'] = new_state['is_eating']
        if 'pursuing_food' in new_state:
            self.state['pursuing_food'] = new_state['pursuing_food']
        if 'is_fleeing' in new_state:
            self.state['is_fleeing'] = new_state['is_fleeing']

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

        # Check for forced neurogenesis
        if new_state.get('_debug_forced_neurogenesis', False):
            self.check_neurogenesis(new_state)

        # Track neurogenesis triggers if they exist in the new state
        neurogenesis_triggers = {
            'novelty_exposure': new_state.get('novelty_exposure', 0),
            'sustained_stress': new_state.get('sustained_stress', 0),
            'recent_rewards': new_state.get('recent_rewards', 0)
        }

        # Special handling for forced neurogenesis
        if new_state.get('_debug_forced_neurogenesis', False):
            created = self.check_neurogenesis(new_state)
            if created:
                self.update()  # Force immediate visual update
                return

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
        """Check conditions for neurogenesis and create new neurons when triggered."""
        current_time = time.time()
        
        # Print debug information for transparency
        if self.debug_mode:
            print("Neurogenesis check starting...")
            print(f"Current triggers: novelty={state.get('novelty_exposure', 0)}, stress={state.get('sustained_stress', 0)}, reward={state.get('recent_rewards', 0)}")
            print(f"Thresholds: novelty={self.neurogenesis_config.get('novelty_threshold', 3)}, stress={self.neurogenesis_config.get('stress_threshold', 0.7)}, reward={self.neurogenesis_config.get('reward_threshold', 0.6)}")
            print(f"Time since last neuron: {current_time - self.neurogenesis_data.get('last_neuron_time', 0)} seconds")
            print(f"Cooldown period: {self.neurogenesis_config.get('cooldown', 300)} seconds")
        
        # Check cooldown period (simplified structure)
        cooldown = self.neurogenesis_config.get('cooldown', 300)  # Default 5 minutes
        if current_time - self.neurogenesis_data.get('last_neuron_time', 0) <= cooldown:
            if self.debug_mode:
                print(f"Neurogenesis blocked by cooldown - {cooldown - (current_time - self.neurogenesis_data.get('last_neuron_time', 0)):.1f} seconds remaining")
            return False
        
        # Define personality modifier fallback
        def get_personality_modifier(personality, trigger_type):
            # Simple modifiers based on personality
            modifiers = {
                'timid': {'novelty': 1.2, 'stress': 0.8},
                'adventurous': {'novelty': 0.8, 'stress': 1.2},
                'greedy': {'novelty': 1.0, 'stress': 1.0},
                'stubborn': {'novelty': 1.1, 'stress': 0.9}
            }
            # Handle personality object or string
            personality_str = getattr(personality, 'value', str(personality)).lower()
            return modifiers.get(personality_str, {}).get(trigger_type, 1.0)
        
        # Use class method if it exists, otherwise use fallback
        personality_modifier = getattr(self, 'get_personality_modifier', get_personality_modifier)
        
        # Simplified threshold checks - direct access to config values
        novelty_threshold = self.neurogenesis_config.get('novelty_threshold', 3)
        stress_threshold = self.neurogenesis_config.get('stress_threshold', 0.7)
        reward_threshold = self.neurogenesis_config.get('reward_threshold', 0.6)
        
        created = False
        
        # Check each trigger with clear logging
        # Novelty check
        novelty_value = state.get('novelty_exposure', 0)
        novelty_mod = personality_modifier(state.get('personality'), 'novelty')
        if novelty_value > (novelty_threshold * novelty_mod):
            if self.debug_mode:
                print(f"Novelty neurogenesis triggered: {novelty_value} > {novelty_threshold} * {novelty_mod}")
            new_neuron = self._create_neuron_internal('novelty', state)
            if self.debug_mode:
                print(f"Created neuron: {new_neuron}")
            created = True
        
        # Stress check
        stress_value = state.get('sustained_stress', 0)
        stress_mod = personality_modifier(state.get('personality'), 'stress')
        if stress_value > (stress_threshold * stress_mod):
            if self.debug_mode:
                print(f"Stress neurogenesis triggered: {stress_value} > {stress_threshold} * {stress_mod}")
            new_neuron = self._create_neuron_internal('stress', state)
            if self.debug_mode:
                print(f"Created neuron: {new_neuron}")
            created = True
        
        # Reward check
        reward_value = state.get('recent_rewards', 0)
        if reward_value > reward_threshold:
            if self.debug_mode:
                print(f"Reward neurogenesis triggered: {reward_value} > {reward_threshold}")
            new_neuron = self._create_neuron_internal('reward', state)
            if self.debug_mode:
                print(f"Created neuron: {new_neuron}")
            created = True

        # Debug output regardless of debug_mode setting
        if state.get('novelty_exposure', 0) > 0 or state.get('sustained_stress', 0) > 0 or state.get('recent_rewards', 0) > 0:
            print(f"Neurogenesis check with values: novelty={state.get('novelty_exposure', 0):.2f}, stress={state.get('sustained_stress', 0):.2f}, reward={state.get('recent_rewards', 0):.2f}")
            print(f"Thresholds: novelty={self.neurogenesis_config.get('novelty_threshold', 3):.2f}, stress={self.neurogenesis_config.get('stress_threshold', 0.7):.2f}, reward={self.neurogenesis_config.get('reward_threshold', 0.6):.2f}")
        
        if created:
            self.neurogenesis_data['last_neuron_time'] = current_time
        
        return created
    
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

    def _create_neuron_internal(self, neuron_type, state):
        """Internal neuron creation with guaranteed success"""
        # Create descriptive neuron name
        base_name = {
            'novelty': 'novel',
            'stress': 'stress',  # Changed from 'defense' to 'stress' for clarity
            'reward': 'reward'
        }[neuron_type]
        
        new_name = f"{base_name}_{len(self.neurogenesis_data['new_neurons'])}"
        
        # Position near most active connected neuron (or center if none)
        active_neurons = sorted(
            [(k, v) for k, v in self.state.items() 
            if isinstance(v, (int, float)) and k in self.neuron_positions],
            key=lambda x: x[1],
            reverse=True
        )
        
        if active_neurons:
            # Place near most active neuron
            anchor_neuron = active_neurons[0][0]
            base_x, base_y = self.neuron_positions[anchor_neuron]
        else:
            # Fallback to center of existing neurons
            neuron_xs = [pos[0] for pos in self.neuron_positions.values()]
            neuron_ys = [pos[1] for pos in self.neuron_positions.values()]
            if neuron_xs and neuron_ys:
                base_x = sum(neuron_xs) / len(neuron_xs)
                base_y = sum(neuron_ys) / len(neuron_ys)
            else:
                base_x, base_y = 600, 300  # Default center
        
        # Add random offset
        self.neuron_positions[new_name] = (
            base_x + random.randint(-50, 50),
            base_y + random.randint(-50, 50)
        )
        
        # Initialize state
        self.state[new_name] = 50  # Start at mid-level
        
        # Set color based on neuron type
        self.state_colors[new_name] = {
            'novelty': (255, 255, 150),  # Pale yellow
            'stress': (255, 150, 150),   # Light red
            'reward': (150, 255, 150)    # Light green
        }[neuron_type]
        
        # Create connections to other neurons
        for existing in list(self.neuron_positions.keys()):
            if existing != new_name and existing not in self.excluded_neurons:
                self.weights[(new_name, existing)] = random.uniform(-0.3, 0.3)
                self.weights[(existing, new_name)] = random.uniform(-0.3, 0.3)
        
        # Update tracking
        self.neurogenesis_data['new_neurons'].append(new_name)
        
        # Set highlight for visualization
        self.neurogenesis_highlight = {
            'neuron': new_name,
            'start_time': time.time(),
            'duration': self.neurogenesis_config.get('highlight_duration', 5.0)
        }
        
        # Force redraw
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

        # Define binary state neurons with proper positions
        binary_neurons = {
            'is_eating': (50, 50),
            'pursuing_food': (50, 150),
            'is_fleeing': (50, 250)
        }

        # Add these positions to the neuron positions
        for name, pos in binary_neurons.items():
            self.neuron_positions[name] = pos

        # Draw all neurons that exist in current positions
        for name, pos in self.neuron_positions.items():
            if name in binary_neurons:
                # Binary state neurons as small rectangles
                self.draw_binary_neuron(painter, pos[0], pos[1],
                                        self.state.get(name, False), name, scale=scale)
            elif name in original_neurons:
                # Original circular/square neurons
                if name in ["hunger", "happiness", "cleanliness", "sleepiness"]:
                    self.draw_circular_neuron(painter, pos[0], pos[1],
                                            self.state[name], name, scale=scale)
                else:
                    self.draw_square_neuron(painter, pos[0], pos[1],
                                            self.state[name], name, scale=scale)
            else:
                # Neurogenesis-created neurons (triangular)
                self.draw_triangular_neuron(painter, pos[0], pos[1],
                                            self.state[name], name, scale=scale)

                
    def draw_binary_neuron(self, painter, x, y, value, label, scale=1.0):
        # Binary state: Black for True, White for False
        color = (0, 0, 0) if value else (255, 255, 255)
        
        painter.setBrush(QtGui.QBrush(QtGui.QColor(*color)))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))  # Always black border
        
        # Draw a rectangular indicator
        x_scaled = x * scale
        y_scaled = y * scale
        size = 30 * scale
        
        # Convert to integers before calling drawRect
        painter.drawRect(int(x_scaled - size/2), int(y_scaled - size/2), 
                        int(size), int(size))
        
        # Draw label with wider container
        font = painter.font()
        font.setPointSize(int(8 * scale))
        painter.setFont(font)
        
        # Increased width from 100 to 150 to accommodate longer labels
        label_width = 150 * scale
        label_height = 20 * scale
        label_x = x_scaled - label_width/2  # Center the wider container
        label_y = y_scaled + 30 * scale
        
        painter.drawText(int(label_x), int(label_y), 
                        int(label_width), int(label_height), 
                        QtCore.Qt.AlignCenter, label)

    def draw_circular_neuron(self, painter, x, y, value, label, scale=1.0):
        current_time = time.time()
        neuron_name = label
        
        # Check if neuron has recently been involved in a weight change
        last_activity = self.weight_change_events.get(neuron_name, 0)
        is_active = (current_time - last_activity) < self.activity_duration
        
        # Set color to black if active, white otherwise
        color = QtGui.QColor(0, 0, 0) if is_active else QtGui.QColor(255, 255, 255)
        
        painter.setBrush(color)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))  # Black border
        painter.drawEllipse(x - 25, y - 25, 50, 50)

        # Draw label
        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(int(8 * scale))
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

    def draw_square_neuron(self, painter, x, y, value, label, scale=1.0):
        current_time = time.time()
        neuron_name = label
        
        # Check if neuron has recently been involved in a weight change
        last_activity = self.weight_change_events.get(neuron_name, 0)
        is_active = (current_time - last_activity) < self.activity_duration
        
        # Set color to black if active, white otherwise
        color = QtGui.QColor(0, 0, 0) if is_active else QtGui.QColor(255, 255, 255)
        
        painter.setBrush(color)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))  # Black border
        painter.drawRect(x - 25, y - 25, 50, 50)

        # Draw label
        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(int(8 * scale))
        painter.setFont(font)
        painter.drawText(x - 50, y + 30, 100, 20, QtCore.Qt.AlignCenter, label)


    def toggle_links(self, state):
        self.show_links = state == QtCore.Qt.Checked
        self.update()

    def toggle_weights(self, state):
        self.show_weights = state == QtCore.Qt.Checked
        self.update()

    def toggle_capture_training_data(self, state):
        self.capture_training_data_enabled = state

    def mousePressEvent(self, event):
        scale_x = self.width() / 1200
        scale_y = self.height() / 600
        scale = min(scale_x, scale_y)
        
        click_pos = event.pos()
        
        if event.button() == QtCore.Qt.LeftButton:
            for name, pos in self.neuron_positions.items():
                if self._is_click_on_neuron(click_pos, pos, scale):
                    self.neuronClicked.emit(name)
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

class NeuronInspector(QtWidgets.QDialog):
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.brain_widget = brain_widget
        self.current_neuron = None
        
        self.setWindowTitle("Neuron Inspector")
        self.resize(600, 500)
        
        # Main layout
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # Neuron info section
        self.info_group = QtWidgets.QGroupBox("Neuron Information")
        self.info_layout = QtWidgets.QFormLayout()
        self.info_group.setLayout(self.info_layout)
        layout.addWidget(self.info_group)
        
        # Info fields
        self.name_label = QtWidgets.QLabel()
        self.state_label = QtWidgets.QLabel()
        self.position_label = QtWidgets.QLabel()
        self.type_label = QtWidgets.QLabel()
        
        self.info_layout.addRow("Name:", self.name_label)
        self.info_layout.addRow("Current State:", self.state_label)
        self.info_layout.addRow("Position:", self.position_label)
        self.info_layout.addRow("Type:", self.type_label)
        
        # Connections table
        self.connections_group = QtWidgets.QGroupBox("Connections")
        self.connections_layout = QtWidgets.QVBoxLayout()
        self.connections_group.setLayout(self.connections_layout)
        layout.addWidget(self.connections_group)
        
        self.connections_table = QtWidgets.QTableWidget()
        self.connections_table.setColumnCount(5)
        self.connections_table.setHorizontalHeaderLabels([
            "Neuron", "Direction", "Weight", "Strength", "State"
        ])
        self.connections_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.connections_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.connections_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.connections_layout.addWidget(self.connections_table)
        
        # Activity graph
        self.activity_group = QtWidgets.QGroupBox("Activity History")
        self.activity_layout = QtWidgets.QVBoxLayout()
        self.activity_group.setLayout(self.activity_layout)
        layout.addWidget(self.activity_group)
        
        self.activity_plot = QtWidgets.QGraphicsView()
        self.activity_scene = QtWidgets.QGraphicsScene()
        self.activity_plot.setScene(self.activity_scene)
        self.activity_layout.addWidget(self.activity_plot)
        
        # Close button
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        layout.addWidget(self.close_button)
        
        # Connect to brain widget's neuron click signal
        if hasattr(brain_widget, 'neuronClicked'):
            brain_widget.neuronClicked.connect(self.inspect_neuron)

    def inspect_neuron(self, neuron_name):
        """Update the inspector with data for the clicked neuron"""
        self.current_neuron = neuron_name
        self.update_display()

    def update_display(self):
        """Update all display elements for current neuron"""
        if not self.current_neuron:
            return
            
        neuron = self.current_neuron
        state = self.brain_widget.state.get(neuron, 0)
        pos = self.brain_widget.neuron_positions.get(neuron, (0, 0))
        
        # Update info fields
        self.name_label.setText(neuron)
        self.state_label.setText(f"{state:.1f}")
        self.position_label.setText(f"({pos[0]:.1f}, {pos[1]:.1f})")
        self.type_label.setText(self.get_neuron_type(neuron))
        
        # Update connections table
        self.update_connections_table()
        
        # Update activity graph
        self.update_activity_graph()

    def get_neuron_type(self, neuron):
        """Determine the type of neuron for display purposes"""
        if neuron in self.brain_widget.original_neuron_positions:
            return "Core Neuron"
        elif neuron in self.brain_widget.neurogenesis_data.get('new_neurons', []):
            return "Neurogenesis Neuron"
        elif neuron in self.brain_widget.excluded_neurons:
            return "System Neuron"
        return "Unknown"

    def update_connections_table(self):
        """Populate the connections table"""
        if not self.current_neuron:
            return
            
        neuron = self.current_neuron
        connections = []
        
        # Gather connection data
        for (src, dst), weight in self.brain_widget.weights.items():
            if src == neuron or dst == neuron:
                other = dst if src == neuron else src
                direction = "→" if src == neuron else "←"
                connections.append({
                    'neuron': other,
                    'weight': weight,
                    'direction': direction,
                    'state': self.brain_widget.state.get(other, 0)
                })
        
        # Sort by absolute weight
        connections.sort(key=lambda x: abs(x['weight']), reverse=True)
        
        # Populate table
        self.connections_table.setRowCount(len(connections))
        for row, conn in enumerate(connections):
            # Neuron name
            neuron_item = QtWidgets.QTableWidgetItem(conn['neuron'])
            self.connections_table.setItem(row, 0, neuron_item)
            
            # Direction
            direction_item = QtWidgets.QTableWidgetItem(conn['direction'])
            direction_item.setTextAlignment(QtCore.Qt.AlignCenter)
            self.connections_table.setItem(row, 1, direction_item)
            
            # Weight
            weight_item = QtWidgets.QTableWidgetItem(f"{conn['weight']:.3f}")
            if conn['weight'] > 0:
                weight_item.setForeground(QtGui.QColor(0, 150, 0))  # Green
            else:
                weight_item.setForeground(QtGui.QColor(200, 0, 0))  # Red
            self.connections_table.setItem(row, 2, weight_item)
            
            # Strength bar
            strength_widget = QtWidgets.QWidget()
            strength_layout = QtWidgets.QHBoxLayout(strength_widget)
            strength_layout.setContentsMargins(0, 0, 0, 0)
            
            bar = QtWidgets.QProgressBar()
            bar.setRange(0, 100)
            bar.setValue(abs(conn['weight']) * 100)
            bar.setTextVisible(False)
            bar.setStyleSheet("""
                QProgressBar {
                    border: 1px solid #ccc;
                    border-radius: 3px;
                    text-align: center;
                }
                QProgressBar::chunk {
                    background-color: %s;
                }
            """ % ("#2ecc71" if conn['weight'] > 0 else "#e74c3c"))
            
            strength_layout.addWidget(bar)
            strength_layout.addStretch()
            self.connections_table.setCellWidget(row, 3, strength_widget)
            
            # State
            state_item = QtWidgets.QTableWidgetItem(f"{conn['state']:.1f}")
            self.connections_table.setItem(row, 4, state_item)

    def update_activity_graph(self):
        """Draw a simple activity history graph"""
        self.activity_scene.clear()
        
        if not self.current_neuron:
            return
            
        # Sample data - replace with real historical data if available
        current_state = self.brain_widget.state.get(self.current_neuron, 50)
        history = [max(0, min(100, current_state + random.randint(-10, 10))) for _ in range(10)]
        history.append(current_state)
        
        # Graph parameters
        width = self.activity_plot.width() - 20
        height = self.activity_plot.height() - 40
        x_step = width / (len(history) - 1)
        
        # Draw axes
        self.activity_scene.addLine(10, 10, 10, height + 10, QtGui.QPen(QtCore.Qt.black))
        self.activity_scene.addLine(10, height + 10, width + 10, height + 10, QtGui.QPen(QtCore.Qt.black))
        
        # Draw labels
        font = QtGui.QFont()
        font.setPointSize(8)
        
        # Y-axis labels
        for y, val in [(10, "100"), (height/2 + 10, "50"), (height + 10, "0")]:
            text = self.activity_scene.addText(val, font)
            text.setPos(0, y - 8)
        
        # X-axis labels
        for i in range(0, len(history), 2):
            x = 10 + i * x_step
            label = f"T-{len(history)-1-i}" if i < len(history)-1 else "Now"
            text = self.activity_scene.addText(label, font)
            text.setPos(x - 10, height + 15)
        
        # Draw graph
        path = QtGui.QPainterPath()
        path.moveTo(10, height + 10 - (history[0] / 100 * height))
        
        for i, val in enumerate(history):
            x = 10 + i * x_step
            y = height + 10 - (val / 100 * height)
            path.lineTo(x, y)
        
        self.activity_scene.addPath(path, QtGui.QPen(QtGui.QColor(52, 152, 219), 2))
        
        # Add data points
        for i, val in enumerate(history):
            x = 10 + i * x_step
            y = height + 10 - (val / 100 * height)
            self.activity_scene.addEllipse(x - 3, y - 3, 6, 6, 
                                         QtGui.QPen(QtCore.Qt.black),
                                         QtGui.QBrush(QtGui.QColor(52, 152, 219)))