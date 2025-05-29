import sys
import csv
import os
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QPixmap, QFont
import numpy as np # Needed for brain_widget, good to have here too

# Assuming display_scaling exists in the same directory or is accessible
try:
    from .display_scaling import DisplayScaling
except ImportError:
    # Fallback if DisplayScaling is not available or in a different structure
    class DisplayScaling:
        @staticmethod
        def scale(val): return val
        @staticmethod
        def font_size(val): return val

# --- HealthTab Class (NEW) ---
class HealthTab(QtWidgets.QWidget):
    """A tab to display network health statistics."""
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.brain_widget = brain_widget
        self.layout = QtWidgets.QVBoxLayout(self)
        self.initialize_ui()
        self.update_data()

    def initialize_ui(self):
        # Overall Score Display
        score_group = QtWidgets.QGroupBox("Overall Network Health")
        score_layout = QtWidgets.QVBoxLayout(score_group)
        self.score_label = QtWidgets.QLabel("Calculating...")
        font = self.score_label.font()
        font.setPointSize(DisplayScaling.font_size(28)) # Use scaling
        font.setBold(True)
        self.score_label.setFont(font)
        self.score_label.setAlignment(QtCore.Qt.AlignCenter)
        self.score_label.setStyleSheet("padding: 20px; border: 2px solid #ADD8E6; border-radius: 10px; background-color: #F0F8FF;")
        score_layout.addWidget(self.score_label)
        self.layout.addWidget(score_group)

        # Splitter for details
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        self.layout.addWidget(splitter, 1) # Add stretch factor

        # Component Scores
        components_group = QtWidgets.QGroupBox("Component Scores")
        components_layout = QtWidgets.QFormLayout(components_group)
        self.weight_score_label = QtWidgets.QLabel("N/A")
        self.activity_score_label = QtWidgets.QLabel("N/A")
        self.connectivity_score_label = QtWidgets.QLabel("N/A")
        components_layout.addRow("Weight Score (40%):", self.weight_score_label)
        components_layout.addRow("Activity Score (30%):", self.activity_score_label)
        components_layout.addRow("Connectivity Score (30%):", self.connectivity_score_label)
        splitter.addWidget(components_group)

        # Raw Data
        raw_data_group = QtWidgets.QGroupBox("Underlying Data")
        raw_data_layout = QtWidgets.QFormLayout(raw_data_group)
        self.avg_weight_label = QtWidgets.QLabel("N/A")
        self.std_dev_label = QtWidgets.QLabel("N/A")
        self.connectivity_ratio_label = QtWidgets.QLabel("N/A")
        self.num_neurons_label = QtWidgets.QLabel("N/A")
        raw_data_layout.addRow("Average Absolute Weight:", self.avg_weight_label)
        raw_data_layout.addRow("Activity Std. Deviation:", self.std_dev_label)
        raw_data_layout.addRow("Connectivity Ratio:", self.connectivity_ratio_label)
        raw_data_layout.addRow("Connected / Total Neurons:", self.num_neurons_label)
        splitter.addWidget(raw_data_group)

        # Refresh Button
        refresh_button = QtWidgets.QPushButton("Refresh Data")
        refresh_button.clicked.connect(self.update_data)
        self.layout.addWidget(refresh_button, 0, QtCore.Qt.AlignRight)

    def update_data(self):
        """Fetch data from brain_widget and update labels."""
        if not self.brain_widget:
            return

        # Check if the detailed health calculation method exists
        if not hasattr(self.brain_widget, 'calculate_network_health_detailed'):
            self.score_label.setText("Error!")
            print("ERROR: brain_widget missing 'calculate_network_health_detailed'.")
            # Set other labels to indicate error or N/A
            self.weight_score_label.setText("N/A")
            self.activity_score_label.setText("N/A")
            self.connectivity_score_label.setText("N/A")
            self.avg_weight_label.setText("N/A")
            self.std_dev_label.setText("N/A")
            self.connectivity_ratio_label.setText("N/A")
            self.num_neurons_label.setText("N/A")
            return

        health_data = self.brain_widget.calculate_network_health_detailed()
        score = health_data['score']
        details = health_data['details']

        # Update Score Label and Color
        self.score_label.setText(f"{score:.1f} / 100")
        if score > 80:
            color = "#E8F5E9" # Green
            border = "#C8E6C9"
        elif score > 60:
            color = "#FFFDE7" # Yellow
            border = "#FFF9C4"
        else:
            color = "#FFEBEE" # Red
            border = "#FFCDD2"
        self.score_label.setStyleSheet(f"padding: 20px; border: 2px solid {border}; border-radius: 10px; background-color: {color};")

        # Update Components
        self.weight_score_label.setText(f"{details['weight_score']:.1f} / 100")
        self.activity_score_label.setText(f"{details['activity_score']:.1f} / 100")
        self.connectivity_score_label.setText(f"{details['connectivity_score']:.1f} / 100")

        # Update Raw Data
        self.avg_weight_label.setText(f"{details['avg_abs_weight']:.3f}")
        self.std_dev_label.setText(f"{details['activity_std_dev']:.2f} (Ideal ~30)")
        self.connectivity_ratio_label.setText(f"{details['connectivity_ratio']:.2%}")
        self.num_neurons_label.setText(f"{details['connected_neurons']} / {details['total_neurons']}")


