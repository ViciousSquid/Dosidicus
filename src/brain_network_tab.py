try:
    from .brain_designer_launcher import launch_brain_designer_process
except ImportError:
    # Fallback if path is wrong (should never happen with the fix above)
    launch_brain_designer_process = None
import json
import time
import subprocess
import os
import sys
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .brain_dialogs import StimulateDialog, DiagnosticReportDialog
from .display_scaling import DisplayScaling
from .laboratory import NeuronLaboratory
from .animation_styles import get_available_styles, get_style_info


class NetworkTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None,
                 config_manager=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config_manager)
        self.config_manager = config_manager   # store it
        self.debug_mode = debug_mode
        self.hebbian_timer_value = 0
        self.neurogenesis_timer_value = 0

        # Initialize persistent storage for metrics
        self._last_active_neurons = 0
        self._last_total_neurons = 0
        self._last_connections = 0

        if not hasattr(self, 'layout') or self.layout is None:
            self.layout = QtWidgets.QVBoxLayout(self)

        self.initialize_ui()
        self.setup_timers()
        self.neuron_lab_dialog = None
        self.experience_buffer_dialog = None

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

        # Add the global cooldown label
        self.global_cooldown_label = QtWidgets.QLabel("Cooldown: 0.0s")
        self.global_cooldown_label.setFont(value_font)
        values_box.addWidget(self.global_cooldown_label)

        values_display_layout.addWidget(values_container)

        # --------------------  BOTTOM BAR --------------------
        bottom_bar = QtWidgets.QHBoxLayout()

        # 1. STYLE DROPDOWN (Far Left)
        self.anim_combo = QtWidgets.QComboBox()
        # Populate with actual style names from animation_styles.py
        style_info = get_style_info()  # [(name, display_name, description), ...]
        for name, display_name, description in style_info:
            self.anim_combo.addItem(display_name, name)  # Display "Classic", store "classic"
            self.anim_combo.setItemData(self.anim_combo.count() - 1, description, QtCore.Qt.ToolTipRole)
        
        # Set current style from brain_widget
        if self.brain_widget:
            current_style = self.brain_widget.get_animation_style()
            for i in range(self.anim_combo.count()):
                if self.anim_combo.itemData(i) == current_style:
                    self.anim_combo.setCurrentIndex(i)
                    break
        
        self.anim_combo.currentIndexChanged.connect(self._change_animation_style)

        bottom_bar.addWidget(QtWidgets.QLabel("Style:"))
        bottom_bar.addWidget(self.anim_combo)

        # Spacing
        bottom_bar.addSpacing(20)

        # 2. CHECKBOXES (Center-Left)
        self.checkbox_links = QtWidgets.QCheckBox("Show links")
        self.checkbox_links.setChecked(True)
        if self.brain_widget:
            self.checkbox_links.stateChanged.connect(self.brain_widget.toggle_links)
            # Connect to neurogenesis signal to refresh links display when new neuron is created
            self.brain_widget.neuronCreated.connect(self._on_neuron_created)
        bottom_bar.addWidget(self.checkbox_links)

        self.checkbox_weights = QtWidgets.QCheckBox("Show weights")
        self.checkbox_weights.setChecked(False)
        if self.brain_widget:
            self.checkbox_weights.stateChanged.connect(self.brain_widget.toggle_weights)
        bottom_bar.addWidget(self.checkbox_weights)

        self.checkbox_pruning = QtWidgets.QCheckBox("Enable pruning")
        self.checkbox_pruning.setChecked(True)
        self.checkbox_pruning.stateChanged.connect(self.toggle_pruning)
        bottom_bar.addWidget(self.checkbox_pruning)

        # 3. STRETCH (Pushes everything else to the far right)
        bottom_bar.addStretch()

        # 4. LOAD BRAIN BUTTON (Far Right)
        from .custom_brain_loader import add_load_brain_button
        add_load_brain_button(self, bottom_bar)

        self.layout.addLayout(bottom_bar)

        # --------------------  FUNCTIONAL EXISTING HELPERS  -------------------- 
        self.update_metrics_display()
        self.update_hebbian_label()

    def showEvent(self, event):
        """Network tab became visible – start timer if wanted."""
        super().showEvent(event)

    def hideEvent(self, event):
        """Network tab hidden – stop timer."""
        super().hideEvent(event)

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

    def _open_brain_designer(self):
        """Launch Brain Designer in a separate process – safe & reliable"""
        
        # === NEW: Pause simulation via UI ===
        # Try to find the UI instance to trigger the full pause effect (overlay + logic)
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
            self.tamagotchi_logic.user_interface.set_simulation_speed(0)
            self.tamagotchi_logic.user_interface.show_message("Paused for Brain Designer")
        elif self.tamagotchi_logic:
            # Fallback if UI link is missing
            self.tamagotchi_logic.set_simulation_speed(0)
        # ====================================

        import multiprocessing
        from src.brain_designer_launcher import launch_brain_designer_process

        # Prevent multiple instances
        if hasattr(self, '_brain_designer_process') and \
           getattr(self._brain_designer_process, 'is_alive', lambda: False)():
            QtWidgets.QMessageBox.information(
                self, "Already Open", "Brain Designer is already running!"
            )
            return

        try:
            self._brain_designer_process = multiprocessing.Process(
                target=launch_brain_designer_process,
                name="BrainDesignerProcess",
                daemon=False
            )
            self._brain_designer_process.start()
            print(f"Brain Designer launched! PID: {self._brain_designer_process.pid}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            QtWidgets.QMessageBox.critical(
                self,
                "Launch Failed",
                f"Could not start Brain Designer:\n\n{e}"
            )

    def _change_animation_style(self, index):
        """
        Handle animation style dropdown change.
        Called when user selects a new style from the combo box.
        
        Args:
            index: The index of the selected item in the combo box
        """
        if not self.brain_widget:
            return
            
        # Get the internal style name (stored as item data)
        style_name = self.anim_combo.itemData(index)
        if not style_name:
            return
        
        # Use brain_widget's API for real-time style switching
        success = self.brain_widget.set_animation_style(style_name)
        
        if success:
            # Optionally persist to config for next session
            if self.config_manager:
                self.config_manager.set_animation_style(style_name)

    def _on_neuron_created(self, neuron_name: str):
        """
        Handle neurogenesis neuron creation event.
        Toggles the 'Show links' checkbox OFF and then ON again after 2 seconds
        to refresh the links display for the newly created neuron.
        
        Args:
            neuron_name: The name of the newly created neuron
        """
        if not hasattr(self, 'checkbox_links') or self.checkbox_links is None:
            return
        
        # Only toggle if links are currently shown
        if self.checkbox_links.isChecked():
            # Turn off links
            self.checkbox_links.setChecked(False)
            
            # Schedule turning links back on after 2 seconds
            QtCore.QTimer.singleShot(2000, self._restore_links_checkbox)
    
    def _restore_links_checkbox(self):
        """Restore the links checkbox to checked state after delay."""
        if hasattr(self, 'checkbox_links') and self.checkbox_links is not None:
            self.checkbox_links.setChecked(True)

    def setup_timers(self):
        # --- existing Hebbian timer ---
        self.hebbian_countdown = QtCore.QTimer(self)
        self.hebbian_countdown.timeout.connect(self._on_every_second)
        self.hebbian_timer_value = getattr(self.config, 'hebbian_cycle_seconds', 30)
        self.hebbian_countdown.start(1000)
        self.update_hebbian_label()
        self._update_global_cooldown_label()

    def _on_every_second(self):
        """Called every second by the single QTimer."""
        # === NEW: Check pause state ===
        is_paused = False
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'simulation_speed'):
            is_paused = (self.tamagotchi_logic.simulation_speed == 0)
            
        if is_paused:
            if hasattr(self, 'hebbian_timer_label'):
                self.hebbian_timer_label.setText("Hebbian: PAUSED")
            # Don't decrement counter
            return
        # ==============================

        # 1. Update Hebbian counter (count down to 0, show 0 for one full second)
        if self.hebbian_timer_value > 0:
            self.hebbian_timer_value -= 1
        else:
            # When we leave the "00" second and reset the timer → fire Hebbian learning
            parent_window = self.brain_widget.parent()  # SquidBrainWindow
            if parent_window and hasattr(parent_window, 'brain_worker') and parent_window.brain_worker:
                parent_window.brain_worker.queue_hebbian_learning()

            # Reset timer for next cycle
            self.hebbian_timer_value = getattr(self.config, 'hebbian_cycle_seconds', 30)

        self.update_hebbian_label()

        # 2. Update global-cooldown counter
        self._update_global_cooldown_label()

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
        '''Update the metrics bar with current network statistics - single source of truth'''
        if hasattr(self, 'brain_widget') and self.brain_widget:
            # Get neuron positions directly from brain widget
            neuron_positions = getattr(self.brain_widget, 'neuron_positions', {})
            total_neurons = len(neuron_positions)
            
            # Get connection count from weights
            weights_dict = getattr(self.brain_widget, 'weights', {})
            connection_count = len(weights_dict)
            
            # Network health calculation
            if hasattr(self.brain_widget, 'calculate_network_health'):
                health_value = self.brain_widget.calculate_network_health()
                health_percentage_str = f"{health_value:.1f}%" if isinstance(health_value, (int, float)) else "N/A"
            else:
                # Fallback health calculation based on connections per neuron
                if total_neurons > 0:
                    connections_per_neuron = connection_count / total_neurons if total_neurons > 0 else 0
                    if connections_per_neuron < 1.5 and total_neurons > 7:
                        health_percentage_str = "Low Density"
                    else:
                        health_percentage_str = "Optimal"
                else:
                    health_percentage_str = "N/A"
        else:
            total_neurons = 0
            connection_count = 0
            health_percentage_str = "N/A"

        # Update labels with consistent data
        if hasattr(self, 'neurons_label'):
            self.neurons_label.setText(f"Neurons: {total_neurons}")
        if hasattr(self, 'connections_label'):
            self.connections_label.setText(f"Connections: {connection_count}")
        if hasattr(self, 'health_label'):
            self.health_label.setText(f"Network Health: {health_percentage_str}")
            # Set color based on health status
            if health_percentage_str == "Optimal":
                self.health_label.setStyleSheet("font-weight: bold; color: green;")
            elif health_percentage_str == "Low Density":
                self.health_label.setStyleSheet("font-weight: bold; color: orange;")
            else:
                self.health_label.setStyleSheet("font-weight: bold; color: gray;")

        # Update global cooldown label
        self._update_global_cooldown_label()

    def update_from_brain_state(self, state):
        self.update_metrics_display()

        # -----  GLOBAL COOLDOWN  ----- 
        self._update_global_cooldown_label()

        # functional-neuron stats
        if hasattr(self.brain_widget, 'enhanced_neurogenesis'):
            self._update_functional_neuron_stats()

    def _update_global_cooldown_label(self):
        """Update the global cooldown label with the remaining time."""
        if not self.brain_widget:
            self.global_cooldown_label.setText("Cooldown: N/A")
            return

        eng = getattr(self.brain_widget, 'enhanced_neurogenesis', None)
        if eng is None:
            self.global_cooldown_label.setText("Cooldown: N/A")
            return

        # This now returns the real cooldown value
        remaining = eng.get_global_cooldown_remaining()
        self.global_cooldown_label.setText(f"Cooldown: {remaining:.1f}s")

    def _create_functional_stats_area(self):
        """Creates the container for functional stats label and the two side-by-side emoji buttons."""
        # Wrapper that holds the green card + button container
        self.functional_stats_area = QtWidgets.QWidget()
        self.stats_and_button_layout = QtWidgets.QHBoxLayout(self.functional_stats_area)
        self.stats_and_button_layout.setContentsMargins(0, 0, 0, 0)
        self.stats_and_button_layout.setSpacing(10)

        # 1. Functional-stats label (green card)
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
        self.stats_and_button_layout.addWidget(self.functional_stats_label, 1)

        # 2. Button container
        self.new_button_container = QtWidgets.QWidget()
        self.new_button_container.setFixedSize(DisplayScaling.scale(90),
                                            DisplayScaling.scale(90))
        btn_layout = QtWidgets.QHBoxLayout(self.new_button_container)
        btn_layout.setContentsMargins(0, 0, 0, 0)
        btn_layout.setSpacing(4)

        # Brain Designer
        self.new_50x50_button = QtWidgets.QPushButton("🧠")
        self.new_50x50_button.setFixedSize(DisplayScaling.scale(90), DisplayScaling.scale(90))
        self.new_50x50_button.setStyleSheet("""
            QPushButton {
                background-color: #0041C2;
                color: white;
                border-radius: 5px;
                font-size: 26pt;
            }
            QToolTip {
                font-size: 9pt;
                color: #ffffff;
                background: #2b2b2b;
                border: 1px solid #444;
            }
        """)
        self.new_50x50_button.setToolTip("Show Brain Designer")
        self.new_50x50_button.clicked.connect(self._open_brain_designer)
        btn_layout.addWidget(self.new_50x50_button)
        self.stats_and_button_layout.addWidget(self.new_button_container)
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
            self.neuron_lab_dialog = NeuronLaboratory(self.brain_widget, parent=self)

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
                
                # Force disable and re-enable links after loading brain state
                if hasattr(self, 'checkbox_links') and self.checkbox_links.isChecked():
                    self.checkbox_links.setChecked(False)
                    QtCore.QTimer.singleShot(1000, self._restore_links_checkbox)
                
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

    def _show_experience_buffer(self):
        """Show the Experience Buffer window when magnifying glass is clicked"""
        if not self.brain_widget:
            QtWidgets.QMessageBox.warning(self, "Missing Brain", "Cannot open Experience Buffer: Brain Widget is not available.")
            return

        if not hasattr(self.brain_widget, 'enhanced_neurogenesis') or self.brain_widget.enhanced_neurogenesis is None:
            QtWidgets.QMessageBox.warning(self, "No Neurogenesis", "Cannot open Experience Buffer: Neurogenesis system is not initialized.")
            return

        # Create or show the dialog
        if self.experience_buffer_dialog is None:
            self.experience_buffer_dialog = ExperienceBufferDialog(self.brain_widget, self)
        
        self.experience_buffer_dialog.refresh_data()
        self.experience_buffer_dialog.show()
        self.experience_buffer_dialog.raise_()
        self.experience_buffer_dialog.activateWindow()

    def _show_decorations(self):
        """Show the Decorations window"""
        # Navigate up the parent hierarchy to find the main window/UI object
        # Handle both cases: parent as a method (PyQt default) or as an attribute
        parent = self.parent() if callable(self.parent) else self.parent
        
        while parent is not None:
            # Check if this parent has the decoration_window attribute
            if hasattr(parent, 'decoration_window'):
                parent.decoration_window.show()
                parent.decoration_window.raise_()
                parent.decoration_window.activateWindow()
                return
            # Get the next parent (handle both method and attribute cases)
            parent = parent.parent() if callable(parent.parent) else parent.parent
        
        # If we couldn't find it, show a warning
        QtWidgets.QMessageBox.warning(self, "Decorations Unavailable", 
                                     "Cannot open Decorations: Window is not available.")


