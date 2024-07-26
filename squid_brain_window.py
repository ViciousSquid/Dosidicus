from PyQt5 import QtCore, QtGui, QtWidgets
import random

class BrainWidget(QtWidgets.QWidget):
    def __init__(self):
        super().__init__()
        self.state = {
            "hunger": 50,
            "happiness": 50,
            "cleanliness": 50,
            "sleepiness": 50,
            "is_sick": False,
            "is_eating": False,
            "is_sleeping": False,
            "pursuing_food": False
        }
        self.neuron_positions = {
            "hunger": (300, 125),
            "happiness": (600, 125),
            "cleanliness": (900, 125),
            "sleepiness": (450, 250),
            "health": (750, 250)
        }
        self.connections = self.initialize_connections()
        self.weights = self.initialize_weights()
        self.show_links = False
        self.frozen_weights = None
        self.history = []

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
        self.state.update(new_state)
        self.update_weights()
        self.update()

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
        painter.drawText(QtCore.QRectF(0, 360, 1200, 30), QtCore.Qt.AlignCenter, "State Indicators")

        self.draw_indicator(painter, 200, 420, self.state["is_eating"], "Eating", scale)
        self.draw_indicator(painter, 600, 420, self.state["is_sleeping"], "Sleeping", scale)
        self.draw_indicator(painter, 1000, 420, self.state["pursuing_food"], "Pursuing Food", scale)

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
            font_size = max(6, min(max_font_size, int(8 * scale)))
            font = painter.font()
            font.setPointSize(font_size)
            painter.setFont(font)

            painter.drawText(midpoint[0] - text_area_width // 2, midpoint[1] - text_area_height // 2, text_area_width, text_area_height, QtCore.Qt.AlignCenter, f"{weight:.2f}")

    def draw_neurons(self, painter, scale):
        for name, pos in self.neuron_positions.items():
            if name == "health":
                value = 100 if self.state["is_sick"] else 0
                self.draw_neuron(painter, pos[0], pos[1], value, name, binary=True, scale=scale)
            else:
                self.draw_neuron(painter, pos[0], pos[1], self.state[name], name, scale=scale)

    def draw_neuron(self, painter, x, y, value, label, binary=False, scale=1.0):
        if binary:
            color = QtGui.QColor(255, 0, 0) if value > 50 else QtGui.QColor(0, 255, 0)
        else:
            color = QtGui.QColor(int(255 * (1 - value / 100)), int(255 * (value / 100)), 0)

        painter.setBrush(QtGui.QBrush(color))
        painter.drawEllipse(x - 25, y - 25, 50, 50)

        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(x - 50, y + 30, 100, 20, QtCore.Qt.AlignCenter, label)

    def draw_indicator(self, painter, x, y, state, label, scale=1.0):
        color = QtGui.QColor(0, 255, 0) if state else QtGui.QColor(200, 200, 200)
        painter.setBrush(QtGui.QBrush(color))
        painter.drawRect(x - 75, y - 5, 150, 10)

        painter.setPen(QtGui.QColor(0, 0, 0))
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)
        painter.drawText(x - 75, y + 10, 150, 20, QtCore.Qt.AlignCenter, label)

    def toggle_links(self, state):
        self.show_links = state
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
        neurons = ["hunger", "happiness", "cleanliness", "sleepiness", "is_sick", "is_eating", "is_sleeping", "pursuing_food"]
        for neuron in neurons:
            if neuron.startswith("is_"):
                input_widget = QtWidgets.QComboBox()
                input_widget.addItems(["False", "True"])
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
                stimulation_values[neuron] = input_widget.currentText() == "True"
        return stimulation_values

class SquidBrainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Brain")
        self.resize(640, 512)  # Set initial window size

        screen = QtWidgets.QDesktopWidget().screenNumber(QtWidgets.QDesktopWidget().cursor().pos())
        screen_geometry = QtWidgets.QDesktopWidget().screenGeometry(screen)
        self.move(screen_geometry.right() - 1200, screen_geometry.top())

        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QtWidgets.QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        self.brain_widget = BrainWidget()
        self.layout.addWidget(self.brain_widget)

        self.checkbox = QtWidgets.QCheckBox("Show neuron links and weights")
        self.checkbox.stateChanged.connect(self.brain_widget.toggle_links)
        self.layout.addWidget(self.checkbox)

        self.button_layout = QtWidgets.QHBoxLayout()
        self.layout.addLayout(self.button_layout)

        self.matplotlib_available = False
        try:
            import matplotlib.pyplot as plt
            from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
            self.matplotlib_available = True
        except ImportError:
            pass

        self.stimulate_button = self.create_button("Stimulate Brain", self.stimulate_brain, "#D8BFD8")  # Thistle
        self.plot_button = self.create_button("Plot Brain History", self.plot_brain_history, "#FFDEE9")  # Blush

        if not self.matplotlib_available:
            self.plot_button.setEnabled(False)
            self.plot_button.setToolTip("Matplotlib is not available. Please install it to use the plotting functionality.")

        self.button_layout.addWidget(self.stimulate_button)
        self.button_layout.addWidget(self.plot_button)

        self.button_layout.addStretch(1)  # Add stretch to push buttons to the left

    def create_button(self, text, callback, color):
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        button.setStyleSheet(f"background-color: {color}; border: 1px solid black; padding: 5px;")
        button.setFixedSize(200, 50)
        return button

    def update_brain(self, state):
        self.brain_widget.update_state(state)

    def save_weights(self):
        filename, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Weights", "", "Text Files (*.txt)")
        if filename:
            self.brain_widget.save_weights(filename)

    def load_weights(self):
        filename, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Weights", "", "Text Files (*.txt)")
        if filename:
            self.brain_widget.load_weights(filename)

    def stimulate_brain(self):
        dialog = StimulateDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            stimulation_values = dialog.get_stimulation_values()
            self.brain_widget.stimulate_brain(stimulation_values)

    def plot_brain_history(self):
        if not self.matplotlib_available:
            QtWidgets.QMessageBox.warning(self, "Missing Library", "Matplotlib is not available. Please install it to use the plotting functionality.")
            return

        if not self.brain_widget.history:
            QtWidgets.QMessageBox.warning(self, "No Data", "No brain history data available to plot.")
            return

        import matplotlib.pyplot as plt
        from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas

        fig, ax = plt.subplots()
        for key in self.brain_widget.state.keys():
            if key not in ["is_sick", "is_eating", "is_sleeping", "pursuing_food"]:
                values = [state[key] for state in self.brain_widget.history]
                ax.plot(values, label=key)

        ax.legend()
        ax.set_xlabel("Time")
        ax.set_ylabel("Value")
        ax.set_title("Brain History")

        canvas = FigureCanvas(fig)
        plot_window = QtWidgets.QDialog(self)
        plot_window.setWindowTitle("Brain History Plot")
        plot_window.setLayout(QtWidgets.QVBoxLayout())
        plot_window.layout().addWidget(canvas)
        plot_window.resize(800, 600)
        plot_window.exec_()

if __name__ == "__main__":
    import sys
    app = QtWidgets.QApplication(sys.argv)
    window = SquidBrainWindow()
    window.show()
    sys.exit(app.exec_())