# --- StimulateDialog Class (As provided, check if it needs updates based on your current project state) ---
class StimulateDialog(QtWidgets.QDialog):
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.brain_widget = brain_widget
        # This looks more like an INSPECTOR than a STIMULATE dialog now.
        # We'll keep it as is, but be aware of its potential name/function mismatch.
        self.current_neuron = None

        self.setWindowTitle("Neuron Inspector / Stimulator (?)") # Adjusted title
        self.setMinimumSize(DisplayScaling.scale(600), DisplayScaling.scale(500)) # Use MinimumSize for flexibility

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        # Neuron selection (Maybe add this?)
        self.neuron_combo = QtWidgets.QComboBox()
        # You'd populate this combo box with neuron names from brain_widget
        # layout.addWidget(self.neuron_combo)

        # Info section
        self.info_group = QtWidgets.QGroupBox("Neuron Information")
        self.info_layout = QtWidgets.QFormLayout()
        self.info_group.setLayout(self.info_layout)
        layout.addWidget(self.info_group)

        self.name_label = QtWidgets.QLabel("Select a neuron")
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
        self.connections_table.setHorizontalHeaderLabels(["Neuron", "Direction", "Weight", "Strength", "State"])
        self.connections_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.connections_layout.addWidget(self.connections_table)

        # Activity graph (Kept as placeholder)
        self.activity_group = QtWidgets.QGroupBox("Activity History")
        self.activity_layout = QtWidgets.QVBoxLayout()
        self.activity_group.setLayout(self.activity_layout)
        layout.addWidget(self.activity_group)
        self.activity_plot = QtWidgets.QGraphicsView()
        self.activity_scene = QtWidgets.QGraphicsScene()
        self.activity_plot.setScene(self.activity_scene)
        self.activity_layout.addWidget(self.activity_plot)


        # --- Input Section (If this is truly a Stimulate Dialog) ---
        # This part was missing from your provided StimulateDialog,
        # but is needed for get_stimulation_values. Added a basic version.
        self.inputs_group = QtWidgets.QGroupBox("Stimulate Values")
        self.inputs_layout = QtWidgets.QFormLayout()
        self.inputs_group.setLayout(self.inputs_layout)
        layout.addWidget(self.inputs_group)
        self.neuron_inputs = {} # Store input widgets

        for neuron, value in self.brain_widget.state.items():
            input_widget = None
            if isinstance(value, (int, float)):
                input_widget = QtWidgets.QSpinBox()
                input_widget.setRange(0, 100)
                input_widget.setValue(int(value))
            elif isinstance(value, bool):
                input_widget = QtWidgets.QComboBox()
                input_widget.addItems(["True", "False"])
                input_widget.setCurrentText(str(value))
            # You might add handling for 'direction' or other types if needed
            
            if input_widget:
                self.neuron_inputs[neuron] = input_widget
                self.inputs_layout.addRow(neuron.capitalize(), input_widget)


        # Buttons
        self.buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        self.buttons.accepted.connect(self.accept) # Simplified, add validation if needed
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        # Connect neuron click if signal exists (Good for inspector)
        if hasattr(brain_widget, 'neuronClicked'):
            brain_widget.neuronClicked.connect(self.inspect_neuron)

    def inspect_neuron(self, neuron_name):
        """Updates the dialog to show info for the clicked neuron."""
        self.current_neuron = neuron_name
        self.setWindowTitle(f"Inspector - {neuron_name}")
        
        state = self.brain_widget.state.get(neuron_name, "N/A")
        pos = self.brain_widget.neuron_positions.get(neuron_name, ("N/A", "N/A"))
        
        self.name_label.setText(neuron_name)
        self.state_label.setText(str(state))
        self.position_label.setText(f"({pos[0]:.1f}, {pos[1]:.1f})" if isinstance(pos, tuple) else "N/A")
        # Add logic to determine and set Type (Core, Neurogenesis, etc.)
        self.type_label.setText("Core/New") 
        
        # Update connections table (Requires detailed implementation)
        self.update_connections_table(neuron_name)
        
        # Update activity plot (Requires detailed implementation)
        self.update_activity_plot(neuron_name)

    def update_connections_table(self, neuron_name):
        """(Placeholder) Update the connections table."""
        self.connections_table.setRowCount(0)
        # Add logic to find and display connections for neuron_name

    def update_activity_plot(self, neuron_name):
        """(Placeholder) Update the activity plot."""
        self.activity_scene.clear()
        # Add logic to draw a graph

    def get_stimulation_values(self):
        """Get stimulation values with proper type conversion."""
        stimulation_values = {}
        for neuron, input_widget in self.neuron_inputs.items():
            if isinstance(input_widget, QtWidgets.QSpinBox):
                stimulation_values[neuron] = input_widget.value()
            elif isinstance(input_widget, QtWidgets.QComboBox):
                text = input_widget.currentText()
                stimulation_values[neuron] = text.lower() == 'true'
        return stimulation_values


