# brain_network_tab.py
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .brain_dialogs import StimulateDialog, DiagnosticReportDialog

class NetworkTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.initialize_ui()
        
    def initialize_ui(self):
        # Create a widget to hold the brain visualization
        main_content_widget = QtWidgets.QWidget()
        main_content_layout = QtWidgets.QVBoxLayout()
        main_content_widget.setLayout(main_content_layout)

        # Add brain widget to the main content layout
        main_content_layout.addWidget(self.brain_widget, 1)  # Give it a stretch factor of 1

        # Checkbox controls
        checkbox_layout = QtWidgets.QHBoxLayout()
        
        self.checkbox_links = QtWidgets.QCheckBox("Show links")
        self.checkbox_links.setChecked(True)
        self.checkbox_links.stateChanged.connect(self.brain_widget.toggle_links)
        checkbox_layout.addWidget(self.checkbox_links)

        self.checkbox_weights = QtWidgets.QCheckBox("Show weights")
        self.checkbox_weights.setChecked(True)
        self.checkbox_weights.stateChanged.connect(self.brain_widget.toggle_weights)
        checkbox_layout.addWidget(self.checkbox_weights)
        
        # Add pruning checkbox - ALWAYS VISIBLE
        self.checkbox_pruning = QtWidgets.QCheckBox("Enable pruning")
        self.checkbox_pruning.setChecked(True)  # Enabled by default
        self.checkbox_pruning.stateChanged.connect(self.toggle_pruning)
        # Removed the line that made it only visible in debug mode
        checkbox_layout.addWidget(self.checkbox_pruning)
        
        # Add stretch to push checkboxes to the left
        checkbox_layout.addStretch(1)
        main_content_layout.addLayout(checkbox_layout)

        # Button controls
        button_layout = QtWidgets.QHBoxLayout()
        
        self.stimulate_button = self.create_button("Stimulate", self.stimulate_brain, "#d3d3d3")
        self.stimulate_button.setEnabled(self.debug_mode)
        
        self.save_button = self.create_button("Save State", self.save_brain_state, "#d3d3d3")
        self.load_button = self.create_button("Load State", self.load_brain_state, "#d3d3d3")
        self.report_button = self.create_button("Network Report", self.show_diagnostic_report, "#ADD8E6")

        button_layout.addWidget(self.report_button)
        button_layout.addWidget(self.stimulate_button)
        button_layout.addWidget(self.save_button)
        button_layout.addWidget(self.load_button)
        
        main_content_layout.addLayout(button_layout)

        # Add the content widget to our layout
        self.layout.addWidget(main_content_widget)

    def preload(self):
        """Preload tab contents to prevent crash during tutorial step 2"""
        # Ensure the brain widget is fully initialized
        if hasattr(self, 'brain_widget') and self.brain_widget:
            # Force the brain widget to update
            self.brain_widget.update()
            
        # Make sure checkbox states are properly initialized    
        if hasattr(self, 'checkbox_links'):
            self.checkbox_links.setChecked(True)
        if hasattr(self, 'checkbox_weights'):
            self.checkbox_weights.setChecked(True)

    def toggle_pruning(self, state):
        """Toggle pruning state in brain widget"""
        if hasattr(self, 'brain_widget') and self.brain_widget:
            enabled = state == QtCore.Qt.Checked
            self.brain_widget.toggle_pruning(enabled)
            
            # Show warning if disabling pruning - using a safer approach
            if not enabled:
                # Print warning to console regardless
                print("\033[91mWARNING: Pruning disabled - neurogenesis unconstrained!\033[0m")
                
                # Try multiple approaches to show a UI message
                warning_shown = False
                
                # Method 1: Check if parent window has show_message
                if hasattr(self.parent, 'show_message'):
                    try:
                        self.parent.show_message("WARNING: Pruning disabled - neurogenesis unconstrained!")
                        warning_shown = True
                    except:
                        pass
                        
                # Method 2: Check if we can find the main window
                if not warning_shown and hasattr(self, 'window'):
                    try:
                        if hasattr(self.window, 'show_message'):
                            self.window.show_message("WARNING: Pruning disabled - neurogenesis unconstrained!")
                            warning_shown = True
                    except:
                        pass
                
                # Method 3: Use a QMessageBox as fallback
                if not warning_shown:
                    try:
                        from PyQt5.QtWidgets import QMessageBox
                        msg = QMessageBox()
                        msg.setIcon(QMessageBox.Warning)
                        msg.setText("WARNING: Pruning disabled")
                        msg.setInformativeText("Neurogenesis will be unconstrained and may lead to network instability.")
                        msg.setWindowTitle("Pruning Disabled")
                        msg.exec_()
                    except:
                        # If all else fails, we've already printed to console
                        pass

    def update_from_brain_state(self, state):
        """Update tab based on brain state"""
        # Don't change pruning checkbox visibility based on debug mode
        # The checkbox should always be visible
        pass

    def stimulate_brain(self):
        dialog = StimulateDialog(self.brain_widget, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            stimulation_values = dialog.get_stimulation_values()
            if stimulation_values is not None:
                self.brain_widget.update_state(stimulation_values)
                if self.tamagotchi_logic:
                    self.tamagotchi_logic.update_from_brain(stimulation_values)
                    
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
            
    def show_diagnostic_report(self):
        dialog = DiagnosticReportDialog(self.brain_widget, self)
        dialog.exec_()

    def create_button(self, text, callback, color):
        """Common utility for creating consistent buttons with proper scaling"""
        from .display_scaling import DisplayScaling
        
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        button.setStyleSheet(f"background-color: {color}; border: 1px solid black; padding: {DisplayScaling.scale(5)}px;")
        button.setFixedSize(DisplayScaling.scale(200), DisplayScaling.scale(50))
        
        font = button.font()
        font.setPointSize(DisplayScaling.font_size(10))
        button.setFont(font)
        
        return button