# brain_network_tab.py
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .brain_dialogs import StimulateDialog, DiagnosticReportDialog

class NetworkTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.hebbian_countdown_label = None 
        self.neurogenesis_cooldown_label = None # Initialize the new label
        self.initialize_ui()
        
    def initialize_ui(self):
        # Create a widget to hold the brain visualization
        main_content_widget = QtWidgets.QWidget()
        main_content_layout = QtWidgets.QVBoxLayout()
        main_content_widget.setLayout(main_content_layout)

        # Add brain widget to the main content layout
        main_content_layout.addWidget(self.brain_widget, 1)  # Give it a stretch factor of 1

        # --- Create Checkboxes ---
        self.checkbox_links = QtWidgets.QCheckBox("Show links")
        self.checkbox_links.setChecked(True)
        self.checkbox_links.stateChanged.connect(self.brain_widget.toggle_links)

        self.checkbox_weights = QtWidgets.QCheckBox("Show weights")
        self.checkbox_weights.setChecked(False)
        self.checkbox_weights.stateChanged.connect(self.brain_widget.toggle_weights)

        self.checkbox_pruning = QtWidgets.QCheckBox("Enable pruning")
        self.checkbox_pruning.setChecked(True)  # Enabled by default
        self.checkbox_pruning.stateChanged.connect(self.toggle_pruning)

        # --- Create Buttons ---
        self.stimulate_button = self.create_button("Stimulate", self.stimulate_brain, "#d3d3d3")
        self.stimulate_button.setEnabled(self.debug_mode)
        
        self.save_button = self.create_button("Save", self.save_brain_state, "#d3d3d3")
        self.load_button = self.create_button("Load", self.load_brain_state, "#d3d3d3")
        
        self.report_button = self.create_button("Network Report", self.show_diagnostic_report, "#ADD8E6")

        # --- Hebbian Countdown Label ---
        self.hebbian_countdown_label = QtWidgets.QLabel("30") # Initial value, added "H: " prefix
        self.hebbian_countdown_label.setStyleSheet("""
            QLabel {
                background-color: #000000; /* Black background */
                color: white;
                border-radius: 4px;
                padding: 2px 5px;
                font-size: 20px; 
                font-weight: bold;
                min-width: 60px; /* Adjusted min-width for prefix and number */
                text-align: center;
            }
        """)
        self.hebbian_countdown_label.setAlignment(QtCore.Qt.AlignCenter)
        self.hebbian_countdown_label.setToolTip("Hebbian timer") # Tooltip added here

        # --- Neurogenesis Cooldown Label (NEW) ---
        self.neurogenesis_cooldown_label = QtWidgets.QLabel("---")
        self.neurogenesis_cooldown_label.setStyleSheet("""
            QLabel {
                background-color: #000000; /* Black background */
                color: white;
                border-radius: 4px;
                padding: 2px 5px;
                font-size: 20px; 
                font-weight: bold;
                min-width: 60px; /* Adjusted min-width for prefix and number */
                text-align: center;
                margin-left: 5px; /* Small margin to separate from Hebbian countdown */
            }
        """)
        self.neurogenesis_cooldown_label.setAlignment(QtCore.Qt.AlignCenter)
        self.neurogenesis_cooldown_label.setToolTip("Neurogenesis cooldown") # Tooltip added here


        # --- Bottom Bar Layout ---
        bottom_bar_layout = QtWidgets.QHBoxLayout()
        
        # Original left-aligned widgets
        bottom_bar_layout.addWidget(self.report_button)
        bottom_bar_layout.addWidget(self.checkbox_links)
        bottom_bar_layout.addWidget(self.checkbox_weights)
        
        # Add a stretch before the counters to push them right
        bottom_bar_layout.addStretch(1) 
        
        # Add both countdown labels here 
        bottom_bar_layout.addWidget(self.hebbian_countdown_label) 
        bottom_bar_layout.addWidget(self.neurogenesis_cooldown_label)
        
        # Add another stretch after the counters to push 'Enable pruning' to the far right
        bottom_bar_layout.addStretch(1)
        
        # Add the 'Enable pruning' checkbox last
        bottom_bar_layout.addWidget(self.checkbox_pruning)
        
        # Add the bottom bar to the main content
        main_content_layout.addLayout(bottom_bar_layout)

        # Add the content widget to our main tab layout
        self.layout.addWidget(main_content_widget)

    def preload(self):
        """Preload tab contents to prevent crash during tutorial step 2"""
        if hasattr(self, 'brain_widget') and self.brain_widget:
            self.brain_widget.update()
            
        if hasattr(self, 'checkbox_links'):
            self.checkbox_links.setChecked(True)
        if hasattr(self, 'checkbox_weights'):
            self.checkbox_weights.setChecked(True) 

    def toggle_pruning(self, state):
        """Toggle pruning state in brain widget"""
        if hasattr(self, 'brain_widget') and self.brain_widget:
            enabled = state == QtCore.Qt.Checked
            self.brain_widget.toggle_pruning(enabled)
            
            if not enabled:
                print("\033[91mWARNING: Pruning disabled - neurogenesis unconstrained!\033[0m")
                warning_shown = False
                if hasattr(self.parent, 'show_message'):
                    try:
                        self.parent.show_message("WARNING: Pruning disabled - neurogenesis unconstrained!")
                        warning_shown = True
                    except: pass
                if not warning_shown and hasattr(self, 'window') and hasattr(self.window, 'show_message'):
                    try:
                        self.window.show_message("WARNING: Pruning disabled - neurogenesis unconstrained!")
                        warning_shown = True
                    except: pass
                if not warning_shown:
                    try:
                        from PyQt5.QtWidgets import QMessageBox
                        msg = QMessageBox()
                        msg.setIcon(QMessageBox.Warning)
                        msg.setText("WARNING: Pruning disabled")
                        msg.setInformativeText("Neurogenesis will be unconstrained and may lead to network instability.")
                        msg.setWindowTitle("Pruning Disabled")
                        msg.exec_()
                    except: pass

    def update_from_brain_state(self, state):
        """Update tab based on brain state.
        This method will be called to update the Hebbian countdown timer.
        """
        if hasattr(self, 'hebbian_countdown_label') and self.hebbian_countdown_label:
            # Safely get the countdown value from the brain_widget if available
            hebbian_countdown_seconds = getattr(self.brain_widget, 'hebbian_countdown_seconds', 30)
            self.hebbian_countdown_label.setText(f"H: {hebbian_countdown_seconds}s")

        if hasattr(self, 'neurogenesis_cooldown_label') and self.neurogenesis_cooldown_label:
            # Safely get the neurogenesis cooldown value from the brain_widget
            # Assuming 'neurogenesis_cooldown_seconds' is an attribute of brain_widget
            neurogenesis_cooldown_seconds = getattr(self.brain_widget, 'neurogenesis_cooldown_seconds', '--')
            self.neurogenesis_cooldown_label.setText(f"N: {neurogenesis_cooldown_seconds}s")


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