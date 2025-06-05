import time
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QLabel, QTableWidget,
                             QTableWidgetItem, QHeaderView, QGroupBox)
from PyQt5.QtCore import Qt

from .brain_base_tab import BrainBaseTab

class NeurogenesisTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        # self.brain_widget is now inherited and correctly set by BrainBaseTab's __init__
        # self.tamagotchi_logic, self.config, self.debug_mode, and self.parent are also set by BrainBaseTab
        self.setWindowTitle("Neurogenesis & Neural Network") # This is specific to NeurogenesisTab
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        self.setLayout(main_layout)

        # Live Tracker Sub-Tab
        live_tracker_content = self._create_live_tracker_sub_tab_content()
        main_layout.addWidget(live_tracker_content)
        
        self.update_tab_data() # Initial population

    def _create_live_tracker_sub_tab_content(self):
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setAlignment(Qt.AlignTop)

        # --- Counters and Thresholds Group ---
        counters_thresholds_group = QGroupBox("Live Counters & Thresholds")
        ct_layout = QVBoxLayout()
        counters_thresholds_group.setLayout(ct_layout)

        self.novelty_counter_label = QLabel("Novelty Counter: N/A")
        ct_layout.addWidget(self.novelty_counter_label)
        self.stress_counter_label = QLabel("Stress Counter: N/A")
        ct_layout.addWidget(self.stress_counter_label)
        self.reward_counter_label = QLabel("Reward Counter: N/A")
        ct_layout.addWidget(self.reward_counter_label)

        ct_layout.addSpacing(10) # Spacer

        self.novelty_threshold_label = QLabel("Novelty Threshold: N/A")
        ct_layout.addWidget(self.novelty_threshold_label)
        self.stress_threshold_label = QLabel("Stress Threshold: N/A")
        ct_layout.addWidget(self.stress_threshold_label)
        self.reward_threshold_label = QLabel("Reward Threshold: N/A")
        ct_layout.addWidget(self.reward_threshold_label)
        
        main_layout.addWidget(counters_thresholds_group)

        # --- Status and Prediction Group ---
        status_group = QGroupBox("Status & Prediction")
        status_layout = QVBoxLayout()
        status_group.setLayout(status_layout)

        self.neurogenesis_cooldown_label = QLabel("Neurogenesis Cooldown: N/A")
        status_layout.addWidget(self.neurogenesis_cooldown_label)

        self.next_neuron_prediction_label = QLabel("Next Neuron Type: Calculating...")
        self.next_neuron_prediction_label.setWordWrap(True)
        status_layout.addWidget(self.next_neuron_prediction_label)
        
        main_layout.addWidget(status_group)

        # --- Recently Created Neurons Group ---
        recent_neurons_group = QGroupBox("Recently Created Neurons")
        rn_layout = QVBoxLayout()
        recent_neurons_group.setLayout(rn_layout)

        self.recent_neurons_table = QTableWidget()
        self.recent_neurons_table.setColumnCount(5)
        self.recent_neurons_table.setHorizontalHeaderLabels([
            "Name", "Created At", "Trigger", "Trigger Value", "Associated State"
        ])
        self.recent_neurons_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.recent_neurons_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.recent_neurons_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.recent_neurons_table.setMinimumHeight(150) # Adjust as needed
        rn_layout.addWidget(self.recent_neurons_table)

        main_layout.addWidget(recent_neurons_group)

        return widget

    def update_tab_data(self):
        # Guard clause from your provided file
        if not self.brain_widget or not hasattr(self.brain_widget, 'neurogenesis_data'):
            self.novelty_counter_label.setText("Novelty Counter: N/A (System Error)")
            self.stress_counter_label.setText("Stress Counter: N/A (System Error)")
            self.reward_counter_label.setText("Reward Counter: N/A (System Error)")
            self.novelty_threshold_label.setText("Novelty Threshold: N/A (System Error)")
            self.stress_threshold_label.setText("Stress Threshold: N/A (System Error)")
            self.reward_threshold_label.setText("Reward Threshold: N/A (System Error)")
            self.neurogenesis_cooldown_label.setText("Neurogenesis Cooldown: N/A (System Error)")
            if hasattr(self, 'next_neuron_prediction_label'):
                self.next_neuron_prediction_label.setText("Next Neuron Type: Data unavailable (System Error)")
            if hasattr(self, 'recent_neurons_table'):
                self.recent_neurons_table.setRowCount(0)
            return

        neuro_data = self.brain_widget.neurogenesis_data

        # Update Counters (from your provided file, assumes numeric values in neuro_data)
        self.novelty_counter_label.setText(f"Novelty Counter: {neuro_data.get('novelty_counter', 0):.2f}")
        self.stress_counter_label.setText(f"Stress Counter: {neuro_data.get('stress_counter', 0):.2f}")
        self.reward_counter_label.setText(f"Reward Counter: {neuro_data.get('reward_counter', 0):.2f}")

        # Update Thresholds
        novelty_thresh, stress_thresh, reward_thresh = None, None, None
        if hasattr(self.brain_widget, 'get_adjusted_threshold'):
            # Corrected calls to get_adjusted_threshold
            novelty_thresh = self.brain_widget.get_adjusted_threshold("NOVELTY_NEURON_THRESHOLD", "novelty_detection")
            stress_thresh = self.brain_widget.get_adjusted_threshold('stress', "threat_response")
            reward_thresh = self.brain_widget.get_adjusted_threshold('reward', "learning_signal")

            # Robust handling for displaying novelty_thresh
            novelty_display_text = "Novelty Threshold: "
            if isinstance(novelty_thresh, (int, float)):
                novelty_display_text += f"{novelty_thresh:.2f}"
            elif isinstance(novelty_thresh, str):
                novelty_display_text += novelty_thresh  # Display string directly
            else:  # Handles None or other unexpected types
                novelty_display_text += "N/A (Calculation Error)"
            self.novelty_threshold_label.setText(novelty_display_text)

            # Robust handling for displaying stress_thresh
            stress_display_text = "Stress Threshold: "
            if isinstance(stress_thresh, (int, float)):
                stress_display_text += f"{stress_thresh:.2f}"
            elif isinstance(stress_thresh, str):
                stress_display_text += stress_thresh
            else:  # Handles None or other unexpected types
                stress_display_text += "N/A (Calculation Error)"
            self.stress_threshold_label.setText(stress_display_text)

            # Robust handling for displaying reward_thresh
            reward_display_text = "Reward Threshold: "
            if isinstance(reward_thresh, (int, float)):
                reward_display_text += f"{reward_thresh:.2f}"
            elif isinstance(reward_thresh, str):
                reward_display_text += reward_thresh
            else:  # Handles None or other unexpected types
                reward_display_text += "N/A (Calculation Error)"
            self.reward_threshold_label.setText(reward_display_text)
        else:
            self.novelty_threshold_label.setText("Novelty Threshold: N/A (method missing)")
            self.stress_threshold_label.setText("Stress Threshold: N/A (method missing)")
            self.reward_threshold_label.setText("Reward Threshold: N/A (method missing)")

        # Update Cooldown Timer
        cooldown_remaining = 0
        cooldown_active = False
        
        neuro_config = {} # Initialize an empty dict for neurogenesis config
        if hasattr(self.brain_widget, 'config') and \
           self.brain_widget.config is not None and \
           hasattr(self.brain_widget.config, 'get_neurogenesis_config'):
            neuro_config = self.brain_widget.config.get_neurogenesis_config()

        if hasattr(self.brain_widget, 'get_neurogenesis_cooldown_remaining') and neuro_config:
            cooldown_remaining = self.brain_widget.get_neurogenesis_cooldown_remaining()
            if cooldown_remaining > 0:
                self.neurogenesis_cooldown_label.setText(f"Neurogenesis Cooldown: {int(cooldown_remaining)}s remaining")
                cooldown_active = True
            elif neuro_config.get("enabled", False):
                 current_neuron_count = len(getattr(self.brain_widget, 'neuron_positions', {})) - \
                                        len(getattr(self.brain_widget, 'excluded_neurons', []))
                 
                 pruning_enabled = False # Default
                 if self.brain_widget.squid_instance and \
                    hasattr(self.brain_widget.squid_instance, 'neurogenesis_manager'):
                    # Assuming neurogenesis_manager might have a pruning_enabled attribute or method
                    pruning_enabled = getattr(self.brain_widget.squid_instance.neurogenesis_manager, 'pruning_enabled', False)
                 elif hasattr(self.brain_widget, 'pruning_enabled'): # Fallback to brain_widget if squid_instance not available
                    pruning_enabled = getattr(self.brain_widget, 'pruning_enabled', False)

                 max_neurons_limit = neuro_config.get('max_neurons', 32)

                 if current_neuron_count >= max_neurons_limit and pruning_enabled:
                     self.neurogenesis_cooldown_label.setText("Neurogenesis: Max neurons (pruning active)")
                 else:
                    self.neurogenesis_cooldown_label.setText("Neurogenesis: Ready to trigger")
            else: # Neurogenesis disabled in config
                self.neurogenesis_cooldown_label.setText("Neurogenesis: Disabled")
        else: 
            self.neurogenesis_cooldown_label.setText("Neurogenesis Cooldown: N/A (config data missing)")

        # PREDICTION LOGIC
        if hasattr(self, 'next_neuron_prediction_label'):
            prediction_text = "<b>Next Neuron Prediction:</b> "
            if cooldown_active:
                prediction_text += f"Undetermined (Cooldown: {int(cooldown_remaining)}s)"
            elif not neuro_config.get("enabled", False): # Check the fetched neuro_config
                prediction_text += "Undetermined (Neurogenesis Disabled)"
            # Check if all thresholds are valid numbers before using them in calculations
            elif not all(isinstance(t, (int, float)) for t in [novelty_thresh, stress_thresh, reward_thresh]):
                 prediction_text += "Data unavailable for prediction (thresholds non-numeric or missing)"
            else:
                # All thresholds are numbers, proceed with calculations
                urgency_novelty = neuro_data.get('novelty_counter', 0) - novelty_thresh
                urgency_stress = neuro_data.get('stress_counter', 0) - stress_thresh
                urgency_reward = neuro_data.get('reward_counter', 0) - reward_thresh

                candidates = []
                if urgency_novelty >= 0: candidates.append({'type': 'Novelty', 'urgency': urgency_novelty, 'counter': neuro_data.get('novelty_counter',0)})
                if urgency_stress >= 0: candidates.append({'type': 'Stress', 'urgency': urgency_stress, 'counter': neuro_data.get('stress_counter',0)})
                if urgency_reward >= 0: candidates.append({'type': 'Reward', 'urgency': urgency_reward, 'counter': neuro_data.get('reward_counter',0)})
                
                if not candidates: 
                    distances = [
                        ('Novelty', novelty_thresh - neuro_data.get('novelty_counter', 0), neuro_data.get('novelty_counter',0)),
                        ('Stress', stress_thresh - neuro_data.get('stress_counter', 0), neuro_data.get('stress_counter',0)),
                        ('Reward', reward_thresh - neuro_data.get('reward_counter', 0), neuro_data.get('reward_counter',0))
                    ]
                    valid_distances = [d for d in distances if d[1] >=0]
                    if valid_distances:
                        valid_distances.sort(key=lambda x: (x[1], -x[2])) 
                        closest_type = valid_distances[0][0]
                        prediction_text += f"Likely {closest_type} (approaching threshold)"
                    else: 
                        all_counters_far = all(d[1] > (novelty_thresh * 0.5 if d[0] == 'Novelty' else (stress_thresh * 0.5 if d[0] == 'Stress' else reward_thresh * 0.5)) for d in distances) # Adjusted heuristic
                        if all_counters_far :
                             prediction_text += "All counters far from thresholds."
                        else: 
                             prediction_text += "Evaluating conditions..."
                else: 
                    candidates.sort(key=lambda x: (x['urgency'], x['counter']), reverse=True)
                    last_type = getattr(self.brain_widget, 'last_neurogenesis_type', None) # This is from neuro_data in BrainWidget
                    if len(candidates) == 1:
                        prediction_text += f"{candidates[0]['type']} (Exceeds threshold)"
                    else: 
                        primary_candidate = candidates[0]
                        if primary_candidate['type'].lower() == last_type:
                            alternatives = [c for c in candidates[1:] if c['type'].lower() != last_type]
                            if alternatives:
                                if alternatives[0]['urgency'] > primary_candidate['urgency'] * 0.75 or \
                                   alternatives[0]['counter'] > primary_candidate['counter'] * 0.75 :
                                    prediction_text += f"{alternatives[0]['type']} (Prioritized over repeating {primary_candidate['type']})"
                                else:
                                    prediction_text += f"{primary_candidate['type']} (Highest urgency)"
                            else: 
                                prediction_text += f"{primary_candidate['type']} (Highest urgency)"
                        else: 
                            prediction_text += f"{primary_candidate['type']} (Highest urgency)"
                        other_actives = [c['type'] for c in candidates if c['type'] != prediction_text.split(" ")[1].strip(',') and c['type'] not in prediction_text] # Ensure correct parsing
                        if other_actives:
                             prediction_text += f", also watching {', '.join(other_actives)}."
            self.next_neuron_prediction_label.setText(prediction_text)

        # Update Recently Created Neurons Table (structure from your provided file)
        if hasattr(self, 'recent_neurons_table'):
            new_neurons_details_dict = neuro_data.get('new_neurons_details', {})
            new_neurons_details_list = []

            for name, details_data in new_neurons_details_dict.items():
                if isinstance(details_data, dict):
                    entry = details_data.copy()
                    entry['name'] = name 
                    new_neurons_details_list.append(entry)
                else:
                    # It's good practice to log this, but print might go to console
                    # self.log_message(f"Details for neuron '{name}' is not a dictionary: {details_data}", level='warning')
                    print(f"Warning: Details for neuron '{name}' is not a dictionary: {details_data}")


            new_neurons_details_list.sort(key=lambda x: x.get('created_at', 0), reverse=True)

            self.recent_neurons_table.setRowCount(len(new_neurons_details_list))
            for row, details in enumerate(new_neurons_details_list):
                self.recent_neurons_table.setItem(row, 0, QTableWidgetItem(details.get('name', 'N/A')))
                
                created_at_timestamp = details.get('created_at')
                time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_at_timestamp)) if created_at_timestamp else 'N/A'
                self.recent_neurons_table.setItem(row, 1, QTableWidgetItem(time_str))
                
                self.recent_neurons_table.setItem(row, 2, QTableWidgetItem(str(details.get('trigger_type', 'N/A')).capitalize()))
                
                trigger_val = details.get('trigger_value_at_creation')
                trigger_val_str = f"{trigger_val:.2f}" if isinstance(trigger_val, float) else str(trigger_val if trigger_val is not None else 'N/A')
                self.recent_neurons_table.setItem(row, 3, QTableWidgetItem(trigger_val_str))
                
                assoc_state = details.get('associated_state_snapshot', {})
                assoc_state_str = ", ".join([f"{k.capitalize()}: {v}" for k,v in assoc_state.items() if v is not None]) if isinstance(assoc_state, dict) and assoc_state else 'N/A'
                self.recent_neurons_table.setItem(row, 4, QTableWidgetItem(assoc_state_str))

    def on_tab_focus(self):
        # print("Neurogenesis Tab focused")
        self.update_tab_data()

    def on_tab_blur(self):
        # print("Neurogenesis Tab blurred")
        pass