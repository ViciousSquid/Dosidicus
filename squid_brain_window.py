###########
########### BRAIN TOOL
########### Version 1.0.5.0 - July 2024
###########
########### by Rufus Pearce
########### github.com/ViciousSquid/Dosidicus
###########

import sys
import os
from PyQt5 import QtCore, QtGui, QtWidgets
import random
import numpy as np
import json
from squid import Personality

class BrainWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
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
        self.weights = self.initialize_weights()
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

        # Define pastel colors for each state
        self.state_colors = {
            'is_sick': (255, 204, 204),  # Pastel red
            'is_eating': (204, 255, 204),  # Pastel green
            'is_sleeping': (204, 229, 255),  # Pastel blue
            'pursuing_food': (255, 229, 204),  # Pastel orange
            'direction': (229, 204, 255)  # Pastel purple
        }

    def initialize_connections(self):
        connections = []
        neurons = list(self.neuron_positions.keys())
        for i in range(len(neurons)):
            for j in range(i+1, len(neurons)):
                connections.append((neurons[i], neurons[j]))
        return connections

    def initialize_weights(self):
        return {conn: random.uniform(-1, 1) for conn in self.connections}

    def update_state(self, new_state):
        # Update only the keys that exist in self.state and are allowed to be modified
        for key in self.state.keys():
            if key in new_state and key not in ['satisfaction', 'anxiety', 'curiosity']:
                self.state[key] = new_state[key]
        self.update_weights()
        self.update()
        if self.capture_training_data_enabled:
            self.capture_training_data(new_state)

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

    def save_weights(self, filename):
        with open(filename, 'w') as file:
            for conn, weight in self.weights.items():
                file.write(f"{conn[0]} {conn[1]} {weight}\n\n")

    def load_weights(self, filename):
        with open(filename, 'r') as file:
            for line in file:
                conn, weight = line.strip().split()
                self.weights[(conn[0], conn[1])] = float(weight)

    def stimulate_brain(self, new_state):
        self.update_state(new_state)
        self.record_history()

    def record_history(self):
        self.history.append(self.state.copy())

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

        self.draw_neurons(painter, scale)

        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(12)
        painter.setFont(font)
        painter.drawText(QtCore.QRectF(0, 20, 1200, 30), QtCore.Qt.AlignCenter, "Neurons")

        if self.show_links:
            self.draw_connections(painter, scale)

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
        circular_neurons = ["hunger", "happiness", "cleanliness", "sleepiness"]
        square_neurons = ["satisfaction", "anxiety", "curiosity"]

        for name in circular_neurons:
            pos = self.neuron_positions[name]
            if name in self.state_colors:
                color = self.state_colors[name]
                self.draw_circular_neuron(painter, pos[0], pos[1], self.state[name], name, color=color, scale=scale)
            else:
                self.draw_circular_neuron(painter, pos[0], pos[1], self.state[name], name, scale=scale)

        for name in square_neurons:
            pos = self.neuron_positions[name]
            if name in self.state_colors:
                color = self.state_colors[name]
                self.draw_square_neuron(painter, pos[0], pos[1], self.state[name], name, color=color, scale=scale)
            else:
                self.draw_square_neuron(painter, pos[0], pos[1], self.state[name], name, scale=scale)

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
                if self.is_point_inside_neuron(event.pos(), pos):
                    self.dragging = True
                    self.dragged_neuron = name
                    self.drag_start_pos = event.pos()
                    break

    def mouseMoveEvent(self, event):
        if self.dragging and self.dragged_neuron:
            delta = event.pos() - self.drag_start_pos
            self.neuron_positions[self.dragged_neuron] = (
                self.neuron_positions[self.dragged_neuron][0] + delta.x(),
                self.neuron_positions[self.dragged_neuron][1] + delta.y()
            )
            self.drag_start_pos = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == QtCore.Qt.LeftButton:
            self.dragging = False
            self.dragged_neuron = None

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
    def __init__(self, tamagotchi_logic=None):
        super().__init__()
        self.tamagotchi_logic = tamagotchi_logic
        self.setWindowTitle("Brain")
        self.resize(1024, 768)

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

        self.log_window = None

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

        # Data tab
        self.data_tab = QtWidgets.QWidget()
        self.data_tab_layout = QtWidgets.QVBoxLayout()
        self.data_tab.setLayout(self.data_tab_layout)
        self.tabs.addTab(self.data_tab, "Data")
        self.init_data_table()

        # Personality tab
        self.personality_tab = QtWidgets.QWidget()
        self.personality_tab_layout = QtWidgets.QVBoxLayout()
        self.personality_tab.setLayout(self.personality_tab_layout)
        self.tabs.addTab(self.personality_tab, "Personality")
        self.init_personality_tab()

        # Training Data tab
        #self.training_data_tab = QtWidgets.QWidget()
        #self.training_data_tab_layout = QtWidgets.QVBoxLayout()
        #self.training_data_tab.setLayout(self.training_data_tab_layout)
        #self.tabs.addTab(self.training_data_tab, "Training")
        #self.init_training_data_tab()

        # Console tab
        self.console_tab = QtWidgets.QWidget()
        self.console_tab_layout = QtWidgets.QVBoxLayout()
        self.console_tab.setLayout(self.console_tab_layout)
        self.tabs.addTab(self.console_tab, "Console")
        self.init_console()

        # About tab
        self.about_tab = QtWidgets.QWidget()
        self.about_tab_layout = QtWidgets.QVBoxLayout()
        self.about_tab.setLayout(self.about_tab_layout)
        self.tabs.addTab(self.about_tab, "About")
        self.init_about_tab()

        # Learning tab
        self.learning_tab = QtWidgets.QWidget()
        self.learning_tab_layout = QtWidgets.QVBoxLayout()
        self.learning_tab.setLayout(self.learning_tab_layout)
        self.tabs.addTab(self.learning_tab, "Learning")
        self.init_learning_tab()

    def init_learning_tab(self):
        self.weight_changes_text = QtWidgets.QTextEdit()
        self.weight_changes_text.setReadOnly(True)
        self.learning_tab_layout.addWidget(self.weight_changes_text)

    def perform_hebbian_learning(self):
        if not hasattr(self, 'brain_widget'):
            return

        neuron_pairs = list(self.brain_widget.weights.keys())
        if not neuron_pairs:
            return

        # Randomly select a pair of neurons
        pair = random.choice(neuron_pairs)

        # Perform Hebbian learning
        prev_weight = self.brain_widget.weights[pair]
        neuron1_value = self.brain_widget.state[pair[0]]
        neuron2_value = self.brain_widget.state[pair[1]]

        # Simple Hebbian learning rule
        weight_change = 0.01 * neuron1_value * neuron2_value
        new_weight = prev_weight + weight_change

        # Update the weight
        self.brain_widget.weights[pair] = new_weight

        # Display the weight change
        timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
        change_text = f"{timestamp} - Weight changed between {pair[0].upper()} and {pair[1].upper()}\n"
        change_text += f"Previous value: {prev_weight:.4f}\n"
        change_text += f"New value: {new_weight:.4f}\n"
        
        # Deduce and add the reason for weight change
        reason = self.deduce_weight_change_reason(pair, neuron1_value, neuron2_value)
        change_text += f"Reason: {reason}\n\n"

        self.weight_changes_text.append(change_text)

        # Update log window if open
        if self.log_window and self.log_window.isVisible():
            self.log_window.update_log(change_text)


    def deduce_weight_change_reason(self, pair, value1, value2):        ## Ask the network for reason why the weights changed (!!):-p
        neuron1, neuron2 = pair
        threshold = 70  # Threshold for considering a value as "high"

        if value1 > threshold and value2 > threshold:
            return f"{neuron1.upper()} was HIGH when {neuron2.upper()} was HIGH"
        elif value1 < threshold and value2 < threshold:
            return f"{neuron1.upper()} was LOW when {neuron2.upper()} was LOW"
        elif value1 > threshold:
            return f"{neuron1.upper()} was HIGH when {neuron2.upper()} changed"
        elif value2 > threshold:
            return f"{neuron2.upper()} was HIGH when {neuron1.upper()} changed"
        else:
            return "No clear single reason, complex interaction"


    def update_personality_display(self, personality):
        if isinstance(personality, Personality):
            self.personality_type_label.setText(f"Squid Personality: {personality.value.capitalize()}")
            modifier = self.get_personality_modifier(personality)
            self.personality_modifier_label.setText(f"Personality Modifier: {modifier}")
            description = self.get_personality_description(personality)
            self.personality_description.setPlainText(description)
        elif isinstance(personality, str):
            self.personality_type_label.setText(f"Squid Personality: {personality.capitalize()}")
            modifier = self.get_personality_modifier(Personality(personality))
            self.personality_modifier_label.setText(f"Personality Modifier: {modifier}")
            description = self.get_personality_description(Personality(personality))
            self.personality_description.setPlainText(description)
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

    def init_personality_tab(self):
        # Personality type display
        self.personality_tab_layout.addWidget(QtWidgets.QFrame(frameShape=QtWidgets.QFrame.HLine))
        self.personality_type_label = QtWidgets.QLabel("Squid Personality: ")
        self.personality_type_label.setStyleSheet("font-size: 22px; font-weight: bold;")
        self.personality_tab_layout.addWidget(self.personality_type_label)

        # Personality modifier display
        self.personality_modifier_label = QtWidgets.QLabel("Personality Modifier: ")
        self.personality_modifier_label.setStyleSheet("font-size: 20px;")
        self.personality_tab_layout.addWidget(self.personality_modifier_label)

        # Separator
        self.personality_tab_layout.addWidget(QtWidgets.QFrame(frameShape=QtWidgets.QFrame.HLine))

        # Personality description
        self.personality_description = QtWidgets.QTextEdit()
        self.personality_description.setReadOnly(True)
        self.personality_description.setStyleSheet("font-size: 16px;")
        self.personality_tab_layout.addWidget(self.personality_description)

        # Note about personality generation
        note_label = QtWidgets.QLabel("Note: Personality is randomly generated at the start of a new game")
        note_label.setStyleSheet("font-size: 14px; font-style: italic;")
        self.personality_tab_layout.addWidget(note_label)

    def update_brain(self, state):
        self.brain_widget.update_state(state)
        self.update_data_table(state)
        if 'personality' in state:
            self.update_personality_display(state['personality'])
        else:
            print("Warning: Personality not found in brain state")

    def init_about_tab(self):
        about_text = QtWidgets.QTextEdit()
        about_text.setReadOnly(True)
        about_text.setHtml("""
        <h1>Dosidicus electronicae</h1>
        <p>github.com/ViciousSquid/Dosidicus</p>
        <p>A Tamagotchi-style digital pet with a simple neural network</p>
        <ul>
            <li>by Rufus Pearce</li>
            <li>Brain Tool version 1.0.5.0</li>
            <li>Dosidicus version 1.0.370 (milestone 1)</li>
        <p>This is a research project. Please suggest features.</p>
        </ul>
        """)
        self.about_tab_layout.addWidget(about_text)

    def train_hebbian(self):
        self.brain_widget.train_hebbian()
        self.update_data_table(self.brain_widget.state)
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

    def init_data_table(self):
        self.data_table = QtWidgets.QTableWidget()
        self.data_tab_layout.addWidget(self.data_table)

        self.data_table.setColumnCount(len(self.brain_widget.neuron_positions))
        self.data_table.setHorizontalHeaderLabels(list(self.brain_widget.neuron_positions.keys()))

        self.data_timer = QtCore.QTimer()
        self.data_timer.timeout.connect(lambda: self.update_data_table(self.brain_widget.state))
        self.data_timer.start(1000)  # Update every second

    def update_data_table(self, state):
        self.data_table.setRowCount(1)
        for col, (key, value) in enumerate(state.items()):
            if key in self.brain_widget.neuron_positions:
                item = QtWidgets.QTableWidgetItem(str(value))
                self.data_table.setItem(0, col, item)

    def init_console(self):
        self.console_output = QtWidgets.QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_tab_layout.addWidget(self.console_output)

        sys.stdout = ConsoleOutput(self.console_output)

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
                self.brain_widget.stimulate_brain(stimulation_values)
                if self.tamagotchi_logic:
                    self.tamagotchi_logic.update_from_brain(stimulation_values)
                else:
                    print("Warning: tamagotchi_logic is not set. Brain stimulation will not affect the squid.")

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
