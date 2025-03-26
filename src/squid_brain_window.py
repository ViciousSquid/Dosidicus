# A window into the mind of a digital pet

import sys
import csv
import os
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtWidgets import QSplitter
import random
import numpy as np
import json
from .personality import Personality

class BrainWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
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

        # Define pastel colors for each state
        self.state_colors = {
            'is_sick': (255, 204, 204),  # Pastel red
            'is_eating': (204, 255, 204),  # Pastel green
            'is_sleeping': (204, 229, 255),  # Pastel blue
            'pursuing_food': (255, 229, 204),  # Pastel orange
            'direction': (229, 204, 255)  # Pastel purple
        }

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

    def update_state(self, new_state):
        # Update only the keys that exist in self.state and are allowed to be modified
        for key in self.state.keys():
            if key in new_state and key not in ['satisfaction', 'anxiety', 'curiosity']:
                self.state[key] = new_state[key]
        self.update_weights()
        self.update()
        if self.capture_training_data_enabled:
            self.capture_training_data(new_state)
            # Neurogenesis check (add at end)
        current_time = time.time()
        if current_time - self.neurogenesis_data['last_neuron_time'] > self.neurogenesis_config['cooldown']:
            self.check_neurogenesis(new_state)
        
        self.update()
  
    def check_neurogenesis(self, state):
        """Force neuron creation when debug flag is set, regardless of cooldown"""
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
        
        # Original checks (only used in normal operation)
        if current_time - self.neurogenesis_data['last_neuron_time'] > self.neurogenesis_config['cooldown']:
            created = False
            if state.get('novelty_exposure', 0) > self.neurogenesis_config['novelty_threshold']:
                self._create_neuron_internal('novelty', state)
                created = True
            if state.get('sustained_stress', 0) > self.neurogenesis_config['stress_threshold']:
                self._create_neuron_internal('stress', state)
                created = True
            if state.get('recent_rewards', 0) > self.neurogenesis_config['reward_threshold']:
                self._create_neuron_internal('reward', state)
                created = True
            return created
        return False
    
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

    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        scale_x = self.width() / 1200
        scale_y = self.height() / 600
        scale = min(scale_x, scale_y)
        painter.scale(scale, scale)

        painter.fillRect(QtCore.QRectF(0, 0, 1024, 768), QtGui.QColor(240, 240, 240))

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

        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(QtCore.QRectF(0, 20, 1200, 30), QtCore.Qt.AlignCenter, "Neurons")

        if self.show_links:
            self.draw_connections(painter, scale)

        # Draw neuron highlights
        if 'highlighted_neuron' in self.neurogenesis_data:
            hl = self.neurogenesis_data['highlighted_neuron']
            if time.time() - hl['start_time'] < self.neurogenesis_config['visual']['highlight_duration']:
                self.draw_neuron_highlight(painter, hl['position'][0], hl['position'][1])
            else:
                del self.neurogenesis_data['highlighted_neuron']

    def draw_neuron_highlight(self, painter, x, y):
        painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), 3))
        painter.setBrush(QtCore.Qt.NoBrush)
        painter.drawEllipse(x - 35, y - 35, 70, 70)

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
        if event.button() == QtCore.Qt.LeftButton:
            for name, pos in self.neuron_positions.items():
                if self._is_click_on_neuron(event.pos(), pos):
                    self.dragging = True
                    self.dragged_neuron = name
                    self.drag_start_pos = event.pos()
                    self.update()
                    break

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

    def _is_click_on_neuron(self, point, neuron_pos):
        """Check if click is within neuron bounds"""
        neuron_x, neuron_y = neuron_pos
        return (abs(neuron_x - point.x()) <= 25 and 
                abs(neuron_y - point.y()) <= 25)

    def is_point_inside_neuron(self, point, neuron_pos):
        neuron_x, neuron_y = neuron_pos
        return (neuron_x - 25 <= point.x() <= neuron_x + 25) and (neuron_y - 25 <= point.y() <= neuron_y + 25)

    def reset_positions(self):
        self.neuron_positions = self.original_neuron_positions.copy()
        self.update()

class StimulateDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stimulate Brain")
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        self.form_layout = QtWidgets.QFormLayout()
        self.layout.addLayout(self.form_layout)

        self.neuron_inputs = {}
        neurons = ["hunger", "happiness", "cleanliness", "sleepiness", "is_sick", "is_eating", "is_sleeping", "pursuing_food", "direction"]
        for neuron in neurons:
            if neuron.startswith("is_"):
                input_widget = QtWidgets.QComboBox()
                input_widget.addItems(["False", "True"])
            elif neuron == "direction":
                input_widget = QtWidgets.QComboBox()
                input_widget.addItems(["up", "down", "left", "right"])
            else:
                input_widget = QtWidgets.QSpinBox()
                input_widget.setRange(0, 100)
            self.form_layout.addRow(neuron, input_widget)
            self.neuron_inputs[neuron] = input_widget

        self.buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        self.layout.addWidget(self.buttons)

    def get_stimulation_values(self):
        stimulation_values = {}
        for neuron, input_widget in self.neuron_inputs.items():
            if isinstance(input_widget, QtWidgets.QSpinBox):
                stimulation_values[neuron] = input_widget.value()
            elif isinstance(input_widget, QtWidgets.QComboBox):
                stimulation_values[neuron] = input_widget.currentText()
        return stimulation_values

