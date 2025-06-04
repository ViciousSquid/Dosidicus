# brain_network_tab.py
import json
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .brain_dialogs import StimulateDialog, DiagnosticReportDialog
from .display_scaling import DisplayScaling # Activated this import

class NetworkTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.hebbian_timer_value = 0
        self.neurogenesis_timer_value = 0
        
        if not hasattr(self, 'layout') or self.layout is None:
            self.layout = QtWidgets.QVBoxLayout(self) # Fallback, BrainBaseTab should provide it
            
        self.initialize_ui()
        self.setup_timers()

    def initialize_ui(self):
        # --- CRITICAL FIX: Clear existing widgets from the layout ---
        # This ensures that if initialize_ui is somehow called again, or if old widgets persist,
        # they are removed before rebuilding the UI for this tab.
        if self.layout is not None:
            while self.layout.count():
                item = self.layout.takeAt(0) # Remove item from layout
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater() # Schedule widget for deletion
                else:
                    # If it's a sub-layout, clear it too
                    sub_layout = item.layout()
                    if sub_layout is not None:
                        self._clear_layout_recursively(sub_layout)

        # --- Metrics Bar (New) ---
        self.metrics_bar = QtWidgets.QWidget()
        self.metrics_bar.setStyleSheet("background-color: rgb(200, 200, 200);")
        self.metrics_bar.setFixedHeight(DisplayScaling.scale(50)) # Use DisplayScaling
        metrics_layout = QtWidgets.QHBoxLayout(self.metrics_bar)
        metrics_layout.setContentsMargins(DisplayScaling.scale(10), 0, DisplayScaling.scale(10), 0)
        metrics_layout.setSpacing(DisplayScaling.scale(20))

        self.neurons_label = QtWidgets.QLabel("Neurons: N/A")
        self.neurons_label.setAlignment(QtCore.Qt.AlignCenter)
        metrics_layout.addWidget(self.neurons_label)

        self.connections_label = QtWidgets.QLabel("Connections: N/A")
        self.connections_label.setAlignment(QtCore.Qt.AlignCenter)
        metrics_layout.addWidget(self.connections_label)

        self.health_label = QtWidgets.QLabel("Network Health: N/A")
        self.health_label.setAlignment(QtCore.Qt.AlignCenter)
        metrics_layout.addWidget(self.health_label)
        
        metrics_layout.addStretch(1) 

        timers_container = QtWidgets.QWidget()
        timers_container.setStyleSheet("background-color: black; border-radius: 5px;")
        timers_layout = QtWidgets.QHBoxLayout(timers_container)
        timers_layout.setContentsMargins(DisplayScaling.scale(10),DisplayScaling.scale(5),DisplayScaling.scale(10),DisplayScaling.scale(5))
        timers_layout.setSpacing(DisplayScaling.scale(10))

        font_size_timers = DisplayScaling.font_size(12)
        timer_font = QtGui.QFont()
        timer_font.setPointSize(font_size_timers)

        self.hebbian_timer_label = QtWidgets.QLabel("Hebbian: XX")
        self.hebbian_timer_label.setStyleSheet("color: white;")
        self.hebbian_timer_label.setFont(timer_font)
        timers_layout.addWidget(self.hebbian_timer_label)

        timer_separator = QtWidgets.QLabel("|")
        timer_separator.setStyleSheet("color: white;")
        timer_separator.setFont(timer_font)
        timers_layout.addWidget(timer_separator)
        
        self.neurogenesis_timer_label = QtWidgets.QLabel("NeuroGenesis: XX")
        self.neurogenesis_timer_label.setStyleSheet("color: white;")
        self.neurogenesis_timer_label.setFont(timer_font)
        timers_layout.addWidget(self.neurogenesis_timer_label)
        
        metrics_layout.addWidget(timers_container)
        self.layout.insertWidget(0, self.metrics_bar)

        # --- Main Content (Brain Widget and Controls) ---
        main_content_widget = QtWidgets.QWidget()
        main_content_layout = QtWidgets.QVBoxLayout(main_content_widget)
        
        if self.brain_widget:
            main_content_layout.addWidget(self.brain_widget, 1)

        checkbox_layout = QtWidgets.QHBoxLayout()
        self.checkbox_links = QtWidgets.QCheckBox("Show links")
        self.checkbox_links.setChecked(True)
        if self.brain_widget:
            self.checkbox_links.stateChanged.connect(self.brain_widget.toggle_links)
        checkbox_layout.addWidget(self.checkbox_links)

        self.checkbox_weights = QtWidgets.QCheckBox("Show weights")
        self.checkbox_weights.setChecked(False)
        if self.brain_widget:
            self.checkbox_weights.stateChanged.connect(self.brain_widget.toggle_weights)
        checkbox_layout.addWidget(self.checkbox_weights)

        checkbox_layout.addSpacing(DisplayScaling.scale(60))

        self.checkbox_pruning = QtWidgets.QCheckBox("Enable pruning")
        self.checkbox_pruning.setChecked(True)
        self.checkbox_pruning.stateChanged.connect(self.toggle_pruning)
        checkbox_layout.addWidget(self.checkbox_pruning)
        
        checkbox_layout.addStretch(1)
        main_content_layout.addLayout(checkbox_layout)

        #button_layout = QtWidgets.QHBoxLayout()
        #self.stimulate_button = self.create_button("Stimulate", self.stimulate_brain, "#d3d3d3")
        #if self.stimulate_button:
        #     self.stimulate_button.setEnabled(self.debug_mode)
        
        #self.save_button = self.create_button("Save", self.save_brain_state, "#d3d3d3")
        #self.load_button = self.create_button("Load", self.load_brain_state, "#d3d3d3")
        #self.report_button = self.create_button("Network Report", self.show_diagnostic_report, "#ADD8E6")

        #if self.report_button: button_layout.addWidget(self.report_button)
        #if self.stimulate_button: button_layout.addWidget(self.stimulate_button)
        #if self.save_button: button_layout.addWidget(self.save_button)
        #if self.load_button: button_layout.addWidget(self.load_button)
        
        #main_content_layout.addLayout(button_layout)
        self.layout.addWidget(main_content_widget)
        
        self.update_metrics_display()
        self.update_hebbian_label()
        self.update_neurogenesis_label()

    def _clear_layout_recursively(self, layout_to_clear):
        """Helper to recursively clear a layout and delete its widgets."""
        if layout_to_clear is None:
            return
        while layout_to_clear.count():
            item = layout_to_clear.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
            else:
                sub_layout = item.layout()
                if sub_layout is not None:
                    self._clear_layout_recursively(sub_layout)

    def setup_timers(self):
        self.hebbian_countdown = QtCore.QTimer(self)
        self.hebbian_countdown.timeout.connect(self.update_hebbian_timer)
        self.hebbian_timer_value = getattr(self.config, 'hebbian_cycle_seconds', 30) 
        self.hebbian_countdown.start(1000)

        self.neurogenesis_countdown = QtCore.QTimer(self)
        self.neurogenesis_countdown.timeout.connect(self.update_neurogenesis_timer)
        default_neuro_cooldown = 180
        if hasattr(self.config, 'neurogenesis') and isinstance(self.config.neurogenesis, dict) and 'cooldown' in self.config.neurogenesis:
            default_neuro_cooldown = self.config.neurogenesis['cooldown']
        elif hasattr(self.config, 'neurogenesis_cooldown'):
            default_neuro_cooldown = self.config.neurogenesis_cooldown
        self.neurogenesis_timer_value = default_neuro_cooldown
        self.neurogenesis_countdown.start(1000)
        
        self.update_hebbian_label()
        self.update_neurogenesis_label()

    def update_hebbian_timer(self):
        if self.hebbian_timer_value > 0:
            self.hebbian_timer_value -= 1
        else:
            self.hebbian_timer_value = getattr(self.config, 'hebbian_cycle_seconds', 30)
        self.update_hebbian_label()

    def update_neurogenesis_timer(self):
        if self.neurogenesis_timer_value > 0:
            self.neurogenesis_timer_value -= 1
        else:
            default_neuro_cooldown = 180
            if hasattr(self.config, 'neurogenesis') and isinstance(self.config.neurogenesis, dict) and 'cooldown' in self.config.neurogenesis:
                default_neuro_cooldown = self.config.neurogenesis['cooldown']
            elif hasattr(self.config, 'neurogenesis_cooldown'):
                 default_neuro_cooldown = self.config.neurogenesis_cooldown
            self.neurogenesis_timer_value = default_neuro_cooldown
        self.update_neurogenesis_label()

    def update_hebbian_label(self):
        if hasattr(self, 'hebbian_timer_label'):
            self.hebbian_timer_label.setText(f"Hebbian: {self.hebbian_timer_value}")

    def update_neurogenesis_label(self):
        if hasattr(self, 'neurogenesis_timer_label'):
            self.neurogenesis_timer_label.setText(f"NeuroGenesis: {self.neurogenesis_timer_value}")

    def update_metrics_display(self):
        neuron_count, connection_count, health_value = "N/A", "N/A", "N/A"
        health_percentage_str = "N/A"

        if hasattr(self, 'brain_widget') and self.brain_widget:
            if hasattr(self.brain_widget, 'get_neuron_count'):
                neuron_count = self.brain_widget.get_neuron_count()
            if hasattr(self.brain_widget, 'get_edge_count'):
                connection_count = self.brain_widget.get_edge_count()
            if hasattr(self.brain_widget, 'calculate_network_health'):
                health_value = self.brain_widget.calculate_network_health()
                health_percentage_str = f"{health_value:.1f}%" if isinstance(health_value, (int, float)) else "N/A"
        
        if hasattr(self, 'neurons_label'):
            self.neurons_label.setText(f"Neurons: {neuron_count}")
        if hasattr(self, 'connections_label'):
            self.connections_label.setText(f"Connections: {connection_count}")
        if hasattr(self, 'health_label'):
            self.health_label.setText(f"Network Health: {health_percentage_str}")

    def update_from_brain_state(self, state):
        self.update_metrics_display() 
        if hasattr(self.brain_widget, 'hebbian_manager') and hasattr(self.brain_widget.hebbian_manager, 'get_countdown_seconds'):
            self.hebbian_timer_value = self.brain_widget.hebbian_manager.get_countdown_seconds()
        elif hasattr(self.brain_widget, 'hebbian_countdown_seconds'):
            self.hebbian_timer_value = self.brain_widget.hebbian_countdown_seconds
        self.update_hebbian_label()

        if hasattr(self.brain_widget, 'neurogenesis_manager') and hasattr(self.brain_widget.neurogenesis_manager, 'get_cooldown_remaining'):
            self.neurogenesis_timer_value = self.brain_widget.neurogenesis_manager.get_cooldown_remaining()
        elif hasattr(self.brain_widget, 'neurogenesis_data') and 'last_neuron_time' in self.brain_widget.neurogenesis_data and self.brain_widget.neurogenesis_data['last_neuron_time'] is not None:
            cooldown_duration = 180 
            if hasattr(self.config, 'neurogenesis') and isinstance(self.config.neurogenesis, dict) and 'cooldown' in self.config.neurogenesis:
                cooldown_duration = self.config.neurogenesis['cooldown']
            elif hasattr(self.config, 'neurogenesis_cooldown'):
                 cooldown_duration = self.config.neurogenesis_cooldown
            
            time_since_last = time.time() - self.brain_widget.neurogenesis_data['last_neuron_time']
            remaining_cooldown = max(0, cooldown_duration - time_since_last)
            self.neurogenesis_timer_value = int(remaining_cooldown)
        self.update_neurogenesis_label()

    def preload(self):
        if hasattr(self, 'brain_widget') and self.brain_widget and hasattr(self.brain_widget, 'update'):
            self.brain_widget.update()
        if hasattr(self, 'checkbox_links'):
            self.checkbox_links.setChecked(True)
        if hasattr(self, 'checkbox_weights'):
            self.checkbox_weights.setChecked(False) 

    def toggle_pruning(self, state):
        if hasattr(self, 'brain_widget') and self.brain_widget and hasattr(self.brain_widget, 'toggle_pruning'):
            enabled = (state == QtCore.Qt.Checked)
            self.brain_widget.toggle_pruning(enabled)
            if not enabled:
                print("\033[91mWARNING: Pruning disabled - neurogenesis unconstrained!\033[0m")

    def stimulate_brain(self):
        if not self.brain_widget: return
        dialog = StimulateDialog(self.brain_widget, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            stimulation_values = dialog.get_stimulation_values()
            if stimulation_values is not None and hasattr(self.brain_widget, 'update_state'):
                self.brain_widget.update_state(stimulation_values)
                if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'update_from_brain'):
                    self.tamagotchi_logic.update_from_brain(stimulation_values)
                    
    def save_brain_state(self):
        if not self.brain_widget: return
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Brain State", "", "JSON Files (*.json)")
        if file_name:
            state_to_save = {}
            if hasattr(self.brain_widget, 'get_brain_state'):
                state_to_save = self.brain_widget.get_brain_state()
            elif hasattr(self.brain_widget, 'state'):
                state_to_save = self.brain_widget.state
            try:
                with open(file_name, 'w') as f:
                    json.dump(state_to_save, f, indent=4)
            except Exception as e:
                print(f"Error saving brain state: {e}")

    def load_brain_state(self):
        if not self.brain_widget: return
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Brain State", "", "JSON Files (*.json)")
        if file_name:
            try:
                with open(file_name, 'r') as f:
                    state = json.load(f)
                if hasattr(self.brain_widget, 'set_brain_state'):
                    self.brain_widget.set_brain_state(state)
                elif hasattr(self.brain_widget, 'update_state'):
                    self.brain_widget.update_state(state)
                self.update_metrics_display()
            except Exception as e:
                print(f"Error loading brain state: {e}")
            
    def show_diagnostic_report(self):
        if not self.brain_widget: return
        dialog = DiagnosticReportDialog(self.brain_widget, self) 
        dialog.exec_()

    def create_button(self, text, callback, color_hex):
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        
        padding_val = DisplayScaling.scale(5)
        btn_width = DisplayScaling.scale(150) # Adjusted for potentially more buttons
        btn_height = DisplayScaling.scale(40) # Adjusted height
        font_size_val = DisplayScaling.font_size(10)

        button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black; padding: {padding_val}px;")
        button.setFixedSize(btn_width, btn_height)
        font = button.font()
        font.setPointSize(font_size_val)
        button.setFont(font)
        return button