# --- RecentThoughtsDialog Class (As provided) ---
class RecentThoughtsDialog(QtWidgets.QDialog):
    def __init__(self, thought_log, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Recent Decisions")
        self.thought_log = thought_log

        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)

        self.thought_list = QtWidgets.QListWidget()
        layout.addWidget(self.thought_list)

        for log in self.thought_log:
             summary = f"Time: {log.get('timestamp', 'Unknown')} - Decision: {log.get('decision', 'Unknown')}"
             self.thought_list.addItem(summary)

        button_layout = QtWidgets.QHBoxLayout()
        self.save_button = QtWidgets.QPushButton("Save Selected")
        self.save_button.clicked.connect(self.save_selected_thoughts)
        button_layout.addWidget(self.save_button)
        self.clear_button = QtWidgets.QPushButton("Clear")
        self.clear_button.clicked.connect(self.clear_all_logs)
        button_layout.addWidget(self.clear_button)
        layout.addLayout(button_layout)
    
    def save_selected_thoughts(self):
        # ... (implementation as provided) ...
        pass

    def clear_all_logs(self):
        # ... (implementation as provided) ...
        pass

# --- LogWindow Class (As provided) ---
class LogWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # ... (implementation as provided) ...
        pass
    def update_log(self, text):
        # ... (implementation as provided) ...
        pass
    def export_log(self):
        # ... (implementation as provided) ...
        pass

