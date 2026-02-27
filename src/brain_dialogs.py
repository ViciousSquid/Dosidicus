import sys
import csv
import os
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QPixmap, QFont

class StimulateDialog(QtWidgets.QDialog):
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
        layout = QtWidgets.QVBoxLayout(tab)
        
        # Get the weakest connections
        weakest = self.brain_widget.get_weakest_connections()
        
        # Connections group
        connections_group = QtWidgets.QGroupBox("Weakest Connections")
        connections_layout = QtWidgets.QVBoxLayout()
        
        # Create the table
        table = QtWidgets.QTableWidget()
        table.setColumnCount(3)
        table.setHorizontalHeaderLabels(["Source", "Target", "Weight"])
        
        # Populate table with weakest connections
        table.setRowCount(len(weakest))
        for i, conn_data in enumerate(weakest):
            try:
                # Handle different possible return formats
                if isinstance(conn_data, tuple) and len(conn_data) == 2 and isinstance(conn_data[0], tuple):
                    # Format: ((source, target), weight)
                    (a, b), weight = conn_data
                elif isinstance(conn_data, tuple) and len(conn_data) == 3:
                    # Format: (source, target, weight)
                    a, b, weight = conn_data
                else:
                    # Unknown format, skip
                    continue
                    
                table.setItem(i, 0, QtWidgets.QTableWidgetItem(str(a)))
                table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(b)))
                table.setItem(i, 2, QtWidgets.QTableWidgetItem(f"{weight:.3f}"))
                
                # Color code based on weight
                color = QtGui.QColor("green" if weight > 0 else "red")
                table.item(i, 2).setForeground(color)
                
            except Exception as e:
                print(f"Error processing connection: {conn_data}, Error: {e}")
                continue
        
        connections_layout.addWidget(table)
        connections_group.setLayout(connections_layout)
        layout.addWidget(connections_group)
        
        # Add to tabs
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