
import json
import time
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .brain_dialogs import StimulateDialog, DiagnosticReportDialog
from .display_scaling import DisplayScaling
from .neuro_debug import NeuronLaboratory


class NetworkTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.hebbian_timer_value = 0
        self.neurogenesis_timer_value = 0

        # --- NEW: 5-second repulsion timer and flag ---
        self.repulsion_timer = QtCore.QTimer(self)
        self.repulsion_timer.setInterval(5000)          # 5 s
        self.repulsion_timer.timeout.connect(self._do_repulsion_step)
        self.repulsion_enabled = True                   # default ON
        # ---------------------------------------------

        if not hasattr(self, 'layout') or self.layout is None:
            self.layout = QtWidgets.QVBoxLayout(self)   # Fallback, BrainBaseTab should provide it

        self.initialize_ui()
        self.setup_timers()
        self.neuron_lab_dialog = None

    # ------------------------------------------------------------------
    #  UI BUILD
    # ------------------------------------------------------------------
    def initialize_ui(self):
        """
        Build the complete Network-tab UI with metrics, timers, controls,
        neurogenesis counters, checkboxes, and emergency status indicators.
        """
        # --------------------  CLEAR ANY OLD LAYOUT  --------------------
        if self.layout is not None:
            while self.layout.count():
                item = self.layout.takeAt(0)
                widget = item.widget()
                if widget is not None:
                    widget.deleteLater()
                else:
                    sub_layout = item.layout()
                    if sub_layout is not None:
                        self._clear_layout_recursively(sub_layout)

        # --------------------  TOP METRICS BAR  --------------------
        self.metrics_bar = QtWidgets.QWidget()
        self.metrics_bar.setStyleSheet("background-color: rgb(200, 200, 200);")
        self.metrics_bar.setFixedHeight(DisplayScaling.scale(50))
        metrics_layout = QtWidgets.QHBoxLayout(self.metrics_bar)
        metrics_layout.setContentsMargins(DisplayScaling.scale(10), 0,
                                        DisplayScaling.scale(10), 0)
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

        # Emergency creation indicator
        self.emergency_status_label = QtWidgets.QLabel()
        self.emergency_status_label.setStyleSheet("""
            QLabel {
                color: white;
                background-color: #d32f2f;
                padding: 5px;
                border-radius: 5px;
                font-weight: bold;
                font-size: 10pt;
            }
        """)
        self.emergency_status_label.setVisible(False)
        self.emergency_status_label.setFixedWidth(DisplayScaling.scale(200))
        metrics_layout.addWidget(self.emergency_status_label)

        metrics_layout.addStretch()

        # Hebbian timer display
        timers_container = QtWidgets.QWidget()
        timers_container.setStyleSheet("background-color: black; border-radius: 5px;")
        timers_layout = QtWidgets.QHBoxLayout(timers_container)
        timers_layout.setContentsMargins(DisplayScaling.scale(10),
                                    DisplayScaling.scale(5),
                                    DisplayScaling.scale(10),
                                    DisplayScaling.scale(5))
        timers_layout.setSpacing(DisplayScaling.scale(10))

        font_size_timers = DisplayScaling.font_size(12)
        timer_font = QtGui.QFont()
        timer_font.setPointSize(font_size_timers)

        self.hebbian_timer_label = QtWidgets.QLabel("Hebbian: XX")
        self.hebbian_timer_label.setStyleSheet("color: white;")
        self.hebbian_timer_label.setFont(timer_font)
        timers_layout.addWidget(self.hebbian_timer_label)

        metrics_layout.addWidget(timers_container)
        self.layout.insertWidget(0, self.metrics_bar)

        # --------------------  MAIN CONTENT  --------------------
        main_content_widget = QtWidgets.QWidget()
        main_content_layout = QtWidgets.QVBoxLayout(main_content_widget)

        if self.brain_widget:
            main_content_layout.addWidget(self.brain_widget, 1)

        self.layout.addWidget(main_content_widget)

        # --------------------  NEUROGENESIS COUNTERS (BOTTOM-RIGHT)  --------------------
        values_display_layout = QtWidgets.QHBoxLayout()
        values_display_layout.addStretch(1)

        values_container = QtWidgets.QWidget()
        values_box = QtWidgets.QHBoxLayout(values_container)
        values_box.setContentsMargins(10, 5, 10, 5)
        values_box.setSpacing(10)

        font_size_values = DisplayScaling.font_size(10)
        value_font = QtGui.QFont("Arial", font_size_values)
        value_font.setBold(True)

        self.novelty_value_label = QtWidgets.QLabel("N: N/A")
        self.novelty_value_label.setFont(value_font)
        self.novelty_value_label.setToolTip("Novelty Counter: Increases with new experiences.")
        values_box.addWidget(self.novelty_value_label)

        separator1 = QtWidgets.QLabel("|")
        separator1.setFont(value_font)
        values_box.addWidget(separator1)

        self.stress_value_label = QtWidgets.QLabel("S: N/A")
        self.stress_value_label.setFont(value_font)
        self.stress_value_label.setToolTip("Stress Counter: Increases during stressful events.")
        values_box.addWidget(self.stress_value_label)

        separator2 = QtWidgets.QLabel("|")
        separator2.setFont(value_font)
        values_box.addWidget(separator2)

        self.reward_value_label = QtWidgets.QLabel("R: N/A")
        self.reward_value_label.setFont(value_font)
        self.reward_value_label.setToolTip("Reward Counter: Increases after positive outcomes.")
        values_box.addWidget(self.reward_value_label)

        values_display_layout.addWidget(values_container)

        # --------------------  BOTTOM BAR (CHECK-BOXES + COUNTERS)  --------------------
        bottom_bar = QtWidgets.QHBoxLayout()

        # left – check-boxes
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

        # >>>  NEW: Repulsion check-box  <<<
        self.checkbox_repulsion = QtWidgets.QCheckBox("Repulsion")
        self.checkbox_repulsion.setChecked(True)
        self.checkbox_repulsion.stateChanged.connect(self._toggle_repulsion)
        checkbox_layout.addWidget(self.checkbox_repulsion)

        checkbox_layout.addSpacing(DisplayScaling.scale(60))

        self.checkbox_pruning = QtWidgets.QCheckBox("Enable pruning")
        self.checkbox_pruning.setChecked(True)
        self.checkbox_pruning.stateChanged.connect(self.toggle_pruning)
        checkbox_layout.addWidget(self.checkbox_pruning)

        checkbox_layout.addStretch()
        bottom_bar.addLayout(checkbox_layout)

        # right – counters
        bottom_bar.addStretch()
        bottom_bar.addLayout(values_display_layout)

        self.layout.addLayout(bottom_bar)

        # --------------------  FUNCTIONAL STATS LABEL (DYNAMIC)  --------------------
        # (created later when needed; keeps order intact)

        # --------------------  FINAL HOOK-UPS  --------------------
        self.update_metrics_display()
        self.update_hebbian_label()

    # ------------------------------------------------------------------
    #  REPULSION HELPERS
    # ------------------------------------------------------------------
    def _toggle_repulsion(self, state):
        """User clicked the Repulsion check-box."""
        self.repulsion_enabled = (state == QtCore.Qt.Checked)
        if self.repulsion_enabled and self.isVisible():
            self.repulsion_timer.start()
        else:
            self.repulsion_timer.stop()

    def _do_repulsion_step(self):
        """Called every 5 s while tab is visible and repulsion ON."""
        if self.brain_widget and hasattr(self.brain_widget, 'apply_repulsion_force'):
            self.brain_widget.apply_repulsion_force()

    def showEvent(self, event):
        """Network tab became visible – start timer if wanted."""
        super().showEvent(event)
        if self.repulsion_enabled:
            self.repulsion_timer.start()

    def hideEvent(self, event):
        """Network tab hidden – stop timer."""
        super().hideEvent(event)
        self.repulsion_timer.stop()

    # ------------------------------------------------------------------
    #  MISC EXISTING HELPERS
    # ------------------------------------------------------------------
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
        self.update_hebbian_label()

    def update_hebbian_timer(self):
        if self.hebbian_timer_value > 0:
            self.hebbian_timer_value -= 1
        else:
            self.hebbian_timer_value = getattr(self.config, 'hebbian_cycle_seconds', 30)
        self.update_hebbian_label()

    def update_hebbian_label(self):
        if hasattr(self, 'hebbian_timer_label'):
            self.hebbian_timer_label.setText(f"Hebbian: {self.hebbian_timer_value}")

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
        # Only sync hebbian timer if there's a significant difference (>2 seconds)
        # This prevents the jumpy behavior from constant small updates
        brain_timer_value = None
        if hasattr(self.brain_widget, 'hebbian_manager') and hasattr(self.brain_widget.hebbian_manager, 'get_countdown_seconds'):
            brain_timer_value = self.brain_widget.hebbian_manager.get_countdown_seconds()
        elif hasattr(self.brain_widget, 'hebbian_countdown_seconds'):
            brain_timer_value = self.brain_widget.hebbian_countdown_seconds
        
        if brain_timer_value is not None and abs(brain_timer_value - self.hebbian_timer_value) > 2:
            self.hebbian_timer_value = brain_timer_value
        
        self.update_hebbian_label()

        # --- Update Neurogenesis Values Display ---
        if self.brain_widget and hasattr(self.brain_widget, 'neurogenesis_data') and self.brain_widget.neurogenesis_data is not None:
            neuro_data = self.brain_widget.neurogenesis_data

            novelty_val = neuro_data.get('novelty_counter', 0)
            stress_val = neuro_data.get('stress_counter', 0)
            reward_val = neuro_data.get('reward_counter', 0)

            # Update labels
            self.novelty_value_label.setText(f"N: {novelty_val:.2f}")
            self.stress_value_label.setText(f"S: {stress_val:.2f}")
            self.reward_value_label.setText(f"R: {reward_val:.2f}")
        else:
            # Handle case where data is not available
            self.novelty_value_label.setText("N: N/A")
            self.stress_value_label.setText("S: N/A")
            self.reward_value_label.setText("R: N/A")

        # NEW: Update functional neuron statistics (2.4.5.0)
        if hasattr(self.brain_widget, 'enhanced_neurogenesis'):
            self._update_functional_neuron_stats()

    def _create_functional_stats_area(self):
        """Creates the container for functional stats label and the new button."""
        # This wrapper widget holds the functional label and the button side-by-side
        self.functional_stats_area = QtWidgets.QWidget()
        self.stats_and_button_layout = QtWidgets.QHBoxLayout(self.functional_stats_area)
        self.stats_and_button_layout.setContentsMargins(0, 0, 0, 0)
        self.stats_and_button_layout.setSpacing(10)

        # 1. Functional Stats Label (The green card)
        self.functional_stats_label = QtWidgets.QLabel()
        self.functional_stats_label.setWordWrap(True)
        self.functional_stats_label.setStyleSheet("""
            QLabel {
                background-color: #e8f5e9;
                padding: 8px;
                border-radius: 5px;
                border: 1px solid #4CAF50;
                margin: 5px;
            }
        """)
        self.stats_and_button_layout.addWidget(self.functional_stats_label, 1) # Give the label maximum space

        # 2. The new 50x50 Button Container
        self.new_button_container = QtWidgets.QWidget()
        self.new_button_container.setFixedSize(DisplayScaling.scale(50), DisplayScaling.scale(50))
        new_button_layout = QtWidgets.QVBoxLayout(self.new_button_container)
        new_button_layout.setContentsMargins(0, 0, 0, 0)

        # Create the 50x50 button
        self.new_50x50_button = QtWidgets.QPushButton("🔍")
        self.new_50x50_button.setFixedSize(DisplayScaling.scale(50), DisplayScaling.scale(50))
        self.new_50x50_button.setStyleSheet("background-color: #3f51b5; color: white; border-radius: 5px; font-size: 32pt;")

        new_button_layout.addWidget(self.new_50x50_button)

        self.stats_and_button_layout.addWidget(self.new_button_container)

        # Insert the new combined widget before the final layout stretch
        self.layout.insertWidget(self.layout.count() - 1, self.functional_stats_area)

    def flash_emergency_creation(self, neuron_name):
        """Show visual indicator of emergency neuron creation"""
        if hasattr(self, 'emergency_status_label'):
            self.emergency_status_label.setText(f"🚨 Emergency: {neuron_name}")
            self.emergency_status_label.setVisible(True)
            QtCore.QTimer.singleShot(5000, lambda: self.emergency_status_label.setVisible(False))

    def _toggle_neuron_laboratory(self):
        """Toggles the visibility of the Neuron Laboratory dialog."""
        if not self.brain_widget:
            QtWidgets.QMessageBox.warning(self, "Missing Brain", "Cannot open Neuron Laboratory: Brain Widget is not available.")
            return

        if self.neuron_lab_dialog is None:
            # Instantiate the dialog only once
            self.neuron_lab_dialog = NeuronLaboratory(self.brain_widget, self.parent())

        if self.neuron_lab_dialog.isVisible():
            self.neuron_lab_dialog.hide()
        else:
            self.neuron_lab_dialog.show()

    def _update_functional_neuron_stats(self):
        """Display functional neuron statistics"""
        if not hasattr(self.brain_widget, 'enhanced_neurogenesis'):
            return

        eng = self.brain_widget.enhanced_neurogenesis
        functional_neurons = eng.functional_neurons          # same dict

        # ---- FIX: always create the variables ----
        spec_counts = {}
        total_utility = 0
        total_activations = 0

        for name, func_neuron in functional_neurons.items():
            spec = func_neuron.specialization
            spec_counts[spec] = spec_counts.get(spec, 0) + 1
            total_utility += func_neuron.utility_score
            total_activations += func_neuron.activation_count

        # Create label *and container* if it doesn't exist
        if not hasattr(self, 'functional_stats_area'):
            self._create_functional_stats_area() # Call the new helper method

        # Build display text
        if spec_counts:
            avg_utility = total_utility / len(eng.functional_neurons)

            text = "<b>🧬 Functional Neurons:</b><br>"
            text += f"<b>Count:</b> {len(eng.functional_neurons)} | "
            text += f"<b>Avg Utility:</b> {avg_utility:.2f} | "
            text += f"<b>Total Activations:</b> {total_activations}<br>"
            text += "<b>Specialisations:</b> "

            spec_list = [f"<i>{spec}</i>({count})" for spec, count in
                        sorted(spec_counts.items(), key=lambda x: x[1], reverse=True)]
            text += ", ".join(spec_list)

            self.functional_stats_label.setText(text)
        else:
            # Always show the card with zero stats (as requested previously)
            text = "<b>🧬 Functional Neurons:</b><br>"
            text += "<b>Count:</b> 0 | "
            text += "<b>Avg Utility:</b> N/A | "
            text += "<b>Total Activations:</b> 0<br>"
            text += "<b>Specialisations:</b> None"
            self.functional_stats_label.setText(text)

        # Ensure the entire area is always shown
        self.functional_stats_area.show()

    # ------------------------------------------------------------------
    #  PRE-EXISTING FUNCTIONALITY
    # ------------------------------------------------------------------
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
        if not self.brain_widget:
            return
        dialog = StimulateDialog(self.brain_widget, self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            stimulation_values = dialog.get_stimulation_values()
            if stimulation_values is not None and hasattr(self.brain_widget, 'update_state'):
                self.brain_widget.update_state(stimulation_values)
                if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'update_from_brain'):
                    self.tamagotchi_logic.update_from_brain(stimulation_values)

    def save_brain_state(self):
        if not self.brain_widget:
            return
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
        if not self.brain_widget:
            return
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
        if not self.brain_widget:
            return
        dialog = DiagnosticReportDialog(self.brain_widget, self)
        dialog.exec_()

    def create_button(self, text, callback, color_hex):
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)

        padding_val = DisplayScaling.scale(5)
        btn_width = DisplayScaling.scale(150)   # Adjusted for potentially more buttons
        btn_height = DisplayScaling.scale(40)   # Adjusted height
        font_size_val = DisplayScaling.font_size(10)

        button.setStyleSheet(f"background-color: {color_hex}; border: 1px solid black; padding: {padding_val}px;")
        button.setFixedSize(btn_width, btn_height)
        font = button.font()
        font.setPointSize(font_size_val)
        button.setFont(font)
        return button