class SquidBrainWindow(QtWidgets.QMainWindow):
    def __init__(self, tamagotchi_logic, debug_mode=False):
        super().__init__()
        self.tamagotchi_logic = tamagotchi_logic
        self.debug_mode = debug_mode
        self.setWindowTitle("Brain Tool")
        self.resize(1024, 768)

        # Initialize logging variables
        self.is_logging = False
        self.thought_log = []

        screen = QtWidgets.QDesktopWidget().screenNumber(QtWidgets.QDesktopWidget().cursor().pos())
        screen_geometry = QtWidgets.QDesktopWidget().screenGeometry(screen)
        self.move(screen_geometry.right() - 1024, screen_geometry.top())

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QtWidgets.QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.init_tabs()

        self.hebbian_timer = QtCore.QTimer()
        self.hebbian_timer.timeout.connect(self.perform_hebbian_learning)
        self.hebbian_timer.start(2000)  # Update every 2 seconds

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
        self.stimulate_button = self.create_button("Stimulate Brain", self.stimulate_brain, "#D8BFD8")
        self.save_button = self.create_button("Save Brain State", self.save_brain_state, "#90EE90")
        self.load_button = self.create_button("Load Brain State", self.load_brain_state, "#ADD8E6")
        # self.reset_button = self.create_button("Reset Positions", self.brain_widget.reset_positions, "#FFD700")

        button_layout.addWidget(self.stimulate_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)
        # button_layout.addWidget(self.reset_button)

        main_content_layout.addLayout(button_layout)

        # Add the main content widget to the main tab layout
        self.main_tab_layout.addWidget(main_content_widget)

        # Thoughts tab
        self.thoughts_tab = QtWidgets.QWidget()
        self.thoughts_tab_layout = QtWidgets.QVBoxLayout()
        self.thoughts_tab.setLayout(self.thoughts_tab_layout)
        self.tabs.addTab(self.thoughts_tab, "Thoughts")
        self.init_thoughts_tab()

        # Personality tab
        self.personality_tab = QtWidgets.QWidget()
        self.personality_tab_layout = QtWidgets.QVBoxLayout()
        self.personality_tab.setLayout(self.personality_tab_layout)
        self.tabs.addTab(self.personality_tab, "Personality")
        self.init_personality_tab()

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

        # Add a new decisions tab
        self.decisions_tab = QtWidgets.QWidget()
        self.decisions_tab_layout = QtWidgets.QVBoxLayout()
        self.decisions_tab.setLayout(self.decisions_tab_layout)
        self.tabs.addTab(self.decisions_tab, "Decisions")
        self.init_decisions_tab()

        # About tab
        self.about_tab = QtWidgets.QWidget()
        self.about_tab_layout = QtWidgets.QVBoxLayout()
        self.about_tab.setLayout(self.about_tab_layout)
        self.tabs.addTab(self.about_tab, "About")
        self.init_about_tab()

    def init_thought_process_tab(self):
        self.thought_process_tab = QtWidgets.QWidget()
        self.thought_process_layout = QtWidgets.QVBoxLayout()
        self.thought_process_tab.setLayout(self.thought_process_layout)

        # Decision flowchart
        self.decision_canvas = QtWidgets.QGraphicsView()
        self.decision_scene = QtWidgets.QGraphicsScene()
        self.decision_canvas.setScene(self.decision_scene)
        self.thought_process_layout.addWidget(self.decision_canvas)

        # Real-time thought display
        self.thought_process_text = QtWidgets.QTextEdit()
        self.thought_process_text.setReadOnly(True)
        self.thought_process_layout.addWidget(self.thought_process_text)

        # Key metrics
        self.metrics_widget = QtWidgets.QWidget()
        metrics_layout = QtWidgets.QHBoxLayout()
        self.confidence_meter = QtWidgets.QProgressBar()
        self.decision_time_label = QtWidgets.QLabel("Processing: 0ms")
        metrics_layout.addWidget(QtWidgets.QLabel("Confidence:"))
        metrics_layout.addWidget(self.confidence_meter)
        metrics_layout.addWidget(self.decision_time_label)
        self.metrics_widget.setLayout(metrics_layout)
        self.thought_process_layout.addWidget(self.metrics_widget)

        # Logging button
        self.logging_button = QtWidgets.QPushButton("Start Logging")
        self.logging_button.clicked.connect(self.toggle_logging)
        self.thought_process_layout.addWidget(self.logging_button)

        # Button to display recent thoughts
        self.view_thoughts_button = QtWidgets.QPushButton("View Recent Thoughts")
        self.view_thoughts_button.clicked.connect(self.show_recent_thoughts)
        self.thought_process_layout.addWidget(self.view_thoughts_button)

        self.tabs.addTab(self.thought_process_tab, "Thinking")

    def toggle_logging(self):
        self.is_logging = not self.is_logging
        if self.is_logging:
            self.logging_button.setText("Stop Logging")
        else:
            self.logging_button.setText("Start Logging")

    def show_recent_thoughts(self):
        dialog = RecentThoughtsDialog(self.thought_log, self)
        dialog.exec_()

    def update_thought_process(self, decision_data):
        self.decision_scene.clear()

        # Format the inputs to show only rounded numbers
        formatted_inputs = "\n".join(f"{k}: {int(v)}" for k, v in decision_data['inputs'].items())

        nodes = {
            'input': f"Senses:\n{formatted_inputs}",
            'memories': "Memories:\n" + '\n'.join(decision_data['active_memories'][:3]),
            'options': "Possible Actions:\n" + '\n'.join(decision_data['possible_actions']),
            'decision': f"Chosen Action:\n{decision_data['final_decision']}"
        }

        positions = {
            'input': (0, 0),
            'memories': (0, 200),  # Adjust position for better spacing
            'options': (350, 100),  # Center options node
            'decision': (700, 0)    # Move decision node to the right
        }

        for name, text in nodes.items():
            node = self.create_thought_node(text)
            node.setPos(*positions[name])
            self.decision_scene.addItem(node)

        self.draw_connection(positions['input'], positions['options'], "Considers")
        self.draw_connection(positions['memories'], positions['options'], "Recalls")
        self.draw_connection(positions['options'], positions['decision'], "Selects")

        # Log the thought process if logging is enabled
        if self.is_logging:
            log_entry = {
                'timestamp': decision_data['timestamp'],
                'inputs': decision_data['inputs'],
                'active_memories': decision_data['active_memories'],
                'possible_actions': decision_data['possible_actions'],
                'final_decision': decision_data['final_decision'],
                'confidence': decision_data['confidence'],
                'processing_time': decision_data['processing_time']
            }
            self.thought_log.append(log_entry)

        self.thought_process_text.setText(
            f"Decision Process:\n"
            f"Time: {decision_data['timestamp']}\n"
            f"Personality Factors: {decision_data['personality_influence']}\n"
            f"Emotional State: {decision_data['emotions']}\n"
            f"Learning History: {decision_data['learning_history']}"
        )
        self.confidence_meter.setValue(int(decision_data['confidence'] * 100))
        self.decision_time_label.setText(f"Processing: {decision_data['processing_time']}ms")

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
        splitter.setSizes([self.height() // 2, self.height() // 2])

        # Add the splitter to the layout
        memory_layout.addWidget(splitter)

        # Set the layout for the memory tab
        self.memory_tab.setLayout(memory_layout)

    def update_memory_tab(self):
        if self.tamagotchi_logic and self.tamagotchi_logic.squid:
            short_term_memories = self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories()
            long_term_memories = self.tamagotchi_logic.squid.memory_manager.get_all_long_term_memories()

            self.debug_print(f"Retrieved {len(short_term_memories)} short-term memories and {len(long_term_memories)} long-term memories")

            # Display short-term memories
            self.short_term_memory_text.clear()
            for memory in short_term_memories:
                if isinstance(memory, dict):
                    # Use the formatted value directly
                    self.short_term_memory_text.append(memory['value'])
                else:
                    self.short_term_memory_text.append(str(memory))

            # Display long-term memories
            self.long_term_memory_text.clear()
            for memory in long_term_memories:
                if isinstance(memory, dict):
                    # Use the formatted value directly
                    self.long_term_memory_text.append(memory['value'])
                else:
                    self.long_term_memory_text.append(str(memory))

            # Force update of the QTextEdit widgets
            self.short_term_memory_text.repaint()
            self.long_term_memory_text.repaint()

    def init_thoughts_tab(self):
        self.thoughts_text = QtWidgets.QTextEdit()
        self.thoughts_text.setReadOnly(True)
        self.thoughts_tab_layout.addWidget(self.thoughts_text)

    def add_thought(self, thought):
        self.thoughts_text.append(thought)
        self.thoughts_text.verticalScrollBar().setValue(self.thoughts_text.verticalScrollBar().maximum())

    def clear_thoughts(self):
        self.thoughts_text.clear()

    def init_decisions_tab(self):
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

        # Weight changes text area
        self.weight_changes_text = AutoScrollTextEdit()
        self.weight_changes_text.setReadOnly(True)
        self.weight_changes_text.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.TextSelectableByKeyboard)
        self.weight_changes_text.setAcceptRichText(True)  # Enable rich text interpretation
        learning_layout.addWidget(self.weight_changes_text)

        # Learning data table
        self.learning_data_table = AutoScrollTable()
        self.learning_data_table.setColumnCount(5)
        self.learning_data_table.setHorizontalHeaderLabels(["Time", "Neuron 1", "Neuron 2", "Weight Change", "Direction"])
        # Set column widths
        header = self.learning_data_table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.Interactive)
        header.resizeSection(0, 150)  # Timestamp
        header.resizeSection(1, 160)  # Neuron 1
        header.resizeSection(2, 160)  # Neuron 2
        header.resizeSection(3, 200)  # Weight Change
        header.resizeSection(4, 150)  # Direction

        learning_layout.addWidget(self.learning_data_table)

        # Controls
        controls_layout = QtWidgets.QHBoxLayout()

        self.export_button = QtWidgets.QPushButton("Export...")
        self.export_button.clicked.connect(self.export_learning_data)
        controls_layout.addWidget(self.export_button)

        # Add Clear button
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_learning_data)
        controls_layout.addWidget(self.clear_button)

        learning_layout.addLayout(controls_layout)

        learning_widget = QtWidgets.QWidget()
        learning_widget.setLayout(learning_layout)
        self.learning_tab_layout.addWidget(learning_widget)

    def clear_learning_data(self):
        self.weight_changes_text.clear()
        self.learning_data_table.setRowCount(0)
        self.learning_data = []
        print("Learning data cleared.")

    def perform_hebbian_learning(self):
        if self.is_paused or not hasattr(self, 'brain_widget') or not self.tamagotchi_logic or not self.tamagotchi_logic.squid:
            return

        # Get the current state of all neurons
        current_state = self.brain_widget.state

        # Determine which neurons are significantly active
        active_neurons = []
        for neuron, value in current_state.items():
            if neuron == 'position':
                # Skip the position tuple
                continue
            if isinstance(value, (int, float)) and value > 50:
                active_neurons.append(neuron)
            elif isinstance(value, bool) and value:
                active_neurons.append(neuron)
            elif isinstance(value, str):
                # For string values (like 'direction'), we consider them active
                active_neurons.append(neuron)

        # Include decoration effects in learning
        decoration_memories = self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories('decorations')

        if isinstance(decoration_memories, dict):
            for decoration, effects in decoration_memories.items():
                for stat, boost in effects.items():
                    if isinstance(boost, (int, float)) and boost > 0:
                        if stat not in active_neurons:
                            active_neurons.append(stat)
        elif isinstance(decoration_memories, list):
            for memory in decoration_memories:
                for stat, boost in memory.get('effects', {}).items():
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
            color = QtGui.QColor("green")
        elif weight_change < 0:
            change_direction = "Decreased"
            color = QtGui.QColor("red")
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
                    if value == "INCREASED":
                        item.setForeground(QtGui.QColor("green"))
                    elif value == "DECREASED":
                        item.setForeground(QtGui.QColor("red"))
                self.learning_data_table.setItem(row, col, item)
        self.learning_data_table.scrollToBottom()

    def set_pause_state(self, is_paused):
        self.is_paused = is_paused
        if is_paused:
            self.hebbian_timer.stop()
        else:
            self.hebbian_timer.start(2000)

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

    def update_personality_display(self, personality):
        if isinstance(personality, Personality):
            self.personality_type_label.setText(f"Squid Personality: {personality.value.capitalize()}")
            modifier = self.get_personality_modifier(personality)
            self.personality_modifier_label.setText(f"Personality Modifier: {modifier}")
            description = self.get_personality_description(personality)
            self.personality_description.setPlainText(description)
            care_tips = self.get_care_tips(personality)
            self.care_tips.setPlainText(care_tips)
            modifiers = self.get_personality_modifiers(personality)
            self.modifiers_text.setPlainText(modifiers)
        elif isinstance(personality, str):
            self.personality_type_label.setText(f"Squid Personality: {personality.capitalize()}")
            modifier = self.get_personality_modifier(Personality(personality))
            self.personality_modifier_label.setText(f"Personality Modifier: {modifier}")
            description = self.get_personality_description(Personality(personality))
            self.personality_description.setPlainText(description)
            care_tips = self.get_care_tips(Personality(personality))
            self.care_tips.setPlainText(care_tips)
            modifiers = self.get_personality_modifiers(Personality(personality))
            self.modifiers_text.setPlainText(modifiers)
        else:
            print(f"Warning: Invalid personality type: {type(personality)}")

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
        base_font_size = 20
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
            
            # Neurogenesis triggers (critical for new neuron creation)
            "novelty_exposure": state.get("novelty_exposure", 0),
            "sustained_stress": state.get("sustained_stress", 0),
            "recent_rewards": state.get("recent_rewards", 0),
            
            # Debug flag for forced neurogenesis
            "_debug_forced_neurogenesis": state.get("_debug_forced_neurogenesis", False),
            
            # Personality
            "personality": state.get("personality", self.brain_widget.state.get("personality", None))
        }

        # Update the brain widget with complete state
        self.brain_widget.update_state(full_state)
        
        # Force immediate visualization update
        self.brain_widget.update()
        
        # Update memory tab
        self.update_memory_tab()

        # Update personality display if available
        if 'personality' in full_state and full_state['personality']:
            self.update_personality_display(full_state['personality'])
        else:
            print("Warning: Personality not found in brain state")

        # Update thought process visualization
        if hasattr(self.tamagotchi_logic, 'get_decision_data'):
            decision_data = self.tamagotchi_logic.get_decision_data()
            self.update_thought_process(decision_data)
        else:
            print("Warning: Decision data not available")

        # Debug output for neurogenesis
        if self.debug_mode:
            print("\nCurrent Brain State:")
            print(f"Neurons: {list(self.brain_widget.neuron_positions.keys())}")
            print(f"New neurons: {self.brain_widget.neurogenesis_data.get('new_neurons', [])}")
            print(f"Novelty: {full_state['novelty_exposure']}")
            print(f"Stress: {full_state['sustained_stress']}")
            print(f"Rewards: {full_state['recent_rewards']}\n")

    def init_about_tab(self):
        about_text = QtWidgets.QTextEdit()
        about_text.setReadOnly(True)
        about_text.setHtml("""
        <h1>Dosidicus electronicae</h1>
        <p>github.com/ViciousSquid/Dosidicus</p>
        <p>A Tamagotchi-style digital pet with a simple neural network</p>
        <ul>
            <li>by Rufus Pearce</li>
            <li>Brain Tool version 1.0.6.1</li>
            <li>Dosidicus version 1.0.400 (milestone 3)</li>
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

class RecentThoughtsDialog(QtWidgets.QDialog):
    def __init__(self, thought_log, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recent Thoughts")
        self.thought_log = thought_log

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # List widget to display recent thoughts
        self.thought_list = QtWidgets.QListWidget()
        self.thought_list.setSelectionMode(QtWidgets.QAbstractItemView.MultiSelection)
        layout.addWidget(self.thought_list)

        # Populate the list with summarized thought logs
        for log in self.thought_log:
            summary = f"Time: {log['timestamp']} - Decision: {log['final_decision']}"
            self.thought_list.addItem(summary)

        # Save button
        self.save_button = QtWidgets.QPushButton("Save Selected Thoughts")
        self.save_button.clicked.connect(self.save_selected_thoughts)
        layout.addWidget(self.save_button)

    def save_selected_thoughts(self):
        selected_items = self.thought_list.selectedItems()
        if not selected_items:
            QtWidgets.QMessageBox.information(self, "No Selection", "No thoughts selected to save.")
            return

        # Get the file name to save the selected thoughts
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Selected Thoughts", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w') as file:
                for item in selected_items:
                    file.write(item.text() + "\n")
            QtWidgets.QMessageBox.information(self, "Save Successful", f"Selected thoughts saved to {file_name}")

class LogWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Learning Log")
        self.resize(600, 400)

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

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = SquidBrainWindow()
    window.show()
    sys.exit(app.exec_())