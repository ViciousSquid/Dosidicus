import sys
from PyQt5 import QtCore, QtGui, QtWidgets
import random
import numpy as np
import pyqtgraph as pg

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
        self.neuron_positions = {
            "hunger": (150, 150),
            "happiness": (450, 150),
            "cleanliness": (750, 150),
            "sleepiness": (150, 350),
            "satisfaction": (450, 350),
            "anxiety": (750, 350),
            "curiosity": (450, 550)
        }
        self.connections = self.initialize_connections()
        self.weights = self.initialize_weights()
        self.show_links = False
        self.frozen_weights = None
        self.history = []
        self.training_data = []
        self.associations = np.zeros((len(self.neuron_positions), len(self.neuron_positions)))
        self.learning_rate = 0.1
        self.capture_training_data_enabled = False

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
        # Update only the keys that exist in self.state
        for key in self.state.keys():
            if key in new_state:
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
                file.write(f"{conn[0]} {conn[1]} {weight}\n")

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

        painter.fillRect(QtCore.QRectF(0, 0, 1200, 600), QtGui.QColor(240, 240, 240))

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
        for name, pos in self.neuron_positions.items():
            self.draw_neuron(painter, pos[0], pos[1], self.state[name], name, scale=scale)

    def draw_neuron(self, painter, x, y, value, label, binary=False, scale=1.0):
        color = QtGui.QColor(int(255 * (1 - value / 100)), int(255 * (value / 100)), 0)

        painter.setBrush(QtGui.QBrush(color))
        painter.drawEllipse(x - 25, y - 25, 50, 50)

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
        self.show_links = state
        self.update()

    def toggle_capture_training_data(self, state):
        self.capture_training_data_enabled = state