# --- DiagnosticReportDialog Class (MODIFIED) ---
class DiagnosticReportDialog(QtWidgets.QDialog):
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Neural Network Performance")
        self.setMinimumSize(640, 800) # Increased size a bit for the graph

        self.brain_widget = brain_widget
        # Attempt to get history, handle if parent or logic doesn't exist
        try:
            # IMPORTANT: Ensure get_health_history() returns a list like:
            # [(timestamp1, value1), (timestamp2, value2), ...]
            # or implement it if it doesn't exist yet.
            self.history_data = parent.tamagotchi_logic.get_health_history()
        except AttributeError:
            print("Warning: Could not get health history data.")
            # Create some dummy data for demonstration if needed:
            # self.history_data = [(i, 50 + (i % 10) * 4 + random.randint(-5, 5)) for i in range(20)]
            self.history_data = [] # Default to empty list if not found

        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        # Create tab widget
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)

        # Create report tabs
        self.create_health_tab()
        self.create_connections_tab()
        self.create_neurons_tab()
        self.create_balance_tab()

        # Add history graph section (MODIFIED)
        self.create_history_section() # <-- This is now updated

        # Add close button
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        self.layout.addWidget(self.close_button, 0, QtCore.Qt.AlignRight)

    def create_health_tab(self):
        # ... (Implementation as before) ...
        tab = HealthTab(self.brain_widget, self)
        self.tabs.addTab(tab, "🩺 Network Health")

    def create_connections_tab(self):
        # ... (Implementation as before) ...
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(tab)
        weakest = self.brain_widget.get_weakest_connections()
        connections_group = QtWidgets.QGroupBox("Weakest Connections (Lowest Absolute Weight)")
        connections_layout = QtWidgets.QVBoxLayout()
        table = QtWidgets.QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Source", "Target", "Weight"])
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setRowCount(len(weakest))
        for i, conn_data in enumerate(weakest):
            try:
                if isinstance(conn_data, tuple) and len(conn_data) == 2 and isinstance(conn_data[0], tuple):
                    (a, b), weight = conn_data
                elif isinstance(conn_data, tuple) and len(conn_data) == 3:
                     a, b, weight = conn_data
                else: continue
                table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(a)))
                table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(b)))
                item_weight = QtWidgets.QTableWidgetItem(f"{weight:.3f}")
                color = QtGui.QColor("#4CAF50" if weight > 0 else "#f44336")
                item_weight.setForeground(color)
                table.setItem(i, 2, item_weight)
            except Exception as e: print(f"Error processing connection: {conn_data}, Error: {e}"); continue
        connections_layout.addWidget(table)
        connections_group.setLayout(connections_layout)
        layout.addWidget(connections_group)
        self.tabs.addTab(tab, "🔗 Connections")

    def create_neurons_tab(self):
        # ... (Implementation as before) ...
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel("<h3>Neuron Activity Extremes</h3>")
        layout.addWidget(label)
        extremes = self.brain_widget.get_extreme_neurons(5)
        text_edit = QtWidgets.QTextEdit()
        text_edit.setReadOnly(True)
        html_content = "<h4>🔥 Overactive Neurons (Highest Values):</h4><ul>"
        for name, val in extremes['overactive']: html_content += f"<li><b>{name}:</b> {val:.1f}</li>"
        html_content += "</ul><h4>❄️ Underactive Neurons (Lowest Values):</h4><ul>"
        for name, val in extremes['underactive']: html_content += f"<li><b>{name}:</b> {val:.1f}</li>"
        html_content += "</ul>"
        text_edit.setHtml(html_content)
        layout.addWidget(text_edit)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "💡 Neurons")

    def create_balance_tab(self):
        # ... (Implementation as before) ...
        tab = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout()
        label = QtWidgets.QLabel("<h3>Connection Balance Report</h3>")
        layout.addWidget(label)
        unbalanced = self.brain_widget.get_unbalanced_connections(5)
        text_edit = QtWidgets.QTextEdit()
        text_edit.setReadOnly(True)
        if not unbalanced: report_text = "<p><i>No significantly unbalanced connections found.</i></p>"
        else:
            report_text = "<h4>↔️ Most Unbalanced Connections (Largest Difference):</h4>"
            report_text += "<table width='100%' border='0' cellpadding='4'>"
            for (a, b), (w1, w2), diff in unbalanced: report_text += f"<tr><td><b>{a} ↔ {b}</b></td><td>{w1:.2f} vs {w2:.2f}</td><td>(Δ {diff:.2f})</td></tr>"
            report_text += "</table>"
        text_edit.setHtml(report_text)
        layout.addWidget(text_edit)
        tab.setLayout(layout)
        self.tabs.addTab(tab, "⚖️ Balance")

    # --- MODIFIED THIS METHOD ---
    def create_history_section(self):
        """Creates the health history graph section."""
        group = QtWidgets.QGroupBox("Recent Health History Trend (Last 50 points)")
        layout = QtWidgets.QVBoxLayout(group) # Set layout for the groupbox

        # Create the graph widget
        self.history_graph_widget = SimpleGraphWidget()

        # Set the data (showing the last 50 points for clarity)
        self.history_graph_widget.set_data(self.history_data[-50:])

        # Add the graph widget to the layout
        layout.addWidget(self.history_graph_widget)

        # Add the groupbox to the main dialog layout
        self.layout.addWidget(group)
    # -----------------------------


