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