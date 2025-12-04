# src/brain_decisions_tab.py

from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .display_scaling import DisplayScaling

class DecisionsTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.initialize_ui()

    def initialize_ui(self):
        """
        Initializes the UI with a persistent, non-flickering layout for the decision path
        and a fixed bar at the bottom for the final action.
        """
        self.layout.setContentsMargins(DisplayScaling.scale(15), DisplayScaling.scale(15), DisplayScaling.scale(15), DisplayScaling.scale(15))
        self.layout.setSpacing(DisplayScaling.scale(10))

        # Main container
        main_container = QtWidgets.QWidget()
        main_container.setObjectName("mainContainer")
        main_container.setStyleSheet("background-color: #f8f9fa; border-radius: 10px;")
        main_layout = QtWidgets.QVBoxLayout(main_container)
        main_layout.setContentsMargins(DisplayScaling.scale(10), DisplayScaling.scale(10), DisplayScaling.scale(10), DisplayScaling.scale(10))
        self.layout.addWidget(main_container)

        # Title
        title_layout = QtWidgets.QHBoxLayout()
        title_icon = QtWidgets.QLabel("🧠")
        title_icon.setStyleSheet(f"font-size: {DisplayScaling.font_size(34)}px;")
        title_label = QtWidgets.QLabel("Squid's Thought Process")
        title_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(30)}px; font-weight: bold; color: #343a40;")
        title_layout.addWidget(title_icon)
        title_layout.addWidget(title_label)
        title_layout.addStretch()
        main_layout.addLayout(title_layout)

        # Scroll area for the decision path (takes up the expandable space)
        path_scroll_area = QtWidgets.QScrollArea()
        path_scroll_area.setWidgetResizable(True)
        path_scroll_area.setStyleSheet("QScrollArea { border: none; background-color: #f8f9fa; }")
        main_layout.addWidget(path_scroll_area, 1) # Set stretch factor to 1
        
        path_container = QtWidgets.QWidget()
        self.path_layout = QtWidgets.QVBoxLayout(path_container)
        self.path_layout.setSpacing(DisplayScaling.scale(15))
        self.path_layout.setAlignment(QtCore.Qt.AlignTop)
        path_scroll_area.setWidget(path_container)

        # --- Create persistent widgets and labels for each step ---
        # Step 1: Current State
        step1, self.step1_label = self._create_path_step_widget(1, "Sensing the World", "📡")
        self.path_layout.addWidget(step1)
        self.path_layout.addWidget(self._create_arrow())

        # Step 2: Base Urges
        step2, self.step2_label = self._create_path_step_widget(2, "Calculating Base Urges", "⚖️")
        self.path_layout.addWidget(step2)
        self.path_layout.addWidget(self._create_arrow())
        
        # Step 3: Personality & Memory
        step3, self.step3_label = self._create_path_step_widget(3, "Applying Personality & Memories", "🎭")
        self.path_layout.addWidget(step3)
        self.path_layout.addWidget(self._create_arrow())

        # Step 4: Final Decision
        step4, self.step4_label = self._create_path_step_widget(4, "Making the Final Decision", "✅")
        self.path_layout.addWidget(step4)

        # --- Final Action Bar (at the bottom) ---
        final_action_bar = QtWidgets.QFrame()
        final_action_bar.setObjectName("finalActionBar")
        final_action_bar.setStyleSheet("""
            #finalActionBar {
                background-color: #e9ecef;
                border: 1px solid #ced4da;
                border-radius: 8px;
            }
        """)
        final_action_bar.setFixedHeight(DisplayScaling.scale(60))
        
        bar_layout = QtWidgets.QHBoxLayout(final_action_bar)
        bar_layout.setContentsMargins(DisplayScaling.scale(15), DisplayScaling.scale(5), DisplayScaling.scale(15), DisplayScaling.scale(5))
        
        action_title_label = QtWidgets.QLabel("<b>Final Action:</b>")
        action_title_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(22)}px; color: #495057;")
        
        self.final_action_label = QtWidgets.QLabel("...")
        self.final_action_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(22)}px; font-weight: bold; color: #007bff;")

        bar_layout.addWidget(action_title_label)
        bar_layout.addWidget(self.final_action_label)
        bar_layout.addStretch()

        main_layout.addWidget(final_action_bar) # Add bar to the main layout
        
        self.update_path_with_placeholder()

    def _create_path_step_widget(self, step_number, title, icon):
        """Creates a styled widget for a single step and returns it and its content label."""
        step_widget = QtWidgets.QWidget()
        step_widget.setObjectName("stepWidget")
        step_widget.setStyleSheet(f"""
            #stepWidget {{
                background-color: #ffffff;
                border: 1px solid #dee2e6;
                border-radius: 8px;
                padding: {DisplayScaling.scale(10)}px;
            }}
        """)
        step_layout = QtWidgets.QVBoxLayout(step_widget)

        header_layout = QtWidgets.QHBoxLayout()
        icon_label = QtWidgets.QLabel(icon)
        icon_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(30)}px;")
        title_label = QtWidgets.QLabel(f"<b>Step {step_number}: {title}</b>")
        title_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(22)}px; color: #495057;")
        header_layout.addWidget(icon_label)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        step_layout.addLayout(header_layout)

        content_label = QtWidgets.QLabel("...")
        content_label.setWordWrap(True)
        content_label.setAlignment(QtCore.Qt.AlignTop)
        content_label.setStyleSheet(f"padding-left: {DisplayScaling.scale(10)}px; padding-top: {DisplayScaling.scale(5)}px; font-size: {DisplayScaling.font_size(19)}px;")
        step_layout.addWidget(content_label)
        
        return step_widget, content_label

    def update_path_with_placeholder(self):
        """Sets initial placeholder content on the persistent labels."""
        placeholder_text = f"<i style='color: #6c757d; font-size: {DisplayScaling.font_size(19)}px;'>Awaiting the squid's next thought...</i>"
        self.step1_label.setText(placeholder_text)
        self.step2_label.setText(placeholder_text)
        self.step3_label.setText(placeholder_text)
        self.step4_label.setText(placeholder_text)
        self.final_action_label.setText("Awaiting Decision...")

    def update_from_brain_state(self, state):
        """Update visualization based on brain state."""
        if hasattr(self.tamagotchi_logic, 'get_decision_data'):
            decision_data = self.tamagotchi_logic.get_decision_data()
            if decision_data:
                self.update_decision_path(decision_data)

    def update_decision_path(self, data):
        """Updates the content of the persistent step labels and the final action bar."""
        final_decision = data.get('final_decision', 'N/A')

        self._update_state_step(data.get('inputs', {}), data.get('brain_state', {}))
        self._update_urges_step(data.get('base_weights', {}))
        self._update_modifiers_step(data)
        self._update_final_decision_step(data, final_decision)

        # Update the bottom bar
        self.final_action_label.setText(final_decision.replace('_', ' ').title())

    def _update_state_step(self, inputs, brain_state):
        text = "The squid assesses his current condition and visible objects:<br><ul>"
        if not inputs:
            text += "<li>No sensory data available.</li>"
        else:
            # Show key stats first
            key_stats = []
            for stat in ['hunger', 'happiness', 'sleepiness', 'anxiety', 'curiosity']:
                if stat in inputs:
                    value = inputs[stat]
                    color = "#dc3545" if value > 75 else "#ffc107" if value > 50 else "#28a745"
                    key_stats.append(f"<span style='color:{color};'><b>{stat.capitalize()}:</b> {value:.0f}</span>")
            
            if key_stats:
                text += f"<li>{'&nbsp;&nbsp;|&nbsp;&nbsp;'.join(key_stats)}</li>"
            
            # Show visible objects
            visible_items = []
            if inputs.get("has_food_visible"):
                visible_items.append("🍖 Food")
            if inputs.get("has_rock_visible"):
                visible_items.append("🪨 Rock")
            if inputs.get("has_poop_visible"):
                visible_items.append("💩 Poop")
            if inputs.get("has_plant_visible"):
                visible_items.append("🌿 Plant")

            if visible_items:
                text += f"<li><b>Visible Objects:</b> {', '.join(visible_items)}</li>"
            else:
                text += "<li><b>Visible Objects:</b> <i>None in sight</i></li>"
            
            # Show if carrying anything
            if inputs.get("carrying_rock"):
                text += "<li>🪨 <b>Carrying a rock</b></li>"
            if inputs.get("carrying_poop"):
                text += "<li>💩 <b>Carrying poop</b></li>"
            
            # Show if sick or sleeping
            if inputs.get("is_sick"):
                text += "<li>🤒 <b>Is sick</b></li>"
            if inputs.get("is_sleeping"):
                text += "<li>💤 <b>Is sleeping</b></li>"
                
        text += "</ul>"
        self.step1_label.setText(text)

    def _update_urges_step(self, weights):
        if not weights:
            self.step2_label.setText("No urges calculated.")
            return

        # Filter out zero weights for cleaner display
        non_zero_weights = {k: v for k, v in weights.items() if v > 0}
        
        if not non_zero_weights:
            self.step2_label.setText("<i>No urges active - all base desires are currently zero.</i>")
            return
        
        strongest_urge = max(non_zero_weights, key=non_zero_weights.get)
        text = f"Based on brain state and needs, the strongest urge is <b style='color: #007bff;'>{strongest_urge.replace('_', ' ').title()}</b>.<br><br>"
        text += "Active urges (sorted by strength):"
        text += "<ul>"
        for action, weight in sorted(non_zero_weights.items(), key=lambda item: item[1], reverse=True):
            # Highlight if this is the strongest
            if action == strongest_urge:
                text += f"<li style='background-color: #e7f3ff; padding: 2px; border-radius: 3px;'><b>➤ {action.replace('_', ' ').title()}:</b> {weight:.2f}</li>"
            else:
                text += f"<li><b>{action.replace('_', ' ').title()}:</b> {weight:.2f}</li>"
        text += "</ul>"
        
        # Show which urges are currently unavailable (zero weight)
        zero_weights = {k: v for k, v in weights.items() if v == 0}
        if zero_weights:
            text += "<br><i style='color: #6c757d; font-size: 0.9em;'>Unavailable urges: "
            unavailable_list = []
            for action in zero_weights.keys():
                reason = ""
                if "eating" in action:
                    reason = "(no food visible)"
                elif "playing" in action:
                    reason = "(no objects to play with)"
                elif "rock" in action:
                    reason = "(no rocks visible/available)"
                elif "plant" in action:
                    reason = "(no plants visible)"
                elif "poop" in action:
                    reason = "(no poop visible/available)"
                unavailable_list.append(f"{action.replace('_', ' ').title()} {reason}")
            text += ", ".join(unavailable_list)
            text += "</i>"
        
        self.step2_label.setText(text)

    def _update_modifiers_step(self, data):
        base_weights = data.get('base_weights', {})
        adj_weights = data.get('adjusted_weights', {})
        personality = data.get('personality', 'UNKNOWN')
        memory_influences = data.get('memory_influences', {})
        personality_modifiers = data.get('personality_modifiers', {})
        
        text = f"<b>Personality:</b> {personality}<br><br>"
        text += "Now personality traits, memories, and urgency adjust these base urges:<br><ul>"

        modified = False
        modifications = []
        
        for action, final_score in adj_weights.items():
            base_score = base_weights.get(action, final_score)
            delta = final_score - base_score
            
            if abs(delta) > 0.01:  # Only show meaningful changes
                direction = "↑ increased" if delta > 0 else "↓ decreased"
                color = "#28a745" if delta > 0 else "#dc3545"
                
                # Try to explain why it changed
                reasons = []
                if action in personality_modifiers and personality_modifiers[action] != 1.0:
                    modifier = personality_modifiers[action]
                    if modifier > 1.0:
                        reasons.append(f"personality boost ×{modifier:.2f}")
                    else:
                        reasons.append(f"personality reduction ×{modifier:.2f}")
                
                if action in memory_influences and memory_influences[action] != 1.0:
                    modifier = memory_influences[action]
                    if modifier > 1.0:
                        reasons.append(f"positive memories ×{modifier:.2f}")
                    else:
                        reasons.append(f"negative memories ×{modifier:.2f}")
                
                reason_text = f" <i>({', '.join(reasons)})</i>" if reasons else ""
                
                modifications.append({
                    'action': action,
                    'direction': direction,
                    'delta': delta,
                    'color': color,
                    'reason': reason_text,
                    'base': base_score,
                    'final': final_score
                })
                modified = True
        
        # Sort by magnitude of change
        modifications.sort(key=lambda x: abs(x['delta']), reverse=True)
        
        for mod in modifications:
            text += f"<li><b>{mod['action'].replace('_', ' ').title()}</b> {mod['direction']}: "
            text += f"{mod['base']:.2f} → <span style='color:{mod['color']};'><b>{mod['final']:.2f}</b></span>"
            text += f" <span style='color:{mod['color']};'>({mod['delta']:+.2f})</span>"
            text += f"{mod['reason']}</li>"

        if not modified:
            text += "<li><i>No significant adjustments from personality or memory this time.</i></li>"

        text += "</ul>"
        self.step3_label.setText(text)

    def _update_final_decision_step(self, data, final_decision):
        confidence = data.get('confidence', 0.0)
        adj_weights = data.get('adjusted_weights', {})

        text = "After all calculations, the final scores determine the action.<br><br>"
        text += "<b>Final Decision Scores:</b>"
        text += "<ul>"
        if not adj_weights:
            text += "<li>No final scores available.</li>"
        else:
            # Only show non-zero or relevant scores
            relevant_scores = sorted(adj_weights.items(), key=lambda item: item[1], reverse=True)[:6]
            
            for action, score in relevant_scores:
                # Check if this is the winning decision
                is_winner = (action == final_decision)
                
                if is_winner:
                    text += f"<li style='background-color: #d4edda; border-left: 4px solid #28a745; padding: 5px; margin: 3px 0; border-radius: 4px;'>"
                    text += f"<b style='color: #155724; font-size: 1.1em;'>🏆 {action.replace('_', ' ').title()}: {score:.2f}</b>"
                    text += f" <span style='color: #155724;'>← CHOSEN</span></li>"
                elif score > 0:
                    text += f"<li><b>{action.replace('_', ' ').title()}:</b> {score:.2f}</li>"
                else:
                    text += f"<li style='color: #6c757d;'><i>{action.replace('_', ' ').title()}: {score:.2f}</i></li>"
        text += "</ul>"

        # Confidence display
        conf_color = "#28a745" if confidence > 0.5 else "#ffc107" if confidence > 0.2 else "#dc3545"
        conf_label = "High" if confidence > 0.5 else "Medium" if confidence > 0.2 else "Low"
        
        text += f"<hr style='margin: 10px 0;'>"
        text += f"<b>Final Decision:</b> <span style='color: #007bff; font-size: 1.1em;'>{final_decision.replace('_', ' ').title()}</span><br>"
        text += f"<b>Confidence:</b> <span style='color:{conf_color};'>{conf_label}</span> ({confidence:.1%})"
        
        if confidence < 0.2:
            text += "<br><i style='color: #6c757d; font-size: 0.9em;'>Note: Low confidence means the squid is uncertain - multiple urges were similarly strong.</i>"
        
        self.step4_label.setText(text)

    def _create_arrow(self):
        arrow_label = QtWidgets.QLabel("⬇️")
        arrow_label.setAlignment(QtCore.Qt.AlignCenter)
        arrow_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(24)}px; color: #adb5bd; margin: -5px 0 -5px 0;")
        return arrow_label