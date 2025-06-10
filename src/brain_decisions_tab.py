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

        self._update_state_step(data.get('inputs', {}))
        self._update_urges_step(data.get('weights', {}))
        self._update_modifiers_step(data)
        self._update_final_decision_step(data, final_decision)

        # Update the bottom bar
        self.final_action_label.setText(final_decision.capitalize())

    def _update_state_step(self, inputs):
        text = "The squid assesses his current condition and visible objects:<br><ul>"
        if not inputs:
            text += "<li>No sensory data available.</li>"
        else:
            visible_items = []
            if inputs.get("has_food_visible"):
                visible_items.append("Food")
            if inputs.get("has_rock_visible"):
                visible_items.append("Rock")
            if inputs.get("has_poop_visible"):
                visible_items.append("Poop")
            if inputs.get("has_plant_visible"):
                visible_items.append("Plant")

            if visible_items:
                text += f"<li><b>Visible Objects:</b> {', '.join(visible_items)}</li>"
            else:
                text += "<li><b>Visible Objects:</b> None</li>"

            excluded_keys = {"has_food_visible", "has_rock_visible", "has_poop_visible", "has_plant_visible"}
            for key, value in sorted(inputs.items()):
                if key not in excluded_keys:
                    formatted_value = f"{value:.2f}" if isinstance(value, float) else str(value)
                    text += f"<li><b>{key.replace('_', ' ').capitalize()}:</b> {formatted_value}</li>"
        text += "</ul>"
        self.step1_label.setText(text)

    def _update_urges_step(self, weights):
        if not weights:
            self.step2_label.setText("No urges calculated.")
            return

        strongest_urge = max(weights, key=weights.get)
        text = f"Based on needs, the strongest urge is <b>{strongest_urge.capitalize()}</b>.<br><br>Initial scores:"
        text += "<ul>"
        for action, weight in sorted(weights.items(), key=lambda item: item[1], reverse=True):
            text += f"<li><b>{action.capitalize()}:</b> {weight:.3f}</li>"
        text += "</ul>"
        self.step2_label.setText(text)

    def _update_modifiers_step(self, data):
        weights = data.get('weights', {})
        adj_weights = data.get('adjusted_weights', {})
        text = "Personality traits and recent memories then adjust these urges:<br><ul>"

        modified = False
        for action, final_score in adj_weights.items():
            base_score = weights.get(action, final_score)
            delta = final_score - base_score
            if abs(delta) > 0.001:
                direction = "increased" if delta > 0 else "decreased"
                color = "#28a745" if delta > 0 else "#dc3545"
                text += f"<li>The score for <b>{action.capitalize()}</b> {direction} by {abs(delta):.3f} <span style='color:{color};'>({delta:+.3f})</span></li>"
                modified = True

        if not modified:
            text += "<li>No significant adjustments from personality or memory this time.</li>"

        text += "</ul>"
        self.step3_label.setText(text)

    def _update_final_decision_step(self, data, final_decision):
        confidence = data.get('confidence', 0.0)
        adj_weights = data.get('adjusted_weights', {})

        text = "After all calculations, the final scores are tallied. The highest score determines the action."
        text += "<ul>"
        if not adj_weights:
            text += "<li>No final scores available.</li>"
        else:
            for action, score in sorted(adj_weights.items(), key=lambda item: item[1], reverse=True):
                item_text = f"<li><b>{action.capitalize()}:</b> {score:.3f}</li>"
                if action == final_decision:
                    item_text = f"<li style='background-color: #d4edda; border-radius: 4px; padding: 2px;'><b>▶ {action.capitalize()}: {score:.3f}</b></li>"
                text += item_text
        text += "</ul>"

        text += f"<hr>The squid has decided <b>{final_decision.capitalize()}</b> with a confidence level of <b>{confidence:.1%}</b>."
        self.step4_label.setText(text)

    def _create_arrow(self):
        arrow_label = QtWidgets.QLabel("⬇️")
        arrow_label.setAlignment(QtCore.Qt.AlignCenter)
        arrow_label.setStyleSheet(f"font-size: {DisplayScaling.font_size(24)}px; color: #adb5bd; margin: -5px 0 -5px 0;")
        return arrow_label