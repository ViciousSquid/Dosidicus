import sys
import csv
import os
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from PyQt5.QtGui import QPixmap, QFont

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