"""The Brain Tool's learning views: statistics, the weight heatmap, the
connection table, and the controls that trigger learning and neurogenesis.
"""
import logging
import os
import time
import json
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_ui_utils import set_html

_LOG = logging.getLogger(__name__)


class LearningViewsMixin:
    """Part of SquidBrainWindow (see brain_tool.py); not used on its own."""

    def update_countdown(self):
        """Update the Hebbian learning countdown display"""
        # Check if simulation is paused
        is_paused = False
        if hasattr(self, 'tamagotchi_logic') and hasattr(self.tamagotchi_logic, 'simulation_speed'):
            is_paused = (self.tamagotchi_logic.simulation_speed == 0)
        
        # Calculate time until next learning cycle
        if not is_paused and hasattr(self.brain_widget, 'last_hebbian_time'):
            elapsed = time.time() - self.brain_widget.last_hebbian_time
            interval_sec = self.config.hebbian.get('learning_interval', 30000) / 1000
            remaining = max(0, interval_sec - elapsed)
            self.brain_widget.hebbian_countdown_seconds = int(remaining)
        elif not hasattr(self.brain_widget, 'last_hebbian_time'):
            self.brain_widget.hebbian_countdown_seconds = 0

        # Debug print statements
        #print(f"Elapsed time: {elapsed:.1f}s")
        #print(f"Interval: {interval_sec:.1f}s")
        #print(f"Remaining: {remaining:.1f}s")
        #print(f"Hebbian countdown seconds: {self.brain_widget.hebbian_countdown_seconds}")

        # If we have the neural network visualizer tab initialized, update its countdown
        if hasattr(self, 'nn_viz_tab') and hasattr(self.nn_viz_tab, 'countdown_label') and self.nn_viz_tab.countdown_label is not None:
            # Update the formatted display
            if is_paused:
                self.nn_viz_tab.countdown_label.setText("PAUSED")
            else:
                self.nn_viz_tab.countdown_label.setText(f"{self.brain_widget.hebbian_countdown_seconds} seconds")
        
        # If countdown reached zero and not paused, trigger learning
        # (moved outside nn_viz_tab check so learning always fires)
        if self.brain_widget.hebbian_countdown_seconds == 0 and not is_paused:
            # print("brain_tool.py >> Countdown hit zero, calling perform_hebbian_learning()")
            self.brain_widget.perform_hebbian_learning()

    def clear_learning_data(self):
        self.weight_changes_text.clear()
        self.learning_data_table.setRowCount(0)
        self.learning_data = []
        print("Learning data cleared.")

    def deduce_weight_change_reason(self, pair, value1, value2, prev_weight, new_weight, weight_change):
        neuron1, neuron2 = pair
        threshold_high = 70
        threshold_low = 30

        reasons = []

        # Analyze neuron activity levels
        if value1 > threshold_high and value2 > threshold_high:
            reasons.append(f"Both {neuron1.upper()} and {neuron2.upper()} were highly active")
        elif value1 < threshold_low and value2 < threshold_low:
            reasons.append(f"Both {neuron1.upper()} and {neuron2.upper()} had low activity")
        elif value1 > threshold_high:
            reasons.append(f"{neuron1.upper()} was highly active")
        elif value2 > threshold_high:
            reasons.append(f"{neuron2.upper()} was highly active")

        # Analyze weight change
        if abs(weight_change) > 0.1:
            if weight_change > 0:
                reasons.append("Strong positive reinforcement")
            else:
                reasons.append("Strong negative reinforcement")
        elif abs(weight_change) > 0.01:
            if weight_change > 0:
                reasons.append("Moderate positive reinforcement")
            else:
                reasons.append("Moderate negative reinforcement")
        else:
            reasons.append("Weak reinforcement")

        # Analyze the relationship between neurons
        if "hunger" in pair and "satisfaction" in pair:
            reasons.append("Potential hunger-satisfaction relationship")
        elif "cleanliness" in pair and "happiness" in pair:
            reasons.append("Potential cleanliness-happiness relationship")

        # Analyze the current weight
        if abs(new_weight) > 0.8:
            reasons.append("Strong connection formed")
        elif abs(new_weight) < 0.2:
            reasons.append("Weak connection")

        # Analyze learning progress
        if abs(prev_weight) < 0.1 and abs(new_weight) > 0.1:
            reasons.append("New significant connection emerging")
        elif abs(prev_weight) > 0.8 and abs(new_weight) < 0.8:
            reasons.append("Previously strong connection weakening")

        # Combine reasons
        if len(reasons) > 1:
            return " | ".join(reasons)
        elif len(reasons) == 1:
            return reasons[0]
        else:
            return "Complex interaction with no clear single reason"

    def update_learning_data_table(self):
        self.learning_data_table.setRowCount(len(self.learning_data))
        for row, data in enumerate(self.learning_data):
            for col, value in enumerate(data):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col == 3:  # Weight change column
                    item.setData(QtCore.Qt.DisplayRole, f"{value:.4f}")
                if col == 4:  # Direction column
                    if value == "increase ⬆️":
                        item.setForeground(QtGui.QColor("green"))
                    elif value == "⬇️ decrease":
                        item.setForeground(QtGui.QColor("red"))
                self.learning_data_table.setItem(row, col, item)
        self.learning_data_table.scrollToBottom()

    def train_hebbian(self):
        self.brain_widget.train_hebbian()
        #self.update_data_table(self.brain_widget.state)
        self.update_training_data_table()

        # Switch to the Console tab
        self.tabs.setCurrentWidget(self.console_tab)

        # Print training results to the console
        print("Hebbian training completed.")
        print("Updated association strengths:")
        for i, neuron1 in enumerate(self.brain_widget.neuron_positions.keys()):
            for j, neuron2 in enumerate(self.brain_widget.neuron_positions.keys()):
                if i < j:
                    strength = self.brain_widget.get_association_strength(neuron1, neuron2)
                    print(f"{neuron1} - {neuron2}: {strength:.2f}")

    def init_training_data_tab(self):
        self.show_overview_checkbox = QtWidgets.QCheckBox("Show Training Process Overview")
        self.show_overview_checkbox.stateChanged.connect(self.toggle_overview)
        self.training_data_tab_layout.addWidget(self.show_overview_checkbox)

        self.overview_label = QtWidgets.QLabel(
            "Training Process Overview:\n\n"
            "1. Data Capture: When 'Capture training data' is checked, the current state of all neurons is recorded each time the brain is stimulated.\n\n"
            "2. Hebbian Learning: The 'Train Hebbian' button applies the Hebbian learning rule to the captured data.\n\n"
            "3. Association Strength: The learning process strengthens connections between neurons that are frequently active together.\n\n"
            "4. Weight Updates: After training, the weights between neurons are updated based on their co-activation patterns.\n\n"
            "5. Adaptive Behavior: Over time, this process allows the brain to adapt its behavior based on input patterns."
        )
        self.overview_label.setWordWrap(True)
        self.overview_label.hide()  # Hide by default
        self.training_data_tab_layout.addWidget(self.overview_label)

        self.training_data_table = QtWidgets.QTableWidget()
        self.training_data_tab_layout.addWidget(self.training_data_table)

        self.training_data_table.setColumnCount(len(self.brain_widget.neuron_positions))
        self.training_data_table.setHorizontalHeaderLabels(list(self.brain_widget.neuron_positions.keys()))

        self.training_data_timer = QtCore.QTimer()
        self.training_data_timer.timeout.connect(self.update_training_data_table)
        self.training_data_timer.start(1000)  # Update every second

        self.checkbox_capture_training_data = QtWidgets.QCheckBox("Capture training data")
        self.checkbox_capture_training_data.stateChanged.connect(self.toggle_capture_training_data)
        self.training_data_tab_layout.addWidget(self.checkbox_capture_training_data)

        self.train_button = self.create_button("Train Hebbian", self.train_hebbian, "#ADD8E6")
        self.train_button.setEnabled(False)  # Initially grey out the train button
        self.training_data_tab_layout.addWidget(self.train_button)

    def toggle_capture_training_data(self, state):
        self.brain_widget.toggle_capture_training_data(state)
        if state == QtCore.Qt.Checked:
            os.makedirs('training_data', exist_ok=True)

    def update_training_data_table(self):
        self.training_data_table.setRowCount(len(self.brain_widget.training_data))
        for row, sample in enumerate(self.brain_widget.training_data):
            for col, value in enumerate(sample):
                self.training_data_table.setItem(row, col, QtWidgets.QTableWidgetItem(str(value)))

        if len(self.brain_widget.training_data) > 0:
            self.train_button.setEnabled(True)

        # Save raw data to file
        if self.checkbox_capture_training_data.isChecked():
            with open(os.path.join('training_data', 'raw_data.json'), 'w') as f:
                json.dump(self.brain_widget.training_data, f)

    def update_learning_status(self, is_active):
        """Update the learning status indicator"""
        if is_active:
            self.learning_status.setText("Learning Status: Active")
            self.learning_status.setStyleSheet("""
                font-size: 14px;
                padding: 5px;
                background-color: #d4edda;
                border-radius: 4px;
                border: 1px solid #c3e6cb;
                color: #155724;
                font-weight: bold;
            """)
        else:
            self.learning_status.setText("Learning Status: Inactive")
            self.learning_status.setStyleSheet("""
                font-size: 14px;
                padding: 5px;
                background-color: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #e9ecef;
                color: #495057;
            """)

    def update_learning_interval(self, seconds):
        """Update the learning interval when spinbox value changes"""
        # Convert seconds to milliseconds (QTimer uses ms)
        interval_ms = seconds * 1000
        
        # Update config
        if hasattr(self.config, 'hebbian'):
            self.config.hebbian['learning_interval'] = interval_ms
        else:
            self.config.hebbian = {'learning_interval': interval_ms}
        
        # Restart timer with new interval
        if hasattr(self, 'hebbian_timer'):
            self.hebbian_timer.setInterval(interval_ms)
            self.brain_widget.last_hebbian_time = time.time()  # Reset countdown
        
        # Log the change
        self.activity_log.append(f"""
        <div style="background-color: #e8f4f8; padding: 8px; margin: 5px; border-radius: 5px;">
            <span style="font-weight: bold;">Learning interval updated</span><br>
            New interval: {seconds} seconds ({interval_ms} ms)
        </div>
        """)
        
        # Force update of countdown
        self.update_countdown()

    def trigger_learning_cycle(self):
        """Force an immediate Hebbian learning cycle"""
        if hasattr(self.brain_widget, 'perform_hebbian_learning'):
            # Record the current state for before/after comparison
            old_weights = {k: v for k, v in self.brain_widget.weights.items()}
            
            # Perform the learning
            self.brain_widget.perform_hebbian_learning()
            
            # Find changed weights
            changes = []
            for k, v in self.brain_widget.weights.items():
                if k in old_weights and abs(v - old_weights[k]) > 0.001:
                    changes.append((k, old_weights[k], v))
            
            # Log the forced learning event
            log_html = f"""
            <div style="background-color: #d4edda; padding: 10px; margin: 8px; border-radius: 5px; border-left: 4px solid #28a745;">
                <span style="font-weight: bold; font-size: 14px;">Manual learning cycle triggered</span><br>
                <span style="color: #555;">Time: {time.strftime('%H:%M:%S')}</span><br>
                <span>Changes detected: {len(changes)}</span>
            """
            
            if changes:
                log_html += "<ul style='margin-top: 5px;'>"
                for (source, target), old_val, new_val in changes[:5]:  # Show top 5 changes
                    direction = "+" if new_val > old_val else ""
                    log_html += f"""
                    <li>
                        <span style="font-weight: bold;">{source} → {target}</span>: 
                        <span style="color: #777;">{old_val:.3f}</span> → 
                        <span style="color: {'green' if new_val > old_val else 'red'}; font-weight: bold;">
                            {new_val:.3f} ({direction}{new_val - old_val:.3f})
                        </span>
                    </li>
                    """
                if len(changes) > 5:
                    log_html += f"<li>...and {len(changes) - 5} more changes</li>"
                log_html += "</ul>"
            else:
                log_html += "<br><span style='font-style: italic;'>No significant weight changes detected</span>"
                
            log_html += "</div>"
            self.activity_log.append(log_html)
            
            # Update the connection table and heatmap
            self.update_connection_table()
            self.update_heatmap()
            self.update_learning_statistics()

    def update_connection_table(self):
        """Update the connection table with current weights"""
        self.connections_view.setRowCount(0)  # Clear existing rows
        
        # Get all weights
        weights = self.brain_widget.weights
        if not weights:
            return
        
        # Get blacklisted neurons to exclude
        excluded_neurons = getattr(self.brain_widget, 'excluded_neurons', ['is_sick', 'is_eating', 'is_sleeping', 'pursuing_food', 'direction'])
        
        # Apply current filter
        filter_text = self.connection_search.text().lower()
        filter_type = self.connection_filter.currentText()
        
        # Add rows to table
        row = 0
        for (source, target), weight in sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True):
            # Skip connections involving blacklisted neurons
            if source in excluded_neurons or target in excluded_neurons:
                continue
                
            # Apply filters
            if filter_type == "Strong Positive" and weight <= 0.5:
                continue
            elif filter_type == "Strong Negative" and weight >= -0.5:
                continue
            elif filter_type == "Weak Connections" and abs(weight) > 0.3:
                continue
            elif filter_type == "New Connections":
                # Check if either neuron is new
                if (source not in self.brain_widget.neurogenesis_data.get('new_neurons', []) and
                    target not in self.brain_widget.neurogenesis_data.get('new_neurons', [])):
                    continue
            
            # Apply text search
            if filter_text and not (filter_text in source.lower() or filter_text in target.lower()):
                continue
                
            # Add the row
            self.connections_view.insertRow(row)
            
            # Source neuron
            source_item = QtWidgets.QTableWidgetItem(source)
            if source in self.brain_widget.neurogenesis_data.get('new_neurons', []):
                source_item.setBackground(QtGui.QColor(255, 255, 200))  # Light yellow for new neurons
            source_item.setFont(QtGui.QFont("Fio UI", 14))  # Bigger font size
            self.connections_view.setItem(row, 0, source_item)
            
            # Target neuron
            target_item = QtWidgets.QTableWidgetItem(target)
            if target in self.brain_widget.neurogenesis_data.get('new_neurons', []):
                target_item.setBackground(QtGui.QColor(255, 255, 200))
            target_item.setFont(QtGui.QFont("Fio UI", 14))  # Bigger font size
            self.connections_view.setItem(row, 1, target_item)
            
            # Weight value
            weight_item = QtWidgets.QTableWidgetItem(f"{weight:.3f}")
            if weight > 0.5:
                weight_item.setForeground(QtGui.QColor(0, 150, 0))  # Green for strong positive
            elif weight > 0:
                weight_item.setForeground(QtGui.QColor(0, 100, 0))  # Dark green for mild positive
            elif weight > -0.5:
                weight_item.setForeground(QtGui.QColor(150, 0, 0))  # Dark red for mild negative
            else:
                weight_item.setForeground(QtGui.QColor(200, 0, 0))  # Bright red for strong negative
            weight_item.setFont(QtGui.QFont("Fio UI", 14))  # Bigger font size
            self.connections_view.setItem(row, 2, weight_item)
            
            # Trend indicator with emoji arrows
            trend_item = QtWidgets.QTableWidgetItem("—")
            if hasattr(self, '_prev_weights') and (source, target) in self._prev_weights:
                prev = self._prev_weights.get((source, target), 0)
                if weight > prev + 0.01:
                    trend_item = QtWidgets.QTableWidgetItem("⬆️")  # Up emoji arrow
                elif weight < prev - 0.01:
                    trend_item = QtWidgets.QTableWidgetItem("⬇️")  # Down emoji arrow
            trend_item.setFont(QtGui.QFont("Fio UI", 14))  # Bigger font size
            self.connections_view.setItem(row, 3, trend_item)
            
            row += 1
        
        # Store current weights for future trend comparison
        if not hasattr(self, '_prev_weights'):
            self._prev_weights = {}
        self._prev_weights = weights.copy()

    def filter_connections(self):
        """Apply the current filters to the connection table"""
        self.update_connection_table()

    def show_connection_details(self):
        """Show details for the selected connection"""
        selected_items = self.connections_view.selectedItems()
        if not selected_items:
            self.connection_details.clear()
            return
        
        # Get the row (assumes single row selection)
        row = selected_items[0].row()
        
        # Get values from the row
        source = self.connections_view.item(row, 0).text()
        target = self.connections_view.item(row, 1).text()
        weight = float(self.connections_view.item(row, 2).text())
        
        # Generate detailed HTML content
        details_html = f"""
        <div style="font-family: Fio UI;">
            <h3 style="margin: 5px 0; color: #2c3e50;">Connection Details</h3>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 5px; font-weight: bold;">Source Neuron:</td>
                    <td style="padding: 5px;">{source}</td>
                </tr>
                <tr>
                    <td style="padding: 5px; font-weight: bold;">Target Neuron:</td>
                    <td style="padding: 5px;">{target}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 5px; font-weight: bold;">Connection Weight:</td>
                    <td style="padding: 5px; font-weight: bold; color: {'green' if weight > 0 else 'red'};">
                        {weight:.4f}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 5px; font-weight: bold;">Connection Strength:</td>
                    <td style="padding: 5px;">
        """
        
        # Add strength description
        if abs(weight) > 0.8:
            details_html += "<span style='color: #2980b9; font-weight: bold;'>Very Strong</span>"
        elif abs(weight) > 0.5:
            details_html += "<span style='color: #3498db; font-weight: bold;'>Strong</span>"
        elif abs(weight) > 0.3:
            details_html += "<span style='color: #7f8c8d;'>Moderate</span>"
        elif abs(weight) > 0.1:
            details_html += "<span style='color: #95a5a6;'>Weak</span>"
        else:
            details_html += "<span style='color: #bdc3c7;'>Very Weak</span>"
            
        details_html += """
                    </td>
                </tr>
            </table>
            
            <div style="margin-top: 15px; font-weight: bold;">Interpretation:</div>
        """
        
        # Add interpretation based on the connection
        if weight > 0:
            details_html += f"""
            <p style="margin: 5px 0;">This is a <span style="color: green;">positive connection</span>. When <b>{source}</b> is active, it will tend to increase the activity of <b>{target}</b>.</p>
            """
        else:
            details_html += f"""
            <p style="margin: 5px 0;">This is an <span style="color: red;">inhibitory connection</span>. When <b>{source}</b> is active, it will tend to decrease the activity of <b>{target}</b>.</p>
            """
        
        # Check if either neuron is from neurogenesis
        if source in self.brain_widget.neurogenesis_data.get('new_neurons', []) or target in self.brain_widget.neurogenesis_data.get('new_neurons', []):
            details_html += """
            <div style="margin-top: 10px; background-color: #fff9c4; padding: 8px; border-radius: 4px;">
                <b>Note:</b> This connection involves a neuron created through neurogenesis!
            </div>
            """
        
        details_html += "</div>"
        
        # Update the details widget
        set_html(self.connection_details, details_html)

    def apply_neurogenesis_settings(self):
        """Apply changes to neurogenesis settings"""
        # Validate and update the neurogenesis configuration
        if not hasattr(self.config, 'neurogenesis'):
            self.config.neurogenesis = {}
        
        # Get current values from UI
        self.config.neurogenesis['novelty_threshold'] = self.novelty_threshold.value()
        self.config.neurogenesis['stress_threshold'] = self.stress_threshold.value()
        self.config.neurogenesis['reward_threshold'] = self.reward_threshold.value()
        self.config.neurogenesis['cooldown'] = self.cooldown_spinbox.value()
        
        # Log the changes
        self.activity_log.append(f"""
        <div style="background-color: #d4edda; padding: 10px; margin: 8px; border-radius: 5px; border-left: 4px solid #4285f4;">
            <span style="font-weight: bold; font-size: 14px;">Neurogenesis Settings Updated</span><br>
            <span style="color: #555;">Time: {time.strftime('%H:%M:%S')}</span><br>
            <ul style="margin-top: 5px;">
                <li>Novelty Threshold: {self.config.neurogenesis['novelty_threshold']}</li>
                <li>Stress Threshold: {self.config.neurogenesis['stress_threshold']}</li>
                <li>Reward Threshold: {self.config.neurogenesis['reward_threshold']}</li>
                <li>Cooldown Period: {self.config.neurogenesis['cooldown']} seconds</li>
            </ul>
        </div>
        """)
        
        # Update the status display
        self.update_neurogenesis_status()
        
        # Show confirmation message
        QtWidgets.QMessageBox.information(
            self, "Settings Applied", 
            "Neurogenesis settings have been updated successfully."
        )

    def trigger_neurogenesis(self):
        """Trigger neurogenesis by boosting natural trigger values"""
        try:
            if not hasattr(self, 'squid_brain_window') or not self.squid_brain_window:
                self.show_message("Brain window not initialized")
                print("Error: Brain window not initialized")
                return
                
            brain = self.squid_brain_window.brain_widget
            print("Brain widget found")
            
            # Get current neuron count to verify success
            old_neurons = set(brain.neuron_positions.keys())
            print(f"Current neurons: {len(old_neurons)}")
            
            # Get thresholds to ensure we exceed them
            novelty_threshold = brain.neurogenesis_config.get('novelty_threshold', 3) 
            stress_threshold = brain.neurogenesis_config.get('stress_threshold', 0.7)
            reward_threshold = brain.neurogenesis_config.get('reward_threshold', 0.6)
            
            print(f"Neurogenesis thresholds - Novelty: {novelty_threshold}, Stress: {stress_threshold}, Reward: {reward_threshold}")
            
            # Reset cooldown to allow neurogenesis to happen
            if hasattr(brain, 'neurogenesis_data'):
                # Store original for restoration
                original_time = brain.neurogenesis_data.get('last_neuron_time', 0)
                brain.neurogenesis_data['last_neuron_time'] = 0
                print("Neurogenesis cooldown temporarily reset")
            
            # Create state with all triggers boosted significantly above thresholds
            state = {
                # Boost all three pathways to ensure at least one succeeds
                'novelty_exposure': novelty_threshold * 2,  # Double the threshold
                'sustained_stress': stress_threshold * 2,
                'recent_rewards': reward_threshold * 2,
                
                # Add current state values for context
                'hunger': getattr(self.tamagotchi_logic.squid, 'hunger', 50),
                'happiness': getattr(self.tamagotchi_logic.squid, 'happiness', 50),
                'personality': getattr(self.tamagotchi_logic.squid, 'personality', None)
            }
            
            print(f"Submitting state with trigger values: {state}")
            
            # Update state which will trigger natural neurogenesis
            brain.update_state(state)
            
            # Verify if neurogenesis occurred
            new_neurons = set(brain.neuron_positions.keys()) - old_neurons
            
            if new_neurons:
                # Get details of the new neuron(s)
                for new_neuron in new_neurons:
                    # Check if connections were created
                    connections = [k for k in brain.weights.keys() if new_neuron in k]
                    
                    # Generate message with details
                    message = f"Created neuron: {new_neuron} with {len(connections)} connections"
                    self.show_message(message)
                    print(message)
                    print(f"Connections: {connections[:5]}...")
                    
                    # Highlight the new neuron
                    if hasattr(brain, 'neurogenesis_highlight'):
                        brain.neurogenesis_highlight = {
                            'neuron': new_neuron,
                            'start_time': time.time(),
                            'duration': 10.0  # 10 seconds highlight
                        }
                        brain.update()  # Force redraw
                    
                    # Force an immediate hebbian learning cycle to integrate the neuron
                    if hasattr(brain, 'perform_hebbian_learning'):
                        print("Triggering hebbian learning cycle to integrate new neuron")
                        brain.perform_hebbian_learning()
            else:
                self.show_message("No new neurons created - check console for details")
                print("WARNING: Neurogenesis was triggered but no new neurons were created")
                print(f"State submitted: {state}")
                print(f"Neurogenesis config: {brain.neurogenesis_config}")
            
            # Restore original cooldown time
            if hasattr(brain, 'neurogenesis_data') and 'original_time' in locals():
                brain.neurogenesis_data['last_neuron_time'] = original_time
                print("Neurogenesis cooldown restored")
                
        except Exception as e:
            self.show_message(f"Neurogenesis Error: {str(e)}")
            import traceback
            traceback.print_exc()

    def update_heatmap(self):
        """Update the connection weight heatmap visualization"""
        if not hasattr(self, 'heatmap_scene') or not hasattr(self, 'brain_widget'):
            return

        self.heatmap_scene.clear()
        
        try:
            # Get neuron data from brain widget
            neurons = list(self.brain_widget.neuron_positions.keys())
            excluded = getattr(self.brain_widget, 'excluded_neurons', [])
            weights = getattr(self.brain_widget, 'weights', {})
            
            # Filter out excluded neurons
            neurons = [n for n in neurons if n not in excluded]
            if not neurons:
                self.heatmap_scene.addText("No neurons available", QtGui.QFont(), QtCore.QPointF(50, 50))
                return

            # Heatmap parameters
            cell_size = 30
            padding = 50
            max_weight = max(abs(w) for w in weights.values()) if weights else 1.0
            max_weight = max(max_weight, 0.01)  # Prevent division by zero

            # Create heatmap grid
            for i, src in enumerate(neurons):
                for j, dst in enumerate(neurons):
                    if src == dst:
                        continue
                        
                    # Get weight value (check both direction permutations)
                    weight = weights.get((src, dst), weights.get((dst, src), 0))
                    
                    # Calculate color intensity
                    intensity = min(abs(weight) / max_weight, 1.0)
                    if weight > 0:
                        color = QtGui.QColor(0, 0, int(255 * intensity))  # Blue for positive
                    else:
                        color = QtGui.QColor(int(255 * intensity), 0, 0)  # Red for negative
                        
                    # Draw cell
                    rect = QtCore.QRectF(
                        padding + j * cell_size,
                        padding + i * cell_size,
                        cell_size - 1,  # -1 for grid lines
                        cell_size - 1
                    )
                    self.heatmap_scene.addRect(rect, QtGui.QPen(QtCore.Qt.black, 0.5), 
                                            QtGui.QBrush(color))

            # Add labels
            font = QtGui.QFont()
            font.setPointSize(8)
            for idx, neuron in enumerate(neurons):
                # Column labels (top)
                text = self.heatmap_scene.addText(neuron, font)
                text.setPos(padding + idx * cell_size + cell_size/2 - text.boundingRect().width()/2, 
                        padding - 25)
                
                # Row labels (left)
                text = self.heatmap_scene.addText(neuron, font)
                text.setPos(padding - text.boundingRect().width() - 5, 
                        padding + idx * cell_size + cell_size/2 - text.boundingRect().height()/2)

            # Add legend
            self._draw_heatmap_legend(padding, len(neurons) * cell_size + padding + 20)

        except Exception as e:
            _LOG.warning('Handled exception', exc_info=True)
            print(f"Heatmap error: {str(e)}")
            error_text = self.heatmap_scene.addText("Heatmap unavailable")
            error_text.setPos(50, 50)

    def _draw_heatmap_legend(self, x, y):
        """Add color legend to heatmap"""
        legend_width = 200
        gradient = QtGui.QLinearGradient(0, 0, legend_width, 0)
        gradient.setColorAt(0, QtGui.QColor(255, 0, 0))  # Red
        gradient.setColorAt(0.5, QtGui.QColor(0, 0, 0))   # Black
        gradient.setColorAt(1, QtGui.QColor(0, 0, 255))  # Blue
        
        legend = QtWidgets.QGraphicsRectItem(x, y, legend_width, 20)
        legend.setBrush(QtGui.QBrush(gradient))
        self.heatmap_scene.addItem(legend)
        
        # Add labels - create text items first, then set their positions
        text_min = self.heatmap_scene.addText("-1.0")
        text_min.setPos(x, y + 20)
        
        text_zero = self.heatmap_scene.addText("0")
        text_zero.setPos(x + legend_width//2 - 10, y + 20)
        
        text_max = self.heatmap_scene.addText("+1.0")
        text_max.setPos(x + legend_width - 30, y + 20)

    def update_learning_statistics(self):
        """Update the statistics tab with comprehensive learning metrics"""
        # Get blacklisted neurons
        excluded_neurons = getattr(self.brain_widget, 'excluded_neurons', ['is_sick', 'is_eating', 'is_sleeping', 'pursuing_food', 'direction'])
        
        # Clear the stats layout
        while self.stats_box_layout.count():
            item = self.stats_box_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add styled stats
        def add_stat_box(title, content, bg_color="#f8f9fa", icon=None):
            box = QtWidgets.QGroupBox()
            box.setStyleSheet(f"""
                QGroupBox {{
                    background-color: {bg_color};
                    border-radius: 8px;
                    border: 1px solid #dee2e6;
                    margin-top: 15px;
                    padding: 10px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #495057;
                }}
            """)
            
            box_layout = QtWidgets.QVBoxLayout(box)
            
            # Add title with icon if provided
            title_layout = QtWidgets.QHBoxLayout()
            
            if icon:
                icon_label = QtWidgets.QLabel()
                icon_label.setPixmap(QtGui.QPixmap(icon).scaled(24, 24, QtCore.Qt.KeepAspectRatio))
                title_layout.addWidget(icon_label)
            
            title_label = QtWidgets.QLabel(title)
            title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #212529;")
            title_layout.addWidget(title_label)
            title_layout.addStretch()
            
            box_layout.addLayout(title_layout)
            
            # Add content
            content_widget = QtWidgets.QLabel(content)
            content_widget.setTextFormat(QtCore.Qt.RichText)
            content_widget.setWordWrap(True)
            content_widget.setStyleSheet("font-size: 13px; color: #343a40; margin: 5px;")
            box_layout.addWidget(content_widget)
            
            self.stats_box_layout.addWidget(box)
        
        # 1. Connection Statistics
        # Filter weights to exclude connections involving blacklisted neurons
        filtered_weights = {(src, dst): weight for (src, dst), weight in self.brain_widget.weights.items() 
                        if src not in excluded_neurons and dst not in excluded_neurons}
        
        positive_weights = sum(1 for w in filtered_weights.values() if w > 0)
        negative_weights = sum(1 for w in filtered_weights.values() if w < 0)
        avg_weight = sum(abs(w) for w in filtered_weights.values()) / max(1, len(filtered_weights))
        
        connection_stats = f"""
        <table style='width:100%; margin-top:5px;'>
            <tr>
                <td style='padding:3px;'><b>Total Connections:</b></td>
                <td style='padding:3px;'>{len(filtered_weights)}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Positive Connections:</b></td>
                <td style='padding:3px;'>{positive_weights} ({positive_weights/max(1,len(filtered_weights))*100:.1f}%)</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Negative Connections:</b></td>
                <td style='padding:3px;'>{negative_weights} ({negative_weights/max(1,len(filtered_weights))*100:.1f}%)</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Average Weight Strength:</b></td>
                <td style='padding:3px;'>{avg_weight:.3f}</td>
            </tr>
        </table>
        """
        add_stat_box("Connection Statistics", connection_stats, "#e3f2fd")
        
        # 2. Neuron Statistics
        from .brain_constants import neuron_row

        all_neurons = self.brain_widget.neuron_positions.keys()
        neurons = [n for n in all_neurons if n not in excluded_neurons]
        new_neurons = [n for n in neurons if n in self.brain_widget.neurogenesis_data.get('new_neurons', [])]

        # Counted by ROW, not as one lump. "Original Core Neurons" used to
        # report every neuron in the newborn layout, which since the motor
        # bank landed there meant a newborn was described as having nineteen
        # core neurons - and the whole design claim is eight.
        by_row = {'core': [], 'motor': [], 'sensor': [], 'social': [], None: []}
        for n in neurons:
            by_row[neuron_row(n)].append(n)

        neuron_stats = f"""
        <table style='width:100%; margin-top:5px;'>
            <tr>
                <td style='padding:3px;'><b>Learning-Eligible Neurons:</b></td>
                <td style='padding:3px;'>{len(neurons)}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Core Neurons (the original eight):</b></td>
                <td style='padding:3px;'>{len(by_row['core'])}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Motor Bank (actions):</b></td>
                <td style='padding:3px;'>{len(by_row['motor'])}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Sense Neurons:</b></td>
                <td style='padding:3px;'>{len(by_row['sensor'])}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Social Network (grown):</b></td>
                <td style='padding:3px;'>{len(by_row['social'])}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Neurons from Neurogenesis:</b></td>
                <td style='padding:3px;'>{len(new_neurons)}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Excluded System Neurons:</b></td>
                <td style='padding:3px;'>{len(excluded_neurons)}</td>
            </tr>
        </table>
        """
        add_stat_box("Neuron Statistics", neuron_stats, "#e8f5e9")
        
        # 3. Learning Parameters
        if hasattr(self.config, 'hebbian'):
            learning_rate = self.config.hebbian.get('base_learning_rate', 0.1)
            threshold = self.config.hebbian.get('threshold', 0.7)
            decay = self.config.hebbian.get('weight_decay', 0.01)
            
            learning_params = f"""
            <table style='width:100%; margin-top:5px;'>
                <tr>
                    <td style='padding:3px;'><b>Learning Rate:</b></td>
                    <td style='padding:3px;'>{learning_rate}</td>
                </tr>
                <tr>
                    <td style='padding:3px;'><b>Activation Threshold:</b></td>
                    <td style='padding:3px;'>{threshold}</td>
                </tr>
                <tr>
                    <td style='padding:3px;'><b>Weight Decay:</b></td>
                    <td style='padding:3px;'>{decay}</td>
                </tr>
                <tr>
                    <td style='padding:3px;'><b>Learning Interval:</b></td>
                    <td style='padding:3px;'>{self.config.hebbian.get('learning_interval', 30000)/1000} seconds</td>
                </tr>
            </table>
            """
            add_stat_box("Learning Parameters", learning_params, "#fff3e0")
        
        # 4. Strong Influence Neurons
        # Find neurons with strongest outgoing connections
        neuron_influence = {}
        for neuron in neurons:
            outgoing_sum = 0
            outgoing_count = 0
            for (src, dst), weight in filtered_weights.items():
                if src == neuron:
                    outgoing_sum += abs(weight)
                    outgoing_count += 1
            
            if outgoing_count > 0:
                neuron_influence[neuron] = outgoing_sum / outgoing_count
        
        top_influence = sorted(neuron_influence.items(), key=lambda x: x[1], reverse=True)[:5]
        
        influence_stats = "<table style='width:100%; margin-top:5px;'>"
        for neuron, influence in top_influence:
            influence_stats += f"""
            <tr>
                <td style='padding:3px;'><b>{neuron}</b></td>
                <td style='padding:3px;'>{influence:.3f}</td>
            </tr>
            """
        influence_stats += "</table>"
        
        add_stat_box("Top Influential Neurons", influence_stats, "#f3e5f5")
        
        # 5. Recently Created Neurons
        if self.brain_widget.neurogenesis_data.get('new_neurons'):
            new_neurons = [n for n in self.brain_widget.neurogenesis_data.get('new_neurons', []) 
                        if n not in excluded_neurons]
            last_time = self.brain_widget.neurogenesis_data.get('last_neuron_time', 0)
            time_ago = time.time() - last_time
            
            neurogenesis_stats = f"""
            <p>Most recent neuron created <b>{int(time_ago/60)} minutes</b> ago.</p>
            <p>Recent neurons (newest first):</p>
            <ul>
            """
            
            for neuron in reversed(new_neurons[-5:]):
                neurogenesis_stats += f"<li>{neuron}</li>"
            
            neurogenesis_stats += "</ul>"
            
            add_stat_box("Neurogenesis", neurogenesis_stats, "#ffebee")
        
        # Add a stretch to push all boxes to the top
        self.stats_box_layout.addStretch()

    def zoom_heatmap(self, value):
        """Zoom the heatmap view based on slider value"""
        scale = value / 100.0
        
        # Get current transform
        transform = QtGui.QTransform()
        transform.scale(scale, scale)
        
        # Apply new transform
        self.heatmap_view.setTransform(transform)

    def clear_learning_log(self):
        """Clear the activity log"""
        reply = QtWidgets.QMessageBox.question(
            self, "Clear Log", 
            "Are you sure you want to clear the learning activity log?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.activity_log.clear()