import sys
import csv
import os
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QPainter, QPen, QBrush, QColor, QPolygonF
from PyQt5.QtCore import Qt, QPointF


class SimpleGraphWidget(QtWidgets.QWidget):
    """A simple widget to draw a line graph using QPainter."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.data = []
        self.padding = 30  # Padding around the graph
        self.setMinimumHeight(200)
        self.setStyleSheet("background-color: white; border: 1px solid #cccccc; border-radius: 5px;")

    def set_data(self, data):
        """
        Sets the data for the graph.
        Expects a list of numbers (health scores).
        """
        # We only need the values for this simple graph
        self.data = [item[1] for item in data if isinstance(item, (list, tuple)) and len(item) == 2]
        self.update()  # Trigger a redraw

    def paintEvent(self, event):
        """Draws the graph."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)

        width = self.width()
        height = self.height()

        # Draw background and border (handled by stylesheet now)
        # painter.fillRect(self.rect(), Qt.white)
        # painter.setPen(QColor(100, 100, 100))
        # painter.drawRect(0, 0, width - 1, height - 1)

        if not self.data:
            painter.drawText(self.rect(), Qt.AlignCenter, "No history data available.")
            return

        # --- Calculate Graph Area and Scales ---
        graph_width = width - 2 * self.padding
        graph_height = height - 2 * self.padding
        
        max_y = 100  # Health is 0-100
        min_y = 0
        max_x = len(self.data) - 1 if len(self.data) > 1 else 1
        min_x = 0

        x_scale = graph_width / max_x if max_x > 0 else 1
        y_scale = graph_height / (max_y - min_y) if (max_y - min_y) > 0 else 1

        # --- Draw Axes ---
        axis_pen = QPen(Qt.black, 2)
        painter.setPen(axis_pen)
        # Y-Axis
        painter.drawLine(self.padding, self.padding, self.padding, height - self.padding)
        # X-Axis
        painter.drawLine(self.padding, height - self.padding, width - self.padding, height - self.padding)

        # --- Draw Y-Axis Labels ---
        label_pen = QPen(Qt.darkGray, 1)
        painter.setPen(label_pen)
        font = painter.font()
        font.setPointSize(8)
        painter.setFont(font)

        for i in range(0, 101, 25): # Labels at 0, 25, 50, 75, 100
            y_pos = height - self.padding - (i * y_scale)
            painter.drawText(5, int(y_pos + 4), str(i)) # +4 for vertical alignment
            painter.drawLine(self.padding - 3, int(y_pos), self.padding, int(y_pos))

        # --- Draw Graph Line ---
        graph_pen = QPen(QColor(0, 100, 200), 2) # Blueish line
        painter.setPen(graph_pen)

        points = []
        for i, value in enumerate(self.data):
            x = self.padding + (i * x_scale)
            y = height - self.padding - (value * y_scale)
            points.append(QPointF(x, y))

        if points:
            path = QtGui.QPainterPath()
            path.moveTo(points[0])
            for point in points[1:]:
                path.lineTo(point)
            painter.drawPath(path)

            # --- Draw Points ---
            painter.setBrush(QColor(0, 100, 200))
            point_pen = QPen(QColor(0, 100, 200), 4) # Make points visible
            painter.setPen(point_pen)
            for point in points:
                 painter.drawPoint(int(point.x()), int(point.y()))