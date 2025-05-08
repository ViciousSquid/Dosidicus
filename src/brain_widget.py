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
    # Define the signal as a class attribute here
    neuronClicked = QtCore.pyqtSignal(str)
    
    def __init__(self, config=None, debug_mode=False, tamagotchi_logic=None):
        self.resolution_scale = 1.0  # Default resolution scale
        self.config = config if config else LearningConfig()
        if not hasattr(self.config, 'hebbian'):
            self.config.hebbian = {
                'learning_interval': 30000,
                'weight_decay': 0.01,
                'active_threshold': 50
            }
        super().__init__()

        self.excluded_neurons = ['is_sick', 'is_eating', 'pursuing_food', 'direction', 'is_sleeping']
        self.hebbian_countdown_seconds = 30  # Default duration
        self.learning_active = True
        self.pruning_enabled = True
        neuronClicked = QtCore.pyqtSignal(str)
        self.config = config if config else LearningConfig()
        self.debug_mode = debug_mode  # Initialize debug_mode
        self.is_paused = False
        self.last_hebbian_time = time.time()
        self.tamagotchi_logic = tamagotchi_logic
        self.recently_updated_neuron_pairs = []
        
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
                'highlight_duration': 5.0,
                'max_neurons': 20
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
            'novelty_threshold': 2.5,
            'stress_threshold': 2.0,
            'reward_threshold': 1.8,
            'cooldown': 120,
            'highlight_duration': 10.0
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
        """Set debug mode without causing circular callbacks"""
        # Only proceed if there's an actual change
        if self.debug_mode == enabled:
            return
            
        # Update our own state
        self.debug_mode = enabled
        
        # Update brain widget
        if hasattr(self, 'brain_widget'):
            self.brain_widget.debug_mode = enabled
        
        # Update tabs
        for tab_name in ['network_tab', 'nn_viz_tab', 'memory_tab', 'decisions_tab', 'about_tab']:
            if hasattr(self, tab_name):
                tab = getattr(self, tab_name)
                if hasattr(tab, 'debug_mode'):
                    tab.debug_mode = enabled
        
        # Enable/disable debug-specific UI elements
        if hasattr(self, 'stimulate_button'):
            self.stimulate_button.setEnabled(enabled)
        
        print(f"Brain window debug mode set to: {enabled}")

    def toggle_pruning(self, enabled):
        """Enable or disable the pruning mechanisms for neurogenesis"""
        previous = self.pruning_enabled
        self.pruning_enabled = enabled
        
        if previous != enabled:
            print(f"\x1b[{'42' if enabled else '41'}mPruning {'enabled' if enabled else 'disabled'}\x1b[0m - Neurogenesis {'constrained' if enabled else 'unconstrained'}")
            
            if not enabled:
                print("\x1b[31mWARNING: Disabling pruning may lead to network instability\x1b[0m")
        
        return self.pruning_enabled

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
        # Add debounce mechanism - prevent multiple calls within short time frame
        current_time = time.time()
        min_interval = 5  # Minimum 5 seconds between learning operations
        
        if hasattr(self, 'last_hebbian_time') and (current_time - self.last_hebbian_time < min_interval):
            print("Hebbian learning skipped - too soon after previous learning")
            return
            
        if self.is_paused:
            return

        print("  ")
        print("\x1b[44mPerforming Hebbian learning...\x1b[0m")
        self.last_hebbian_time = current_time

        # Initialize the list of updated neuron pairs
        self.recently_updated_neuron_pairs = []

        # Clean up old weight change events
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

        # Select only 2 pairs for learning
        sample_size = min(2, len(active_neurons) * (len(active_neurons) - 1) // 2)
        sampled_pairs = random.sample([(i, j) for i in range(len(active_neurons)) for j in range(i + 1, len(active_neurons))], sample_size)
        
        print(f">> Learning on {sample_size} random neuron pairs")

        for i, j in sampled_pairs:
            neuron1 = active_neurons[i]
            neuron2 = active_neurons[j]
            value1 = self.get_neuron_value(current_state.get(neuron1, 50))  # Default to 50 if not in current_state
            value2 = self.get_neuron_value(current_state.get(neuron2, 50))
            self.update_connection(neuron1, neuron2, value1, value2)
            # Add the pair to recently updated neurons
            self.recently_updated_neuron_pairs.append((neuron1, neuron2))

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

    def get_recently_updated_neurons(self):
        """Return the list of neuron pairs updated in the last learning cycle"""
        return self.recently_updated_neuron_pairs


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
        if not hasattr(self, 'weights') or not self.weights:
            return []
            
        sorted_weights = sorted(self.weights.items(), key=lambda x: abs(x[1]))
        return sorted_weights[:n]  # Returns list of ((source, target), weight) tuples

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

        # Initialize neurogenesis data if missing
        if 'neurogenesis_data' not in dir(self) or self.neurogenesis_data is None:
            self.neurogenesis_data = {}
        
        # Initialize missing counters if they don't exist
        if 'novelty_counter' not in self.neurogenesis_data:
            self.neurogenesis_data['novelty_counter'] = 0
        if 'stress_counter' not in self.neurogenesis_data:
            self.neurogenesis_data['stress_counter'] = 0
        if 'reward_counter' not in self.neurogenesis_data:
            self.neurogenesis_data['reward_counter'] = 0
        if 'new_neurons' not in self.neurogenesis_data:
            self.neurogenesis_data['new_neurons'] = []
        if 'last_neuron_time' not in self.neurogenesis_data:
            self.neurogenesis_data['last_neuron_time'] = time.time() - 300  # Start with cooldown passed

        # Add counter increment logic based on brain state with REDUCED increments
        # Increment novelty counter when curiosity is high
        if 'curiosity' in self.state and self.state['curiosity'] > 75:
            self.neurogenesis_data['novelty_counter'] += 0.1
            if self.debug_mode:
                print(f"Novelty counter increased by 0.1 due to high curiosity")
        
        # Increment stress counter when anxiety is high or cleanliness is low
        if ('anxiety' in self.state and self.state['anxiety'] > 80) or \
        ('cleanliness' in self.state and self.state['cleanliness'] < 20):
            self.neurogenesis_data['stress_counter'] += 0.05
            if self.debug_mode:
                print(f"Stress counter increased by 0.05 due to high anxiety or low cleanliness")
        
        # Increment reward counter when happiness or satisfaction is high
        if ('happiness' in self.state and self.state['happiness'] > 85) or \
        ('satisfaction' in self.state and self.state['satisfaction'] > 85):
            self.neurogenesis_data['reward_counter'] += 0.05
            if self.debug_mode:
                print(f"Reward counter increased by 0.05 due to high happiness or satisfaction")

        # NEW: Add emergency conditions that cause large counter increases
        if 'anxiety' in self.state and self.state['anxiety'] > 95:
            self.neurogenesis_data['stress_counter'] += 1.0
            if self.debug_mode:
                print(f"EMERGENCY: Stress counter increased by 1.0 due to extreme anxiety")
        
        if 'curiosity' in self.state and self.state['curiosity'] > 95:
            self.neurogenesis_data['novelty_counter'] += 1.0
            if self.debug_mode:
                print(f"EMERGENCY: Novelty counter increased by 1.0 due to extreme curiosity")
                
        if 'happiness' in self.state and self.state['happiness'] > 95 and \
        'satisfaction' in self.state and self.state['satisfaction'] > 95:
            self.neurogenesis_data['reward_counter'] += 1.0
            if self.debug_mode:
                print(f"EMERGENCY: Reward counter increased by 1.0 due to extreme happiness and satisfaction")

        # Handle direct state triggers from tamagotchi_logic
        if new_state.get('novelty_exposure', 0) > 0:
            self.neurogenesis_data['novelty_counter'] += new_state.get('novelty_exposure', 0)
            if self.debug_mode:
                print(f"Novelty counter increased by {new_state.get('novelty_exposure', 0)} from external trigger")
        
        if new_state.get('sustained_stress', 0) > 0:
            self.neurogenesis_data['stress_counter'] += new_state.get('sustained_stress', 0)
            if self.debug_mode:
                print(f"Stress counter increased by {new_state.get('sustained_stress', 0)} from external trigger")
        
        if new_state.get('recent_rewards', 0) > 0:
            self.neurogenesis_data['reward_counter'] += new_state.get('recent_rewards', 0)
            if self.debug_mode:
                print(f"Reward counter increased by {new_state.get('recent_rewards', 0)} from external trigger")

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

        # Check for natural neurogenesis directly without requiring hebbian_learning
        # Check thresholds for each counter using config values with adjusted thresholds
        
        # Get base thresholds
        novelty_threshold_base = self.neurogenesis_config.get('novelty_threshold', 3)
        stress_threshold_base = self.neurogenesis_config.get('stress_threshold', 0.7)
        reward_threshold_base = self.neurogenesis_config.get('reward_threshold', 0.6)
        
        # Apply threshold scaling only if pruning is enabled
        if self.pruning_enabled:
            novelty_threshold = self.get_adjusted_threshold(novelty_threshold_base, 'novelty')
            stress_threshold = self.get_adjusted_threshold(stress_threshold_base, 'stress')
            reward_threshold = self.get_adjusted_threshold(reward_threshold_base, 'reward')
        else:
            # Use base thresholds when pruning is disabled
            novelty_threshold = novelty_threshold_base
            stress_threshold = stress_threshold_base
            reward_threshold = reward_threshold_base
        
        # Check if thresholds are exceeded
        if (self.neurogenesis_data['novelty_counter'] > novelty_threshold or
            self.neurogenesis_data['stress_counter'] > stress_threshold or
            self.neurogenesis_data['reward_counter'] > reward_threshold):
            
            # Check neuron limit and cooldown
            max_neurons = self.neurogenesis_config.get('max_neurons', 15)
            current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
            cooldown_ok = current_time - self.neurogenesis_data['last_neuron_time'] > self.neurogenesis_config.get('cooldown', 300)
            
            # Skip neuron limit check if pruning is disabled
            if (not self.pruning_enabled or current_neuron_count < max_neurons) and cooldown_ok:
                # Determine trigger type
                neuron_type = None
                if self.neurogenesis_data['novelty_counter'] > novelty_threshold:
                    neuron_type = 'novelty'
                elif self.neurogenesis_data['stress_counter'] > stress_threshold:
                    neuron_type = 'stress'
                elif self.neurogenesis_data['reward_counter'] > reward_threshold:
                    neuron_type = 'reward'
                
                if neuron_type:
                    # Create new neuron
                    new_neuron_name = self._create_neuron_internal(neuron_type, new_state)
                    if new_neuron_name:  # Check if creation was successful
                        print(" ")
                        print(f"\x1b[43mNeurogenesis occurred!\x1b[0m Created {neuron_type} neuron: {new_neuron_name}")
                        print(" ")
                        
                        # Update visualization
                        self.neurogenesis_highlight = {
                            'neuron': new_neuron_name,
                            'start_time': time.time(),
                            'duration': self.neurogenesis_config.get('highlight_duration', 5.0)
                        }
                        
                        # Reset the counter that triggered it
                        if neuron_type == 'novelty':
                            self.neurogenesis_data['novelty_counter'] = 0
                        elif neuron_type == 'stress':
                            self.neurogenesis_data['stress_counter'] = 0
                        elif neuron_type == 'reward':
                            self.neurogenesis_data['reward_counter'] = 0
                        
                        # Force update
                        self.update()
            else:
                if self.debug_mode:
                    if self.pruning_enabled and current_neuron_count >= max_neurons:
                        print(f"Neurogenesis blocked: max neurons ({max_neurons}) reached")
                    else:
                        remaining = self.neurogenesis_config.get('cooldown', 300) - (current_time - self.neurogenesis_data['last_neuron_time'])
                        print(f"Neurogenesis blocked by cooldown: {remaining:.1f} seconds remaining")
        
        # Check if pruning is needed (when neuron count is high)
        if self.pruning_enabled:  # Only perform pruning if enabled
            current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
            max_neurons = self.neurogenesis_config.get('max_neurons', 15)
            prune_threshold = int(max_neurons * 0.8)  # Prune at 80% of max

            if current_neuron_count > prune_threshold:
                # Higher chance of pruning as we get closer to the limit
                prune_chance = (current_neuron_count - prune_threshold) / (max_neurons - prune_threshold)
                if random.random() < prune_chance:
                    pruned = self.prune_weak_neurons()
                    if pruned and self.debug_mode:
                        print(f"Proactive pruning performed ({current_neuron_count-1}/{max_neurons} neurons)")
        
        # Update the visualization
        self.update()

        # Capture training data if enabled
        if self.capture_training_data_enabled:
            self.capture_training_data(new_state)

        # Update neurogenesis counters with decay - AFTER we've checked them
        # Use decay rates from config
        self.neurogenesis_data['novelty_counter'] *= self.neurogenesis_config.get('decay_rate', 0.95)
        self.neurogenesis_data['stress_counter'] *= self.neurogenesis_config.get('decay_rate', 0.95)
        self.neurogenesis_data['reward_counter'] *= self.neurogenesis_config.get('decay_rate', 0.95)
        
        # Debug output for neurogenesis triggers
        if self.debug_mode and (self.neurogenesis_data['novelty_counter'] > 0.1 or 
                            self.neurogenesis_data['stress_counter'] > 0.1 or 
                            self.neurogenesis_data['reward_counter'] > 0.1):
            print(f"Neurogenesis counters: novelty={self.neurogenesis_data['novelty_counter']:.2f}, " + 
                f"stress={self.neurogenesis_data['stress_counter']:.2f}, " +
                f"reward={self.neurogenesis_data['reward_counter']:.2f}")
            print(f"Adjusted thresholds: novelty={novelty_threshold:.2f}, " +
                f"stress={stress_threshold:.2f}, " +
                f"reward={reward_threshold:.2f}")

  
    def check_neurogenesis(self, state):
        """Check conditions for neurogenesis and create new neurons when triggered."""
        current_time = time.time()
        
        # Print debug information for transparency
        if self.debug_mode:
            print("Neurogenesis check starting...")
            print(f"Current triggers: novelty={state.get('novelty_exposure', 0)}, stress={state.get('sustained_stress', 0)}, reward={state.get('recent_rewards', 0)}")
            
            # Get base thresholds
            novelty_base = self.neurogenesis_config.get('novelty_threshold', 3)
            stress_base = self.neurogenesis_config.get('stress_threshold', 0.7)
            reward_base = self.neurogenesis_config.get('reward_threshold', 0.6)
            
            # Get adjusted thresholds
            if self.pruning_enabled:
                novelty_adj = self.get_adjusted_threshold(novelty_base, 'novelty')
                stress_adj = self.get_adjusted_threshold(stress_base, 'stress')
                reward_adj = self.get_adjusted_threshold(reward_base, 'reward')
                print(f"Base thresholds: novelty={novelty_base:.2f}, stress={stress_base:.2f}, reward={reward_base:.2f}")
                print(f"Adjusted thresholds: novelty={novelty_adj:.2f}, stress={stress_adj:.2f}, reward={reward_adj:.2f}")
            else:
                print(f"Using base thresholds (pruning disabled): novelty={novelty_base:.2f}, stress={stress_base:.2f}, reward={reward_base:.2f}")
                
            print(f"Time since last neuron: {current_time - self.neurogenesis_data.get('last_neuron_time', 0)} seconds")
            print(f"Cooldown period: {self.neurogenesis_config.get('cooldown', 300)} seconds")
            if hasattr(self, 'pruning_enabled'):
                print(f"Pruning: {'Enabled' if self.pruning_enabled else 'Disabled'}")
        
        # Check maximum neuron limit only if pruning is enabled
        if hasattr(self, 'pruning_enabled') and self.pruning_enabled:
            max_neurons = self.neurogenesis_config.get('max_neurons', 15)
            current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
            
            if current_neuron_count >= max_neurons:
                if self.debug_mode:
                    print(f"Neurogenesis blocked: maximum neuron limit ({max_neurons}) reached")
                return False
        
        # Check cooldown period
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
        
        # Get base thresholds from neurogenesis_config
        novelty_threshold_base = self.neurogenesis_config.get('novelty_threshold', 3)
        stress_threshold_base = self.neurogenesis_config.get('stress_threshold', 0.7)
        reward_threshold_base = self.neurogenesis_config.get('reward_threshold', 0.6)
        
        # Apply threshold scaling only if pruning is enabled
        if hasattr(self, 'pruning_enabled') and self.pruning_enabled:
            novelty_threshold = self.get_adjusted_threshold(novelty_threshold_base, 'novelty')
            stress_threshold = self.get_adjusted_threshold(stress_threshold_base, 'stress')
            reward_threshold = self.get_adjusted_threshold(reward_threshold_base, 'reward')
        else:
            # Use base thresholds when pruning is disabled
            novelty_threshold = novelty_threshold_base
            stress_threshold = stress_threshold_base
            reward_threshold = reward_threshold_base
        
        created = False
        
        # Check each trigger with clear logging
        # Novelty check
        novelty_value = state.get('novelty_exposure', 0)
        novelty_mod = personality_modifier(state.get('personality'), 'novelty')
        if novelty_value > (novelty_threshold * novelty_mod):
            if self.debug_mode:
                print(f"Novelty neurogenesis triggered: {novelty_value} > {novelty_threshold} * {novelty_mod}")
            new_neuron = self._create_neuron_internal('novelty', state)
            if new_neuron and self.debug_mode:
                print(f"Created neuron: {new_neuron}")
            created = new_neuron is not None
        
        # Stress check
        stress_value = state.get('sustained_stress', 0)
        stress_mod = personality_modifier(state.get('personality'), 'stress')
        if stress_value > (stress_threshold * stress_mod):
            if self.debug_mode:
                print(f"Stress neurogenesis triggered: {stress_value} > {stress_threshold} * {stress_mod}")
            new_neuron = self._create_neuron_internal('stress', state)
            if new_neuron and self.debug_mode:
                print(f"Created neuron: {new_neuron}")
            created = new_neuron is not None
        
        # Reward check
        reward_value = state.get('recent_rewards', 0)
        if reward_value > reward_threshold:
            if self.debug_mode:
                print(f"Reward neurogenesis triggered: {reward_value} > {reward_threshold}")
            new_neuron = self._create_neuron_internal('reward', state)
            if new_neuron and self.debug_mode:
                print(f"Created neuron: {new_neuron}")
            created = new_neuron is not None

        # Debug output regardless of debug_mode setting
        if state.get('novelty_exposure', 0) > 0 or state.get('sustained_stress', 0) > 0 or state.get('recent_rewards', 0) > 0:
            print(f"Neurogenesis check with values: novelty={state.get('novelty_exposure', 0):.2f}, stress={state.get('sustained_stress', 0):.2f}, reward={state.get('recent_rewards', 0):.2f}")
            print(f"{'Adjusted' if hasattr(self, 'pruning_enabled') and self.pruning_enabled else 'Base'} thresholds: novelty={novelty_threshold:.2f}, stress={stress_threshold:.2f}, reward={reward_threshold:.2f}")
        
        if created:
            self.neurogenesis_data['last_neuron_time'] = current_time
            
            # Consider pruning if we're close to the limit after creation
            if hasattr(self, 'pruning_enabled') and self.pruning_enabled:
                current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
                max_neurons = self.neurogenesis_config.get('max_neurons', 15)
                if current_neuron_count > max_neurons * 0.8:
                    prune_chance = (current_neuron_count - (max_neurons * 0.8)) / (max_neurons * 0.2)
                    if random.random() < prune_chance:
                        self.prune_weak_neurons()
        
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

    def get_adjusted_threshold(self, base_threshold, trigger_type):
        """Scale threshold based on network size to prevent runaway neurogenesis"""
        # Count non-system neurons
        original_count = len(self.original_neuron_positions)
        current_count = len(self.neuron_positions) - len(self.excluded_neurons)
        new_neuron_count = current_count - original_count
        
        # Calculate scaling factor based on how many neurons above baseline
        baseline = original_count + 3  # Allow a few new neurons before scaling
        
        if new_neuron_count <= 0 or current_count <= baseline:
            return base_threshold
        
        # Different scaling rules for different trigger types
        scaling_factors = {
            'novelty': 0.15,  # 15% increase per neuron
            'stress': 0.2,    # 20% increase per neuron
            'reward': 0.1     # 10% increase per neuron
        }
        
        scaling_factor = scaling_factors.get(trigger_type, 0.15)
        multiplier = 1.0 + (scaling_factor * (new_neuron_count - baseline + 1))
        
        adjusted = base_threshold * multiplier
        
        if self.debug_mode and adjusted > base_threshold:
            print(f"Adjusted {trigger_type} threshold: {base_threshold:.2f} → {adjusted:.2f} " +
                f"(network size: {current_count} neurons)")
        
        return adjusted

    def prune_weak_neurons(self):
        """Remove weakly connected or inactive neurons to maintain network stability"""
        # Skip if not enough neurons to prune
        min_neurons = len(self.original_neuron_positions)
        current_count = len(self.neuron_positions) - len(self.excluded_neurons)
        
        if current_count <= min_neurons:
            return False
        
        # Find pruning candidates (new neurons with weak connections)
        candidates = []
        
        for neuron in list(self.neuron_positions.keys()):
            # Skip original and system neurons
            if neuron in self.original_neuron_positions or neuron in self.excluded_neurons:
                continue
                
            # Calculate average connection strength
            connections = [abs(w) for (a, b), w in self.weights.items() 
                        if (a == neuron or b == neuron)]
            
            # Check activity level
            activity = self.state.get(neuron, 0)
            activity_score = 0 if isinstance(activity, bool) else abs(activity - 50)
            
            # Score based on both connection strength and activity
            if not connections or sum(connections) / len(connections) < 0.2:
                # Weak connections
                candidates.append((neuron, 1))
            elif activity_score < 10:
                # Low activity differential
                candidates.append((neuron, 2))
        
        # Sort candidates by priority (lowest priority first)
        candidates.sort(key=lambda x: x[1])
        
        # Remove the weakest neuron if candidates exist
        if candidates:
            neuron_to_remove = candidates[0][0]
            
            # Remove from neuron positions
            if neuron_to_remove in self.neuron_positions:
                del self.neuron_positions[neuron_to_remove]
                
            # Remove from state
            if neuron_to_remove in self.state:
                del self.state[neuron_to_remove]
                
            # Remove connections involving this neuron
            for conn in list(self.weights.keys()):
                if isinstance(conn, tuple) and (conn[0] == neuron_to_remove or conn[1] == neuron_to_remove):
                    del self.weights[conn]
                    
            # Remove from new_neurons list if present
            if neuron_to_remove in self.neurogenesis_data.get('new_neurons', []):
                self.neurogenesis_data['new_neurons'].remove(neuron_to_remove)
                
            print(f"\x1b[43mPruned neuron\x1b[0m: {neuron_to_remove} removed due to weak connections/activity")
            return True
            
        return False

    def _create_neuron_internal(self, neuron_type, state):
        """
        Create a new neuron with type-specific characteristics and connections.
        
        Args:
            neuron_type (str): Type of neuron ('novelty', 'stress', 'reward')
            state (dict): Current brain state for context
        
        Returns:
            str: Name of the newly created neuron or None if max neurons reached
        """
        # Calculate current neuron count (excluding system neurons)
        current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
        max_neurons = self.neurogenesis_config.get('max_neurons', 15)
        
        if current_neuron_count >= max_neurons:
            print(f"\x1b[41mNeurogenesis blocked\x1b[0m: Maximum neuron count ({max_neurons}) reached")
            return None

        # Ensure existing weights are in tuple format
        converted_weights = {}
        for key, weight in self.weights.items():
            # Convert string keys to tuples
            if isinstance(key, str) and '_' in key:
                source, target = key.split('_')
                converted_weights[(source, target)] = weight
            # Keep tuple keys as they are
            elif isinstance(key, tuple):
                converted_weights[key] = weight
        self.weights = converted_weights

        # Create descriptive neuron name
        base_name = {
            'novelty': 'novel',
            'stress': 'stress',
            'reward': 'reward'
        }[neuron_type]
        
        # Ensure unique neuron name by appending a counter
        new_name = f"{base_name}_{len(self.neurogenesis_data['new_neurons'])}"
        
        # Find a strategic position for the new neuron
        active_neurons = sorted(
            [(k, v) for k, v in self.state.items() 
            if isinstance(v, (int, float)) and k in self.neuron_positions],
            key=lambda x: x[1],
            reverse=True
        )
        
        # Position the new neuron near the most active neuron or at a default center
        if active_neurons:
            # Place near most active neuron
            anchor_neuron = active_neurons[0][0]
            base_x, base_y = self.neuron_positions[anchor_neuron]
        else:
            # Fallback to center if no active neurons
            neuron_xs = [pos[0] for pos in self.neuron_positions.values()]
            neuron_ys = [pos[1] for pos in self.neuron_positions.values()]
            base_x = sum(neuron_xs) / len(neuron_xs) if neuron_xs else 600
            base_y = sum(neuron_ys) / len(neuron_ys) if neuron_ys else 300
        
        # Add random offset to prevent overcrowding
        self.neuron_positions[new_name] = (
            base_x + random.randint(-50, 50),
            base_y + random.randint(-50, 50)
        )
        
        # Initialize neuron state
        self.state[new_name] = 50  # Start at mid-level activation
        
        # Set color based on neuron type
        self.state_colors[new_name] = {
            'novelty': (255, 255, 150),  # Pale yellow
            'stress': (255, 150, 150),   # Light red
            'reward': (150, 255, 150)    # Light green
        }[neuron_type]
        
        # Create default connections to existing neurons
        default_connections = {
            'novelty': {'curiosity': 0.6, 'anxiety': -0.4},
            'stress': {'anxiety': -0.7, 'happiness': 0.3},
            'reward': {'satisfaction': 0.8, 'happiness': 0.5}
        }
        
        # Personality modifier (if available in state)
        personality = state.get('personality', None)
        personality_weights = {
            Personality.TIMID: 0.8,
            Personality.ADVENTUROUS: 1.2,
            Personality.GREEDY: 1.5,
            Personality.STUBBORN: 0.7
        }.get(personality, 1.0)
        
        # Create connections to existing neurons
        for existing in list(self.neuron_positions.keys()):
            # Skip excluded system neurons
            if existing in self.excluded_neurons:
                continue
            
            # Determine default connection strength
            default_strength = default_connections.get(neuron_type, {}).get(existing, 0)
            
            # Apply personality modifier
            weight = default_strength * personality_weights
            
            # Add some randomness
            weight += random.uniform(-0.1, 0.1)
            
            # Ensure weight stays within bounds
            weight = max(-1, min(1, weight))
            
            # Create bidirectional weights as tuples
            self.weights[(new_name, existing)] = weight
            self.weights[(existing, new_name)] = weight * 0.5  # Slightly weaker reverse connection
        
        # Update neurogenesis tracking
        self.neurogenesis_data['new_neurons'].append(new_name)
        self.neurogenesis_data['last_neuron_time'] = time.time()
        
        # Set highlight for visualization
        self.neurogenesis_highlight = {
            'neuron': new_name,
            'start_time': time.time(),
            'duration': self.neurogenesis_config.get('highlight_duration', 5.0)
        }
        
        # Force redraw
        self.update()
        
        # Debug print
        if self.debug_mode:
            print(f"Created {neuron_type} neuron: {new_name}")
            print("Connections:")
            for key, weight in self.weights.items():
                if new_name in key:
                    print(f"  {key}: {weight}")
        
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
        # Only draw if links are visible
        if not self.show_links:
            return

        # Use weights dictionary directly to draw connections
        for key, weight in self.weights.items():
            # Handle different possible key formats
            if isinstance(key, tuple):
                # Skip multi-part keys or keys involving 'is_fleeing'
                if len(key) > 2 or 'is_fleeing' in key:
                    continue
                source, target = key
            elif isinstance(key, str):
                # If key is a string, try to parse it
                try:
                    source, target = key.split('_')
                    # Skip if any part contains 'is_fleeing'
                    if 'is_fleeing' in source or 'is_fleeing' in target:
                        continue
                except ValueError:
                    print(f"Skipping invalid connection key: {key}")
                    continue
            else:
                print(f"Skipping unrecognized connection key: {key}")
                continue

            # Skip if either neuron is not in neuron positions or is in excluded neurons
            if (source not in self.neuron_positions or 
                target not in self.neuron_positions or 
                source in self.excluded_neurons or 
                target in self.excluded_neurons):
                continue

            # Get neuron positions and ensure they are converted to integers
            start = self.neuron_positions[source]
            end = self.neuron_positions[target]

            # Convert to QPointF to ensure compatibility
            start_point = QtCore.QPointF(float(start[0]), float(start[1]))
            end_point = QtCore.QPointF(float(end[0]), float(end[1]))

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
            
            # Draw the connection line using QPointF
            painter.drawLine(start_point, end_point)

            # Add weight text with scaling and visibility threshold
            if self.show_weights and abs(weight) > 0.1:
                midpoint = QtCore.QPointF(
                    (start_point.x() + end_point.x()) / 2, 
                    (start_point.y() + end_point.y()) / 2
                )

                # Increase the area for drawing the weights
                text_area_width = 80.0
                text_area_height = 22.0

                # Adjust the font size based on the scale with a maximum font size
                max_font_size = 12
                font_size = max(8, min(max_font_size, int(8 * scale)))
                font = painter.font()
                font.setPointSize(font_size)
                painter.setFont(font)

                # Create QRectF for drawing
                rect = QtCore.QRectF(
                    midpoint.x() - text_area_width / 2, 
                    midpoint.y() - text_area_height / 2,
                    text_area_width, 
                    text_area_height
                )

                # Draw black background rectangle
                painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0)))
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
                painter.drawRect(rect)

                # Draw the weight text on top of the black background
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255)))  # White text color
                painter.drawText(
                    rect,
                    QtCore.Qt.AlignCenter, 
                    f"{weight:.2f}"
                )


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
        
        from .display_scaling import DisplayScaling

        # Define binary state neurons with proper scaled positions
        binary_neurons = {
            'is_eating': (DisplayScaling.scale(50), DisplayScaling.scale(50)),
            'pursuing_food': (DisplayScaling.scale(50), DisplayScaling.scale(150)),
            'is_fleeing': (DisplayScaling.scale(50), DisplayScaling.scale(250))
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
        x_scaled = int(x * scale)
        y_scaled = int(y * scale)
        size = int(30 * scale)
        
        # Draw rectangle with integer coordinates
        painter.drawRect(x_scaled - size//2, y_scaled - size//2, 
                        size, size)
        
        # Draw label with wider container
        font = painter.font()
        font.setPointSize(int(8 * scale))
        painter.setFont(font)
        
        # Increased width from 100 to 150 to accommodate longer labels
        label_width = int(150 * scale)
        label_height = int(20 * scale)
        label_x = x_scaled - label_width//2  # Center the wider container
        label_y = y_scaled + int(30 * scale)
        
        painter.drawText(label_x, label_y, 
                        label_width, label_height, 
                        QtCore.Qt.AlignCenter, label)

    def draw_circular_neuron(self, painter, x, y, value, label, scale=1.0):
        from .display_scaling import DisplayScaling
        
        # Get screen resolution
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()
        
        current_time = time.time()
        neuron_name = label
        
        # Check if neuron has recently been involved in a weight change
        last_activity = self.weight_change_events.get(neuron_name, 0)
        is_active = (current_time - last_activity) < self.activity_duration
        
        # Set color
        color = QtGui.QColor(0, 0, 0) if is_active else QtGui.QColor(255, 255, 255)
        
        painter.setBrush(color)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))  # Black border
        
        # Resolution-specific size adjustment
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            # Use 60% of the original size for 1080p
            neuron_radius = int(25 * 0.6 * scale)
        else:
            neuron_radius = int(25 * scale)
        
        painter.drawEllipse(int(x - neuron_radius), int(y - neuron_radius), 
                        int(neuron_radius * 2), int(neuron_radius * 2))

        # Draw label with resolution-appropriate font
        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            font_size = max(6, int(8 * 0.75 * scale))
        else:
            font_size = int(8 * scale) 
        font.setPointSize(font_size)
        painter.setFont(font)
        
        # Reduced label width for 1080p
        if screen_size.width() <= 1920:
            label_width = int(100 * 0.8)
        else:
            label_width = 100
        
        # Convert ALL arguments to integers for drawText
        painter.drawText(int(x - label_width/2), int(y + 30*scale), 
                        int(label_width), int(20*scale), 
                        QtCore.Qt.AlignCenter, label)

    def draw_triangular_neuron(self, painter, x, y, value, label, scale=1.0):
        # Use fixed size instead of relying on resolution_scale
        base_size = 25 * scale
        
        # Determine color based on neuron type
        if label.startswith('defense') or label.startswith('stress'):
            color = QtGui.QColor(255, 150, 150)  # Light red
        elif label.startswith('novel'):
            color = QtGui.QColor(255, 255, 150)  # Pale yellow
        elif label.startswith('reward'):
            color = QtGui.QColor(150, 255, 150)  # Light green
        elif label.startswith('forced'):
            color = QtGui.QColor(150, 200, 255)  # Light blue
        else:
            color = QtGui.QColor(200, 200, 200)  # Default gray

        painter.setBrush(color)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))  # Black border

        # Create triangle
        triangle = QtGui.QPolygonF()
        size = base_size
        triangle.append(QtCore.QPointF(x - size, y + size))
        triangle.append(QtCore.QPointF(x + size, y + size))
        triangle.append(QtCore.QPointF(x, y - size))

        painter.drawPolygon(triangle)

        # Draw label with integer coordinates
        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(int(8 * scale))
        painter.setFont(font)
        
        # Calculate text dimensions
        label_width = int(60 * scale)
        label_height = int(20 * scale)
        label_y_offset = int(40 * scale)
        
        painter.drawText(int(x - label_width/2), int(y + label_y_offset), 
                        label_width, label_height, 
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
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), int(3 * scale)))
                painter.setBrush(QtCore.Qt.NoBrush)
                radius = int(40 * scale)
                
                # Convert all values to integers
                x = int(pos[0] - radius)
                y = int(pos[1] - radius)
                width = int(radius * 2)
                height = int(radius * 2)
                
                # Use integers for all arguments
                painter.drawEllipse(x, y, width, height)

    def draw_square_neuron(self, painter, x, y, value, label, scale=1.0):
        from .display_scaling import DisplayScaling
        
        # Get screen resolution
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()
        
        current_time = time.time()
        neuron_name = label
        
        # Check if neuron has recently been involved in a weight change
        last_activity = self.weight_change_events.get(neuron_name, 0)
        is_active = (current_time - last_activity) < self.activity_duration
        
        # Set color to black if active, white otherwise
        color = QtGui.QColor(0, 0, 0) if is_active else QtGui.QColor(255, 255, 255)
        
        painter.setBrush(color)
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))  # Black border
        
        # Resolution-specific size adjustment
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            # Use 60% of the original size for 1080p
            neuron_size = int(25 * 0.6 * scale)
        else:
            neuron_size = int(25 * scale)
        
        painter.drawRect(int(x - neuron_size), int(y - neuron_size), 
                        int(neuron_size * 2), int(neuron_size * 2))

        # Draw label
        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            font_size = max(6, int(8 * 0.75 * scale))
        else:
            font_size = int(8 * scale)
        font.setPointSize(font_size)
        painter.setFont(font)
        
        # Reduced label width for 1080p
        if screen_size.width() <= 1920:
            label_width = int(100 * 0.8)
        else:
            label_width = 100
        
        # Convert ALL arguments to integers for drawText
        painter.drawText(int(x - label_width/2), int(y + 30*scale), 
                        int(label_width), int(20*scale), 
                        QtCore.Qt.AlignCenter, label)


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
                    self.neuronClicked.emit(name)  # Now this should work
                    self.dragging = True
                    self.dragged_neuron = name
                    self.drag_start_pos = click_pos
                    self.update()
                    break

    def handle_neuron_clicked(self, neuron_name):
        # Handle the neuron click event
        print(f"Neuron clicked: {neuron_name}")

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
        
        from .display_scaling import DisplayScaling
        
        self.setWindowTitle("Neuron Inspector")
        self.setFixedSize(DisplayScaling.scale(600), DisplayScaling.scale(500))
        
        # Main layout
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # Style all text properly
        self.setStyleSheet(f"""
            QLabel, QComboBox, QPushButton {{
                font-size: {DisplayScaling.font_size(12)}px;
            }}
            QTextEdit, QListWidget {{
                font-size: {DisplayScaling.font_size(12)}px;
                line-height: {DisplayScaling.scale(1.5)};
            }}
        """)
        
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