class StimulateDialog(QtWidgets.QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Stimulate Brain")
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        self.form_layout = QtWidgets.QFormLayout()
        self.layout.addLayout(self.form_layout)

        self.neuron_inputs = {}
        neurons = ["hunger", "happiness", "cleanliness", "sleepiness", "satisfaction", "anxiety", "curiosity", "is_sick", "is_eating", "is_sleeping", "pursuing_food", "direction", "position"]
        for neuron in neurons:
            if neuron.startswith("is_"):
                input_widget = QtWidgets.QComboBox()
                input_widget.addItems(["False", "True"])
            elif neuron == "direction":
                input_widget = QtWidgets.QComboBox()
                input_widget.addItems(["up", "down", "left", "right"])
            elif neuron == "position":
                input_widget = QtWidgets.QLineEdit()
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
            elif isinstance(input_widget, QtWidgets.QLineEdit):
                position_text = input_widget.text()
                if position_text:
                    try:
                        stimulation_values[neuron] = tuple(map(int, position_text.split(',')))
                    except ValueError:
                        QtWidgets.QMessageBox.warning(self, "Invalid Input", f"Invalid format for {neuron}. Expected format: x,y")
                        return None
                else:
                    QtWidgets.QMessageBox.warning(self, "Invalid Input", f"{neuron} cannot be empty.")
                    return None
        return stimulation_values

class SquidBrainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Brain")
        self.resize(900, 600)  # Set initial window size

        screen = QtWidgets.QDesktopWidget().screenNumber(QtWidgets.QDesktopWidget().cursor().pos())
        screen_geometry = QtWidgets.QDesktopWidget().screenGeometry(screen)
        self.move(screen_geometry.right() - 1200, screen_geometry.top())

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QtWidgets.QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.init_tabs()

    def init_tabs(self):
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)

        self.main_tab = QtWidgets.QWidget()
        self.main_tab_layout = QtWidgets.QVBoxLayout()
        self.main_tab.setLayout(self.main_tab_layout)
        self.tabs.addTab(self.main_tab, "Main")

        self.brain_widget = BrainWidget()
        self.main_tab_layout.addWidget(self.brain_widget)

        self.checkbox_links = QtWidgets.QCheckBox("Show neuron links and weights")
        self.checkbox_links.stateChanged.connect(self.brain_widget.toggle_links)
        self.main_tab_layout.addWidget(self.checkbox_links)

        self.checkbox_capture_training_data = QtWidgets.QCheckBox("Capture training data")
        self.checkbox_capture_training_data.stateChanged.connect(self.brain_widget.toggle_capture_training_data)
        self.main_tab_layout.addWidget(self.checkbox_capture_training_data)

        self.stimulate_button = self.create_button("Stimulate Brain", self.stimulate_brain, "#D8BFD8")
        self.main_tab_layout.addWidget(self.stimulate_button)

        self.train_button = self.create_button("Train Hebbian", self.train_hebbian, "#ADD8E6")
        self.train_button.setVisible(False)  # Initially hide the train button
        self.main_tab_layout.addWidget(self.train_button)

        self.graphs_tab = QtWidgets.QWidget()
        self.graphs_tab_layout = QtWidgets.QVBoxLayout()
        self.graphs_tab.setLayout(self.graphs_tab_layout)
        self.tabs.addTab(self.graphs_tab, "Graphs")

        self.init_graphs()

        self.data_tab = QtWidgets.QWidget()
        self.data_tab_layout = QtWidgets.QVBoxLayout()
        self.data_tab.setLayout(self.data_tab_layout)
        self.tabs.addTab(self.data_tab, "Data")

        self.init_data_table()

        self.training_data_tab = QtWidgets.QWidget()
        self.training_data_tab_layout = QtWidgets.QVBoxLayout()
        self.training_data_tab.setLayout(self.training_data_tab_layout)
        self.tabs.addTab(self.training_data_tab, "Training Data")

        self.init_training_data_table()

        self.console_tab = QtWidgets.QWidget()
        self.console_tab_layout = QtWidgets.QVBoxLayout()
        self.console_tab.setLayout(self.console_tab_layout)
        self.tabs.addTab(self.console_tab, "Console")

        self.init_console()

    def init_graphs(self):
        self.graph_widget = pg.PlotWidget()
        self.graphs_tab_layout.addWidget(self.graph_widget)

        self.plot_data = {}
        for neuron in self.brain_widget.neuron_positions.keys():
            self.plot_data[neuron] = []

        self.graph_timer = QtCore.QTimer()
        self.graph_timer.timeout.connect(self.update_graphs)
        self.graph_timer.start(1000)  # Update every second

        self.graph_type_combo = QtWidgets.QComboBox()
        self.graph_type_combo.addItems(["Line", "Scatter"])
        self.graphs_tab_layout.addWidget(self.graph_type_combo)

        self.data_type_combo = QtWidgets.QComboBox()
        self.data_type_combo.addItems(["Raw", "Smoothed"])
        self.graphs_tab_layout.addWidget(self.data_type_combo)

    def update_graphs(self):
        self.graph_widget.clear()
        for neuron, data in self.plot_data.items():
            if self.graph_type_combo.currentText() == "Line":
                self.graph_widget.plot(data, name=neuron, pen=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
            elif self.graph_type_combo.currentText() == "Scatter":
                self.graph_widget.plot(data, name=neuron, symbol='o', pen=None, symbolPen=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)), symbolBrush=(random.randint(0, 255), random.randint(0, 255), random.randint(0, 255)))
            if len(data) > 100:
                self.plot_data[neuron] = data[-100:]

        # Add labels to the graph
        self.graph_widget.setLabel('left', 'Value')
        self.graph_widget.setLabel('bottom', 'Time')
        self.graph_widget.setTitle('Neuron Values Over Time')

    def init_data_table(self):
        self.data_table = QtWidgets.QTableWidget()
        self.data_tab_layout.addWidget(self.data_table)

        self.data_table.setColumnCount(len(self.brain_widget.neuron_positions))
        self.data_table.setHorizontalHeaderLabels(list(self.brain_widget.neuron_positions.keys()))

        self.data_timer = QtCore.QTimer()
        self.data_timer.timeout.connect(self.update_data_table)
        self.data_timer.start(1000)  # Update every second

    def update_data_table(self):
        self.data_table.insertRow(0)
        for col, neuron in enumerate(self.brain_widget.neuron_positions.keys()):
            value = self.brain_widget.state[neuron]
            self.data_table.setItem(0, col, QtWidgets.QTableWidgetItem(str(value)))

        if self.data_table.rowCount() > 100:
            self.data_table.removeRow(100)

    def init_training_data_table(self):
        self.training_data_table = QtWidgets.QTableWidget()
        self.training_data_tab_layout.addWidget(self.training_data_table)

        self.training_data_table.setColumnCount(len(self.brain_widget.neuron_positions))
        self.training_data_table.setHorizontalHeaderLabels(list(self.brain_widget.neuron_positions.keys()))

        self.training_data_timer = QtCore.QTimer()
        self.training_data_timer.timeout.connect(self.update_training_data_table)
        self.training_data_timer.start(1000)  # Update every second

    def update_training_data_table(self):
        self.training_data_table.setRowCount(len(self.brain_widget.training_data))
        for row, sample in enumerate(self.brain_widget.training_data):
            for col, value in enumerate(sample):
                self.training_data_table.setItem(row, col, QtWidgets.QTableWidgetItem(str(value)))

        if len(self.brain_widget.training_data) > 0:
            self.train_button.setVisible(True)

    def init_console(self):
        self.console_output = QtWidgets.QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_tab_layout.addWidget(self.console_output)

        sys.stdout = self.ConsoleOutput(self.console_output)

    def update_brain(self, state):
        # Update the brain_widget state with the provided state
        # If a key is missing, use a default value of 0
        updated_state = {
            neuron: state.get(neuron, 0)
            for neuron in self.brain_widget.neuron_positions.keys()
        }
        self.brain_widget.update_state(updated_state)

        # Update the plot data with the provided state values
        for neuron, value in state.items():
            if neuron in self.plot_data:
                self.plot_data[neuron].append(value)

    def train_hebbian(self):
        self.brain_widget.train_hebbian()
        self.update_data_table()
        self.update_training_data_table()

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

    class ConsoleOutput:
        def __init__(self, text_edit):
            self.text_edit = text_edit

        def write(self, text):
            self.text_edit.append(text)

        def flush(self):
            pass

if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    window = SquidBrainWindow()
    window.show()
    sys.exit(app.exec_())