class ExperienceBufferDialog(QtWidgets.QDialog):
    """Floating window showing the experience buffer contents"""
    
    def __init__(self, brain_widget, parent=None):
        super().__init__(parent)
        self.brain_widget = brain_widget
        self.setWindowTitle("Neurogenesis Experience Buffer")
        self.setMinimumSize(800, 480)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        
        self.setup_ui()
        
    def setup_ui(self):
        """Create the UI elements"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Header with info
        header = QtWidgets.QLabel("Recent Experiences")
        header.setStyleSheet("font-weight: bold; font-size: 12pt; padding: 5px;")
        layout.addWidget(header)
        
        # Create table to show experiences
        self.table = QtWidgets.QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["Type", "Pattern", "Outcome", "Time"])
        
        # Set column widths
        self.table.setColumnWidth(0, 100)   # Type
        self.table.setColumnWidth(1, 400)  # Pattern
        self.table.setColumnWidth(2, 100)   # Outcome
        self.table.setColumnWidth(3, 100)   # Time
        
        # Style the table
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: white;
                gridline-color: #ddd;
            }
            QHeaderView::section {
                background-color: #3f51b5;
                color: white;
                padding: 5px;
                font-weight: bold;
            }
        """)
        
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        
        layout.addWidget(self.table)
        
        # Bottom info panel
        self.info_label = QtWidgets.QLabel()
        self.info_label.setStyleSheet("padding: 5px; background-color: #f5f5f5; border-radius: 3px;")
        layout.addWidget(self.info_label)
        
        # Refresh button
        button_layout = QtWidgets.QHBoxLayout()
        refresh_btn = QtWidgets.QPushButton("Refresh")
        refresh_btn.clicked.connect(self.refresh_data)
        refresh_btn.setFixedSize(80, 30)
        button_layout.addStretch()
        button_layout.addWidget(refresh_btn)
        layout.addLayout(button_layout)
        
    def refresh_data(self):
        """Update the table with current experience buffer data"""
        if not hasattr(self.brain_widget, 'enhanced_neurogenesis') or self.brain_widget.enhanced_neurogenesis is None:
            return
            
        eng = self.brain_widget.enhanced_neurogenesis
        
        if not hasattr(eng, 'experience_buffer'):
            self.info_label.setText("⚠️ Experience buffer not available")
            return
            
        buffer = eng.experience_buffer
        experiences = list(buffer.buffer)
        
        # Clear and populate table
        self.table.setRowCount(len(experiences))
        
        for i, exp in enumerate(reversed(experiences)):  # Most recent first
            # Type column
            type_item = QtWidgets.QTableWidgetItem(exp.trigger_type.capitalize())
            type_color = {
                'novelty': '#2196F3',
                'stress': '#F44336',
                'reward': '#4CAF50'
            }.get(exp.trigger_type, '#757575')
            type_item.setForeground(QtGui.QColor(type_color))
            type_item.setFont(QtGui.QFont("Arial", 9, QtGui.QFont.Bold))
            self.table.setItem(i, 0, type_item)
            
            # Pattern column
            pattern = exp.get_pattern_signature()
            pattern_item = QtWidgets.QTableWidgetItem(pattern)
            pattern_item.setToolTip(pattern)
            self.table.setItem(i, 1, pattern_item)
            
            # Outcome column
            outcome_item = QtWidgets.QTableWidgetItem(exp.outcome.capitalize())
            outcome_item.setForeground(QtGui.QColor('#4CAF50' if exp.outcome == 'positive' else '#757575'))
            self.table.setItem(i, 2, outcome_item)
            
            # Time column (relative)
            time_ago = int(time.time() - exp.timestamp)
            if time_ago < 60:
                time_str = f"{time_ago}s ago"
            elif time_ago < 3600:
                time_str = f"{time_ago // 60}m ago"
            else:
                time_str = f"{time_ago // 3600}h ago"
            time_item = QtWidgets.QTableWidgetItem(time_str)
            time_item.setForeground(QtGui.QColor('#757575'))
            self.table.setItem(i, 3, time_item)
        
        # Update info label with pattern counts
        pattern_counts = buffer.pattern_counts
        top_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)[:3]
        
        if top_patterns:
            pattern_text = "Top patterns: " + " | ".join([f"{p}: {c}" for p, c in top_patterns])
        else:
            pattern_text = "No patterns yet"
            
        self.info_label.setText(f"📊 Buffer size: {len(experiences)}/{buffer.buffer.maxlen} | {pattern_text}")