

import sys
import csv
import os
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtGui import QPixmap, QFont

import random
import numpy as np
import json
from .personality import Personality
from .learning import LearningConfig

class BrainWidget(QtWidgets.QWidget):
    def __init__(self, config=None, debug_mode=False): 
        super().__init__()
        # Initialize with config
        self.config = config if config else LearningConfig()
        self.debug_mode = debug_mode  # Initialize debug_mode
        self.is_paused = False
        
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
        self.neurogenesis_data = {
            'novelty_counter': 0,
            'new_neurons': [],
            'last_neuron_time': time.time()
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
            "hunger": (150, 150),
            "happiness": (450, 150),
            "cleanliness": (750, 150),
            "sleepiness": (1050, 150),
            "satisfaction": (300, 350),
            "anxiety": (600, 350),
            "curiosity": (900, 350)
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
                brain_state = self.brain_widget.save_brain_state()
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
        return len(self.neuron_positions)
    
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

                color = QtGui.QColor(0, int(255 * abs(weight)), 0) if weight > 0 else QtGui.QColor(int(255 * abs(weight)), 0, 0)
                painter.setPen(QtGui.QPen(color, 2))
                painter.drawLine(start[0], start[1], end[0], end[1])

                midpoint = ((start[0] + end[0]) // 2, (start[1] + end[1]) // 2)
                painter.setPen(QtGui.QColor(0, 0, 0))

                # Increase the area for drawing the weights
                text_area_width = 60
                text_area_height = 20

                # Adjust the font size based on the scale with a maximum font size
                max_font_size = 12
                font_size = max(8, min(max_font_size, int(8 * scale)))
                font = painter.font()
                font.setPointSize(font_size)
                painter.setFont(font)

                painter.drawText(midpoint[0] - text_area_width // 2, midpoint[1] - text_area_height // 2, text_area_width, text_area_height, QtCore.Qt.AlignCenter, f"{weight:.2f}")

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
        # Original neurons
        original_neurons = list(self.original_neuron_positions.keys())
        
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
            else:
                # Neurogenesis-created neurons (triangular)
                self.draw_triangular_neuron(painter, pos[0], pos[1], 
                                          self.state[name], name, scale=scale)

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

    def draw_text(self, painter, x, y, text, scale=1.0):
        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(x - 75, y + 10, 150, 20, QtCore.Qt.AlignCenter, text)

    def toggle_links(self, state):
        self.show_links = state == QtCore.Qt.Checked
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

class StimulateDialog(QtWidgets.QDialog):
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stimulate Brain")
        self.brain_widget = brain_widget
        
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        self.form_layout = QtWidgets.QFormLayout()
        self.layout.addLayout(self.form_layout)

        self.neuron_inputs = {}
        neurons = ["hunger", "happiness", "cleanliness", "sleepiness", 
                  "is_sick", "is_eating", "is_sleeping", "pursuing_food", "direction"]
        
        # Load current values from brain widget
        current_state = self.brain_widget.state
        
        for neuron in neurons:
            current_value = current_state.get(neuron, None)
            
            if neuron.startswith("is_"):
                input_widget = QtWidgets.QComboBox()
                input_widget.addItems(["False", "True"])
                if current_value is not None:
                    input_widget.setCurrentText(str(current_value))
            elif neuron == "direction":
                input_widget = QtWidgets.QComboBox()
                input_widget.addItems(["up", "down", "left", "right"])
                if current_value is not None:
                    input_widget.setCurrentText(current_value)
            else:
                input_widget = QtWidgets.QSpinBox()
                input_widget.setRange(0, 100)
                if current_value is not None:
                    input_widget.setValue(int(current_value))
                
                # Prevent manual entry of invalid values
                input_widget.setKeyboardTracking(False)
                input_widget.lineEdit().setValidator(QtGui.QIntValidator(0, 100))
            
            self.form_layout.addRow(neuron, input_widget)
            self.neuron_inputs[neuron] = input_widget

        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.buttons.accepted.connect(self.validate_and_accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def validate_and_accept(self):
        """Validate all fields before accepting the dialog"""
        try:
            # Validate all spinbox values
            for neuron, widget in self.neuron_inputs.items():
                if isinstance(widget, QtWidgets.QSpinBox):
                    value = widget.value()
                    if value < 0 or value > 100:
                        QtWidgets.QMessageBox.warning(
                            self, "Invalid Value", 
                            f"{neuron} must be between 0 and 100"
                        )
                        return
                        
            # If all validations pass, accept the dialog
            self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Validation Error", 
                f"An error occurred during validation: {str(e)}"
            )

    def get_stimulation_values(self):
        """Get stimulation values with proper type conversion"""
        stimulation_values = {}
        for neuron, input_widget in self.neuron_inputs.items():
            if isinstance(input_widget, QtWidgets.QSpinBox):
                stimulation_values[neuron] = input_widget.value()
            elif isinstance(input_widget, QtWidgets.QComboBox):
                text = input_widget.currentText()
                if text.lower() == 'true':
                    stimulation_values[neuron] = True
                elif text.lower() == 'false':
                    stimulation_values[neuron] = False
                else:
                    stimulation_values[neuron] = text
        return stimulation_values

class SquidBrainWindow(QtWidgets.QMainWindow):
    def __init__(self, tamagotchi_logic, debug_mode=False, config=None):
        super().__init__()
        # Initialize font size FIRST
        self.base_font_size = 8
        self.debug_mode = debug_mode
        self.config = config if config else LearningConfig()  # Initialize config
        self.tamagotchi_logic = tamagotchi_logic
        self.initialized = False
        self.brain_widget = BrainWidget(self.config, self.debug_mode)
        self.setWindowTitle("Brain Tool")
        self.resize(1280, 768)

        # Initialize logging variables
        self.is_logging = False
        self.thought_log = []

        screen = QtWidgets.QDesktopWidget().screenNumber(QtWidgets.QDesktopWidget().cursor().pos())
        screen_geometry = QtWidgets.QDesktopWidget().screenGeometry(screen)
        self.move(screen_geometry.right() - 1280, screen_geometry.top())

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QtWidgets.QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.init_tabs()

        self.hebbian_timer = QtCore.QTimer()
        self.hebbian_timer.timeout.connect(self.perform_hebbian_learning)
        self.hebbian_timer.start(self.config.hebbian.get('learning_interval', 30000))
        self.hebbian_countdown_seconds = 0
        self.last_hebbian_time = time.time()  # Track last learning time

        # Add countdown timer
        self.countdown_timer = QtCore.QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)  # Update every second


        # Add countdown display to learning tab
        self.countdown_label = QtWidgets.QLabel()
        self.learning_tab_layout.insertWidget(0, self.countdown_label)
        
        self.last_hebbian_time = time.time()

        # Add a last_hebbian_time tracking variable
        self.last_hebbian_time = time.time()

        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_associations)
        self.update_timer.start(10000)  # Update every 10 seconds
        self.last_update_time = time.time()
        self.update_threshold = 5  # Minimum seconds between updates

        self.log_window = None
        self.learning_data = []
        self.is_paused = False
        self.console = ConsoleOutput(self.console_output)

        # Initialize memory text widgets
        self.short_term_memory_text = QtWidgets.QTextEdit()
        self.short_term_memory_text.setReadOnly(True)
        self.short_term_memory_text.setAcceptRichText(True)

        self.long_term_memory_text = QtWidgets.QTextEdit()
        self.long_term_memory_text.setReadOnly(True)
        self.long_term_memory_text.setAcceptRichText(True)

        self.memory_tab_layout.addWidget(QtWidgets.QLabel("Short-term Memories:"))
        self.memory_tab_layout.addWidget(self.short_term_memory_text)
        self.memory_tab_layout.addWidget(QtWidgets.QLabel("Long-term Memories:"))
        self.memory_tab_layout.addWidget(self.long_term_memory_text)

        # Set up a timer to update the memory tab
        self.memory_update_timer = QtCore.QTimer(self)
        self.memory_update_timer.timeout.connect(self.update_memory_tab)
        self.memory_update_timer.start(2000)  # Update every 2 secs
        self.init_thought_process_tab()

        def set_debug_mode(self, enabled):
            self.debug_mode = enabled
            if hasattr(self, 'brain_widget'):
                self.brain_widget.debug_mode = enabled
            self.update()


    def on_hebbian_countdown_finished(self):
        """Called when the Hebbian learning countdown reaches zero"""
        pass

    def set_pause_state(self, is_paused):
        self.is_paused = is_paused
        if hasattr(self, 'brain_widget'):
            self.brain_widget.is_paused = is_paused
        if is_paused:
            self.hebbian_timer.stop()
        else:
            self.hebbian_timer.start(self.config.hebbian['learning_interval'])

    def init_inspector(self):
        self.inspector_action = QtWidgets.QAction("Neuron Inspector", self)
        self.inspector_action.triggered.connect(self.show_inspector)
        self.debug_menu.addAction(self.inspector_action)

    def show_inspector(self):
        if not hasattr(self, '_inspector') or not self._inspector:
            self._inspector = NeuronInspector(self.brain_widget)
        self._inspector.show()
        self._inspector.raise_()

    def debug_print(self, message):
        if self.debug_mode:
            print(f"DEBUG: {message}")

    def toggle_debug_mode(self, enabled):
        self.debug_mode = enabled
        self.debug_print(f"Debug mode {'enabled' if enabled else 'disabled'}")
        # Update stimulate button state
        if hasattr(self, 'stimulate_button'):
            self.stimulate_button.setEnabled(enabled)

    def get_brain_state(self):
        weights = {}
        for k, v in self.brain_widget.weights.items():
            if isinstance(k, tuple):
                key = f"{k[0]}_{k[1]}"
            else:
                key = str(k)
            weights[key] = v

        return {
            'weights': weights,
            'neuron_positions': {str(k): v for k, v in self.brain_widget.neuron_positions.items()}
        }

    def set_brain_state(self, state):
        if 'weights' in state:
            weights = {}
            for k, v in state['weights'].items():
                if '_' in k:
                    key = tuple(k.split('_'))
                else:
                    key = k
                weights[key] = v
            self.brain_widget.weights = weights

        if 'neuron_positions' in state:
            self.brain_widget.neuron_positions = {k: v for k, v in state['neuron_positions'].items()}

        self.brain_widget.update()  # Trigger a redraw of the brain widget

    def init_tabs(self):
        # First create the tab widget
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # Set base font for all tab content
        base_font = QtGui.QFont()
        base_font.setPointSize(self.base_font_size)
        self.tabs.setFont(base_font)
        
        # Create brain widget after tabs are set up
        self.brain_widget = BrainWidget(self.config)
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)

        # Main tab
        self.main_tab = QtWidgets.QWidget()
        self.main_tab_layout = QtWidgets.QVBoxLayout()
        self.main_tab.setLayout(self.main_tab_layout)
        self.tabs.addTab(self.main_tab, "Network")

        # Create a widget to hold the brain visualization and controls
        main_content_widget = QtWidgets.QWidget()
        main_content_layout = QtWidgets.QVBoxLayout()
        main_content_widget.setLayout(main_content_layout)

        # Add brain widget to the main content layout
        self.brain_widget = BrainWidget()
        self.brain_widget.show_links = True
        main_content_layout.addWidget(self.brain_widget, 1)  # Give it a stretch factor of 1

        # Add checkbox for neuron links and weights
        self.checkbox_links = QtWidgets.QCheckBox("Show neuron links and weights")
        self.checkbox_links.setChecked(True)
        self.checkbox_links.stateChanged.connect(self.brain_widget.toggle_links)
        main_content_layout.addWidget(self.checkbox_links)

        # Create button layout
        button_layout = QtWidgets.QHBoxLayout()
        self.stimulate_button = self.create_button("Stimulate", self.stimulate_brain, "#d3d3d3")
        self.stimulate_button.setEnabled(self.debug_mode)
        self.save_button = self.create_button("Save State", self.save_brain_state, "#d3d3d3")
        self.load_button = self.create_button("Load State", self.load_brain_state, "#d3d3d3")
        self.report_button = self.create_button("Network Report", self.brain_widget.show_diagnostic_report, "#ADD8E6")

        button_layout.addWidget(self.report_button)
        button_layout.addWidget(self.stimulate_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)

        main_content_layout.addLayout(button_layout)

        # Add the main content widget to the main tab layout
        self.main_tab_layout.addWidget(main_content_widget)

        # Thoughts tab
        self.thoughts_tab = QtWidgets.QWidget()
        self.thoughts_tab_layout = QtWidgets.QVBoxLayout()
        self.thoughts_tab.setLayout(self.thoughts_tab_layout)
        self.tabs.addTab(self.thoughts_tab, "Thoughts")
        self.init_thoughts_tab()

        # Personality tab - initialize but don't add to tab widget
        self.personality_tab = QtWidgets.QWidget()
        self.personality_tab_layout = QtWidgets.QVBoxLayout()
        self.personality_tab.setLayout(self.personality_tab_layout)
        # Comment out or remove this line:
        # self.tabs.addTab(self.personality_tab, "Personality")
        self.init_personality_tab()  # Still initialize the tab contents

        # Learning tab
        self.learning_tab = QtWidgets.QWidget()
        self.learning_tab_layout = QtWidgets.QVBoxLayout()
        self.learning_tab.setLayout(self.learning_tab_layout)
        self.tabs.addTab(self.learning_tab, "Learning")
        self.init_learning_tab()

        # Associations tab
        self.associations_tab = QtWidgets.QWidget()
        self.associations_tab_layout = QtWidgets.QVBoxLayout()
        self.associations_tab.setLayout(self.associations_tab_layout)
        self.tabs.addTab(self.associations_tab, "Associations")
        self.init_associations_tab()

        # Console tab
        self.console_tab = QtWidgets.QWidget()
        self.console_tab_layout = QtWidgets.QVBoxLayout()
        self.console_tab.setLayout(self.console_tab_layout)
        self.tabs.addTab(self.console_tab, "Console")
        self.init_console()

        # Remove the console and thought tabs
        self.tabs.removeTab(self.tabs.indexOf(self.console_tab))
        self.tabs.removeTab(self.tabs.indexOf(self.thoughts_tab))
        self.tabs.removeTab(self.tabs.indexOf(self.associations_tab))

        # Add a new memory tab
        self.memory_tab = QtWidgets.QWidget()
        self.memory_tab_layout = QtWidgets.QVBoxLayout()
        self.memory_tab.setLayout(self.memory_tab_layout)
        self.tabs.addTab(self.memory_tab, "Memory")
        self.init_memory_tab()

        # Decisions tab - initialize but don't add to tab widget
        self.decisions_tab = QtWidgets.QWidget()
        self.decisions_tab_layout = QtWidgets.QVBoxLayout()
        self.decisions_tab.setLayout(self.decisions_tab_layout)
        # self.tabs.addTab(self.decisions_tab, "Decisions")
        self.init_decisions_tab()  # Still initialize the tab contents

        # About tab
        self.about_tab = QtWidgets.QWidget()
        self.about_tab_layout = QtWidgets.QVBoxLayout()
        self.about_tab.setLayout(self.about_tab_layout)
        self.tabs.addTab(self.about_tab, "About")
        self.init_about_tab()


    def init_thought_process_tab(self):
        """Initialize the thinking tab with visualizations focused on the decision engine"""
        self.thought_process_tab = QtWidgets.QWidget()
        self.thought_process_layout = QtWidgets.QVBoxLayout()
        self.thought_process_tab.setLayout(self.thought_process_layout)
        self.thought_process_layout.setContentsMargins(0, 0, 0, 0)  # Remove extra margins

        # Create a QSplitter for resizable sections
        main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.thought_process_layout.addWidget(main_splitter)

        # Top section: Decision weights visualization
        self.weights_widget = QtWidgets.QWidget()
        weights_layout = QtWidgets.QVBoxLayout(self.weights_widget)
        
        weights_title = QtWidgets.QLabel("<h2>Decision Weights</h2>")
        weights_title.setAlignment(QtCore.Qt.AlignCenter)
        weights_layout.addWidget(weights_title)
        
        # Create a scene for the decision weights bars
        self.weights_scene = QtWidgets.QGraphicsScene()
        self.weights_view = QtWidgets.QGraphicsView(self.weights_scene)
        self.weights_view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.weights_view.setMinimumHeight(200)
        weights_layout.addWidget(self.weights_view)
        
        # Add the weights widget to the splitter
        main_splitter.addWidget(self.weights_widget)

        # Middle section: Decision flow
        self.flow_widget = QtWidgets.QWidget()
        flow_layout = QtWidgets.QVBoxLayout(self.flow_widget)
        
        flow_title = QtWidgets.QLabel("<h2>Decision Flow</h2>")
        flow_title.setAlignment(QtCore.Qt.AlignCenter)
        flow_layout.addWidget(flow_title)
        
        # Horizontal flow diagram
        flow_diagram = QtWidgets.QWidget()
        flow_diagram_layout = QtWidgets.QHBoxLayout(flow_diagram)
        
        # 1. Input factors group - made wider
        inputs_group = QtWidgets.QGroupBox("Input State")
        inputs_layout = QtWidgets.QVBoxLayout(inputs_group)
        
        self.inputs_table = QtWidgets.QTableWidget()
        self.inputs_table.setColumnCount(2)
        self.inputs_table.setHorizontalHeaderLabels(["Factor", "Value"])
        self.inputs_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        inputs_layout.addWidget(self.inputs_table)
        
        flow_diagram_layout.addWidget(inputs_group, stretch=1)  # Add stretch factor
        
        # Arrow1
        arrow_pixmap = QPixmap("images/arrow.png")
        arrow1 = QtWidgets.QLabel()
        arrow1.setPixmap(arrow_pixmap)
        arrow1.setAlignment(QtCore.Qt.AlignCenter)
        flow_diagram_layout.addWidget(arrow1)
        
        # 2. Memory influence - made wider
        memory_group = QtWidgets.QGroupBox("Memory Influence")
        memory_layout = QtWidgets.QVBoxLayout(memory_group)
        
        self.memory_list = QtWidgets.QListWidget()
        memory_layout.addWidget(self.memory_list)
        
        flow_diagram_layout.addWidget(memory_group, stretch=1)  # Add stretch factor
        
        # Arrow2
        arrow_pixmap = QPixmap("images/arrow.png")
        arrow2 = QtWidgets.QLabel()
        arrow2.setPixmap(arrow_pixmap)
        arrow2.setAlignment(QtCore.Qt.AlignCenter)
        flow_diagram_layout.addWidget(arrow2)
        
        # 3. Final decision
        decision_group = QtWidgets.QGroupBox("Final Decision")
        decision_layout = QtWidgets.QVBoxLayout(decision_group)
        
        self.decision_output = QtWidgets.QLabel("exploring")
        self.decision_output.setAlignment(QtCore.Qt.AlignCenter)
        self.decision_output.setStyleSheet("font-size: 24px; font-weight: bold;")  # Bigger text
        decision_layout.addWidget(self.decision_output)
        
        self.decision_confidence = QtWidgets.QProgressBar()
        self.decision_confidence.setRange(0, 100)
        self.decision_confidence.setValue(60)
        self.decision_confidence.setFixedHeight(16)  # Set height to 16px
        decision_layout.addWidget(QtWidgets.QLabel("Confidence:"))
        decision_layout.addWidget(self.decision_confidence)
        
        self.decision_explanation = QtWidgets.QLabel("Chosen due to high curiosity")
        self.decision_explanation.setWordWrap(True)
        decision_layout.addWidget(self.decision_explanation)
        
        flow_diagram_layout.addWidget(decision_group)
        
        # Add the flow diagram to the layout
        flow_layout.addWidget(flow_diagram)
        
        # Add the flow widget to the splitter
        main_splitter.addWidget(self.flow_widget)

        # Bottom section: Thought log
        self.log_widget = QtWidgets.QWidget()
        log_layout = QtWidgets.QVBoxLayout(self.log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)  # Remove padding
        
        log_title = QtWidgets.QLabel("<h2>Decision Log</h2>")
        log_title.setAlignment(QtCore.Qt.AlignCenter)
        log_layout.addWidget(log_title)
        
        # Thought log
        self.thought_log_text = QtWidgets.QTextEdit()
        self.thought_log_text.setReadOnly(True)
        # Set default text
        self.thought_log_text.setHtml("<p style='color: gray;'>Start logging by clicking the green button "
                "and perform some actions with your squid to generate logs <br> Then use the 'view logs' button</p>")
        log_layout.addWidget(self.thought_log_text)
        
        # Controls
        controls_layout = QtWidgets.QHBoxLayout()
        
        self.logging_button = QtWidgets.QPushButton("Start Logging")
        self.logging_button.setCheckable(True)
        # Initially set to green
        self.logging_button.setStyleSheet("""
            background-color: green; 
            color: white; 
            font-weight: bold;
        """)
        self.logging_button.clicked.connect(self.toggle_logging)
        controls_layout.addWidget(self.logging_button)
        
        # NEW: Add View Logs button
        self.view_logs_button = QtWidgets.QPushButton("View Logs")
        self.view_logs_button.clicked.connect(self.view_thought_logs)
        controls_layout.addWidget(self.view_logs_button)
        
        log_layout.addLayout(controls_layout)
        
        # Add the log widget to the splitter
        main_splitter.addWidget(self.log_widget)
        
        # Set initial splitter sizes
        main_splitter.setSizes([250, 300, 200])
        
        # Set up the initial visualization
        self.initialize_weights_visualization()
        
        # Add the tab
        self.tabs.addTab(self.thought_process_tab, "Decisions")
        
        # Initialize state
        self.is_logging = False
        self.thought_log = []

    def view_thought_logs(self):
        """Open a window to view captured decision logs"""
        # Check if there are any thought logs
        if not self.thought_log:
            # Display a friendly message if no logs exist
            QtWidgets.QMessageBox.information(
                self, 
                "No Logs Available", 
                "No decision logs have been captured yet.\n\n"
                "Start logging by clicking the 'Start Logging' button "
                "and perform some actions with your squid to generate logs!"
            )
            return

        # Open the RecentThoughtsDialog with the captured logs
        log_viewer = RecentThoughtsDialog(self.thought_log, self)
        log_viewer.exec_()

    def toggle_logging(self):
        """Toggle decision logging on/off"""
        # Don't allow enabling logging if simulation is paused
        if not self.is_logging and hasattr(self, 'is_paused') and self.is_paused:
            self.logging_button.setChecked(False)  # Reset the button state
            return  # Exit without changing logging state

        self.is_logging = not self.is_logging
        
        if self.is_logging:
            # Red when logging is active
            self.logging_button.setStyleSheet("""
                background-color: red; 
                color: white; 
                font-weight: bold;
            """)
            self.logging_button.setText("Stop Logging")
            # Clear the default text
            self.thought_log_text.clear()
            self.thought_log_text.append("<b>--- Logging started ---</b>")
        else:
            # Green when logging is inactive
            self.logging_button.setStyleSheet("""
                background-color: green; 
                color: white; 
                font-weight: bold;
            """)
            self.logging_button.setText("Start Logging")
            self.thought_log_text.append("<b>--- Logging stopped ---</b>")
            
            # If no logs were added, revert to default text
            if not self.thought_log:
                self.thought_log_text.setHtml("<p style='color: gray;'>Logging has not been started</p>")
        
        self.logging_button.setChecked(self.is_logging)

    def initialize_weights_visualization(self):
        """Initialize the decision weights visualization"""
        # Clear the scene
        self.weights_scene.clear()
        
        # Add a white background
        self.weights_scene.addRect(0, 0, 700, 180, 
                                QtGui.QPen(QtCore.Qt.NoPen),
                                QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        
        # Add title and legend
        title = self.weights_scene.addText("Decision Action Weights")
        title.setPos(250, 10)
        
        # Add legend items
        self.weights_scene.addRect(580, 30, 20, 10, QtGui.QPen(QtCore.Qt.black), 
                                QtGui.QBrush(QtGui.QColor(120, 180, 255)))
        normal_legend = self.weights_scene.addText("Base Weight")
        normal_legend.setPos(605, 25)
        
        self.weights_scene.addRect(580, 50, 20, 10, QtGui.QPen(QtCore.Qt.black), 
                                QtGui.QBrush(QtGui.QColor(255, 120, 120)))
        adjusted_legend = self.weights_scene.addText("After Personality")
        adjusted_legend.setPos(605, 45)
        
        # Add initial bars (we'll update these later)
        self.weight_bars = {}
        self.weight_labels = {}
        self.weight_values = {}
        
        actions = ["exploring", "eating", "approaching_rock", 
                "throwing_rock", "avoiding_threat", "organizing"]
        
        for i, action in enumerate(actions):
            x = 50
            y = 40 + i * 22
            width = 200  # Initial width, will be updated
            height = 15
            
            # Add label
            label = self.weights_scene.addText(action)
            label.setPos(x - 120, y - 5)
            self.weight_labels[action] = label
            
            # Add base weight bar (blue)
            base_bar = self.weights_scene.addRect(x, y, width, height, 
                                                QtGui.QPen(QtCore.Qt.black),
                                                QtGui.QBrush(QtGui.QColor(120, 180, 255)))
            
            # Add adjusted weight bar (red) - starts at same size
            adjusted_bar = self.weights_scene.addRect(x, y, width, height, 
                                                    QtGui.QPen(QtCore.Qt.black),
                                                    QtGui.QBrush(QtGui.QColor(255, 120, 120)))
            
            # Add value text
            value_text = self.weights_scene.addText("0.0")
            value_text.setPos(x + width + 10, y - 5)
            self.weight_values[action] = value_text
            
            # Store references
            self.weight_bars[action] = {
                "base": base_bar,
                "adjusted": adjusted_bar
            }
        
        # Add highlight for selected decision (initially hidden)
        self.selected_decision_highlight = self.weights_scene.addRect(0, 0, 0, 0, 
                                                                    QtGui.QPen(QtGui.QColor(0, 200, 0), 2),
                                                                    QtGui.QBrush(QtCore.Qt.NoBrush))
        self.selected_decision_highlight.setVisible(False)
        
        # Make sure scene is properly sized
        self.weights_scene.setSceneRect(self.weights_scene.itemsBoundingRect())

    def export_thought_log(self):
        """Export the thought log to a file"""
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Thought Log", "", "Text Files (*.txt);;HTML Files (*.html)"
        )
        
        if file_name:
            try:
                if file_name.endswith('.html'):
                    with open(file_name, 'w') as f:
                        f.write("<html><body>\n")
                        f.write(self.thought_log_text.toHtml())
                        f.write("</body></html>")
                else:
                    with open(file_name, 'w') as f:
                        f.write(self.thought_log_text.toPlainText())
                
                QtWidgets.QMessageBox.information(self, "Export Successful", f"Thought log exported to {file_name}")
            except Exception as e:
                QtWidgets.QMessageBox.critical(self, "Export Error", f"Error exporting log: {str(e)}")

    def show_recent_thoughts(self):
        """Show the recent thoughts dialog"""
        dialog = RecentThoughtsDialog(self.thought_log, self.window)
        dialog.exec_()

    def update_thought_process(self, decision_data):
        """Update the thinking tab visualizations with new decision data"""
        if not hasattr(self, 'weight_bars') or not self.weight_bars:
            self.initialize_weights_visualization()
        
        # If simulation is paused, override confidence to 0
        if self.is_paused:
            decision_data['confidence'] = 0.0
        
        # Extract the key data from decision_data
        inputs = decision_data.get('inputs', {})
        personality = decision_data.get('personality_influence', 'unknown')
        decision = decision_data.get('final_decision', 'exploring')
        confidence = decision_data.get('confidence', 0.5)
        weights = decision_data.get('weights', {})
        adjusted_weights = decision_data.get('adjusted_weights', {})
        active_memories = decision_data.get('active_memories', [])
        
        # 1. Update the weights visualization
        self.update_weights_visualization(weights, adjusted_weights, decision)
        
        # 2. Update the inputs table
        self.update_inputs_table(inputs)
        
        # 3. Update memory influences
        self.update_memory_list(active_memories)
        
        # 4. Update decision output
        self.update_decision_output(decision, confidence, weights, adjusted_weights)
        
        # 5. Add to thought log if logging is enabled
        if self.is_logging:
            self.add_to_thought_log(decision_data)

    def update_weights_visualization(self, weights, adjusted_weights, selected_decision):
        """Update the decision weights visualization bars"""
        max_weight = max(max(weights.values(), default=0), max(adjusted_weights.values(), default=0), 1.0)
        scale_factor = 400 / max_weight  # Scale to fit in 400px width
        
        for action, bar_items in self.weight_bars.items():
            # Get base and adjusted weights
            base_weight = weights.get(action, 0)
            adjusted_weight = adjusted_weights.get(action, base_weight)
            
            # Update the bars
            base_width = base_weight * scale_factor
            adjusted_width = adjusted_weight * scale_factor
            
            bar_items["base"].setRect(bar_items["base"].rect().x(), 
                                    bar_items["base"].rect().y(),
                                    base_width, 
                                    bar_items["base"].rect().height())
            
            bar_items["adjusted"].setRect(bar_items["adjusted"].rect().x(), 
                                        bar_items["adjusted"].rect().y(),
                                        adjusted_width, 
                                        bar_items["adjusted"].rect().height())
            
            # Update value text
            self.weight_values[action].setPlainText(f"{adjusted_weight:.2f}")
            
            # Highlight the selected decision
            if action == selected_decision:
                rect = bar_items["adjusted"].rect()
                self.selected_decision_highlight.setRect(
                    rect.x() - 5, rect.y() - 2, rect.width() + 10, rect.height() + 4
                )
                self.selected_decision_highlight.setVisible(True)

    def update_inputs_table(self, inputs):
        """Update the input state table"""
        # Keep only numerical inputs for simplicity
        numerical_inputs = {k: v for k, v in inputs.items() 
                        if isinstance(v, (int, float))}
        
        # Sort by value, highest first
        sorted_inputs = sorted(numerical_inputs.items(), 
                            key=lambda x: x[1], reverse=True)
        
        # Update table
        self.inputs_table.setRowCount(len(sorted_inputs))
        
        for i, (factor, value) in enumerate(sorted_inputs):
            # Factor name
            name_item = QtWidgets.QTableWidgetItem(factor)
            self.inputs_table.setItem(i, 0, name_item)
            
            # Value with color coding
            value_item = QtWidgets.QTableWidgetItem(f"{int(value)}")
            if value > 70:
                value_item.setForeground(QtGui.QColor("darkred"))
            elif value < 30:
                value_item.setForeground(QtGui.QColor("blue"))
            self.inputs_table.setItem(i, 1, value_item)

    def update_decision_output(self, decision, confidence, weights, adjusted_weights):
        """Update the final decision output"""
        self.decision_output.setText(decision.capitalize())
        self.decision_confidence.setValue(int(confidence * 100))
        
        # Generate explanation
        weight = adjusted_weights.get(decision, 0)
        runner_up = ""
        runner_up_weight = 0
        
        for action, action_weight in adjusted_weights.items():
            if action != decision and action_weight > runner_up_weight:
                runner_up = action
                runner_up_weight = action_weight
        
        if runner_up:
            difference = weight - runner_up_weight
            explanation = f"Chosen over {runner_up} by {difference:.2f} points"
        else:
            explanation = f"Selected with weight {weight:.2f}"
        
        self.decision_explanation.setText(explanation)

    def update_randomness_factors(self, randomness):
        """Update the randomness factors table"""
        self.random_factors_table.setRowCount(len(randomness))
        
        for i, (action, factor) in enumerate(randomness.items()):
            # Action name
            action_item = QtWidgets.QTableWidgetItem(action)
            self.random_factors_table.setItem(i, 0, action_item)
            
            # Random factor
            value_item = QtWidgets.QTableWidgetItem(f"{factor:.2f}")
            color = QtGui.QColor("darkgreen") if factor > 1.0 else QtGui.QColor("darkred")
            value_item.setForeground(color)
            self.random_factors_table.setItem(i, 1, value_item)

    def add_to_thought_log(self, decision_data):
        """Add the current decision process to the thought log"""
        # Skip logging if paused
        if hasattr(self, 'is_paused') and self.is_paused:
            return
            
        if not self.is_logging:
            return
            
        timestamp = time.strftime("%H:%M:%S")
        decision = decision_data.get('final_decision', 'unknown')
        confidence = decision_data.get('confidence', 0.0)
        
        # Create log entry
        entry = f"[{timestamp}] <b>Decision: {decision}</b> (Confidence: {confidence:.2f})<br>"
        
        # Add more details
        personality = decision_data.get('personality_influence', 'unknown')
        entry += f"<i>Personality {personality} applied the following modifiers:</i><br>"
        
        # Show weight modifications
        weights = decision_data.get('weights', {})
        adjusted_weights = decision_data.get('adjusted_weights', {})
        
        for action, weight in weights.items():
            adjusted = adjusted_weights.get(action, weight)
            if abs(adjusted - weight) > 0.01:
                direction = "+" if adjusted > weight else ""
                entry += f"- {action}: {direction}{adjusted - weight:.2f}<br>"
        
        # Add memory influence
        memories = decision_data.get('active_memories', [])
        if memories:
            entry += "<i>Memory influences:</i><br>"
            for memory in memories:
                entry += f"- {memory}<br>"
        
        # Add final entry to log
        entry += "<hr>"
        self.thought_log_text.append(entry)
        
        # Save to log list
        self.thought_log.append({
            'timestamp': timestamp,
            'decision': decision,
            'data': decision_data
        })
        
        # Scroll to bottom
        self.thought_log_text.verticalScrollBar().setValue(
            self.thought_log_text.verticalScrollBar().maximum()
        )

    def update_memory_list(self, memories):
        """Update the memory influence list"""
        self.memory_list.clear()
        
        if not memories:
            self.memory_list.addItem("No active memories")
            return
        
        for memory in memories:
            item = QtWidgets.QListWidgetItem(memory)
            
            # Style based on content
            if "positive" in memory.lower():
                item.setForeground(QtGui.QColor("darkgreen"))
            elif "negative" in memory.lower():
                item.setForeground(QtGui.QColor("darkred"))
            
            self.memory_list.addItem(item)

    def create_thought_node(self, text):
        node = QtWidgets.QGraphicsRectItem(0, 0, 250, 150)  # Increase node size
        node.setBrush(QtGui.QBrush(QtGui.QColor(240, 248, 255)))

        # Use QTextDocument for better text handling
        text_document = QtGui.QTextDocument()
        text_document.setPlainText(text)
        text_document.setTextWidth(230)  # Set text width to fit within the node

        # Create a QGraphicsTextItem with an empty string
        text_item = QtWidgets.QGraphicsTextItem()
        text_item.setDocument(text_document)
        text_item.setPos(10, 10)

        group = QtWidgets.QGraphicsItemGroup()
        group.addToGroup(node)
        group.addToGroup(text_item)
        return group

    def draw_connection(self, start, end, label):
        line = QtWidgets.QGraphicsLineItem(start[0]+200, start[1]+50, end[0], end[1]+50)
        line.setPen(QtGui.QPen(QtCore.Qt.darkGray, 2, QtCore.Qt.DashLine))
        self.decision_scene.addItem(line)

        arrow = QtWidgets.QGraphicsPolygonItem(
            QtGui.QPolygonF([QtCore.QPointF(0, -5), QtCore.QPointF(10, 0), QtCore.QPointF(0, 5)]))
        arrow.setPos(end[0], end[1]+50)
        arrow.setRotation(180 if start[0] > end[0] else 0)
        self.decision_scene.addItem(arrow)

        label_item = QtWidgets.QGraphicsTextItem(label)
        label_item.setPos((start[0]+end[0])/2, (start[1]+end[1])/2)
        self.decision_scene.addItem(label_item)

    def init_memory_tab(self):
        font = QtGui.QFont()
        font.setPointSize(self.base_font_size)
        # Create a layout for the memory tab
        memory_layout = QtWidgets.QVBoxLayout()

        # Short-term memories section
        memory_layout.addWidget(QtWidgets.QLabel("Short-term Memories:"))
        self.short_term_memory_text = QtWidgets.QTextEdit()
        self.short_term_memory_text.setReadOnly(True)
        self.short_term_memory_text.setAcceptRichText(True)

        # Long-term memories section
        self.long_term_memory_text = QtWidgets.QTextEdit()
        self.long_term_memory_text.setReadOnly(True)
        self.long_term_memory_text.setAcceptRichText(True)

        # Create a QSplitter to add a vertical drag handle between short and long term memories
        splitter = QSplitter(QtCore.Qt.Vertical)
        splitter.addWidget(self.short_term_memory_text)
        splitter.addWidget(self.long_term_memory_text)

        # Set initial sizes for the splitter
        splitter.setSizes([self.height() // 3, self.height() // 2])

        # Add the splitter to the layout
        memory_layout.addWidget(splitter)

        # Set the layout for the memory tab
        self.memory_tab.setLayout(memory_layout)

    def update_memory_tab(self):
        if self.tamagotchi_logic and self.tamagotchi_logic.squid:
            # Get only properly formatted short-term memories
            short_term_memories = [
                mem for mem in self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories()
                if self._is_displayable_memory(mem)
            ]
            
            # Get only properly formatted long-term memories
            long_term_memories = [
                mem for mem in self.tamagotchi_logic.squid.memory_manager.get_all_long_term_memories()
                if self._is_displayable_memory(mem)
            ]

            self.debug_print(f"Retrieved {len(short_term_memories)} short-term and {len(long_term_memories)} long-term displayable memories")

            # Display short-term memories
            self.short_term_memory_text.clear()
            for memory in short_term_memories:
                self.short_term_memory_text.append(self.format_memory_display(memory))

            # Display long-term memories
            self.long_term_memory_text.clear()
            for memory in long_term_memories:
                self.long_term_memory_text.append(self.format_memory_display(memory))

    def _is_displayable_memory(self, memory):
        """Check if a memory should be displayed in the UI"""
        if not isinstance(memory, dict):
            return False
        
        # Skip timestamp-only memories (they have numeric keys)
        if isinstance(memory.get('key'), str) and memory['key'].isdigit():
            return False
            
        # Skip memories that don't have a proper category or value
        if not memory.get('category') or not memory.get('value'):
            return False
            
        # Skip memories where the value is just a timestamp number
        if isinstance(memory.get('value'), (int, float)) and 'timestamp' in str(memory['value']).lower():
            return False
            
        # Must have either formatted_value or a displayable string value
        if 'formatted_value' not in memory and not isinstance(memory.get('value'), str):
            return False
            
        return True

    def format_memory_display(self, memory):
        """Format a memory dictionary for display with colored boxes based on valence"""
        if not self._is_displayable_memory(memory):
            return ""
        
        # Get the display text - prefer formatted_value, fall back to value
        display_text = memory.get('formatted_value', str(memory.get('value', '')))
        
        # Skip if the display text contains just a timestamp
        if 'timestamp' in display_text.lower() and len(display_text.split()) < 3:
            return ""
        
        # Rest of the formatting logic remains the same...
        timestamp = memory.get('timestamp', '')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
            except:
                timestamp = ""
        
        # Determine valence (same logic as MemoryManager.format_memory())
        if memory.get('category') == 'mental_state' and memory.get('key') == 'startled':
            interaction_type = "Negative"
            background_color = "#FFD1DC"  # Pastel red
        elif isinstance(memory.get('raw_value'), dict):
            total_effect = sum(float(val) for val in memory['raw_value'].values() 
                            if isinstance(val, (int, float)))
            if total_effect > 0:
                interaction_type = "Positive"
                background_color = "#D1FFD1"  # Pastel green
            elif total_effect < 0:
                interaction_type = "Negative"
                background_color = "#FFD1DC"  # Pastel red
            else:
                interaction_type = "Neutral"
                background_color = "#FFFACD"  # Pastel yellow
        else:
            interaction_type = "Neutral"
            background_color = "#FFFACD"  # Pastel yellow
        
        # Create HTML formatted memory box
        formatted_memory = f"""
        <div style="
            background-color: {background_color}; 
            padding: 8px; 
            margin: 5px; 
            border-radius: 5px;
            border: 1px solid #ccc;
        ">
            <div style="font-weight: bold; margin-bottom: 5px;">{interaction_type}</div>
            <div>{display_text}</div>
            <div style="font-size: 0.8em; color: #555; margin-top: 5px;">{timestamp}</div>
        </div>
        """
        
        return formatted_memory

    def init_thoughts_tab(self):
        font = QtGui.QFont()
        font.setPointSize(self.base_font_size)
        self.thoughts_text = QtWidgets.QTextEdit()
        self.thoughts_text.setReadOnly(True)
        self.thoughts_tab_layout.addWidget(self.thoughts_text)

    def add_thought(self, thought):
        self.thoughts_text.append(thought)
        self.thoughts_text.verticalScrollBar().setValue(self.thoughts_text.verticalScrollBar().maximum())

    def clear_thoughts(self):
        self.thoughts_text.clear()

    def init_decisions_tab(self):
        font = QtGui.QFont()
        font.setPointSize(self.base_font_size)
        # Add a label for decision history
        decision_history_label = QtWidgets.QLabel("Decision History:")
        self.decisions_tab_layout.addWidget(decision_history_label)

        # Add a text area to display decision history
        self.decision_history_text = QtWidgets.QTextEdit()
        self.decision_history_text.setReadOnly(True)
        self.decisions_tab_layout.addWidget(self.decision_history_text)

        # Add a label for decision inputs
        decision_inputs_label = QtWidgets.QLabel("Decision Inputs:")
        self.decisions_tab_layout.addWidget(decision_inputs_label)

        # Add a text area to display decision inputs
        self.decision_inputs_text = QtWidgets.QTextEdit()
        self.decision_inputs_text.setReadOnly(True)
        self.decisions_tab_layout.addWidget(self.decision_inputs_text)

    def update_decisions_tab(self, decision, decision_inputs):
        # Append the decision to the decision history
        self.decision_history_text.append(f"Decision: {decision}")

        # Display the decision inputs
        self.decision_inputs_text.clear()
        for key, value in decision_inputs.items():
            self.decision_inputs_text.append(f"{key}: {value}")

    def init_associations_tab(self):
        font = QtGui.QFont()
        font.setPointSize(self.base_font_size)
        # Add a checkbox to toggle explanation
        self.show_explanation_checkbox = QtWidgets.QCheckBox("Show Explanation")
        self.show_explanation_checkbox.stateChanged.connect(self.toggle_explanation)
        self.associations_tab_layout.addWidget(self.show_explanation_checkbox)

        # Add explanation text (hidden by default)
        self.explanation_text = QtWidgets.QTextEdit()
        self.explanation_text.setReadOnly(True)
        self.explanation_text.setHidden(True)
        self.explanation_text.setPlainText(
            "This tab shows the learned associations between different neural states of the squid. "
            "These associations are formed through the Hebbian learning process, where 'neurons that fire together, wire together'. "
            "The strength of an association is determined by how often these states occur together or influence each other. "
            "Positive associations mean that as one state increases, the other tends to increase as well. "
            "Negative associations (indicated by 'reduced') mean that as one state increases, the other tends to decrease. "
            "These associations help us understand how the squid's experiences shape its behavior and decision-making processes."
        )
        self.associations_tab_layout.addWidget(self.explanation_text)

        # Add a label for the associations
        label = QtWidgets.QLabel("Learned associations:")
        self.associations_tab_layout.addWidget(label)

        # Add a text area to display associations
        self.associations_text = QtWidgets.QTextEdit()
        self.associations_text.setReadOnly(True)
        self.associations_tab_layout.addWidget(self.associations_text)

        # Add export button
        self.export_associations_button = QtWidgets.QPushButton("Export Associations")
        self.export_associations_button.clicked.connect(self.export_associations)
        self.associations_tab_layout.addWidget(self.export_associations_button, alignment=QtCore.Qt.AlignRight)

    def toggle_explanation(self, state):
        self.explanation_text.setVisible(state == QtCore.Qt.Checked)

    def update_associations(self):
        self.associations_text.clear()
        sorted_weights = sorted(self.brain_widget.weights.items(), key=lambda x: abs(x[1]), reverse=True)
        for pair, weight in sorted_weights[:15]:  # Display only top 15 strongest associations
            summary = self.generate_association_summary(pair[0], pair[1], weight)
            self.associations_text.append(summary + "\n")

    def generate_association_summary(self, neuron1, neuron2, weight):
        strength = "strongly" if abs(weight) > 0.8 else "moderately"
        if weight > 0:
            relation = "associated with"
        else:
            relation = "associated with reduced"

        # Correct grammar for specific neurons
        neuron1_text = self.get_neuron_display_name(neuron1)
        neuron2_text = self.get_neuron_display_name(neuron2)

        summaries = {
            "hunger-satisfaction": f"{neuron1_text} is {strength} associated with satisfaction (probably from eating)",
            "satisfaction-hunger": f"Feeling satisfied is {strength} associated with reduced hunger",
            "cleanliness-anxiety": f"{neuron1_text} is {strength} {relation} anxiety",
            "anxiety-cleanliness": f"Feeling anxious is {strength} associated with reduced cleanliness",
            "curiosity-happiness": f"{neuron1_text} is {strength} associated with happiness",
            "happiness-curiosity": f"Being happy is {strength} associated with increased curiosity",
            "hunger-anxiety": f"{neuron1_text} is {strength} associated with increased anxiety",
            "sleepiness-satisfaction": f"{neuron1_text} is {strength} {relation} satisfaction",
            "happiness-cleanliness": f"Being happy is {strength} associated with cleanliness",
        }

        key = f"{neuron1}-{neuron2}"
        if key in summaries:
            return summaries[key]
        else:
            return f"{neuron1_text} is {strength} {relation} {neuron2_text}"

    def get_neuron_display_name(self, neuron):
        display_names = {
            "cleanliness": "Being clean",
            "sleepiness": "Being sleepy",
            "happiness": "Being happy",
            "hunger": "Being hungry",
            "satisfaction": "Satisfaction",
            "anxiety": "Being anxious",
            "curiosity": "Curiosity",
            "direction": "Direction"
        }
        return display_names.get(neuron, f"{neuron}")

    def init_learning_tab(self):
        learning_layout = QtWidgets.QVBoxLayout()
        
        # 1. Add countdown and interval controls at the TOP with larger fonts
        control_layout = QtWidgets.QHBoxLayout()
        
        # Create and configure font for control elements
        control_font = QtGui.QFont()
        control_font.setPointSize(8)
        
        # Countdown label
        #self.countdown_label = QtWidgets.QLabel("Next Hebbian learning in: -- seconds")
        #self.countdown_label.setFont(control_font)
        #control_layout.addWidget(self.countdown_label)
        
        # Interval control
        control_layout.addStretch()
        
        interval_label = QtWidgets.QLabel("Interval (sec):")
        interval_label.setFont(control_font)
        control_layout.addWidget(interval_label)
        
        self.interval_spinbox = QtWidgets.QSpinBox()
        self.interval_spinbox.setFont(control_font)
        self.interval_spinbox.setRange(5, 300)  # 5 sec to 5 min
        self.interval_spinbox.setValue(int(self.config.hebbian['learning_interval'] / 1000))
        self.interval_spinbox.valueChanged.connect(self.update_learning_interval)
        control_layout.addWidget(self.interval_spinbox)
        
        learning_layout.addLayout(control_layout)
        
        # 2. Add separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        learning_layout.addWidget(separator)

        # 3. Existing weight changes text area (keep original font size)
        self.weight_changes_text = AutoScrollTextEdit()
        self.weight_changes_text.setReadOnly(True)
        self.weight_changes_text.setTextInteractionFlags(
            QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard)
        self.weight_changes_text.setAcceptRichText(True)
        learning_layout.addWidget(self.weight_changes_text)

        # 4. Learning data table (keep original font size)
        self.learning_data_table = AutoScrollTable()
        self.learning_data_table.setColumnCount(5)
        self.learning_data_table.setHorizontalHeaderLabels(
            ["Time", "Neuron 1", "Neuron 2", "Weight Change", "Direction"])
        
        header = self.learning_data_table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.resizeSection(0, 150)  # Timestamp
        header.resizeSection(1, 160)  # Neuron 1
        header.resizeSection(2, 160)  # Neuron 2
        header.resizeSection(3, 200)  # Weight Change
        header.resizeSection(4, 150)  # Direction

        learning_layout.addWidget(self.learning_data_table)

        # 5. Button controls at bottom (keep original font size)
        controls_layout = QtWidgets.QHBoxLayout()
        
        self.export_button = QtWidgets.QPushButton("Export...")
        self.export_button.clicked.connect(self.export_learning_data)
        controls_layout.addWidget(self.export_button)
        
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_learning_data)
        controls_layout.addWidget(self.clear_button)
        
        learning_layout.addLayout(controls_layout)

        # Set the layout to a container widget
        learning_widget = QtWidgets.QWidget()
        learning_widget.setLayout(learning_layout)
        self.learning_tab_layout.addWidget(learning_widget)

    def update_countdown(self):
        # Check if attribute exists (defensive programming)
        if not hasattr(self, 'hebbian_countdown_seconds'):
            self.hebbian_countdown_seconds = 0

        # Show paused message if paused
        if self.is_paused:
            countdown_text = "Next Hebbian learning in: [ SIMULATION IS PAUSED ]"
        else:
            # Calculate time until next learning cycle
            if hasattr(self, 'last_hebbian_time'):
                time_remaining = max(0, (self.last_hebbian_time + (self.config.hebbian['learning_interval'] / 1000)) - time.time())
                self.hebbian_countdown_seconds = int(time_remaining)
                
            # Update countdown display with larger font
            if self.hebbian_countdown_seconds > 0:
                countdown_text = f"Next Hebbian learning in: {self.hebbian_countdown_seconds} seconds"
            else:
                countdown_text = "Next Hebbian learning in: -- seconds"

        # Apply consistent styling
        self.countdown_label.setText(countdown_text)

        # Set a larger font for the countdown label
        font = QFont()
        font.setPointSize(8)  # Set the desired font size
        self.countdown_label.setFont(font)

        # Check if reached zero this tick
        if not self.is_paused and self.hebbian_countdown_seconds == 0:
            if hasattr(self, 'on_hebbian_countdown_finished'):
                self.on_hebbian_countdown_finished()
            else:
                print("Warning: Countdown finished but no handler!")

        # Force UI update if needed
        if self.countdown_label.isVisible():
            self.countdown_label.repaint()

    def clear_learning_data(self):
        self.weight_changes_text.clear()
        self.learning_data_table.setRowCount(0)
        self.learning_data = []
        print("Learning data cleared.")

    def update_learning_interval(self, seconds):
        """Update the learning interval when spinbox value changes"""
        # Convert seconds to milliseconds (QTimer uses ms)
        interval_ms = seconds * 1000
        
        # Update config
        if hasattr(self.config, 'hebbian'):
            self.config.hebbian['learning_interval'] = interval_ms
        else:
            self.config.hebbian = {'learning_interval': interval_ms}
        
        # Restart timer with new interval
        if hasattr(self, 'hebbian_timer'):
            self.hebbian_timer.setInterval(interval_ms)
            self.last_hebbian_time = time.time()  # Reset countdown
        
        if self.debug_mode:
            print(f"Learning interval updated to {seconds} seconds ({interval_ms} ms)")

    def perform_hebbian_learning(self):
        if self.is_paused:
            return
        self.last_hebbian_time = time.time()
        if self.is_paused or not hasattr(self, 'brain_widget') or not self.tamagotchi_logic or not self.tamagotchi_logic.squid:
            return

        # Get the current state of all neurons
        current_state = self.brain_widget.state

        # Determine which neurons are significantly active (excluding specified neurons)
        excluded_neurons = ['is_sick', 'is_eating', 'pursuing_food', 'direction']
        active_neurons = []
        for neuron, value in current_state.items():
            if neuron in excluded_neurons:
                continue
            if isinstance(value, (int, float)) and value > 50:
                active_neurons.append(neuron)
            elif isinstance(value, bool) and value:
                active_neurons.append(neuron)
            elif isinstance(value, str):
                # For string values (like 'direction'), we consider them active
                # But we're excluding 'direction' via excluded_neurons
                active_neurons.append(neuron)

        # Include decoration effects in learning
        decoration_memories = self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories('decorations')

        if isinstance(decoration_memories, dict):
            for decoration, effects in decoration_memories.items():
                for stat, boost in effects.items():
                    if stat in excluded_neurons:
                        continue
                    if isinstance(boost, (int, float)) and boost > 0:
                        if stat not in active_neurons:
                            active_neurons.append(stat)
        elif isinstance(decoration_memories, list):
            for memory in decoration_memories:
                for stat, boost in memory.get('effects', {}).items():
                    if stat in excluded_neurons:
                        continue
                    if isinstance(boost, (int, float)) and boost > 0:
                        if stat not in active_neurons:
                            active_neurons.append(stat)

        # If less than two neurons are active, no learning occurs
        if len(active_neurons) < 2:
            return

        # Perform learning for a random subset of active neuron pairs
        sample_size = min(5, len(active_neurons) * (len(active_neurons) - 1) // 2)
        sampled_pairs = random.sample([(i, j) for i in range(len(active_neurons)) for j in range(i+1, len(active_neurons))], sample_size)

        for i, j in sampled_pairs:
            neuron1 = active_neurons[i]
            neuron2 = active_neurons[j]
            value1 = self.get_neuron_value(current_state.get(neuron1, 50))  # Default to 50 if not in current_state
            value2 = self.get_neuron_value(current_state.get(neuron2, 50))
            self.update_connection(neuron1, neuron2, value1, value2)

        # Update the brain visualization
        self.brain_widget.update()

    def deduce_weight_change_reason(self, pair, value1, value2, prev_weight, new_weight, weight_change):
        neuron1, neuron2 = pair
        threshold_high = 70
        threshold_low = 30

        reasons = []

        # Analyze neuron activity levels
        if value1 > threshold_high and value2 > threshold_high:
            reasons.append(f"Both {neuron1.upper()} and {neuron2.upper()} were highly active")
        elif value1 < threshold_low and value2 < threshold_low:
            reasons.append(f"Both {neuron1.upper()} and {neuron2.upper()} had low activity")
        elif value1 > threshold_high:
            reasons.append(f"{neuron1.upper()} was highly active")
        elif value2 > threshold_high:
            reasons.append(f"{neuron2.upper()} was highly active")

        # Analyze weight change
        if abs(weight_change) > 0.1:
            if weight_change > 0:
                reasons.append("Strong positive reinforcement")
            else:
                reasons.append("Strong negative reinforcement")
        elif abs(weight_change) > 0.01:
            if weight_change > 0:
                reasons.append("Moderate positive reinforcement")
            else:
                reasons.append("Moderate negative reinforcement")
        else:
            reasons.append("Weak reinforcement")

        # Analyze the relationship between neurons
        if "hunger" in pair and "satisfaction" in pair:
            reasons.append("Potential hunger-satisfaction relationship")
        elif "cleanliness" in pair and "happiness" in pair:
            reasons.append("Potential cleanliness-happiness relationship")

        # Analyze the current weight
        if abs(new_weight) > 0.8:
            reasons.append("Strong connection formed")
        elif abs(new_weight) < 0.2:
            reasons.append("Weak connection")

        # Analyze learning progress
        if abs(prev_weight) < 0.1 and abs(new_weight) > 0.1:
            reasons.append("New significant connection emerging")
        elif abs(prev_weight) > 0.8 and abs(new_weight) < 0.8:
            reasons.append("Previously strong connection weakening")

        # Combine reasons
        if len(reasons) > 1:
            return " | ".join(reasons)
        elif len(reasons) == 1:
            return reasons[0]
        else:
            return "Complex interaction with no clear single reason"

    def update_connection(self, neuron1, neuron2, value1, value2):
        pair = (neuron1, neuron2)
        reverse_pair = (neuron2, neuron1)

        # Check if the pair or its reverse exists in weights, if not, initialize it
        if pair not in self.brain_widget.weights and reverse_pair not in self.brain_widget.weights:
            self.brain_widget.weights[pair] = 0.0  # Initialize with a neutral weight
            print(f"\033[36m** Hebbian: Initialized new weight for pair: {(neuron1, neuron2)}\033[0m")

        # Use the correct pair order
        use_pair = pair if pair in self.brain_widget.weights else reverse_pair

        prev_weight = self.brain_widget.weights[use_pair]

        # Hebbian learning rule: neurons that fire together, wire together
        weight_change = 0.01 * (value1 / 100) * (value2 / 100)  # Normalize values to 0-1 range
        new_weight = min(max(prev_weight + weight_change, -1), 1)  # Ensure weight stays in [-1, 1] range

        # Update the weight
        self.brain_widget.weights[use_pair] = new_weight

        # Determine if weight increased or decreased
        if weight_change > 0:
            change_direction = "Increased"
            color = QtGui.QColor("black")
        elif weight_change < 0:
            change_direction = "Decreased"
            color = QtGui.QColor("black")
        else:
            change_direction = "No change"
            color = QtGui.QColor("black")

        # Check if enough time has passed since the last update
        current_time = time.time()
        if current_time - self.last_update_time >= self.update_threshold:
            self.update_associations()
            self.last_update_time = current_time

        # Display the weight change
        timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
        self.weight_changes_text.append(f"{timestamp} - Weight changed between {neuron1.upper()} and {neuron2.upper()}")
        self.weight_changes_text.append(f"Previous value: {prev_weight:.4f}")
        self.weight_changes_text.append(f"New value: {new_weight:.4f}")

        # Set text color for the change line
        cursor = self.weight_changes_text.textCursor()
        format = QtGui.QTextCharFormat()
        format.setForeground(color)
        cursor.insertText(f"Change: {change_direction} by {abs(weight_change):.4f}\n", format)

        # Deduce and add the reason for weight change
        reason = self.deduce_weight_change_reason(use_pair, value1, value2, prev_weight, new_weight, weight_change)
        self.weight_changes_text.append(f"Reason: {reason}\n")

        # Update learning data
        self.learning_data.append((timestamp, neuron1, neuron2, weight_change, change_direction))
        self.update_learning_data_table()
        # Update associations after each connection update
        self.update_associations()

        # Update log window if open
        if self.log_window and self.log_window.isVisible():
            self.log_window.update_log(self.weight_changes_text.toPlainText())

    def get_neuron_value(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, bool):
            return 100.0 if value else 0.0
        elif isinstance(value, str):
            # For string values (like 'direction'), return a default value
            return 75.0
        else:
            return 0.0

    def update_learning_data_table(self):
        self.learning_data_table.setRowCount(len(self.learning_data))
        for row, data in enumerate(self.learning_data):
            for col, value in enumerate(data):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col == 3:  # Weight change column
                    item.setData(QtCore.Qt.DisplayRole, f"{value:.4f}")
                if col == 4:  # Direction column
                    if value == "increase ⬆️":
                        item.setForeground(QtGui.QColor("green"))
                    elif value == "⬇️ decrease":
                        item.setForeground(QtGui.QColor("red"))
                self.learning_data_table.setItem(row, col, item)
        self.learning_data_table.scrollToBottom()

    def export_learning_data(self):
        # Save the weight changes text to a file
        with open("learningdata_reasons.txt", 'w') as file:
            file.write(self.weight_changes_text.toPlainText())

        # Save the learning data table to a CSV file
        with open("learningdata_weights.csv", 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Neuron 1", "Neuron 2", "Weight Change", "Direction"])
            for row in range(self.learning_data_table.rowCount()):
                row_data = []
                for col in range(self.learning_data_table.columnCount()):
                    item = self.learning_data_table.item(row, col)
                    row_data.append(item.text() if item else "")
                writer.writerow(row_data)

        QtWidgets.QMessageBox.information(self, "Export Successful", "Learning data exported to 'weight_changes.txt' and 'learning_data.csv'")

    def export_learning_tab_contents(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Learning Tab Contents", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w') as file:
                file.write("Learning Data Table:\n")
                for row in range(self.learning_data_table.rowCount()):
                    row_data = []
                    for col in range(self.learning_data_table.columnCount()):
                        item = self.learning_data_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    file.write("\t".join(row_data) + "\n")

                file.write("\nWeight Changes Text:\n")
                file.write(self.weight_changes_text.toPlainText())

            QtWidgets.QMessageBox.information(self, "Export Successful", f"Learning tab contents exported to {file_name}")

    def export_associations(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Associations", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w') as file:
                file.write(self.associations_text.toPlainText())
            QtWidgets.QMessageBox.information(self, "Export Successful", f"Associations exported to {file_name}")

    def update_personality_effects(self, personality, weights, adjusted_weights):
        """Update the personality modifier display in the thinking tab"""
        # Convert enum to string if needed
        personality_str = getattr(personality, 'value', str(personality))
        
        self.personality_label.setText(f"Personality: {personality_str.capitalize()}")
        
        # Generate effect text based on weight differences
        effects_text = []
        for action, weight in weights.items():
            adjusted = adjusted_weights.get(action, weight)
            if abs(adjusted - weight) > 0.01:  # If there's a significant difference
                direction = "increases" if adjusted > weight else "decreases"
                effect = f"{action}: {direction} by {abs(adjusted - weight):.2f}"
                effects_text.append(effect)
        
        if effects_text:
            self.personality_effects.setPlainText("\n".join(effects_text))
        else:
            self.personality_effects.setPlainText("No significant personality effects")

    def update_personality_display(self, personality):
        # Convert enum to string if needed
        personality_str = getattr(personality, 'value', str(personality))
        
        # Set personality type label
        self.personality_type_label.setText(f"Squid Personality: {personality_str.capitalize()}")
        
        # Set personality modifier label
        self.personality_modifier_label.setText(f"Personality Modifier: {self.get_personality_modifier(personality)}")
        
        # Set description text
        self.personality_description.setPlainText(self.get_personality_description(personality))
        
        # Set modifiers text
        self.modifiers_text.setPlainText(self.get_personality_modifiers(personality))
        
        # Set care tips text
        self.care_tips.setPlainText(self.get_care_tips(personality))

    def get_personality_description(self, personality):
        descriptions = {
            Personality.TIMID: "Your squid is Timid. It tends to be more easily startled and anxious, especially in new situations. It may prefer quiet, calm environments and might be less likely to explore on its own. However, it can form strong bonds when it feels safe and secure.",
            Personality.ADVENTUROUS: "Your squid is Adventurous. It loves to explore and try new things. It's often the first to investigate new objects or areas in its environment. This squid thrives on novelty and might get bored more easily in unchanging surroundings.",
            Personality.LAZY: "Your squid is Lazy. It prefers a relaxed lifestyle and may be less active than other squids. It might need extra encouragement to engage in activities but can be quite content just lounging around. This squid is great at conserving energy!",
            Personality.ENERGETIC: "Your squid is Energetic. It's always on the move, full of life and vigor. This squid needs plenty of stimulation and activities to keep it happy. It might get restless if not given enough opportunity to burn off its excess energy.",
            Personality.INTROVERT: "Your squid is an Introvert. It enjoys solitude and might prefer quieter, less crowded spaces. While it can interact with others, it may need time alone to 'recharge'. This squid might be more observant and thoughtful in its actions.",
            Personality.GREEDY: "Your squid is Greedy. It has a strong focus on food and resources. This squid might be more motivated by treats and rewards than others. While it can be more demanding, it also tends to be resourceful and good at finding hidden treats!",
            Personality.STUBBORN: "Your squid is Stubborn. It has a strong will and definite preferences. This squid might be more resistant to change and could take longer to adapt to new routines. However, its determination can also make it persistent in solving problems."
        }
        return descriptions.get(personality, "Unknown personality type")

    def get_personality_modifier(self, personality):
        modifiers = {
            Personality.TIMID: "Higher chance of becoming anxious",
            Personality.ADVENTUROUS: "Increased curiosity and exploration",
            Personality.LAZY: "Slower movement and energy consumption",
            Personality.ENERGETIC: "Faster movement and higher activity levels",
            Personality.INTROVERT: "Prefers solitude and quiet environments",
            Personality.GREEDY: "More focused on food and resources",
            Personality.STUBBORN: "Only eats favorite food (sushi), may refuse to sleep"
        }
        return modifiers.get(personality, "No specific modifier")

    def get_care_tips(self, personality):
        tips = {
            Personality.TIMID: "- Place plants in the environment to reduce anxiety\n- Keep the environment clean and calm\n- Approach slowly and avoid sudden movements",
            Personality.ADVENTUROUS: "- Regularly introduce new objects or decorations\n- Provide diverse food options\n- Encourage exploration with strategic food placement",
            Personality.LAZY: "- Place food closer to the squid's resting spots\n- Clean the environment more frequently\n- Use enticing food to encourage movement",
            Personality.ENERGETIC: "- Provide a large, open space for movement\n- Offer frequent feeding opportunities\n- Introduce interactive elements or games",
            Personality.INTROVERT: "- Create quiet, secluded areas with decorations\n- Avoid overcrowding the environment\n- Respect the squid's need for alone time",
            Personality.GREEDY: "- Offer a variety of food types, including sushi\n- Use food as a reward for desired behaviors\n- Be cautious not to overfeed",
            Personality.STUBBORN: "- Always have sushi available as it's their favorite food\n- Be patient when introducing changes\n- Use positive reinforcement for desired behaviors"
        }
        return tips.get(personality, "No specific care tips available for this personality.")

    def get_personality_modifiers(self, personality):
        modifiers = {
            Personality.TIMID: "- Anxiety increases 50% faster\n- Curiosity increases 50% slower\n- Anxiety decreases by 50% when near plants",
            Personality.ADVENTUROUS: "- Curiosity increases 50% faster",
            Personality.LAZY: "- Moves slower\n- Energy consumption is lower",
            Personality.ENERGETIC: "- Moves faster\n- Energy consumption is higher",
            Personality.INTROVERT: "- Prefers quieter, less crowded spaces\n- May need more time alone to 'recharge'",
            Personality.GREEDY: "- Gets 50% more anxious when hungry\n- Satisfaction increases more when eating",
            Personality.STUBBORN: "- Only eats favorite food (sushi)\n- May refuse to sleep even when tired"
        }
        return modifiers.get(personality, "No specific modifiers available for this personality.")

    def init_personality_tab(self):
        # Common style for all text elements
        base_font_size = 18
        text_style = f"font-size: {base_font_size}px;"
        header_style = f"font-size: {base_font_size + 4}px; font-weight: bold;"

        # Personality type display
        self.personality_tab_layout.addWidget(QtWidgets.QFrame(frameShape=QtWidgets.QFrame.HLine))
        self.personality_type_label = QtWidgets.QLabel("Squid Personality: ")
        self.personality_type_label.setStyleSheet(header_style)
        self.personality_tab_layout.addWidget(self.personality_type_label)

        # Personality modifier display
        self.personality_modifier_label = QtWidgets.QLabel("Personality Modifier: ")
        self.personality_modifier_label.setStyleSheet(text_style)
        self.personality_tab_layout.addWidget(self.personality_modifier_label)

        # Separator
        self.personality_tab_layout.addWidget(QtWidgets.QFrame(frameShape=QtWidgets.QFrame.HLine))

        # Personality description
        description_label = QtWidgets.QLabel("Description:")
        description_label.setStyleSheet(header_style)
        self.personality_tab_layout.addWidget(description_label)

        self.personality_description = QtWidgets.QTextEdit()
        self.personality_description.setReadOnly(True)
        self.personality_description.setStyleSheet(text_style)
        self.personality_tab_layout.addWidget(self.personality_description)

        # Personality modifiers
        self.modifiers_label = QtWidgets.QLabel("Personality Modifiers:")
        self.modifiers_label.setStyleSheet(header_style)
        self.personality_tab_layout.addWidget(self.modifiers_label)

        self.modifiers_text = QtWidgets.QTextEdit()
        self.modifiers_text.setReadOnly(True)
        self.modifiers_text.setStyleSheet(text_style)
        self.personality_tab_layout.addWidget(self.modifiers_text)

        # Care tips
        self.care_tips_label = QtWidgets.QLabel("Care Tips:")
        self.care_tips_label.setStyleSheet(header_style)
        self.personality_tab_layout.addWidget(self.care_tips_label)

        self.care_tips = QtWidgets.QTextEdit()
        self.care_tips.setReadOnly(True)
        self.care_tips.setStyleSheet(text_style)
        self.personality_tab_layout.addWidget(self.care_tips)

        # Note about personality generation
        note_label = QtWidgets.QLabel("Note: Personality is randomly generated at the start of a new game")
        note_label.setStyleSheet(text_style + "font-style: italic;")
        self.personality_tab_layout.addWidget(note_label)

    def update_brain(self, state):
        if not self.initialized:
            self.initialized = True
            return  # Skip first update
        # Ensure all required state values are present
        full_state = {
            # Core state values
            "hunger": state.get("hunger", self.brain_widget.state.get("hunger", 50)),
            "happiness": state.get("happiness", self.brain_widget.state.get("happiness", 50)),
            "cleanliness": state.get("cleanliness", self.brain_widget.state.get("cleanliness", 50)),
            "sleepiness": state.get("sleepiness", self.brain_widget.state.get("sleepiness", 50)),
            "satisfaction": state.get("satisfaction", self.brain_widget.state.get("satisfaction", 50)),
            "anxiety": state.get("anxiety", self.brain_widget.state.get("anxiety", 50)),
            "curiosity": state.get("curiosity", self.brain_widget.state.get("curiosity", 50)),
            
            # Status flags
            "is_sick": state.get("is_sick", False),
            "is_eating": state.get("is_eating", False),
            "is_sleeping": state.get("is_sleeping", False),
            "pursuing_food": state.get("pursuing_food", False),
            
            # Movement/position
            "direction": state.get("direction", "up"),
            "position": state.get("position", (0, 0)),
            
            # Neurogenesis triggers
            "novelty_exposure": state.get("novelty_exposure", 0),
            "sustained_stress": state.get("sustained_stress", 0),
            "recent_rewards": state.get("recent_rewards", 0),
            
            # Debug flag
            "_debug_forced_neurogenesis": state.get("_debug_forced_neurogenesis", False),
            
            # Personality
            "personality": state.get("personality", self.brain_widget.state.get("personality", None))
        }

        # Update the brain widget with complete state
        self.brain_widget.update_state(full_state)
        
        # Force immediate visualization update
        self.brain_widget.update()
        
        # Update memory tab with properly filtered memories
        if hasattr(self.tamagotchi_logic, 'squid') and hasattr(self.tamagotchi_logic.squid, 'memory_manager'):
            # Run periodic memory management
            self.tamagotchi_logic.squid.memory_manager.periodic_memory_management()
            
            # Get only properly formatted short-term memories
            short_term_memories = [
                mem for mem in self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories()
                if self._is_displayable_memory(mem)
            ]
            
            # Get only properly formatted long-term memories
            long_term_memories = [
                mem for mem in self.tamagotchi_logic.squid.memory_manager.get_all_long_term_memories()
                if self._is_displayable_memory(mem)
            ]

            # Update short-term memory display
            self.short_term_memory_text.clear()
            for memory in short_term_memories:
                self.short_term_memory_text.append(self.format_memory_display(memory))

            # Update long-term memory display
            self.long_term_memory_text.clear()
            for memory in long_term_memories:
                self.long_term_memory_text.append(self.format_memory_display(memory))

        # Update personality display if available - only update the personality tab
        if 'personality' in full_state and full_state['personality']:
            self.update_personality_display(full_state['personality'])
        else:
            print("Warning: Personality not found in brain state")

        # Update thought process visualization
        if hasattr(self.tamagotchi_logic, 'get_decision_data'):
            decision_data = self.tamagotchi_logic.get_decision_data()
            self.update_thought_process(decision_data)

        # Debug output for neurogenesis
        #if self.debug_mode:
        #    print("\nCurrent Brain State:")
        #    print(f"Neurons: {list(self.brain_widget.neuron_positions.keys())}")
        #    print(f"New neurons: {self.brain_widget.neurogenesis_data.get('new_neurons', [])}")
        #    print(f"Novelty: {full_state['novelty_exposure']}")
        #    print(f"Stress: {full_state['sustained_stress']}")
        #    print(f"Rewards: {full_state['recent_rewards']}\n")

    def init_about_tab(self):
        about_text = QtWidgets.QTextEdit()
        about_text.setReadOnly(True)
        about_text.setHtml("""
        <h1>Dosidicus electronicae</h1>
        <p>github.com/ViciousSquid/Dosidicus</p>
        <p>A Tamagotchi-style digital pet with a simple neural network</p>
        <ul>
            <li>by Rufus Pearce</li><br><br>
        <br>
        <b>Dosidicus version 1.0.400.5</b> (milestone 4)<br>
        Brain Tool version 1.0.6.5<br>
        Decision engine version 1.0<br>

        <p>This is a research project. Please suggest features.</p>
        </ul>
        """)
        self.about_tab_layout.addWidget(about_text)

    def train_hebbian(self):
        self.brain_widget.train_hebbian()
        #self.update_data_table(self.brain_widget.state)
        self.update_training_data_table()

        # Switch to the Console tab
        self.tabs.setCurrentWidget(self.console_tab)

        # Print training results to the console
        print("Hebbian training completed.")
        print("Updated association strengths:")
        for i, neuron1 in enumerate(self.brain_widget.neuron_positions.keys()):
            for j, neuron2 in enumerate(self.brain_widget.neuron_positions.keys()):
                if i < j:
                    strength = self.brain_widget.get_association_strength(neuron1, neuron2)
                    print(f"{neuron1} - {neuron2}: {strength:.2f}")

    def init_training_data_tab(self):
        self.show_overview_checkbox = QtWidgets.QCheckBox("Show Training Process Overview")
        self.show_overview_checkbox.stateChanged.connect(self.toggle_overview)
        self.training_data_tab_layout.addWidget(self.show_overview_checkbox)

        self.overview_label = QtWidgets.QLabel(
            "Training Process Overview:\n\n"
            "1. Data Capture: When 'Capture training data' is checked, the current state of all neurons is recorded each time the brain is stimulated.\n\n"
            "2. Hebbian Learning: The 'Train Hebbian' button applies the Hebbian learning rule to the captured data.\n\n"
            "3. Association Strength: The learning process strengthens connections between neurons that are frequently active together.\n\n"
            "4. Weight Updates: After training, the weights between neurons are updated based on their co-activation patterns.\n\n"
            "5. Adaptive Behavior: Over time, this process allows the brain to adapt its behavior based on input patterns."
        )
        self.overview_label.setWordWrap(True)
        self.overview_label.hide()  # Hide by default
        self.training_data_tab_layout.addWidget(self.overview_label)

        self.training_data_table = QtWidgets.QTableWidget()
        self.training_data_tab_layout.addWidget(self.training_data_table)

        self.training_data_table.setColumnCount(len(self.brain_widget.neuron_positions))
        self.training_data_table.setHorizontalHeaderLabels(list(self.brain_widget.neuron_positions.keys()))

        self.training_data_timer = QtCore.QTimer()
        self.training_data_timer.timeout.connect(self.update_training_data_table)
        self.training_data_timer.start(1000)  # Update every second

        self.checkbox_capture_training_data = QtWidgets.QCheckBox("Capture training data")
        self.checkbox_capture_training_data.stateChanged.connect(self.toggle_capture_training_data)
        self.training_data_tab_layout.addWidget(self.checkbox_capture_training_data)

        self.train_button = self.create_button("Train Hebbian", self.train_hebbian, "#ADD8E6")
        self.train_button.setEnabled(False)  # Initially grey out the train button
        self.training_data_tab_layout.addWidget(self.train_button)

    def toggle_overview(self, state):
        if state == QtCore.Qt.Checked:
            self.overview_label.show()
        else:
            self.overview_label.hide()

    def toggle_capture_training_data(self, state):
        self.brain_widget.toggle_capture_training_data(state)
        if state == QtCore.Qt.Checked:
            os.makedirs('training_data', exist_ok=True)

    def update_training_data_table(self):
        self.training_data_table.setRowCount(len(self.brain_widget.training_data))
        for row, sample in enumerate(self.brain_widget.training_data):
            for col, value in enumerate(sample):
                self.training_data_table.setItem(row, col, QtWidgets.QTableWidgetItem(str(value)))

        if len(self.brain_widget.training_data) > 0:
            self.train_button.setEnabled(True)

        # Save raw data to file
        if self.checkbox_capture_training_data.isChecked():
            with open(os.path.join('training_data', 'raw_data.json'), 'w') as f:
                json.dump(self.brain_widget.training_data, f)

    def save_brain_state(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Brain State", "", "JSON Files (*.json)")
        if file_name:
            with open(file_name, 'w') as f:
                json.dump(self.brain_widget.state, f)

    def load_brain_state(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Brain State", "", "JSON Files (*.json)")
        if file_name:
            with open(file_name, 'r') as f:
                state = json.load(f)
            self.brain_widget.update_state(state)

    def init_console(self):
        self.console_output = QtWidgets.QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_tab_layout.addWidget(self.console_output)
        self.console = ConsoleOutput(self.console_output)

    def create_button(self, text, callback, color):
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        button.setStyleSheet(f"background-color: {color}; border: 1px solid black; padding: 5px;")
        button.setFixedSize(200, 50)
        return button

    def stimulate_brain(self):
        dialog = StimulateDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            stimulation_values = dialog.get_stimulation_values()
            if stimulation_values is not None:
                self.brain_widget.update_state(stimulation_values)
                if self.tamagotchi_logic:
                    self.tamagotchi_logic.update_from_brain(stimulation_values)
                else:
                    print("Warning: tamagotchi_logic is not set. Brain stimulation will not affect the squid.")


    def update_neural_visualization(self, inputs):
        """Update the neural network visualization with current input values"""
        if not hasattr(self, 'neuron_items') or not self.neuron_items:
            self.setup_neural_visualization()
            return
        
        # Update neuron colors based on activation values
        for neuron, value in inputs.items():
            if neuron in self.neuron_items:
                # Only update numerical values
                if isinstance(value, (int, float)):
                    # Update stored value
                    self.neuron_items[neuron]["value"] = value
                    
                    # Calculate color based on value (0-100)
                    intensity = int(value * 2.55)  # Scale 0-100 to 0-255
                    
                    if neuron in ["hunger", "sleepiness", "anxiety"]:
                        # Red-based for "negative" neurons (more red = higher activation)
                        color = QtGui.QColor(255, 255 - intensity, 255 - intensity)
                    else:
                        # Blue/green-based for "positive" neurons (more color = higher activation)
                        color = QtGui.QColor(100, intensity, 255)
                    
                    # Update neuron ellipse color
                    self.neuron_items[neuron]["shape"].setBrush(QtGui.QBrush(color))
                    
                    # Make neurons pulse slightly based on value
                    scale = 1.0 + (value / 200)  # 1.0 to 1.5
                    rect = self.neuron_items[neuron]["shape"].rect()
                    center_x = rect.x() + rect.width()/2
                    center_y = rect.y() + rect.height()/2
                    new_width = 40 * scale
                    new_height = 40 * scale
                    self.neuron_items[neuron]["shape"].setRect(
                        center_x - new_width/2,
                        center_y - new_height/2,
                        new_width,
                        new_height
                    )
        
        # Update connection line widths and colors based on neuron activations
        for connection, items in self.connection_items.items():
            source, target = connection
            source_value = self.neuron_items.get(source, {}).get("value", 50)
            target_value = self.neuron_items.get(target, {}).get("value", 50)
            
            # Calculate connection strength based on both neuron activations
            # Higher when both neurons are highly activated
            connection_strength = (source_value * target_value) / 10000  # Scale to 0-1
            
            # Update line width and color
            pen_width = 1 + 3 * connection_strength
            
            # Get current brain connection weight if available
            weight = items.get("weight", 0)
            
            # Color based on weight (green for positive, red for negative)
            if weight > 0:
                pen_color = QtGui.QColor(0, 150, 0, 50 + int(200 * connection_strength))
            else:
                pen_color = QtGui.QColor(150, 0, 0, 50 + int(200 * connection_strength))
            
            items["line"].setPen(QtGui.QPen(pen_color, pen_width))
            
            # Update the weight display
            items["text"].setPlainText(f"{weight:.1f}")


    def update_brain_weights(self, weights_data):
        """Update the brain connection weights based on current neural network weights"""
        if not hasattr(self, 'connection_items'):
            return
            
        # Update connection weights
        for (src, dst), weight in weights_data.items():
            # Look for the connection in either direction
            connection = (src, dst)
            if connection in self.connection_items:
                self.connection_items[connection]["weight"] = weight
            else:
                # Try the reverse connection
                connection = (dst, src)
                if connection in self.connection_items:
                    self.connection_items[connection]["weight"] = weight
                    

    def animate_decision_process(self, decision_data):
        """Animate the decision-making process with visual effects"""
        if not hasattr(self, 'processing_animation'):
            return
            
        # Get the decision information
        decision = decision_data.get('final_decision', 'unknown')
        processing_time = decision_data.get('processing_time', 1000)
        
        # Display processing text
        self.processing_text.setText(f"Processing decision ({processing_time}ms)...")
        
        # Start the animation with a brief delay to show processing
        QtCore.QTimer.singleShot(300, lambda: self.highlight_decision_in_ui(decision))


    def highlight_decision_in_ui(self, decision):
        """Highlight the chosen decision in the UI"""
        # Update decision output with animation effect
        self.decision_output.setText(decision.capitalize())
        
        # Flash the decision with a highlight animation
        original_style = self.decision_output.styleSheet()
        self.decision_output.setStyleSheet("font-size: 18px; font-weight: bold; color: white; background-color: green; padding: 5px; border-radius: 5px;")
        
        # Reset after brief highlight
        QtCore.QTimer.singleShot(500, lambda: self.decision_output.setStyleSheet(original_style))
        
        # Update processing text
        self.processing_text.setText(f"Decision made: {decision.capitalize()}")



class RecentThoughtsDialog(QtWidgets.QDialog):
    def __init__(self, thought_log, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recent Decisions")
        self.thought_log = thought_log

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # List widget to display recent thoughts
        self.thought_list = QtWidgets.QListWidget()
        self.thought_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        layout.addWidget(self.thought_list)

        # Populate the list with summarized thought logs
        for log in self.thought_log:
            summary = f"Time: {log.get('timestamp', 'Unknown')} - Decision: {log.get('decision', 'Unknown')}"
            self.thought_list.addItem(summary)

        # Button layout
        button_layout = QtWidgets.QHBoxLayout()

        # Save button
        self.save_button = QtWidgets.QPushButton("Save Selected")
        self.save_button.clicked.connect(self.save_selected_thoughts)
        button_layout.addWidget(self.save_button)

        # Clear button
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_all_logs)
        button_layout.addWidget(self.clear_button)

        layout.addLayout(button_layout)

    def save_selected_thoughts(self):
        selected_items = self.thought_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(self, "No Selection", "No decisions selected to save.")
            return

        # Get the file name to save the selected thoughts
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Selected decisions", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w') as file:
                for item in selected_items:
                    file.write(item.text() + "\n")
            QtWidgets.QMessageBox.information(self, "Save Successful", f"Selected decisions saved to {file_name}")

    def clear_all_logs(self):
        # Confirm before clearing
        reply = QtWidgets.QMessageBox.question(
            self, 'Clear Logs', 
            "Are you sure you want to clear all decision logs?", 
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )

        if reply == QtWidgets.QMessageBox.Yes:
            # Clear the logs in the parent window
            if hasattr(self.parent(), 'thought_log'):
                self.parent().thought_log.clear()
                self.thought_list.clear()
                QtWidgets.QMessageBox.information(self, "Logs Cleared", "All decision logs have been cleared.")

class LogWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Learning Log")
        self.resize(640, 480)

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.log_text = QtWidgets.QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self.export_button = QtWidgets.QPushButton("Export Log")
        self.export_button.clicked.connect(self.export_log)
        layout.addWidget(self.export_button)

    def update_log(self, text):
        self.log_text.append(text)

    def export_log(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Log", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w') as f:
                f.write(self.log_text.toPlainText())
            QtWidgets.QMessageBox.information(self, "Export Successful", f"Log exported to {file_name}")

class AutoScrollTextEdit(QtWidgets.QTextEdit):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.textChanged.connect(self.scroll_to_bottom)

    def scroll_to_bottom(self):
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

class AutoScrollTable(QtWidgets.QTableWidget):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.verticalScrollBar().rangeChanged.connect(self.scroll_to_bottom)

    def scroll_to_bottom(self):
        scrollbar = self.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())



class ConsoleOutput:
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def write(self, text):
        cursor = self.text_edit.textCursor()
        format = QtGui.QTextCharFormat()

        if text.startswith("Previous value:"):
            format.setForeground(QtGui.QColor("red"))
        elif text.startswith("New value:"):
            format.setForeground(QtGui.QColor("green"))
        else:
            format.setForeground(QtGui.QColor("black"))

        cursor.insertText(text, format)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def flush(self):
        pass

class DiagnosticReportDialog(QtWidgets.QDialog):
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Network Health Diagnosis")
        self.setMinimumSize(640, 800)
        
        self.brain_widget = brain_widget
        self.history_data = parent.tamagotchi_logic.get_health_history() if hasattr(parent, 'tamagotchi_logic') else []
        
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)
        
        # Create tab widget
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)
        
        # Create report tabs
        self.create_connections_tab()
        self.create_neurons_tab()
        self.create_balance_tab()
        
        # Add history graph section
        self.create_history_section()
        
        # Add close button
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        self.layout.addWidget(self.close_button)
    
    def create_connections_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        label = QtWidgets.QLabel("<h3>Weak Connections Report</h3>")
        layout.addWidget(label)
        
        weakest = self.brain_widget.get_weakest_connections(5)
        report_text = "TOP WEAK CONNECTIONS:\n\n"
        for (a, b), weight in weakest:
            report_text += f"{a} ↔ {b}: {weight:.2f}\n"
        
        text_edit = QtWidgets.QTextEdit()
        text_edit.setPlainText(report_text)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Connections")
    
    def create_neurons_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        label = QtWidgets.QLabel("<h3>Neuron Activity Report</h3>")
        layout.addWidget(label)
        
        extremes = self.brain_widget.get_extreme_neurons(3)
        report_text = "OVERACTIVE NEURONS:\n"
        for name, val in extremes['overactive']:
            report_text += f"{name}: {val:.0f}%\n"
        
        report_text += "\nUNDERACTIVE NEURONS:\n"
        for name, val in extremes['underactive']:
            report_text += f"{name}: {val:.0f}%\n"
        
        text_edit = QtWidgets.QTextEdit()
        text_edit.setPlainText(report_text)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Neurons")
    
    def create_balance_tab(self):
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        
        label = QtWidgets.QLabel("<h3>Connection Balance Report</h3>")
        layout.addWidget(label)
        
        unbalanced = self.brain_widget.get_unbalanced_connections(5)
        report_text = "UNBALANCED CONNECTIONS:\n\n"
        for (a, b), (w1, w2), diff in unbalanced:
            report_text += f"{a}→{b}: {w1:.2f}\n"
            report_text += f"{b}→{a}: {w2:.2f} (Δ{diff:.2f})\n\n"
        
        text_edit = QtWidgets.QTextEdit()
        text_edit.setPlainText(report_text)
        text_edit.setReadOnly(True)
        layout.addWidget(text_edit)
        
        tab.setLayout(layout)
        self.tabs.addTab(tab, "Balance")
    
    def create_history_section(self):
        group = QtWidgets.QGroupBox("Health History")
        layout = QtWidgets.QVBoxLayout()
        
        # Add toggle checkbox
        #self.show_history_check = QtWidgets.QCheckBox("Show historical trends")
        #self.show_history_check.toggled.connect(self.toggle_history_graph)
        #layout.addWidget(self.show_history_check)
        
        # Placeholder for graph
        #self.history_graph = QtWidgets.QLabel("Graph will appear here when enabled")
        #self.history_graph.setAlignment(QtCore.Qt.AlignCenter)
        #self.history_graph.setMinimumHeight(200)
        #layout.addWidget(self.history_graph)
        
        #group.setLayout(layout)
        self.layout.addWidget(group)
    
    def toggle_history_graph(self, checked):
        if checked and self.history_data:
            # In a real implementation, you'd generate an actual graph here
            timestamps = [x[0] for x in self.history_data]
            values = [x[1] for x in self.history_data]
            
            # This is placeholder - you'd use matplotlib or similar in practice
            graph_text = "HEALTH TREND:\n\n"
            for t, v in zip(timestamps[-10:], values[-10:]):
                graph_text += f"{t}: {'='*int(v/10)}{v:.0f}%\n"
            
            self.history_graph.setText(graph_text)
        else:
            self.history_graph.setText("Graph will appear here when enabled")

class RecentThoughtsDialog(QtWidgets.QDialog):
    """Dialog for displaying and analyzing recent thought logs"""
    def __init__(self, thought_log, parent=None):
        super().__init__(parent)
        self.thought_log = thought_log
        self.setWindowTitle("Recent Decisions")
        self.setMinimumSize(640, 480)
        
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # Create tabs for different views
        self.tab_widget = QtWidgets.QTabWidget()
        layout.addWidget(self.tab_widget)
        
        # Tab 1: List of decisions
        self.list_tab = QtWidgets.QWidget()
        list_layout = QtWidgets.QVBoxLayout(self.list_tab)
        
        # Create list widget
        self.thought_list = QtWidgets.QListWidget()
        self.thought_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.thought_list.currentRowChanged.connect(self.display_selected_thought)
        list_layout.addWidget(self.thought_list)
        
        # Detailed view of selected thought
        self.thought_detail = QtWidgets.QTextEdit()
        self.thought_detail.setReadOnly(True)
        list_layout.addWidget(self.thought_detail)
        
        self.tab_widget.addTab(self.list_tab, "Decision List")
        
        # Tab 2: Statistics
        self.stats_tab = QtWidgets.QWidget()
        stats_layout = QtWidgets.QVBoxLayout(self.stats_tab)
        
        # Decision stats
        decision_stats_group = QtWidgets.QGroupBox("Decision Statistics")
        decision_stats_layout = QtWidgets.QVBoxLayout(decision_stats_group)
        
        self.stats_text = QtWidgets.QTextEdit()
        self.stats_text.setReadOnly(True)
        decision_stats_layout.addWidget(self.stats_text)
        
        stats_layout.addWidget(decision_stats_group)
        
        # Decision distribution
        self.decision_chart = QtWidgets.QGraphicsView()
        self.decision_scene = QtWidgets.QGraphicsScene()
        self.decision_chart.setScene(self.decision_scene)
        self.decision_chart.setMinimumHeight(200)
        stats_layout.addWidget(self.decision_chart)
        
        self.tab_widget.addTab(self.stats_tab, "Statistics")
        
        # Tab 3: Timeline
        self.timeline_tab = QtWidgets.QWidget()
        timeline_layout = QtWidgets.QVBoxLayout(self.timeline_tab)
        
        self.timeline_view = QtWidgets.QGraphicsView()
        self.timeline_scene = QtWidgets.QGraphicsScene()
        self.timeline_view.setScene(self.timeline_scene)
        timeline_layout.addWidget(self.timeline_view)
        
        self.tab_widget.addTab(self.timeline_tab, "Timeline")
        
        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        
        self.export_button = QtWidgets.QPushButton("Export Selected")
        self.export_button.clicked.connect(self.export_selected)
        button_layout.addWidget(self.export_button)
        
        self.export_all_button = QtWidgets.QPushButton("Export All")
        self.export_all_button.clicked.connect(self.export_all)
        button_layout.addWidget(self.export_all_button)
        
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        button_layout.addWidget(self.close_button)
        
        layout.addLayout(button_layout)
        
        # Populate the dialog
        self.populate_thought_list()
        self.calculate_statistics()
        self.draw_timeline()
    
    def populate_thought_list(self):
        """Populate the thought list with entries from the log"""
        self.thought_list.clear()
        
        for i, entry in enumerate(self.thought_log):
            timestamp = entry.get('timestamp', '')
            decision = entry.get('decision', 'unknown')
            list_item = QtWidgets.QListWidgetItem(f"{timestamp} - {decision.capitalize()}")
            
            # Color code different decisions
            if decision in ["exploring", "eating", "approaching_rock", "throwing_rock", 
                          "avoiding_threat", "organizing"]:
                colors = {
                    "exploring": QtGui.QColor(100, 180, 255),      # Blue
                    "eating": QtGui.QColor(100, 255, 100),         # Green
                    "approaching_rock": QtGui.QColor(200, 150, 100), # Brown
                    "throwing_rock": QtGui.QColor(200, 100, 100),  # Red
                    "avoiding_threat": QtGui.QColor(255, 100, 100), # Brighter red
                    "organizing": QtGui.QColor(180, 180, 100)      # Yellow/brown
                }
                list_item.setForeground(colors.get(decision, QtGui.QColor(0, 0, 0)))
            
            self.thought_list.addItem(list_item)
        
        # Select first item if available
        if self.thought_list.count() > 0:
            self.thought_list.setCurrentRow(0)
    
    def display_selected_thought(self, row):
        """Display detailed information about the selected thought"""
        if row < 0 or row >= len(self.thought_log):
            self.thought_detail.clear()
            return
        
        entry = self.thought_log[row]
        decision = entry.get('decision', 'unknown')
        data = entry.get('data', {})
        
        # Format the detail text with HTML for better presentation
        html = f"""
        <h2>Decision: {decision.capitalize()}</h2>
        <p><b>Time:</b> {entry.get('timestamp', 'unknown')}</p>
        <p><b>Confidence:</b> {data.get('confidence', 0.0):.2f}</p>
        <p><b>Processing Time:</b> {data.get('processing_time', 0)} ms</p>
        
        <h3>Input Factors</h3>
        <table border="1" cellspacing="0" cellpadding="3">
            <tr>
                <th>Factor</th>
                <th>Value</th>
            </tr>
        """
        
        # Add inputs
        inputs = data.get('inputs', {})
        for factor, value in sorted(inputs.items(), key=lambda x: x[1], reverse=True):
            if isinstance(value, (int, float)):
                color = ""
                if value > 70:
                    color = ' style="color: darkred;"'
                elif value < 30:
                    color = ' style="color: blue;"'
                html += f"<tr><td>{factor}</td><td{color}>{int(value)}</td></tr>"
        
        html += """
        </table>
        
        <h3>Decision Weights</h3>
        <table border="1" cellspacing="0" cellpadding="3">
            <tr>
                <th>Action</th>
                <th>Base Weight</th>
                <th>Adjusted Weight</th>
                <th>Random Factor</th>
                <th>Final Weight</th>
            </tr>
        """
        
        # Add decision weights
        weights = data.get('weights', {})
        adjusted_weights = data.get('adjusted_weights', {})
        randomness = data.get('randomness', {})
        
        for action, weight in sorted(adjusted_weights.items(), key=lambda x: x[1], reverse=True):
            base = weights.get(action, 0)
            adjusted = adjusted_weights.get(action, 0)
            random_factor = randomness.get(action, 1.0)
            final = adjusted * random_factor
            
            # Highlight the selected decision
            row_style = ' style="background-color: #FFFFCC;"' if action == decision else ''
            
            html += f"""
            <tr{row_style}>
                <td>{action}</td>
                <td>{base:.2f}</td>
                <td>{adjusted:.2f}</td>
                <td>{random_factor:.2f}</td>
                <td><b>{final:.2f}</b></td>
            </tr>
            """
        
        html += """
        </table>
        
        <h3>Active Memories</h3>
        <ul>
        """
        
        # Add memories
        memories = data.get('active_memories', [])
        if memories:
            for memory in memories:
                html += f"<li>{memory}</li>"
        else:
            html += "<li><i>No active memories</i></li>"
        
        html += "</ul>"
        
        self.thought_detail.setHtml(html)
    
    def calculate_statistics(self):
        """Calculate and display statistics about the thought log"""
        if not self.thought_log:
            self.stats_text.setText("No thought data available")
            return
        
        # Count decision frequencies
        decision_counts = {}
        for entry in self.thought_log:
            decision = entry.get('decision', 'unknown')
            decision_counts[decision] = decision_counts.get(decision, 0) + 1
        
        # Calculate average confidence per decision type
        confidence_by_decision = {}
        for entry in self.thought_log:
            decision = entry.get('decision', 'unknown')
            confidence = entry.get('data', {}).get('confidence', 0)
            
            if decision not in confidence_by_decision:
                confidence_by_decision[decision] = []
            
            confidence_by_decision[decision].append(confidence)
        
        avg_confidence = {d: sum(c)/len(c) for d, c in confidence_by_decision.items()}
        
        # Format statistics text
        stats_html = """
        <h3>Decision Distribution</h3>
        <table border="1" cellspacing="0" cellpadding="3">
            <tr>
                <th>Decision</th>
                <th>Count</th>
                <th>Percentage</th>
                <th>Avg. Confidence</th>
            </tr>
        """
        
        total_decisions = len(self.thought_log)
        
        for decision, count in sorted(decision_counts.items(), key=lambda x: x[1], reverse=True):
            percentage = (count / total_decisions) * 100
            confidence = avg_confidence.get(decision, 0) * 100
            
            stats_html += f"""
            <tr>
                <td>{decision.capitalize()}</td>
                <td>{count}</td>
                <td>{percentage:.1f}%</td>
                <td>{confidence:.1f}%</td>
            </tr>
            """
        
        stats_html += """
        </table>
        
        <h3>Summary</h3>
        """
        
        stats_html += f"<p>Total decisions analyzed: {total_decisions}</p>"
        most_common = max(decision_counts.items(), key=lambda x: x[1])[0] if decision_counts else "none"
        stats_html += f"<p>Most common decision: {most_common.capitalize()}</p>"
        avg_overall_confidence = sum(c for cs in confidence_by_decision.values() for c in cs) / total_decisions if total_decisions > 0 else 0
        stats_html += f"<p>Average decision confidence: {avg_overall_confidence*100:.1f}%</p>"
        
        self.stats_text.setHtml(stats_html)
        
        # Draw the bar chart
        self.draw_decision_chart(decision_counts)
    
    def draw_decision_chart(self, decision_counts):
        """Draw a bar chart of decision distribution"""
        self.decision_scene.clear()
        
        if not decision_counts:
            return
        
        # Setup
        chart_width = 580
        chart_height = 180
        bar_width = min(60, chart_width / (len(decision_counts) * 1.5))
        max_count = max(decision_counts.values())
        
        # Add background and border
        self.decision_scene.addRect(0, 0, chart_width, chart_height, 
                                   QtGui.QPen(QtCore.Qt.black),
                                   QtGui.QBrush(QtGui.QColor(250, 250, 250)))
        
        # Colors for different decisions
        colors = {
            "exploring": QtGui.QColor(100, 180, 255),      # Blue
            "eating": QtGui.QColor(100, 255, 100),         # Green
            "approaching_rock": QtGui.QColor(200, 150, 100), # Brown
            "throwing_rock": QtGui.QColor(200, 100, 100),  # Red
            "avoiding_threat": QtGui.QColor(255, 100, 100), # Brighter red
            "organizing": QtGui.QColor(180, 180, 100)      # Yellow/brown
        }
        
        # Draw bars
        x_position = 20
        for decision, count in sorted(decision_counts.items(), key=lambda x: x[1], reverse=True):
            # Calculate bar height proportional to count
            bar_height = (count / max_count) * (chart_height - 40)
            
            # Draw the bar
            color = colors.get(decision, QtGui.QColor(150, 150, 150))
            self.decision_scene.addRect(
                x_position, chart_height - 20 - bar_height, 
                bar_width, bar_height,
                QtGui.QPen(QtCore.Qt.black),
                QtGui.QBrush(color)
            )
            
            # Add label
            label = self.decision_scene.addText(decision[:8])
            label.setPos(x_position, chart_height - 15)
            
            # Add count
            count_text = self.decision_scene.addText(str(count))
            count_text.setPos(x_position + (bar_width/2) - 5, chart_height - 40 - bar_height)
            
            x_position += bar_width * 1.5
    
    def draw_timeline(self):
        """Draw a timeline visualization of decisions over time"""
        self.timeline_scene.clear()
        
        if not self.thought_log:
            return
        
        # Setup
        timeline_width = 600
        timeline_height = 200
        
        # Add background and border
        self.timeline_scene.addRect(0, 0, timeline_width, timeline_height, 
                                    QtGui.QPen(QtCore.Qt.black),
                                    QtGui.QBrush(QtGui.QColor(250, 250, 250)))
        
        # Draw timeline axis
        self.timeline_scene.addLine(
            50, timeline_height - 50, 
            timeline_width - 50, timeline_height - 50,
            QtGui.QPen(QtCore.Qt.black, 2)
        )
        
        # Calculate position scale
        time_span = len(self.thought_log)
        x_scale = (timeline_width - 100) / time_span if time_span > 0 else 1
        
        # Draw data points
        for i, entry in enumerate(self.thought_log):
            decision = entry.get('decision', 'unknown')
            confidence = entry.get('data', {}).get('confidence', 0.5)
            
            # X position based on index
            x_pos = 50 + (i * x_scale)
            
            # Y position based on decision (each gets its own level)
            decision_types = ["exploring", "eating", "approaching_rock", 
                             "throwing_rock", "avoiding_threat", "organizing"]
            try:
                y_level = decision_types.index(decision)
            except ValueError:
                y_level = len(decision_types)  # For unknown decisions
                
            y_spacing = 20
            y_pos = timeline_height - 70 - (y_level * y_spacing)
            
            # Draw dot with confidence-based size
            dot_size = 4 + (confidence * 10)
            
            # Colors for different decisions
            colors = {
                "exploring": QtGui.QColor(100, 180, 255),      # Blue
                "eating": QtGui.QColor(100, 255, 100),         # Green
                "approaching_rock": QtGui.QColor(200, 150, 100), # Brown
                "throwing_rock": QtGui.QColor(200, 100, 100),  # Red
                "avoiding_threat": QtGui.QColor(255, 100, 100), # Brighter red
                "organizing": QtGui.QColor(180, 180, 100)      # Yellow/brown
            }
            
            color = colors.get(decision, QtGui.QColor(150, 150, 150))
            
            self.timeline_scene.addEllipse(
                x_pos - dot_size/2, y_pos - dot_size/2, 
                dot_size, dot_size,
                QtGui.QPen(QtCore.Qt.black),
                QtGui.QBrush(color)
            )
            
            # Add connecting lines if more than one data point
            if i > 0:
                prev_decision = self.thought_log[i-1].get('decision', 'unknown')
                try:
                    prev_y_level = decision_types.index(prev_decision)
                except ValueError:
                    prev_y_level = len(decision_types)
                    
                prev_y_pos = timeline_height - 70 - (prev_y_level * y_spacing)
                prev_x_pos = 50 + ((i-1) * x_scale)
                
                self.timeline_scene.addLine(
                    prev_x_pos, prev_y_pos,
                    x_pos, y_pos,
                    QtGui.QPen(QtGui.QColor(200, 200, 200))
                )
        
        # Add legend
        legend_y = 30
        for i, decision in enumerate(["exploring", "eating", "approaching_rock", 
                                    "throwing_rock", "avoiding_threat", "organizing"]):
            legend_x = 50 + (i * 90)
            
            # Color box
            color = colors.get(decision, QtGui.QColor(150, 150, 150))
            self.timeline_scene.addRect(
                legend_x, legend_y, 
                15, 15,
                QtGui.QPen(QtCore.Qt.black),
                QtGui.QBrush(color)
            )
            
            # Label
            label = self.timeline_scene.addText(decision)
            label.setPos(legend_x + 20, legend_y - 2)
    
    def export_selected(self):
        """Export the selected thought entry"""
        selected_row = self.thought_list.currentRow()
        if selected_row < 0 or selected_row >= len(self.thought_log):
            QtWidgets.QMessageBox.warning(self, "No Selection", "Please select a thought to export.")
            return
        
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Selected Thought", "", "HTML Files (*.html);;Text Files (*.txt)")
        
        if not file_name:
            return
        
        try:
            if file_name.endswith('.html'):
                with open(file_name, 'w') as f:
                    f.write("<html><body>\n")
                    f.write(self.thought_detail.toHtml())
                    f.write("</body></html>")
            else:
                with open(file_name, 'w') as f:
                    f.write(self.thought_detail.toPlainText())
            
            QtWidgets.QMessageBox.information(self, "Export Complete", 
                                            f"Thought data exported to {file_name}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", 
                                         f"Failed to export data: {str(e)}")
    
    def export_all(self):
        """Export all thought entries"""
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export All Thoughts", "", "HTML Files (*.html);;Text Files (*.txt)")
        
        if not file_name:
            return
        
        try:
            if file_name.endswith('.html'):
                with open(file_name, 'w') as f:
                    f.write("<html><body>\n")
                    f.write("<h1>Squid Decision Log</h1>\n")
                    
                    for i, entry in enumerate(self.thought_log):
                        f.write(f"<h2>Decision {i+1}: {entry.get('decision', 'unknown').capitalize()}</h2>\n")
                        f.write(f"<p><b>Time:</b> {entry.get('timestamp', 'unknown')}</p>\n")
                        
                        # Save detailed entry
                        self.thought_list.setCurrentRow(i)
                        f.write(self.thought_detail.toHtml())
                        f.write("<hr>\n")
                    
                    f.write("</body></html>")
            else:
                with open(file_name, 'w') as f:
                    f.write("SQUID DECISION LOG\n\n")
                    
                    for i, entry in enumerate(self.thought_log):
                        f.write(f"=== Decision {i+1}: {entry.get('decision', 'unknown').capitalize()} ===\n")
                        f.write(f"Time: {entry.get('timestamp', 'unknown')}\n\n")
                        
                        # Save detailed entry
                        self.thought_list.setCurrentRow(i)
                        f.write(self.thought_detail.toPlainText())
                        f.write("\n" + "-" * 80 + "\n\n")
            
            QtWidgets.QMessageBox.information(self, "Export Complete", 
                                            f"All thought data exported to {file_name}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Export Error", 
                                         f"Failed to export data: {str(e)}")

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = SquidBrainWindow()
    window.show()
    sys.exit(app.exec_())