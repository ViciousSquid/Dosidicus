import time
import math
# import os # No longer needed
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .brain_dialogs import RecentThoughtsDialog
from .display_scaling import DisplayScaling

class DecisionsTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.is_logging = False
        self.thought_log = []
        self.initialize_ui()

    def initialize_ui(self):
        """Initialize the decisions tab with a tabbed interface."""
        self.layout.setContentsMargins(10, 10, 10, 10)

        # Create Tab Widget
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)

        # Create and add tabs
        self.current_decision_tab_widget = self._create_current_decision_tab()
        self.tabs.addTab(self.current_decision_tab_widget, "Current Decision")

        self.factors_tab_widget = self._create_factors_tab()
        self.tabs.addTab(self.factors_tab_widget, "Decision Factors")

        self.log_tab_widget = self._create_thought_log_widget() # Reuse existing log
        self.tabs.addTab(self.log_tab_widget, "Decision Log")

        # Initial update
        self.update_visualization_with_placeholder()

    def _create_current_decision_tab(self):
        """Create the current decision visualization tab."""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setAlignment(QtCore.Qt.AlignTop)

        # --- Decision Output Section ---
        decision_section = QtWidgets.QGroupBox("Decision Output")
        decision_section.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #2ecc71; border-radius: 8px; margin-top: 1ex; background-color: #f8f9fa; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; background-color: #2ecc71; color: white; }"
        )
        decision_layout = QtWidgets.QVBoxLayout(decision_section)
        decision_layout.setSpacing(10)
        decision_layout.setContentsMargins(15, 15, 15, 15)

        # Decision Text
        self.decision_output = QtWidgets.QLabel("No Decision")
        self.decision_output.setStyleSheet(f"font-size: {DisplayScaling.font_size(28)}px; font-weight: bold; color: #2c3e50;")
        self.decision_output.setAlignment(QtCore.Qt.AlignCenter)
        decision_layout.addWidget(self.decision_output)

        layout.addWidget(decision_section)

        # --- Explanation Section ---
        explanation_group = QtWidgets.QGroupBox("Why did the Squid do that?")
        explanation_group.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 1px solid #3498db; border-radius: 8px; margin-top: 1ex; background-color: #f8f9fa; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; background-color: #3498db; color: white; }"
        )
        explanation_layout = QtWidgets.QVBoxLayout(explanation_group)
        self.decision_explanation = QtWidgets.QTextEdit()
        self.decision_explanation.setReadOnly(True)
        self.decision_explanation.setStyleSheet("background-color: #ffffff; border: 1px solid #ddd; padding: 10px; font-size: 14px;")
        explanation_layout.addWidget(self.decision_explanation)

        layout.addWidget(explanation_group)
        layout.setStretchFactor(explanation_group, 1) # Give more space to explanation

        return container

    def _create_factors_tab(self):
        """Create the decision factors visualization tab."""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)

        # Possible Decisions Table
        decisions_group = QtWidgets.QGroupBox("⚡ Possible Actions & Weights")
        decisions_layout = QtWidgets.QVBoxLayout(decisions_group)
        self.factors_table = QtWidgets.QTableWidget()
        self.factors_table.setColumnCount(4)
        self.factors_table.setHorizontalHeaderLabels(["Action", "Base Weight", "Personality Adj.", "Random Factor"])
        self.factors_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.factors_table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.factors_table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.factors_table.setAlternatingRowColors(True)
        decisions_layout.addWidget(self.factors_table)
        layout.addWidget(decisions_group)

        # Influencing Factors Splitter
        factors_splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)

        # Inputs Group
        inputs_group = QtWidgets.QGroupBox("🧠 Key Inputs")
        inputs_layout = QtWidgets.QVBoxLayout(inputs_group)
        self.inputs_text = QtWidgets.QTextEdit()
        self.inputs_text.setReadOnly(True)
        inputs_layout.addWidget(self.inputs_text)
        factors_splitter.addWidget(inputs_group)

        # Personality Group
        personality_group = QtWidgets.QGroupBox("🎭 Personality Influence")
        personality_layout = QtWidgets.QVBoxLayout(personality_group)
        self.personality_text = QtWidgets.QTextEdit()
        self.personality_text.setReadOnly(True)
        personality_layout.addWidget(self.personality_text)
        factors_splitter.addWidget(personality_group)

        # Memories Group
        memories_group = QtWidgets.QGroupBox("📚 Memory Influence")
        memories_layout = QtWidgets.QVBoxLayout(memories_group)
        self.memories_text = QtWidgets.QTextEdit()
        self.memories_text.setReadOnly(True)
        memories_layout.addWidget(self.memories_text)
        factors_splitter.addWidget(memories_group)

        factors_splitter.setSizes([300, 250, 250]) # Adjust initial sizes
        layout.addWidget(factors_splitter)
        layout.setStretchFactor(decisions_group, 1)
        layout.setStretchFactor(factors_splitter, 1)

        return container

    def _create_thought_log_widget(self):
        """Create the thought log tab (reusing existing structure)."""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)

        header_layout = QtWidgets.QHBoxLayout()
        title = QtWidgets.QLabel("Decision Log")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(title)
        header_layout.addStretch()

        self.log_filter = QtWidgets.QComboBox()
        self.log_filter.addItem("All Decisions")
        self.log_filter.addItems(["Exploring", "Eating", "Organizing", "Approaching", "Throwing", "Avoiding"])
        self.log_filter.setFixedWidth(150)
        self.log_filter.currentIndexChanged.connect(self.filter_thought_log)
        header_layout.addWidget(QtWidgets.QLabel("Filter:"))
        header_layout.addWidget(self.log_filter)

        self.logging_button = QtWidgets.QPushButton("Start Logging")
        self.logging_button.setCheckable(True)
        self.logging_button.setStyleSheet(
            "QPushButton { background-color: #2ecc71; color: white; border: none; border-radius: 5px; padding: 5px 10px; font-weight: bold; }"
            "QPushButton:checked { background-color: #e74c3c; }"
        )
        self.logging_button.clicked.connect(self.toggle_logging)
        header_layout.addWidget(self.logging_button)

        self.view_logs_button = QtWidgets.QPushButton("View History")
        self.view_logs_button.setStyleSheet("background-color: #3498db; color: white; border: none; border-radius: 5px; padding: 5px 10px;")
        self.view_logs_button.clicked.connect(self.view_thought_logs)
        header_layout.addWidget(self.view_logs_button)
        layout.addLayout(header_layout)

        self.thought_log_text = QtWidgets.QTextEdit()
        self.thought_log_text.setReadOnly(True)
        self.thought_log_text.setStyleSheet(
            "QTextEdit { background-color: #f8f9fa; border: 1px solid #bdc3c7; border-radius: 5px; padding: 10px; font-family: Arial, sans-serif; }"
        )
        layout.addWidget(self.thought_log_text)
        return container

    def update_visualization_with_placeholder(self):
        """Initialize tabs with placeholder content."""
        # Current Decision Tab
        self.decision_output.setText("Awaiting Decision...")
        self.decision_explanation.setHtml("<p><i>Waiting for the squid to make its next move...</i></p>")

        # Factors Tab
        self.factors_table.setRowCount(0)
        self.inputs_text.setHtml("<p><i>Inputs will appear here.</i></p>")
        self.personality_text.setHtml("<p><i>Personality influence will appear here.</i></p>")
        self.memories_text.setHtml("<p><i>Memory influence will appear here.</i></p>")

        # Log Tab
        self.thought_log_text.setHtml(
            "<div style='color: #7f8c8d; text-align: center; padding: 50px;'>"
            "<p>Start logging to view the squid's decision process.</p>"
            "<p>Click the 'Start Logging' button to begin recording decisions.</p>"
            "</div>"
        )

    def update_from_brain_state(self, state):
        """Update decision visualization based on brain state."""
        if hasattr(self.tamagotchi_logic, 'get_decision_data'):
            decision_data = self.tamagotchi_logic.get_decision_data()
            if decision_data: # Ensure data is not None
                self.update_thought_process(decision_data)

    def update_thought_process(self, decision_data):
        """Update all visualizations with new decision data."""
        inputs = decision_data.get('inputs', {})
        decision = decision_data.get('final_decision', 'exploring')
        confidence = decision_data.get('confidence', 0.5)
        weights = decision_data.get('weights', {})
        adjusted_weights = decision_data.get('adjusted_weights', {})
        randomness = decision_data.get('randomness', {})
        active_memories = decision_data.get('active_memories', [])

        # 1. Update Current Decision Tab
        self._update_current_decision_tab(decision, confidence,
                                        self._generate_explanation(decision, weights, adjusted_weights,
                                                               randomness, active_memories, inputs))

        # 2. Update Factors Tab
        self._update_factors_tab(decision_data)

        # 3. Add to thought log if logging is enabled
        if self.is_logging:
            self.add_to_thought_log(decision_data)

    def _update_current_decision_tab(self, decision, confidence, explanation):
        """Update the current decision display tab."""
        self.decision_output.setText(decision.capitalize())
        self.decision_explanation.setHtml(explanation)

    def _update_factors_tab(self, decision_data):
        """Update the decision factors tab with new data."""
        weights = decision_data.get('weights', {})
        adjusted_weights = decision_data.get('adjusted_weights', {})
        randomness = decision_data.get('randomness', {})
        inputs = decision_data.get('inputs', {})
        memories = decision_data.get('active_memories', [])
        final_decision = decision_data.get('final_decision')
        personality = "Unknown"
        if self.tamagotchi_logic and self.tamagotchi_logic.squid:
            personality = self.tamagotchi_logic.squid.personality.value.capitalize()

        # --- Update Table ---
        self.factors_table.setRowCount(0) # Clear previous
        all_actions = set(weights.keys()) | set(adjusted_weights.keys())
        sorted_actions = sorted(list(all_actions), key=lambda x: adjusted_weights.get(x, 0), reverse=True)
        self.factors_table.setRowCount(len(sorted_actions))

        for i, action in enumerate(sorted_actions):
            base = weights.get(action, 0)
            adj = adjusted_weights.get(action, base) # Use base if no adjustment
            rand = randomness.get(action, 1.0)

            item_action = QtWidgets.QTableWidgetItem(action.capitalize())
            item_base = QtWidgets.QTableWidgetItem(f"{base:.3f}")
            item_adj = QtWidgets.QTableWidgetItem(f"{adj:.3f}")
            item_rand = QtWidgets.QTableWidgetItem(f"x{rand:.2f}")

            self.factors_table.setItem(i, 0, item_action)
            self.factors_table.setItem(i, 1, item_base)
            self.factors_table.setItem(i, 2, item_adj)
            self.factors_table.setItem(i, 3, item_rand)

            if action == final_decision:
                font = item_action.font()
                font.setBold(True)
                for j in range(4):
                    item = self.factors_table.item(i, j)
                    item.setBackground(QtGui.QColor("#d4edda")) # Highlight green
                    item.setFont(font)

            # Color code adjustments
            if abs(adj - base) > 0.01:
                color = QtGui.QColor("green") if adj > base else QtGui.QColor("red")
                self.factors_table.item(i, 2).setForeground(color)


        # --- Update Inputs Text (HTML) ---
        inputs_html = """
        <style> ul { list-style-type: '⚪'; padding-left: 20px; } li { margin-bottom: 5px; } </style>
        <p>The squid's current feelings and perceptions:</p><ul>
        """
        for k, v in sorted(inputs.items()):
            if isinstance(v, (int, float)):
                inputs_html += f"<li><b>{k.capitalize()}:</b> {v:.1f}</li>"
            elif isinstance(v, bool):
                inputs_html += f"<li><b>{k.capitalize()}:</b> {'<span style=\"color:green;\">Yes</span>' if v else '<span style=\"color:red;\">No</span>'}</li>"
            else:
                inputs_html += f"<li><b>{k.capitalize()}:</b> {v}</li>"
        inputs_html += "</ul>"
        self.inputs_text.setHtml(inputs_html)

        # --- Update Personality Text (HTML) ---
        personality_html = f"<h3>Current Trait: {personality}</h3>"
        personality_html += "<p>This trait nudges the squid towards certain behaviors:</p><ul>"
        changes = False
        for action, base in weights.items():
            adj = adjusted_weights.get(action, base)
            if abs(adj - base) > 0.01:
                diff = adj - base
                color = "green" if diff > 0 else "red"
                direction = "Increased" if diff > 0 else "Decreased"
                personality_html += f"<li><b>{action.capitalize()}:</b> {direction} by <span style='color:{color}; font-weight:bold;'>{abs(diff):.2f}</span></li>"
                changes = True
        if not changes:
            personality_html += "<li>No significant influence this cycle.</li>"
        personality_html += "</ul>"
        self.personality_text.setHtml(personality_html)

        # --- Update Memories Text (HTML) ---
        memories_html = "<p>Recent events shaping the decision:</p><ul>"
        if memories:
            for mem in memories:
                memories_html += f"<li>{mem}</li>"
        else:
            memories_html += "<li>No significant memories influencing this decision.</li>"
        memories_html += "</ul>"
        self.memories_text.setHtml(memories_html)

    def _generate_explanation(self, decision, weights, adjusted_weights, randomness, memories, inputs):
        """Generate rich HTML explanation for the decision."""
        html = """
        <style>
            body { font-family: Arial, sans-serif; font-size: 14px; line-height: 1.5; }
            h4 { color: #2c3e50; border-bottom: 1px solid #eee; padding-bottom: 3px; margin-top: 15px; margin-bottom: 5px; }
            ul { list-style-type: none; padding-left: 0; }
            li { margin-bottom: 6px; padding: 6px; border-left: 3px solid; border-radius: 3px; }
            .base { border-color: #3498db; background-color: #eaf5fd; }
            .personality { border-color: #9b59b6; background-color: #f5eef8; }
            .random { border-color: #f39c12; background-color: #fef8e7; }
            .input { border-color: #16a085; background-color: #e8f6f3; }
            .memory { border-color: #e67e22; background-color: #fbeee4; }
            .competing { border-color: #c0392b; background-color: #faeaea; }
            .final { border-color: #27ae60; background-color: #e9f7ef; font-weight: bold;}
            b { color: #34495e; }
        </style>
        """
        html += f"<p>The squid chose to <b>{decision.capitalize()}</b>. Here's a breakdown of why:</p>"

        decision_weight = adjusted_weights.get(decision, 0)
        base = weights.get(decision, 0)
        rand = randomness.get(decision, 1.0)
        final_score = decision_weight * rand # Approximate final score

        html += "<h4>📊 Weight Calculation:</h4><ul>"
        html += f"<li class='base'><b>Base Weight:</b> {base:.2f} (Initial urge based on core needs/desires)</li>"
        if abs(decision_weight - base) > 0.01:
            html += f"<li class='personality'><b>Personality Nudge:</b> {(decision_weight - base):+.2f} (How its traits influenced the urge)</li>"
        html += f"<li class='random'><b>Randomness Factor:</b> x{rand:.2f} (A touch of unpredictability!)</li>"
        html += f"<li class='final'><b>Resulting Likelihood:</b> ~{final_score:.2f}</li>"
        html += "</ul>"

        html += "<h4>🧠 Key Influencing Inputs:</h4><ul>"
        top_inputs = sorted(
            [(k, v) for k, v in inputs.items() if (isinstance(v, (int, float)) and v > 50) or (isinstance(v, bool) and v)],
            key=lambda x: abs(x[1]) if isinstance(x[1], (int, float)) else 0, reverse=True
        )[:3]
        if top_inputs:
            for k, v_val in top_inputs:
                formatted_v_val = ""
                if isinstance(v_val, (int, float)):
                    formatted_v_val = f"{v_val:.1f}"
                elif isinstance(v_val, bool):
                    formatted_v_val = 'Yes' if v_val else 'No'
                else:
                    formatted_v_val = str(v_val)
                html += f"<li class='input'><b>{k.capitalize()}:</b> {formatted_v_val}</li>"
        else:
            html += "<li class='input'>No single input strongly dominated.</li>"
        html += "</ul>"

        if memories:
            html += "<h4>📚 Memory Influence:</h4><ul>"
            for mem in memories:
                html += f"<li class='memory'>{mem[:80]}...</li>" # Show first 80 chars
            html += "</ul>"

        competing = sorted(
            [(k, v * randomness.get(k, 1.0)) for k, v in adjusted_weights.items() if k != decision and v > 0],
            key=lambda x: x[1], reverse=True
        )
        if competing:
            html += "<h4>📉 Top Competing Decisions:</h4><ul>"
            for action, weight_val in competing[:2]: # Renamed 'weight' to 'weight_val' to avoid conflict
                html += f"<li class='competing'><b>{action.capitalize()}:</b> {weight_val:.2f}</li>"
            html += "</ul>"

        return html

    def toggle_logging(self):
        """Toggle decision logging on/off."""
        self.is_logging = not self.is_logging
        if self.is_logging:
            self.logging_button.setText("Stop Logging")
            self.thought_log_text.clear()
            self.thought_log_text.append("<b>--- Logging started ---</b>")
        else:
            self.logging_button.setText("Start Logging")
            self.thought_log_text.append("<b>--- Logging stopped ---</b>")
        self.logging_button.setChecked(self.is_logging)

    def add_to_thought_log(self, decision_data):
        """Add the current decision process to the thought log."""
        if not self.is_logging:
            return

        timestamp = time.strftime("%H:%M:%S")
        decision = decision_data.get('final_decision', 'unknown')
        confidence = decision_data.get('confidence', 0.0)
        adjusted_weights = decision_data.get('adjusted_weights', {})

        color_map = {
            "exploring": "#3498db", "eating": "#2ecc71", "moving_to_food": "#2ecc71",
            "approaching_rock": "#9b59b6", "throwing_rock": "#e67e22",
            "avoiding_threat": "#e74c3c", "organizing": "#f1c40f", "sleeping": "#34495e",
            "approaching_poop": "#8B4513", "throwing_poop": "#8B4513"
        }
        decision_color = color_map.get(decision.lower().replace(" ", "_"), "#7f8c8d")

        competing = sorted([(k, v) for k, v in adjusted_weights.items() if k != decision and v > 0], key=lambda x: x[1], reverse=True)
        comp_text = ", ".join([f"{a.capitalize()} ({w:.2f})" for a, w in competing[:2]])

        entry = f"""
        <div style="margin: 5px 0; padding: 8px; border-left: 4px solid {decision_color};
                   background-color: rgba({', '.join(str(int(c)) for c in QtGui.QColor(decision_color).getRgb()[:-1])}, 0.1);">
            <div style="display: flex; justify-content: space-between;">
                <span style="font-weight: bold; color: {decision_color};">{decision.capitalize()}</span>
                <span style="color: #7f8c8d;">{timestamp}</span>
            </div>
            <div style="margin-top: 3px; font-size: 0.9em; color: #555;">
                Confidence: {int(confidence * 100)}% | Competing: {comp_text if comp_text else 'None'}
            </div>
        </div>
        """
        # Ensure only new entries are added to the list, not during filtering
        if not hasattr(self, '_filtering_log') or not self._filtering_log:
             self.thought_log.append({'timestamp': timestamp, 'decision': decision, 'data': decision_data})

        self.thought_log_text.append(entry)
        self.thought_log_text.verticalScrollBar().setValue(self.thought_log_text.verticalScrollBar().maximum())


    def view_thought_logs(self):
        """Open a window to view captured decision logs."""
        if not self.thought_log:
            QtWidgets.QMessageBox.information(self, "No Logs", "Start logging to capture decisions.")
            return
        log_viewer = RecentThoughtsDialog(self.thought_log, self)
        log_viewer.exec_()

    def filter_thought_log(self):
        """Filter the thought log based on selected decision type."""
        filter_text = self.log_filter.currentText().lower()
        self.thought_log_text.clear()
        self._filtering_log = True # Set flag to prevent re-adding to list

        start_message = "<b>--- Logging started ---</b>"
        stop_message = "<b>--- Logging stopped ---</b>"

        # Always add the start message if logging is active or has been active
        if self.thought_log or self.is_logging:
            self.thought_log_text.append(start_message)

        # Iterate through the stored logs and add matching ones
        for log_entry in self.thought_log:
            decision = log_entry['data'].get('final_decision', '').lower()
            if filter_text == "all decisions" or filter_text in decision:
                # Call a modified version or just format and append
                timestamp = log_entry['timestamp']
                decision_val = log_entry['decision']
                decision_data = log_entry['data']
                confidence = decision_data.get('confidence', 0.0)
                adjusted_weights = decision_data.get('adjusted_weights', {})

                color_map = {
                    "exploring": "#3498db", "eating": "#2ecc71", "moving_to_food": "#2ecc71",
                    "approaching_rock": "#9b59b6", "throwing_rock": "#e67e22",
                    "avoiding_threat": "#e74c3c", "organizing": "#f1c40f", "sleeping": "#34495e",
                    "approaching_poop": "#8B4513", "throwing_poop": "#8B4513"
                }
                decision_color = color_map.get(decision_val.lower().replace(" ", "_"), "#7f8c8d")
                competing = sorted([(k, v) for k, v in adjusted_weights.items() if k != decision_val and v > 0], key=lambda x: x[1], reverse=True)
                comp_text = ", ".join([f"{a.capitalize()} ({w:.2f})" for a, w in competing[:2]])

                entry = f"""
                <div style="margin: 5px 0; padding: 8px; border-left: 4px solid {decision_color};
                           background-color: rgba({', '.join(str(int(c)) for c in QtGui.QColor(decision_color).getRgb()[:-1])}, 0.1);">
                    <div style="display: flex; justify-content: space-between;">
                        <span style="font-weight: bold; color: {decision_color};">{decision_val.capitalize()}</span>
                        <span style="color: #7f8c8d;">{timestamp}</span>
                    </div>
                    <div style="margin-top: 3px; font-size: 0.9em; color: #555;">
                        Confidence: {int(confidence * 100)}% | Competing: {comp_text if comp_text else 'None'}
                    </div>
                </div>
                """
                self.thought_log_text.append(entry)


        # Add the stop message if logging is not active
        if not self.is_logging and self.thought_log:
            self.thought_log_text.append(stop_message)

        self._filtering_log = False # Reset flag
        self.thought_log_text.verticalScrollBar().setValue(self.thought_log_text.verticalScrollBar().maximum())


    def _clear_layout(self, layout):
        """Utility to clear all widgets from a layout."""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()