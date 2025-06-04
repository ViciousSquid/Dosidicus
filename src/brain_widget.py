import sys
import csv
import os
import time
import math
import random
import numpy as np
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtGui import QPixmap, QFont
from datetime import datetime

from .personality import Personality
from .learning import LearningConfig

class BrainWidget(QtWidgets.QWidget):
    neuronClicked = QtCore.pyqtSignal(str)

    def __init__(self, config=None, debug_mode=False, tamagotchi_logic=None):
        self.resolution_scale = 1.0  # Default resolution scale
        self.config = config if config else LearningConfig() #
        if not hasattr(self.config, 'hebbian'): #
            self.config.hebbian = { #
                'learning_interval': 30000, #
                'weight_decay': 0.01, #
                'active_threshold': 50 #
            }
        super().__init__() #

        self.excluded_neurons = ['is_sick', 'is_eating', 'pursuing_food', 'direction', 'is_sleeping'] #
        self.hebbian_countdown_seconds = 30  # Default duration
        self.learning_active = True #
        self.pruning_enabled = True #
        self.debug_mode = debug_mode  # Initialize debug_mode
        self.is_paused = False #
        self.last_hebbian_time = time.time() #
        self.last_neurogenesis_type = None
        self.tamagotchi_logic = tamagotchi_logic #
        self.recently_updated_neuron_pairs = [] #
        self.neuron_shapes = {} #

        # Neural communication tracking system
        self.communication_events = {} #
        self.communication_highlight_duration = 0.5 #
        self.weight_change_events = {} #
        self.activity_duration = 0.5 #

        # Initialize neurogenesis data
        self.neurogenesis_data = { #
            'novelty_counter': 0, #
            'stress_counter': 0, #
            'reward_counter': 0, #
            'new_neurons': [], #
            'last_neuron_time': time.time(), #
            'new_neurons_details': {} # Added to ensure it exists
        }

        # Ensure neurogenesis config exists
        if not hasattr(self.config, 'neurogenesis'): #
            self.config.neurogenesis = { #
                'decay_rate': 0.75,  # Default decay rate if not specified
                'novelty_threshold': 3, #
                'stress_threshold': 0.7, #
                'reward_threshold': 0.6, #
                'cooldown': 300, #
                'highlight_duration': 5.0, #
                'max_neurons': 32 # <-- MODIFIED
            }

        self.neurogenesis_config = self.config.neurogenesis #

        # <<< MAX NEURO COUNTER VALUES >>>
        self.max_novelty_counter = 100
        self.max_stress_counter = 100
        self.max_reward_counter = 100

        # Neural state initialization
        self.state = { #
            "hunger": 50, #
            "happiness": 50, #
            "cleanliness": 50, #
            "sleepiness": 50, #
            "satisfaction": 50, #
            "anxiety": 50, #
            "curiosity": 50, #
            "is_sick": False, #
            "is_eating": False, #
            "is_sleeping": False, #
            "pursuing_food": False, #
            "direction": "up", #
            "position": (0, 0), #
            "is_startled": False, #
            "is_fleeing": False, #
            'neurogenesis_active': False # Added for consistency with usage
        }

        # Neuron position configuration
        self.original_neuron_positions = { #
            "hunger": (127, 81), #
            "happiness": (361, 81), #
            "cleanliness": (627, 81), #
            "sleepiness": (840, 81), #
            "satisfaction": (271, 380), #
            "anxiety": (491, 389), #
            "curiosity": (701, 386) #
        }
        self.neuron_positions = self.original_neuron_positions.copy() #

        # Set shapes for specific original neurons to 'square'
        self.neuron_shapes["curiosity"] = 'square' #
        self.neuron_shapes["anxiety"] = 'square' #
        self.neuron_shapes["satisfaction"] = 'square' #

        # Set shapes for other original neurons (defaults to circle if not set)
        self.neuron_shapes["hunger"] = 'circle' #
        self.neuron_shapes["happiness"] = 'circle' #
        self.neuron_shapes["cleanliness"] = 'circle' #
        self.neuron_shapes["sleepiness"] = 'circle' #

        # Initialize communication events for all neurons
        for neuron in self.neuron_positions.keys(): #
            self.communication_events[neuron] = 0 #

        # Add neurogenesis visualization tracking
        self.neurogenesis_highlight = { #
            'neuron': None, #
            'start_time': 0, #
            'duration': 5.0  # seconds
        }

        # Connection and weight initialization
        self.connections = self.initialize_connections() #
        self.weights = {}  # Initialize empty dictionary for weights
        self.initialize_weights()  # Populate weights
        self.show_links = True #
        self.frozen_weights = None #
        self.history = [] #
        self.training_data = [] #
        self.associations = np.zeros((len(self.neuron_positions), len(self.neuron_positions))) #
        self.learning_rate = 0.1 #
        self.capture_training_data_enabled = False #
        self.dragging = False #
        self.dragged_neuron = None #
        self.drag_start_pos = None #
        self.setMouseTracking(True) #
        self.show_weights = False #

        # Visual state colors
        self.state_colors = { #
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
        
    def is_new_neuron(self, neuron_name, newness_duration_sec=300): # 300s = 5 minutes
        """Check if a neuron was created within the newness duration."""
        # Check if it's in the primary neurogenesis data
        if neuron_name in self.neurogenesis_data.get('new_neurons', []):
            details = self.neurogenesis_data.get('new_neurons_details', {}).get(neuron_name)
            if details:
                created_at = details.get('created_at')
                if created_at and (time.time() - created_at) < newness_duration_sec:
                    return True # It's new based on details
            else:
                 # If no details but in list, assume it might be new (fallback)
                 # You might want to refine this based on how 'new_neurons' is managed.
                 # For now, if it's in the list and < 5 mins, assume new.
                 # A better check is needed if 'new_neurons' isn't pruned.
                 # Let's rely *only* on details for a stricter check.
                 pass
        return False


    def update_connection(self, neuron1, neuron2, value1, value2):
        """
        Update the connection weight between two neurons based on their activation values,
        with modulated learning rate. # MODIFIED
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
            # Only add if both neurons exist - crucial check!
            if neuron1 in self.neuron_positions and neuron2 in self.neuron_positions:
                 self.weights[pair] = 0.0 # Start with 0 weight
            else:
                 # print(f"Skipping connection: {neuron1} or {neuron2} not found.") # Optional Debug
                 return # Don't create connection if a neuron doesn't exist


        # Use the correct pair order
        use_pair = pair if pair in self.weights else reverse_pair
        
        # Ensure the pair still exists before proceeding (might be pruned)
        if use_pair not in self.weights:
            return

        prev_weight = self.weights[use_pair]

        # --- START: MODIFIED Learning Rate ---
        base_lr = self.learning_rate # Use the instance learning_rate (0.1 by default)
        newness_boost = 2.0 # New neurons learn 2x faster
        effective_lr = base_lr

        is_n1_new = self.is_new_neuron(neuron1)
        is_n2_new = self.is_new_neuron(neuron2)

        if is_n1_new or is_n2_new:
            effective_lr = base_lr * newness_boost
        # --- END: MODIFIED Learning Rate ---

        # Use effective_lr for weight change (basic Hebbian)
        weight_change = effective_lr * (value1 / 100.0) * (value2 / 100.0) 
        
        # Add weight decay (optional but good for stability)
        decay_rate = self.config.hebbian.get('weight_decay', 0.01) * 0.1 # Slow decay during learning
        new_weight = prev_weight + weight_change - (prev_weight * decay_rate)
        
        new_weight = min(max(new_weight, -1.0), 1.0)  # Ensure weight stays in [-1, 1] range # MODIFIED
        self.weights[use_pair] = new_weight

        # Record weight change time for both neurons
        if abs(new_weight - prev_weight) > 0.001:  # Only if significant change
            self.weight_change_events[neuron1] = current_time
            self.weight_change_events[neuron2] = current_time
            # Add to recently updated for visualization/logging
            if (neuron1, neuron2) not in self.recently_updated_neuron_pairs and \
               (neuron2, neuron1) not in self.recently_updated_neuron_pairs:
                self.recently_updated_neuron_pairs.append((neuron1, neuron2))
            self.update()

        # Debugging statement to check if update_connection is being called correctly
        lr_indicator = " (\x1b[35mBOOSTED\x1b[0m)" if effective_lr > base_lr else ""
        print(f"\x1b[42mUpdated connection\x1b[0m between {neuron1} and {neuron2}: \x1b[31m {prev_weight:.3f} -> \x1b[32m {new_weight:.3f} \x1b[0m (LR: {effective_lr:.3f}{lr_indicator})")

        # Record communication time for both neurons
        self.communication_events[neuron1] = current_time
        self.communication_events[neuron2] = current_time

    def prune_weak_connections(self, threshold=0.05, min_age_sec=600): # Prune if < 0.05 abs weight & > 10 mins old
        """Removes connections with absolute weight below the threshold, ignoring new neurons."""
        if not self.pruning_enabled: # Respect the global pruning flag
            return 0

        current_time = time.time()
        to_delete = []

        # Iterate over a copy of keys to allow deletion during iteration
        for pair, weight in list(self.weights.items()):
            # Ensure pair is a valid tuple
            if not (isinstance(pair, tuple) and len(pair) == 2):
                # print(f"Skipping invalid weight key during pruning: {pair}") # Optional Debug
                continue

            neuron1, neuron2 = pair

            # Don't prune if either neuron is "new" (gives them time to establish)
            if self.is_new_neuron(neuron1, min_age_sec) or self.is_new_neuron(neuron2, min_age_sec):
                continue
            
            # Don't prune connections involving core/original neurons (optional, but safer)
            # if neuron1 in self.original_neuron_positions or neuron2 in self.original_neuron_positions:
            #    continue

            # Check if absolute weight is below the threshold
            if abs(weight) < threshold:
                to_delete.append(pair)

        for pair in to_delete:
            if pair in self.weights:
                del self.weights[pair]

        if len(to_delete) > 0:
            print(f"\x1b[33mPruned {len(to_delete)} weak connections (Threshold: {threshold}).\x1b[0m")
            self.update() # Update visualization if connections changed
        
        return len(to_delete) # Return how many were pruned


    def perform_hebbian_learning(self):
        """Perform Hebbian learning with pre-pruning."""
        current_time = time.time()
        min_interval = 5  # Minimum 5 seconds between learning operations

        if hasattr(self, 'last_hebbian_time') and (current_time - self.last_hebbian_time < min_interval):
            return

        if self.is_paused:
            return

        # --- NEW: Call Connection Pruning ---
        # Call this *before* learning to remove very weak/old connections
        self.prune_weak_connections()
        # ---------------------------------

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
        active_threshold = self.config.hebbian.get('active_threshold', 50)
        active_neurons = []
        for neuron, value in current_state.items():
            if neuron in self.excluded_neurons:
                continue
            
            num_value = self.get_neuron_value(value) # Use helper to get numerical value
            
            if num_value > active_threshold:
                active_neurons.append(neuron)

        # Include decoration effects in learning (ensure manager exists)
        decoration_memories = {}
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'squid') and hasattr(self.tamagotchi_logic.squid, 'memory_manager'):
            decoration_memories = self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories('decorations')

        if isinstance(decoration_memories, list): # Updated to handle list format
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
            if hasattr(self, 'hebbian_countdown_seconds'):
                interval_ms = self.config.hebbian.get('learning_interval', 40000)
                self.hebbian_countdown_seconds = int(interval_ms / 1000)
            return

        # Select only 2 pairs for learning (or fewer if not enough pairs)
        num_possible_pairs = len(active_neurons) * (len(active_neurons) - 1) // 2
        sample_size = min(2, num_possible_pairs)
        
        if sample_size > 0:
            sampled_pairs_indices = random.sample([(i, j) for i in range(len(active_neurons)) for j in range(i + 1, len(active_neurons))], sample_size)
            print(f">> Learning on {sample_size} random neuron pairs")
            for i, j in sampled_pairs_indices:
                neuron1 = active_neurons[i]
                neuron2 = active_neurons[j]
                value1 = self.get_neuron_value(current_state.get(neuron1, 50))
                value2 = self.get_neuron_value(current_state.get(neuron2, 50))
                self.update_connection(neuron1, neuron2, value1, value2)
        else:
            print("No valid pairs found for Hebbian learning.")


        # Update the brain visualization
        self.update()

        # Reset the countdown after learning
        if hasattr(self, 'hebbian_countdown_seconds'):
            interval_ms = self.config.hebbian.get('learning_interval', 40000)
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
            'neuron_positions': self.neuron_positions,
            'neuron_states': self.state
        }

    def load_brain_state(self, state):
        """Load the brain state from a saved state dictionary"""
        self.weights = state['weights']
        self.neuron_positions = state['neuron_positions']
        # Load neuron states, defaulting to empty dict if not present
        self.state = state.get('neuron_states', {})

        # Ensure all neurons in neuron_positions exist in state
        for neuron in self.neuron_positions:
            if neuron not in self.state:
                # Initialize missing neurons with default value
                self.state[neuron] = 50  # Default activation value

        # Explicitly update excluded neurons if they exist in positions
        for neuron in self.excluded_neurons:
            if neuron in self.neuron_positions and neuron not in self.state:
                self.state[neuron] = False  # Default boolean state

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
        """Returns the actual count of neurons in the network positions."""
        return len(self.neuron_positions)

    def get_edge_count(self):
        """Returns the actual count of connections (weights) in the network."""
        return len(self.weights) # MODIFIED: Use self.weights

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
        health = min(100, max(0, avg_weight * 100))
        return health

    def calculate_network_efficiency(self):
        """Calculate network efficiency based on connection distribution"""
        if not self.connections:
            return 0
        reciprocal_count = 0
        for conn in self.connections:
            reverse_conn = (conn[1], conn[0])
            if reverse_conn in self.connections:
                reciprocal_count += 1
        efficiency = (reciprocal_count / len(self.connections)) * 100
        return efficiency

    def log_neurogenesis_event(self, neuron_name, event_type, reason=None, details=None): # details parameter was added
        """Log neurogenesis events in the specified text format"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S") #
        log_entry = ""

        if event_type == "created":
            connections = []
            if hasattr(self, 'weights') and isinstance(self.weights, dict):
                for (src, dest), weight in self.weights.items():
                    if isinstance(src, str) and isinstance(dest, str):
                        if src == neuron_name or dest == neuron_name:
                            other_neuron = dest if src == neuron_name else src
                            connections.append(f"{other_neuron} {weight:+.2f}") #

            log_entry = f"{timestamp} Neuron created: {neuron_name}" #

            if details: # If details about the creation are provided
                trigger_type = details.get("trigger_type", "Unknown trigger") #
                trigger_value = details.get("trigger_value", "N/A") #
                context_info = details.get("context", "") # Get the pre-formatted context string

                log_entry += f"\n  Trigger: {trigger_type.capitalize()} (Value at creation: {trigger_value})" #
                if context_info: #
                    log_entry += f"\n  Context: {context_info}" #

            log_entry += "\n" # Newline before connections or if no details/connections

            if connections: #
                log_entry += f"  Connections: {'  |  '.join(connections)}" #
            else:
                log_entry += "  Connections: None initially." #

        elif event_type == "pruned":
            log_entry = f"{timestamp} PRUNED: {neuron_name} due to {reason if reason else 'Unknown reason'}" #

        if log_entry: # Only write to file if there's something to log
            try:
                with open('neurogenesis_log.txt', 'a', encoding='utf-8') as f: #
                    f.write(log_entry + "\n\n")  # Two newlines between entries #
            except Exception as e:
                print(f"\x1b[31mNeurogenesis logging failed: {str(e)}\x1b[0m") #

    def update_state(self, new_state):
        if self.is_paused:
            return

        current_time = time.time()

        # Update core states, excluding those handled elsewhere or binary
        excluded_from_direct_update = ['is_sick', 'is_eating', 'pursuing_food', 'direction', 'is_sleeping', 'is_startled', 'is_fleeing']
        for key in self.state.keys():
            if key in new_state and key not in excluded_from_direct_update:
                self.state[key] = new_state[key]

        # Update binary/special states directly
        binary_states_to_update = ['is_eating', 'pursuing_food', 'is_fleeing', 'is_startled', 'is_sleeping', 'is_sick']
        for b_state in binary_states_to_update:
            if b_state in new_state:
                self.state[b_state] = new_state[b_state]

        # Ensure neurogenesis data exists
        if not hasattr(self, 'neurogenesis_data') or self.neurogenesis_data is None:
            self.neurogenesis_data = {
                'novelty_counter': 0, 'stress_counter': 0, 'reward_counter': 0,
                'new_neurons': [], 'last_neuron_time': time.time() - self.neurogenesis_config.get('cooldown', 300),
                'new_neurons_details': {}
            }
        
        # Ensure individual counters exist
        for counter_key in ['novelty_counter', 'stress_counter', 'reward_counter']:
            if counter_key not in self.neurogenesis_data:
                self.neurogenesis_data[counter_key] = 0
        if 'last_neuron_time' not in self.neurogenesis_data:
             self.neurogenesis_data['last_neuron_time'] = time.time() - self.neurogenesis_config.get('cooldown', 300)


        # Update neurogenesis counters based on internal state and new_state triggers
        if 'curiosity' in self.state and self.state['curiosity'] > 75:
            self.neurogenesis_data['novelty_counter'] += 0.1
        if ('anxiety' in self.state and self.state['anxiety'] > 80) or \
           ('cleanliness' in self.state and self.state['cleanliness'] < 20):
            self.neurogenesis_data['stress_counter'] += 0.25
        if ('happiness' in self.state and self.state['happiness'] > 85) or \
           ('satisfaction' in self.state and self.state['satisfaction'] > 85):
            self.neurogenesis_data['reward_counter'] += 0.2

        if 'anxiety' in self.state and self.state['anxiety'] > 75:
            self.neurogenesis_data['stress_counter'] += 2.5
        if 'curiosity' in self.state and self.state['curiosity'] > 95:
            self.neurogenesis_data['novelty_counter'] += 1.0
        if 'happiness' in self.state and self.state['happiness'] > 90:
            self.neurogenesis_data['reward_counter'] += 2.0

        # Update from explicit triggers in new_state
        if new_state.get('novelty_exposure', 0) > 0:
            self.neurogenesis_data['novelty_counter'] += new_state.get('novelty_exposure', 0)
        if new_state.get('sustained_stress', 0) > 0:
            self.neurogenesis_data['stress_counter'] += new_state.get('sustained_stress', 0)
        if new_state.get('recent_rewards', 0) > 0:
            self.neurogenesis_data['reward_counter'] += new_state.get('recent_rewards', 0)

        # Cap the counters
        self.neurogenesis_data['novelty_counter'] = min(self.neurogenesis_data['novelty_counter'], self.max_novelty_counter)
        self.neurogenesis_data['stress_counter'] = min(self.neurogenesis_data['stress_counter'], self.max_stress_counter)
        self.neurogenesis_data['reward_counter'] = min(self.neurogenesis_data['reward_counter'], self.max_reward_counter)

        # Handle forced neurogenesis for debugging
        if new_state.get('_debug_forced_neurogenesis', False):
            created = self.check_neurogenesis(new_state)
            if created:
                self.update()
                return # Skip rest of update if forced

        # --- Weight Decay Logic (Moved from update_weights) ---
        if hasattr(self, 'last_weight_decay_time'):
            if current_time - self.last_weight_decay_time > 60: # Decay every 60 seconds
                for conn_key in list(self.weights.keys()):
                    decay_factor = 1.0 - self.config.hebbian.get('weight_decay', 0.01)
                    self.weights[conn_key] *= decay_factor
                self.last_weight_decay_time = current_time
        else:
            self.last_weight_decay_time = current_time

        # --- REMOVED/COMMENTED OUT ---
        # self.update_weights() # This line is now commented out

        # --- Neurogenesis Check Logic ---
        novelty_threshold_base = self.neurogenesis_config.get('novelty_threshold', 3)
        stress_threshold_base = self.neurogenesis_config.get('stress_threshold', 0.7)
        reward_threshold_base = self.neurogenesis_config.get('reward_threshold', 0.6)

        if self.pruning_enabled:
            novelty_threshold = self.get_adjusted_threshold(novelty_threshold_base, 'novelty')
            stress_threshold = self.get_adjusted_threshold(stress_threshold_base, 'stress')
            reward_threshold = self.get_adjusted_threshold(reward_threshold_base, 'reward')
        else:
            novelty_threshold = novelty_threshold_base
            stress_threshold = stress_threshold_base
            reward_threshold = reward_threshold_base

        max_neurons = self.neurogenesis_config.get('max_neurons', 32)
        current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
        cooldown_ok = current_time - self.neurogenesis_data.get('last_neuron_time', 0) > self.neurogenesis_config.get('cooldown', 300)

        potential_triggers = []
        if self.neurogenesis_data['novelty_counter'] > novelty_threshold:
            potential_triggers.append(('novelty', self.neurogenesis_data['novelty_counter']))
        if self.neurogenesis_data['stress_counter'] > stress_threshold:
            potential_triggers.append(('stress', self.neurogenesis_data['stress_counter']))
        if self.neurogenesis_data['reward_counter'] > reward_threshold:
            potential_triggers.append(('reward', self.neurogenesis_data['reward_counter']))

        neuron_type_to_create = None

        if potential_triggers and cooldown_ok and (not self.pruning_enabled or current_neuron_count < max_neurons):
            potential_triggers.sort(key=lambda x: x[1], reverse=True)
            if len(potential_triggers) == 1:
                neuron_type_to_create = potential_triggers[0][0]
            else:
                highest_type = potential_triggers[0][0]
                second_highest_type = potential_triggers[1][0]
                if highest_type != self.last_neurogenesis_type:
                    neuron_type_to_create = highest_type
                else:
                    neuron_type_to_create = second_highest_type
            
            # Avoid repeating the same type twice in a row if possible
            if neuron_type_to_create == self.last_neurogenesis_type:
                 found_different = False
                 for p_type, _ in potential_triggers:
                     if p_type != self.last_neurogenesis_type:
                         neuron_type_to_create = p_type
                         found_different = True
                         break
                 if not found_different:
                      neuron_type_to_create = None # Only create if different type available


        if neuron_type_to_create:
            new_neuron_name = self._create_neuron_internal(neuron_type_to_create, new_state)
            if new_neuron_name:
                self.neurogenesis_highlight = {
                    'neuron': new_neuron_name,
                    'start_time': time.time(),
                    'duration': self.neurogenesis_config.get('highlight_duration', 5.0)
                }
                self.last_neurogenesis_type = neuron_type_to_create
                # Reset the specific counter that triggered the neuron
                if neuron_type_to_create == 'reward':
                    self.neurogenesis_data['reward_counter'] = 0
                elif neuron_type_to_create == 'novelty':
                    self.neurogenesis_data['novelty_counter'] = 0
                elif neuron_type_to_create == 'stress':
                    self.neurogenesis_data['stress_counter'] = 0
                self.update() # Redraw to show new neuron & connections
            else:
                self.last_neurogenesis_type = None # Reset if creation failed

        # --- Pruning Check Logic ---
        if self.pruning_enabled:
            current_neuron_count_for_pruning = len(self.neuron_positions) - len(self.excluded_neurons)
            max_neurons_for_pruning = self.neurogenesis_config.get('max_neurons', 32)
            prune_threshold_percent = int(max_neurons_for_pruning * 0.95) # Start pruning when 95% full
            if current_neuron_count_for_pruning > prune_threshold_percent:
                # Increase chance as it gets fuller
                prune_chance = (current_neuron_count_for_pruning - prune_threshold_percent) / (max_neurons_for_pruning - prune_threshold_percent)
                if random.random() < prune_chance:
                    self.prune_weak_neurons()

        # --- Counter Decay ---
        decay_rate = self.neurogenesis_config.get('decay_rate', 0.90)
        self.neurogenesis_data['novelty_counter'] = max(0, self.neurogenesis_data['novelty_counter'] * decay_rate)
        self.neurogenesis_data['stress_counter'] = max(0, self.neurogenesis_data['stress_counter'] * decay_rate)
        self.neurogenesis_data['reward_counter'] = max(0, self.neurogenesis_data['reward_counter'] * decay_rate)

        # Final update and data capture
        self.update()
        if self.capture_training_data_enabled:
            self.capture_training_data(new_state)

    def check_neurogenesis(self, state):
        """Check conditions for neurogenesis and create new neurons when triggered."""
        current_time = time.time()
        if hasattr(self, 'pruning_enabled') and self.pruning_enabled:
            max_neurons = self.neurogenesis_config.get('max_neurons', 32)
            current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
            if current_neuron_count >= max_neurons:
                return False

        cooldown = self.neurogenesis_config.get('cooldown', 300)
        if current_time - self.neurogenesis_data.get('last_neuron_time', 0) <= cooldown:
            return False

        def get_personality_modifier(personality, trigger_type):
            modifiers = {'timid': {'novelty': 1.2, 'stress': 0.8}, 'adventurous': {'novelty': 0.8, 'stress': 1.2}, 'greedy': {'novelty': 1.0, 'stress': 1.0}, 'stubborn': {'novelty': 1.1, 'stress': 0.9}}
            personality_str = getattr(personality, 'value', str(personality)).lower()
            return modifiers.get(personality_str, {}).get(trigger_type, 1.0)
        personality_modifier = getattr(self, 'get_personality_modifier', get_personality_modifier)

        novelty_threshold_base = self.neurogenesis_config.get('novelty_threshold', 3)
        stress_threshold_base = self.neurogenesis_config.get('stress_threshold', 0.7)
        reward_threshold_base = self.neurogenesis_config.get('reward_threshold', 0.6)

        if hasattr(self, 'pruning_enabled') and self.pruning_enabled:
            novelty_threshold = self.get_adjusted_threshold(novelty_threshold_base, 'novelty')
            stress_threshold = self.get_adjusted_threshold(stress_threshold_base, 'stress')
            reward_threshold = self.get_adjusted_threshold(reward_threshold_base, 'reward')
        else:
            novelty_threshold = novelty_threshold_base
            stress_threshold = stress_threshold_base
            reward_threshold = reward_threshold_base

        created = False
        reward_value = state.get('recent_rewards', 0)
        if not created and reward_value > reward_threshold:
            new_neuron = self._create_neuron_internal('reward', state)
            created = new_neuron is not None
        novelty_value = state.get('novelty_exposure', 0)
        novelty_mod = personality_modifier(state.get('personality'), 'novelty')
        if not created and novelty_value > (novelty_threshold * novelty_mod):
            new_neuron = self._create_neuron_internal('novelty', state)
            created = new_neuron is not None
        stress_value = state.get('sustained_stress', 0)
        stress_mod = personality_modifier(state.get('personality'), 'stress')
        if not created and stress_value > (stress_threshold * stress_mod):
            new_neuron = self._create_neuron_internal('stress', state)
            created = new_neuron is not None

        if created:
            self.neurogenesis_data['last_neuron_time'] = current_time
            if hasattr(self, 'pruning_enabled') and self.pruning_enabled:
                current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
                max_neurons = self.neurogenesis_config.get('max_neurons', 32)
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
            defaults = {'novelty': 0.7, 'stress': 0.8, 'reward': 0.6}
            return defaults.get(trigger_type, 1.0)

    def stimulate_brain(self, stimulation_values):
        """Handle brain stimulation with validation"""
        if not isinstance(stimulation_values, dict):
            return
        filtered_update = {}
        for key in self.state.keys():
            if key in stimulation_values:
                filtered_update[key] = stimulation_values[key]
        self.update_state(filtered_update)

    def get_adjusted_threshold(self, base_threshold, trigger_type):
        """Scale threshold based on network size to prevent runaway neurogenesis"""
        original_count = len(self.original_neuron_positions)
        current_count = len(self.neuron_positions) - len(self.excluded_neurons)
        new_neuron_count = current_count - original_count
        baseline = original_count + 3
        if new_neuron_count <= 0 or current_count <= baseline:
            return base_threshold
        scaling_factors = {'novelty': 0.25, 'stress': 0.1, 'reward': 0.08}
        scaling_factor = scaling_factors.get(trigger_type, 0.15)
        multiplier = 1.0 + (scaling_factor * (new_neuron_count - baseline + 1))
        adjusted = base_threshold * multiplier
        return adjusted

    def prune_weak_neurons(self):
        """Remove weakly connected or inactive neurons to maintain network stability"""
        min_neurons = len(self.original_neuron_positions)
        current_count = len(self.neuron_positions) - len(self.excluded_neurons)
        if current_count <= min_neurons:
            return False

        candidates = []
        for neuron in list(self.neuron_positions.keys()):
            if neuron in self.original_neuron_positions or neuron in self.excluded_neurons:
                continue
            connections = [abs(w) for (a, b), w in self.weights.items() if (a == neuron or b == neuron)]
            activity = self.state.get(neuron, 0)
            activity_score = 0 if isinstance(activity, bool) else abs(activity - 50)
            if not connections or sum(connections) / len(connections) < 0.2:
                candidates.append((neuron, 1))
            elif activity_score < 10:
                candidates.append((neuron, 2))
        candidates.sort(key=lambda x: x[1])

        if candidates:
            neuron_to_remove = candidates[0][0]
            if neuron_to_remove in self.neuron_positions: del self.neuron_positions[neuron_to_remove]
            if neuron_to_remove in self.state: del self.state[neuron_to_remove]
            for conn in list(self.weights.keys()):
                if isinstance(conn, tuple) and (conn[0] == neuron_to_remove or conn[1] == neuron_to_remove):
                    del self.weights[conn]
            if neuron_to_remove in self.neurogenesis_data.get('new_neurons', []):
                self.neurogenesis_data['new_neurons'].remove(neuron_to_remove)
            reason = "weak connections/activity"
            self.log_neurogenesis_event(neuron_to_remove, "pruned", reason)
            return True
        return False

    def _create_neuron_internal(self, neuron_type, state):
        """Create a new neuron with complete state initialization and contextual connections."""
        current_neuron_count = len(self.neuron_positions) - len(self.excluded_neurons)
        max_neurons_config = self.neurogenesis_config.get('max_neurons', 32)
        if self.pruning_enabled and current_neuron_count >= max_neurons_config:
            print(f"\x1b[33mNeurogenesis blocked: Max neuron limit ({max_neurons_config}) reached.\x1b[0m")
            return None

        base_name = {'novelty': 'novel', 'stress': 'stress', 'reward': 'reward'}[neuron_type]
        new_name_index = 0
        new_name = f"{base_name}_{new_name_index}"
        while new_name in self.neuron_positions:
            new_name_index +=1
            new_name = f"{base_name}_{new_name_index}"

        # Determine base position (near active neurons or center)
        active_neurons_pos = sorted([
            (k, v, self.neuron_positions[k]) for k, v in self.state.items()
            if isinstance(v, (int, float)) and k in self.neuron_positions and k not in self.excluded_neurons
            ], key=lambda x: x[1], reverse=True)

        if active_neurons_pos:
            base_x, base_y = active_neurons_pos[0][2] # Position of most active neuron
        else:
            non_excluded_positions = [pos for name, pos in self.neuron_positions.items() if name not in self.excluded_neurons]
            if non_excluded_positions:
                base_x = sum(p[0] for p in non_excluded_positions) / len(non_excluded_positions)
                base_y = sum(p[1] for p in non_excluded_positions) / len(non_excluded_positions)
            else:
                base_x, base_y = (600,300) # Fallback center

        self.neuron_positions[new_name] = (base_x + random.randint(-50, 50), base_y + random.randint(-50, 50))

        # Set color and shape from config
        cfg_appearance = self.config.neurogenesis.get('appearance', {})
        cfg_colors = cfg_appearance.get('colors', {})
        cfg_shapes = cfg_appearance.get('shapes', {})
        self.state.setdefault(new_name, 50) # Initialize state
        default_colors = {'novelty': (255, 255, 150), 'stress': (255, 150, 150), 'reward': (173, 216, 230)} # Light Blue for reward
        self.state_colors[new_name] = tuple(cfg_colors.get(neuron_type, default_colors.get(neuron_type, (200,200,200))))

        # --- MODIFIED ---
        # Ensure each neuron type has a unique default shape.
        default_shapes = {'novelty': 'diamond', 'stress': 'square', 'reward': 'triangle'}
        # --- END MODIFIED ---

        self.neuron_shapes[new_name] = cfg_shapes.get(neuron_type, default_shapes.get(neuron_type, 'circle'))
        self.communication_events[new_name] = time.time() # Initialize communication event


        # --- START: Connection Logic ---

        # 1. Contextual Connections
        num_context_connections = 3
        current_state_snapshot = state if state else self.state
        active_neurons = sorted([
            (k, v) for k, v in current_state_snapshot.items()
            if isinstance(v, (int, float))
            and k in self.neuron_positions
            and k not in self.excluded_neurons
            and k != new_name
        ], key=lambda x: x[1], reverse=True)

        print(f"\x1b[36mNeurogenesis ({new_name}): Creating contextual connections...\x1b[0m")
        for target_neuron, activity in active_neurons[:num_context_connections]:
            weight = 0.2 + (self.get_neuron_value(activity) / 100.0) * 0.3
            weight = max(-1.0, min(1.0, weight))
            self.weights[(new_name, target_neuron)] = weight
            self.weights[(target_neuron, new_name)] = weight * 0.5
            print(f"  -> {target_neuron} (Activity: {self.get_neuron_value(activity):.1f}, Weight: {weight:.2f})")
            self.communication_events[target_neuron] = time.time()

        # 2. Inter-New-Neuron Connections
        num_inter_new_connections = 2
        other_new_neurons = [
            n for n in self.neurogenesis_data.get('new_neurons', [])
            if n != new_name and n in self.neuron_positions
        ]
        connect_to_these = other_new_neurons[-num_inter_new_connections:]

        print(f"\x1b[36mNeurogenesis ({new_name}): Creating inter-new connections...\x1b[0m")
        for target_neuron in connect_to_these:
            weight = 0.15
            self.weights[(new_name, target_neuron)] = weight
            self.weights[(target_neuron, new_name)] = weight
            print(f"  -> {target_neuron} (Weight: {weight:.2f})")
            self.communication_events[target_neuron] = time.time()

        # --- END: Connection Logic ---


        # Determine trigger reason and value for logging/details
        trigger_reason_value = 0
        trigger_context_for_log = ""
        current_associated_state_for_details = {}
        if neuron_type == 'novelty':
            trigger_reason_value = state.get('novelty_exposure', self.neurogenesis_data.get('novelty_counter', 0))
            curiosity_val = state.get('curiosity', self.state.get('curiosity',0))
            trigger_context_for_log = f"Curiosity at {self.get_neuron_value(curiosity_val):.1f}"
            current_associated_state_for_details['curiosity'] = round(self.get_neuron_value(curiosity_val),1)
        elif neuron_type == 'stress':
            trigger_reason_value = state.get('sustained_stress', self.neurogenesis_data.get('stress_counter', 0))
            anxiety_val = state.get('anxiety', self.state.get('anxiety',0))
            trigger_context_for_log = f"Anxiety at {self.get_neuron_value(anxiety_val):.1f}"
            current_associated_state_for_details['anxiety'] = round(self.get_neuron_value(anxiety_val),1)
        elif neuron_type == 'reward':
            trigger_reason_value = state.get('recent_rewards', self.neurogenesis_data.get('reward_counter', 0))
            happiness_val = state.get('happiness', self.state.get('happiness',0))
            satisfaction_val = state.get('satisfaction', self.state.get('satisfaction',0))
            trigger_context_for_log = f"Happiness at {self.get_neuron_value(happiness_val):.1f}, Satisfaction at {self.get_neuron_value(satisfaction_val):.1f}"
            current_associated_state_for_details['happiness'] = round(self.get_neuron_value(happiness_val),1)
            current_associated_state_for_details['satisfaction'] = round(self.get_neuron_value(satisfaction_val),1)

        # Update neurogenesis tracking data
        if 'new_neurons_details' not in self.neurogenesis_data:
            self.neurogenesis_data['new_neurons_details'] = {}
        self.neurogenesis_data['new_neurons_details'][new_name] = {
            'created_at': time.time(),
            'trigger_type': neuron_type,
            'trigger_value_at_creation': round(trigger_reason_value, 2),
            'associated_state_snapshot': current_associated_state_for_details
        }
        self.neurogenesis_data.setdefault('new_neurons', []).append(new_name)
        self.neurogenesis_data['last_neuron_time'] = time.time()
        self.neurogenesis_highlight = {
            'neuron': new_name,
            'start_time': time.time(),
            'duration': self.neurogenesis_config.get('highlight_duration', 5.0)
        }

        # Log the event
        log_creation_details = {
            "trigger_type": neuron_type,
            "trigger_value": round(trigger_reason_value, 2),
            "context": trigger_context_for_log
        }
        self.log_neurogenesis_event(new_name, "created", details=log_creation_details)

        # Apply repulsion forces to adjust layout
        self.apply_repulsion_force()

        return new_name

    def apply_repulsion_force(self, iterations=15, strength=0.6, threshold=120.0):
        """Applies a repulsion force between nearby neurons to spread them out."""

        neuron_list = [name for name in self.neuron_positions.keys() if name not in self.excluded_neurons]

        for _ in range(iterations):
            displacements = {name: [0.0, 0.0] for name in neuron_list}

            for i in range(len(neuron_list)):
                for j in range(i + 1, len(neuron_list)):
                    neuron1 = neuron_list[i]
                    neuron2 = neuron_list[j]

                    pos1 = self.neuron_positions[neuron1]
                    pos2 = self.neuron_positions[neuron2]

                    dx = pos1[0] - pos2[0]
                    dy = pos1[1] - pos2[1]

                    distance_sq = dx*dx + dy*dy

                    if 0 < distance_sq < threshold*threshold:
                        distance = math.sqrt(distance_sq)
                        force = strength * (threshold - distance) / distance
                        move_x = (dx / distance) * force
                        move_y = (dy / distance) * force
                        displacements[neuron1][0] += move_x
                        displacements[neuron1][1] += move_y
                        displacements[neuron2][0] -= move_x
                        displacements[neuron2][1] -= move_y

            damping = 0.5
            moved = False
            for name in neuron_list:
                if name in self.original_neuron_positions:
                   continue

                pos = self.neuron_positions[name]
                disp = displacements[name]

                if abs(disp[0]) > 0.1 or abs(disp[1]) > 0.1:
                    new_x = pos[0] + disp[0] * damping
                    new_y = pos[1] + disp[1] * damping
                    new_x = max(50, min(974, new_x))
                    new_y = max(50, min(668, new_y))
                    self.neuron_positions[name] = (new_x, new_y)
                    moved = True

            if not moved:
                break
        if moved:
           self.update()

    def update_weights(self):
        """
        Update weights by adding small random noise. 
        WARNING: This adds noise and might counteract Hebbian learning.
        Consider disabling or further reducing noise if learning seems unstable.
        """
        if self.frozen_weights is not None:
            return

        # --- MODIFIED: Iterate over a copy of the actual weight keys ---
        for conn in list(self.weights.keys()):
            # Check if the connection still exists (it might be pruned concurrently)
            if conn in self.weights:
                # Add a very small amount of noise/drift
                self.weights[conn] += random.uniform(-0.01, 0.01) # Reduced noise
                # Clamp the weight to stay within [-1, 1]
                self.weights[conn] = max(-1, min(1, self.weights[conn]))

    def freeze_weights(self):
        self.frozen_weights = self.weights.copy()

    def unfreeze_weights(self):
        self.frozen_weights = None

    def strengthen_connection(self, neuron1, neuron2, amount):
        pair = (neuron1, neuron2)
        reverse_pair = (neuron2, neuron1)
        if pair not in self.weights and reverse_pair not in self.weights:
            self.weights[pair] = 0.0
        use_pair = pair if pair in self.weights else reverse_pair
        self.weights[use_pair] += amount
        self.weights[use_pair] = max(-1, min(1, self.weights[use_pair]))
        self.update()

    def create_neuron(self, neuron_type, trigger_data):
        """Add after all other methods"""
        base_name = {'novelty': 'novel', 'stress': 'defense', 'reward': 'reward'}[neuron_type]
        new_name = f"{base_name}_{len(self.neurogenesis_data['new_neurons'])}"
        active_neurons = sorted([(k,v) for k,v in self.state.items() if isinstance(v, (int, float))], key=lambda x: x[1], reverse=True)
        base_x, base_y = self.neuron_positions[active_neurons[0][0]] if active_neurons else (600, 300)
        self.neuron_positions[new_name] = (base_x + random.randint(-50, 50), base_y + random.randint(-50, 50))
        self.neurogenesis_highlight = {'neuron': new_name, 'start_time': time.time(), 'duration': 5.0}
        self.update()
        self.state[new_name] = 50
        self.state_colors[new_name] = {'novelty': (255, 255, 150), 'stress': (255, 150, 150), 'reward': (150, 255, 150)}[neuron_type]
        default_weights = {'novelty': {'curiosity': 0.6, 'anxiety': -0.4}, 'stress': {'anxiety': -0.7, 'happiness': 0.3}, 'reward': {'satisfaction': 0.8, 'happiness': 0.5}}
        for target, weight in default_weights[neuron_type].items():
            self.weights[(new_name, target)] = weight
            self.weights[(target, new_name)] = weight * 0.5
        self.neurogenesis_data['new_neurons'].append(new_name)
        self.neurogenesis_data['last_neuron_time'] = time.time()
        return new_name

    def capture_training_data(self, state):
        training_sample = [state[neuron] for neuron in self.neuron_positions.keys()]
        self.training_data.append(training_sample)
        print("Captured training data:", training_sample)

    def train_hebbian(self):
        print("Starting Hebbian training...")
        for sample in self.training_data:
            for i in range(len(sample)):
                for j in range(i+1, len(sample)):
                    self.associations[i][j] += self.learning_rate * sample[i] * sample[j]
                    self.associations[j][i] = self.associations[i][j]
        self.training_data = []

    def get_association_strength(self, neuron1, neuron2):
        idx1 = list(self.neuron_positions.keys()).index(neuron1)
        idx2 = list(self.neuron_positions.keys()).index(neuron2)
        return self.associations[idx1][idx2]

    def draw_connections(self, painter, scale):
        if not self.show_links:
            return
        for key, weight in self.weights.items():
            if isinstance(key, tuple):
                if len(key) > 2 or 'is_fleeing' in key: continue
                source, target = key
            elif isinstance(key, str):
                try:
                    source, target = key.split('_')
                    if 'is_fleeing' in source or 'is_fleeing' in target: continue
                except ValueError: continue
            else: continue
            if (source not in self.neuron_positions or target not in self.neuron_positions or source in self.excluded_neurons or target in self.excluded_neurons): continue
            start = self.neuron_positions[source]
            end = self.neuron_positions[target]
            start_point = QtCore.QPointF(float(start[0]), float(start[1]))
            end_point = QtCore.QPointF(float(end[0]), float(end[1]))
            color = QtGui.QColor(0, int(255 * abs(weight)), 0) if weight > 0 else QtGui.QColor(int(255 * abs(weight)), 0, 0)
            if abs(weight) < 0.1: pen_style = QtCore.Qt.DotLine; line_width = 1 * scale
            elif abs(weight) < 0.3: pen_style = QtCore.Qt.SolidLine; line_width = 1 * scale
            elif abs(weight) < 0.6: pen_style = QtCore.Qt.SolidLine; line_width = 2 * scale
            else: pen_style = QtCore.Qt.SolidLine; line_width = 3 * scale
            painter.setPen(QtGui.QPen(color, line_width, pen_style))
            painter.drawLine(start_point, end_point)
            if self.show_weights and abs(weight) > 0.1:
                midpoint = QtCore.QPointF((start_point.x() + end_point.x()) / 2, (start_point.y() + end_point.y()) / 2)
                text_area_width, text_area_height = 80.0, 22.0
                font_size = max(8, min(12, int(8 * scale)))
                font = painter.font(); font.setPointSize(font_size); painter.setFont(font)
                rect = QtCore.QRectF(midpoint.x() - text_area_width / 2, midpoint.y() - text_area_height / 2, text_area_width, text_area_height)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0))); painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0))); painter.drawRect(rect)
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255))); painter.drawText(rect, QtCore.Qt.AlignCenter, f"{weight:.2f}")

    def _get_logical_coords(self, widget_pos):
        """Maps widget QPoint/QPointF to logical neuron coordinates."""
        indicator_space = 60
        base_width_logical = 1024
        base_height_logical = 768 - indicator_space
        scale_x = self.width() / base_width_logical
        scale_y = (self.height() - indicator_space) / base_height_logical
        scale = min(scale_x, max(0.1, scale_y))
        translate_y = indicator_space
        lx = widget_pos.x() / scale
        ly = (widget_pos.y() - translate_y) / scale
        return QtCore.QPointF(lx, ly)

    def get_neuron_at_pos(self, widget_pos):
        """Finds a neuron at the given QPoint widget coordinates."""
        logical_pos = self._get_logical_coords(widget_pos)
        neuron_radius = 25
        for name, pos in self.neuron_positions.items():
            dist_sq = (logical_pos.x() - pos[0])**2 + (logical_pos.y() - pos[1])**2
            if dist_sq <= neuron_radius**2:
                return name
        return None

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        painter.fillRect(self.rect(), QtGui.QColor(240, 240, 240))
        metrics_font = QtGui.QFont("Arial", 10); metrics_font.setBold(True); painter.setFont(metrics_font); painter.setPen(QtGui.QColor(0, 0, 0))
        metrics_text = f"Neurons: {self.get_neuron_count()}    Connections: {self.get_edge_count()}    Network Health: {self.calculate_network_health():.1f}%"
        painter.drawText(QtCore.QRectF(10, 5, self.width() - 20, 30), QtCore.Qt.AlignLeft | QtCore.Qt.AlignVCenter, metrics_text)
        indicator_y_position = 10; indicator_font = QtGui.QFont("Arial", 9, QtGui.QFont.Bold); painter.setFont(indicator_font); font_metrics = painter.fontMetrics()
        active_indicators_data = []
        if self.state.get('is_fleeing', False): active_indicators_data.append({"text": "Fleeing!", "color": QtGui.QColor(220, 20, 60)})
        if self.state.get('is_startled', False): active_indicators_data.append({"text": "Startled!", "color": QtGui.QColor(255, 165, 0)})
        if self.state.get('pursuing_food', False): active_indicators_data.append({"text": "Food?", "color": QtGui.QColor(60, 179, 113)})
        indicators_to_display = active_indicators_data[:2]
        padding_horizontal, padding_vertical, spacing_between_indicators, min_left_padding, right_padding_from_widget_edge = 8, 4, 10, 10, 100
        min_sensible_width = font_metrics.horizontalAdvance("...") + (2 * padding_horizontal)
        rect_height = font_metrics.height() + (2 * padding_vertical)
        current_target_right_edge_x = self.width() - right_padding_from_widget_edge
        for indicator_details in reversed(indicators_to_display):
            indicator_text_original = indicator_details["text"]; indicator_bg_color = indicator_details["color"]
            ideal_text_width = font_metrics.horizontalAdvance(indicator_text_original); ideal_rect_width = ideal_text_width + (2 * padding_horizontal)
            max_possible_width_for_this_indicator = current_target_right_edge_x - min_left_padding
            if max_possible_width_for_this_indicator < min_sensible_width: current_target_right_edge_x = min_left_padding - spacing_between_indicators; continue
            render_rect_width = min(ideal_rect_width, max_possible_width_for_this_indicator)
            if render_rect_width < min_sensible_width: current_target_right_edge_x = min_left_padding - spacing_between_indicators; continue
            render_rect_start_x = current_target_right_edge_x - render_rect_width
            indicator_rect = QtCore.QRectF(render_rect_start_x, indicator_y_position, render_rect_width, rect_height)
            painter.setBrush(indicator_bg_color); painter.setPen(QtCore.Qt.NoPen); painter.drawRoundedRect(indicator_rect, 4, 4)
            available_width_for_text = render_rect_width - (2 * padding_horizontal)
            elided_text = font_metrics.elidedText(indicator_text_original, QtCore.Qt.ElideRight, available_width_for_text)
            text_color = QtCore.Qt.white if indicator_bg_color.lightnessF() < 0.5 else QtCore.Qt.black
            painter.setPen(text_color); painter.drawText(indicator_rect, QtCore.Qt.AlignCenter, elided_text)
            current_target_right_edge_x = render_rect_start_x - spacing_between_indicators
        painter.save()
        fixed_indicator_area_height = rect_height + 10 if indicators_to_display else 30
        indicator_space_at_top = indicator_y_position + fixed_indicator_area_height
        base_width_logical = 1024; base_height_logical = 768 - indicator_space_at_top
        if base_height_logical <=0: base_height_logical = 1
        scale_x = self.width() / base_width_logical
        drawable_height_for_neurons = self.height() - indicator_space_at_top
        if drawable_height_for_neurons <= 0: drawable_height_for_neurons = 1
        scale_y = drawable_height_for_neurons / base_height_logical; scale_y = max(0.01, scale_y)
        scale = max(0.01, min(scale_x, scale_y))
        painter.translate(0, indicator_space_at_top); painter.scale(scale, scale)
        self.draw_neurons(painter, 1.0)
        if self.dragging and self.dragged_neuron:
            pos = self.neuron_positions[self.dragged_neuron]
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 3 / scale)); painter.setBrush(QtCore.Qt.NoBrush); painter.drawEllipse(QtCore.QPointF(pos[0], pos[1]), 30, 30)
        self.draw_neurogenesis_highlights(painter, 1.0)
        if self.show_links: self.draw_connections(painter, 1.0)
        painter.restore()

    def draw_neurons(self, painter, scale):
        """Draw all neurons with state validation and error handling"""
        for name, pos in self.neuron_positions.items():
            try:
                if name in self.excluded_neurons: continue
                shape = self.neuron_shapes.get(name, 'circle')
                value = self.state.get(name, 50)
                color = QtGui.QColor(*self.state_colors.get(name, (200, 200, 200)))

                # Check the shape and call the appropriate drawing function
                if shape == 'diamond': 
                    self.draw_diamond_neuron(painter, pos[0], pos[1], value, name, scale)
                elif shape == 'triangle': 
                    self.draw_triangular_neuron(painter, pos[0], pos[1], value, name, scale) # Draws triangle
                elif shape == 'square': 
                    self.draw_square_neuron(painter, pos[0], pos[1], value, name, scale) # Draws square
                else: 
                    # Default circular neuron
                    painter.setBrush(QtGui.QBrush(color)); 
                    painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0))); 
                    radius = 25 * scale; 
                    painter.drawEllipse(int(pos[0] - radius), int(pos[1] - radius), int(radius * 2), int(radius * 2)); 
                    self._draw_neuron_label(painter, pos[0], pos[1], name, scale)

            except Exception as e: print(f"Error drawing neuron {name}: {str(e)}")

    def draw_binary_neuron(self, painter, x, y, value, label, scale=1.0):
        color = (0, 0, 0) if value else (255, 255, 255)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(*color))); painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        x_scaled, y_scaled, size = int(x * scale), int(y * scale), int(30 * scale)
        painter.drawRect(x_scaled - size//2, y_scaled - size//2, size, size)
        font = painter.font(); font.setPointSize(int(8 * scale)); painter.setFont(font)
        label_width, label_height = int(150 * scale), int(20 * scale)
        painter.drawText(x_scaled - label_width//2, y_scaled + int(30 * scale), label_width, label_height, QtCore.Qt.AlignCenter, label)

    def draw_circular_neuron(self, painter, x, y, value, label, scale=1.0):
        color = QtGui.QColor(150, 255, 150); radius = 25 * scale
        painter.setBrush(QtGui.QBrush(color)); painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        painter.drawEllipse(int(x - radius), int(y - radius), int(radius*2), int(radius*2))
        self._draw_neuron_label(painter, x, y, label, scale)

    def draw_triangular_neuron(self, painter, x, y, value, label, scale=1.0):
        color = QtGui.QColor(*self.state_colors.get(label, (255, 255, 150)))
        self._draw_polygon_neuron(painter, x, y, 3, color, label, scale)

    def show_diagnostic_report(self):
        if hasattr(self, 'brain_widget'): self.brain_widget.show_diagnostic_report()
        else: print("Error: Brain widget not initialized")

    def _draw_polygon_neuron(self, painter, x, y, sides, color, label, scale, rotation=0):
        painter.save(); painter.translate(x, y); painter.rotate(rotation)
        painter.setBrush(QtGui.QBrush(color)); painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        polygon = QtGui.QPolygonF(); radius = 25 * scale; angle_step = 360.0 / sides
        for i in range(sides):
            angle = i * angle_step - 90
            polygon.append(QtCore.QPointF(radius * math.cos(math.radians(angle)), radius * math.sin(math.radians(angle))))
        painter.drawPolygon(polygon); painter.restore()
        self._draw_neuron_label(painter, x, y, label, scale)

    def _draw_neuron_label(self, painter, x, y, label, scale):
        painter.setPen(QtGui.QColor(0, 0, 0)); font = painter.font(); font.setPointSize(int(8 * scale)); painter.setFont(font)
        painter.drawText(int(x - 50*scale), int(y + 40*scale), int(100*scale), int(20*scale), QtCore.Qt.AlignCenter, label)

    def draw_neurogenesis_highlights(self, painter, scale):
        if (self.neurogenesis_highlight['neuron'] and time.time() - self.neurogenesis_highlight['start_time'] < self.neurogenesis_highlight['duration']):
            pos = self.neuron_positions.get(self.neurogenesis_highlight['neuron'])
            if pos:
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), int(3 * scale))); painter.setBrush(QtCore.Qt.NoBrush); radius = int(40 * scale)
                x, y, width, height = int(pos[0] - radius), int(pos[1] - radius), int(radius * 2), int(radius * 2)
                painter.drawEllipse(x, y, width, height)

    def draw_square_neuron(self, painter, x, y, value, label, scale=1.0):
        color = QtGui.QColor(*self.state_colors.get(label, (152, 251, 152)))
        self._draw_polygon_neuron(painter, x, y, 4, color, label, scale, rotation=45)

    def draw_diamond_neuron(self, painter, x, y, value, label, scale=1.0):
        color = QtGui.QColor(*self.state_colors.get(label, (152, 251, 152)))
        self._draw_polygon_neuron(painter, x, y, 4, color, label, scale, rotation=00)

    def toggle_links(self, state):
        self.show_links = state == QtCore.Qt.Checked
        self.update()

    def toggle_weights(self, state):
        self.show_weights = state == QtCore.Qt.Checked
        self.update()

    def toggle_capture_training_data(self, state):
        self.capture_training_data_enabled = state

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            neuron = self.get_neuron_at_pos(event.pos())
            if neuron: self.dragged_neuron = neuron; self.dragging = True; self.drag_start_pos = event.pos(); self.update()
            else: self.dragged_neuron = None; self.dragging = False
        super().mousePressEvent(event)

    def handle_neuron_clicked(self, neuron_name):
        print(f"Neuron clicked: {neuron_name}")

    def show_diagnostic_report(self):
        dialog = DiagnosticReportDialog(self, self.parent())
        dialog.exec_()

    def mouseMoveEvent(self, event):
        if self.dragging and self.dragged_neuron:
            logical_pos = self._get_logical_coords(event.pos())
            self.neuron_positions[self.dragged_neuron] = (logical_pos.x(), logical_pos.y())
            self.update()
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            is_click = False
            if self.dragged_neuron and self.drag_start_pos:
                distance = (event.pos() - self.drag_start_pos).manhattanLength()
                if distance < QtWidgets.QApplication.startDragDistance(): is_click = True
            if is_click: self.neuronClicked.emit(self.dragged_neuron)
            self.dragging = False
            self.dragged_neuron = None
            self.drag_start_pos = None
            self.update()
            # Apply repulsion forces to settle network after drag/click
            self.apply_repulsion_force()
        super().mouseReleaseEvent(event)

    def _is_click_on_neuron(self, point, neuron_pos, scale):
        neuron_x, neuron_y = neuron_pos
        scaled_x = neuron_x * scale; scaled_y = neuron_y * scale
        return (abs(scaled_x - point.x()) <= 25 * scale and abs(scaled_y - point.y()) <= 25 * scale)

    def is_point_inside_neuron(self, point, neuron_pos, scale):
        neuron_x, neuron_y = neuron_pos
        scaled_x = neuron_x * scale; scaled_y = neuron_y * scale
        return ((scaled_x - 25 * scale) <= point.x() <= (scaled_x + 25 * scale) and (scaled_y - 25 * scale) <= point.y() <= (scaled_y + 25 * scale))

    def reset_positions(self):
        self.neuron_positions = self.original_neuron_positions.copy()
        self.update()