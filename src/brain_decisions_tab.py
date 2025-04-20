import time
import math
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .brain_dialogs import RecentThoughtsDialog

class DecisionsTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.is_logging = False
        self.thought_log = []
        self.initialize_ui()

    def initialize_ui(self):
        """Initialize the thinking tab with visualization focused on the decision process"""
        self.layout.setContentsMargins(10, 10, 10, 10)  # Add some padding
        
        # Use a QSplitter for resizable sections
        self.main_splitter = QtWidgets.QSplitter(QtCore.Qt.Vertical)
        self.layout.addWidget(self.main_splitter)
        
        # TOP SECTION: Decision process visualization
        self.decision_process_widget = self._create_decision_process_widget()
        self.main_splitter.addWidget(self.decision_process_widget)
        
        # MIDDLE SECTION: Neural weights visualization
        self.weights_widget = self._create_weights_visualization_widget()
        self.main_splitter.addWidget(self.weights_widget)
        
        # BOTTOM SECTION: Thought log
        self.log_widget = self._create_thought_log_widget()
        self.main_splitter.addWidget(self.log_widget)
        
        # Set initial splitter sizes (40% process, 30% weights, 30% log)
        self.main_splitter.setSizes([400, 300, 300])
        
        # Initial update of visualizations with empty data
        self.update_visualization_with_placeholder()

    def _create_decision_process_widget(self):
        """Create the decision process visualization section"""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        
        from .display_scaling import DisplayScaling
        
        # Main visualization area
        self.process_visualization = QtWidgets.QWidget()
        process_layout = QtWidgets.QHBoxLayout(self.process_visualization)
        
        # --- Neural Processing Section (Expanded) ---
        self.processing_section = QtWidgets.QGroupBox("Neural Processing")
        self.processing_section.setStyleSheet(
            f"QGroupBox {{ font-weight: bold; border: 2px solid #9b59b6; border-radius: {DisplayScaling.scale(8)}px; margin-top: 1ex; background-color: #f8f9fa; }}"
            f"QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 5px; background-color: #9b59b6; color: white; }}"
        )
        processing_layout = QtWidgets.QVBoxLayout(self.processing_section)
        
        # Neural network visualization widget
        self.neural_view = QtWidgets.QGraphicsView()
        self.neural_view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.neural_scene = QtWidgets.QGraphicsScene()
        self.neural_view.setScene(self.neural_scene)
        processing_layout.addWidget(self.neural_view)
        
        # Add processing section
        process_layout.addWidget(self.processing_section)
        
        # Flow arrow
        arrow = QtWidgets.QLabel("→")
        arrow.setStyleSheet("font-size: 24px; font-weight: bold;")
        arrow.setAlignment(QtCore.Qt.AlignCenter)
        process_layout.addWidget(arrow)
        
        # --- Decision Output Section ---
        self.decision_section = QtWidgets.QGroupBox("Decision Output")
        self.decision_section.setStyleSheet(
            "QGroupBox { font-weight: bold; border: 2px solid #2ecc71; border-radius: 8px; margin-top: 1ex; background-color: #f8f9fa; }"
            "QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; background-color: #2ecc71; color: white; }"
        )
        decision_layout = QtWidgets.QVBoxLayout(self.decision_section)
        decision_layout.setSpacing(5)  # Reduced spacing between widgets
        decision_layout.setContentsMargins(8, 8, 8, 8)  # Reduced margins
        
        # Current decision (large, prominent display)
        self.decision_icon = QtWidgets.QLabel()
        self.decision_icon.setAlignment(QtCore.Qt.AlignCenter)
        self.decision_icon.setFixedSize(DisplayScaling.scale(64), DisplayScaling.scale(64))  # Scaled fixed size
        decision_layout.addWidget(self.decision_icon)
        
        self.decision_output = QtWidgets.QLabel("No Decision")
        self.decision_output.setStyleSheet(f"font-size: {DisplayScaling.font_size(24)}px; font-weight: bold; color: #2c3e50; margin-top: 0;")
        self.decision_output.setAlignment(QtCore.Qt.AlignCenter)
        decision_layout.addWidget(self.decision_output)
        
        # Decision explanation
        explanation_label = QtWidgets.QLabel("Explanation:")
        explanation_label.setStyleSheet("margin-top: 10px;")  # Add some space above explanation
        decision_layout.addWidget(explanation_label)
        
        self.decision_explanation = QtWidgets.QTextEdit()
        self.decision_explanation.setReadOnly(True)
        self.decision_explanation.setFixedHeight(200)  # Fixed height instead of maximum
        self.decision_explanation.setStyleSheet("background-color: #f8f9fa; border: 1px solid #ddd; margin-top: 0;")
        decision_layout.addWidget(self.decision_explanation)
        
        process_layout.addWidget(self.decision_section)
        
        # Add the process visualization to the container
        layout.addWidget(self.process_visualization)
        
        # Set stretch factors for the sections
        process_layout.setStretch(0, 70)  # Neural Processing section (70%)
        process_layout.setStretch(1, 5)   # Arrow (5%)
        process_layout.setStretch(2, 25)  # Decision section (25%)
        
        return container

    def _create_weights_visualization_widget(self):
        """Create enhanced weight visualization section"""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        
        # Title
        title = QtWidgets.QLabel("Decision Action Weights")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50; padding: 5px;")
        title.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(title)
        
        # Two-panel layout: Radar chart and bar chart
        charts_layout = QtWidgets.QHBoxLayout()
        
        # 1. Radar Chart View (for relationships between decisions)
        self.radar_view = QtWidgets.QGraphicsView()
        self.radar_view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.radar_scene = QtWidgets.QGraphicsScene()
        self.radar_view.setScene(self.radar_scene)
        
        radar_container = QtWidgets.QGroupBox("Decision Weight Relationships")
        radar_container.setStyleSheet("""
            QGroupBox {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 1ex;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        radar_layout = QtWidgets.QVBoxLayout(radar_container)
        radar_layout.addWidget(self.radar_view)
        
        # 2. Bar Chart (improved version of current implementation)
        self.bar_view = QtWidgets.QGraphicsView()
        self.bar_view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.bar_scene = QtWidgets.QGraphicsScene()
        self.bar_view.setScene(self.bar_scene)
        
        bar_container = QtWidgets.QGroupBox("Action Weight Comparison")
        bar_container.setStyleSheet("""
            QGroupBox {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                margin-top: 1ex;
                background-color: white;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
        """)
        bar_layout = QtWidgets.QVBoxLayout(bar_container)
        bar_layout.addWidget(self.bar_view)
        
        # Add legend
        legend_layout = QtWidgets.QHBoxLayout()
        
        # Base weight legend item
        base_color = QtWidgets.QFrame()
        base_color.setStyleSheet("background-color: #3498db; border: none;")
        base_color.setFixedSize(15, 15)
        legend_layout.addWidget(base_color)
        legend_layout.addWidget(QtWidgets.QLabel("Base Weight"))
        legend_layout.addSpacing(15)
        
        # Adjusted weight legend item
        adjusted_color = QtWidgets.QFrame()
        adjusted_color.setStyleSheet("background-color: #e74c3c; border: none;")
        adjusted_color.setFixedSize(15, 15)
        legend_layout.addWidget(adjusted_color)
        legend_layout.addWidget(QtWidgets.QLabel("After Personality"))
        legend_layout.addSpacing(15)
        
        # Random factor legend item
        random_color = QtWidgets.QFrame()
        random_color.setStyleSheet("background-color: #f39c12; border: none;")
        random_color.setFixedSize(15, 15)
        legend_layout.addWidget(random_color)
        legend_layout.addWidget(QtWidgets.QLabel("Random Factor"))
        
        # Add stretch to push legend items to the left
        legend_layout.addStretch()
        
        bar_layout.addLayout(legend_layout)
        
        # Add both chart containers to the layout
        charts_layout.addWidget(radar_container)
        charts_layout.addWidget(bar_container)
        layout.addLayout(charts_layout)
        
        return container

    def _create_thought_log_widget(self):
        """Create improved thought log widget"""
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        
        # Header with controls
        header_layout = QtWidgets.QHBoxLayout()
        
        title = QtWidgets.QLabel("Decision Log")
        title.setStyleSheet("font-size: 16px; font-weight: bold; color: #2c3e50;")
        header_layout.addWidget(title)
        
        header_layout.addStretch()
        
        # Filter dropdown
        self.log_filter = QtWidgets.QComboBox()
        self.log_filter.addItem("All Decisions")
        self.log_filter.addItems(["Exploring", "Eating", "Organizing", "Approaching", "Throwing", "Avoiding"])
        self.log_filter.setFixedWidth(150)
        self.log_filter.currentIndexChanged.connect(self.filter_thought_log)
        header_layout.addWidget(QtWidgets.QLabel("Filter:"))
        header_layout.addWidget(self.log_filter)
        
        # Logging control button
        self.logging_button = QtWidgets.QPushButton("Start Logging")
        self.logging_button.setCheckable(True)
        self.logging_button.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
                font-weight: bold;
            }
            QPushButton:checked {
                background-color: #e74c3c;
            }
        """)
        self.logging_button.clicked.connect(self.toggle_logging)
        header_layout.addWidget(self.logging_button)
        
        # View logs button
        self.view_logs_button = QtWidgets.QPushButton("View History")
        self.view_logs_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 5px 10px;
            }
        """)
        self.view_logs_button.clicked.connect(self.view_thought_logs)
        header_layout.addWidget(self.view_logs_button)
        
        layout.addLayout(header_layout)
        
        # Rich text log display (styled entries with collapsible sections)
        self.thought_log_text = QtWidgets.QTextEdit()
        self.thought_log_text.setReadOnly(True)
        self.thought_log_text.setStyleSheet("""
            QTextEdit {
                background-color: #f8f9fa;
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                padding: 10px;
                font-family: Arial, sans-serif;
            }
        """)
        layout.addWidget(self.thought_log_text)
        
        return container

    def update_visualization_with_placeholder(self):
        """Initialize visualizations with placeholder data"""
        # Draw empty neural network
        self._draw_neural_network_placeholder()
        
        # Draw empty radar chart
        self._draw_radar_chart_placeholder()
        
        # Draw empty bar chart
        self._draw_bar_chart_placeholder()
        
        # Set placeholder text for thought log
        self.thought_log_text.setHtml(
            "<div style='color: #7f8c8d; text-align: center; padding: 50px;'>"
            "<p>Start logging to view the squid's decision process.</p>"
            "<p>Click the 'Start Logging' button to begin recording decisions.</p>"
            "</div>"
        )

    def _draw_neural_network_placeholder(self):
        """Draw a placeholder neural network visualization"""
        self.neural_scene.clear()
        
        # Background
        self.neural_scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#f8f9fa")))
        
        # Add placeholder text
        text = self.neural_scene.addText("Neural network visualization will appear here")
        text.setDefaultTextColor(QtGui.QColor("#7f8c8d"))
        text.setPos(50, 50)
        
        # Default nodes (faded)
        self._draw_neural_nodes(active=False)

    def _draw_neural_nodes(self, active=False):
        """Draw neural network nodes"""
        # Define node positions (3 layers: input, hidden, output)
        input_nodes = [(50, 30), (50, 90), (50, 150)]
        hidden_nodes = [(150, 30), (150, 90), (150, 150)]
        output_nodes = [(250, 90)]
        
        # Node color based on active state
        node_color = QtGui.QColor(60, 60, 60, 255 if active else 100)
        edge_color = QtGui.QColor(100, 100, 100, 255 if active else 50)
        
        # Draw edges first (so they're behind nodes)
        pen = QtGui.QPen(edge_color)
        pen.setWidth(1)
        
        # Connect input to hidden layer
        for i_pos in input_nodes:
            for h_pos in hidden_nodes:
                self.neural_scene.addLine(i_pos[0], i_pos[1], h_pos[0], h_pos[1], pen)
        
        # Connect hidden to output layer
        for h_pos in hidden_nodes:
            for o_pos in output_nodes:
                self.neural_scene.addLine(h_pos[0], h_pos[1], o_pos[0], o_pos[1], pen)
        
        # Draw nodes
        for pos in input_nodes + hidden_nodes + output_nodes:
            node = self.neural_scene.addEllipse(pos[0]-10, pos[1]-10, 20, 20, 
                                            QtGui.QPen(node_color), 
                                            QtGui.QBrush(node_color))

    def _draw_radar_chart_placeholder(self):
        """Draw a placeholder radar chart"""
        self.radar_scene.clear()
        
        # Background
        self.radar_scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#f8f9fa")))
        
        # Add placeholder text
        text = self.radar_scene.addText("Decision relationships will appear here")
        text.setDefaultTextColor(QtGui.QColor("#7f8c8d"))
        text.setPos(50, 50)
        
        # Basic radar chart outline
        self._draw_radar_outline()

    def _draw_radar_outline(self):
        """Draw radar chart axes outline"""
        # Center position
        center_x, center_y = 150, 100
        radius = 70
        
        # Axes
        axes_pen = QtGui.QPen(QtGui.QColor("#bdc3c7"))
        axes_pen.setWidth(1)
        
        # Draw 6 axes (one for each common decision type)
        for i in range(6):
            angle = i * 60 * (math.pi / 180)  # Convert to radians
            x = center_x + radius * math.cos(angle)  # Use math.cos instead of QtCore.qCos
            y = center_y + radius * math.sin(angle)  # Use math.sin instead of QtCore.qSin
            self.radar_scene.addLine(center_x, center_y, x, y, axes_pen)
            
            # Add labels
            actions = ["Exploring", "Eating", "Approach", "Throw", "Avoid", "Organize"]
            label = self.radar_scene.addText(actions[i])
            label.setDefaultTextColor(QtGui.QColor("#7f8c8d"))
            # Position label at end of axis
            label.setPos(x - 20, y - 10)
            
        # Draw concentric circles
        for r in range(1, 4):
            circle_radius = radius * r / 3
            self.radar_scene.addEllipse(
                center_x - circle_radius, 
                center_y - circle_radius,
                circle_radius * 2, 
                circle_radius * 2,
                axes_pen
            )

    def _draw_bar_chart_placeholder(self):
        """Draw a placeholder bar chart"""
        self.bar_scene.clear()
        
        # Background
        self.bar_scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#f8f9fa")))
        
        # Add placeholder bars (faded)
        self._draw_placeholder_bars()

    def _draw_placeholder_bars(self):
        """Draw placeholder bars for the weight chart"""
        actions = ["exploring", "eating", "approaching", "throwing", "avoiding", "organizing"]
        
        for i, action in enumerate(actions):
            y_pos = 30 + i * 25
            
            # Action label
            label = self.bar_scene.addText(action)
            label.setDefaultTextColor(QtGui.QColor("#7f8c8d"))
            label.setPos(10, y_pos)
            
            # Bars (base and adjusted, faded)
            base_rect = self.bar_scene.addRect(
                100, y_pos, 100, 15,
                QtGui.QPen(QtGui.QColor("#3498db")),
                QtGui.QBrush(QtGui.QColor(52, 152, 219, 100))  # Faded blue
            )
            
            adj_rect = self.bar_scene.addRect(
                100, y_pos, 80, 15,  # Shorter than base
                QtGui.QPen(QtGui.QColor("#e74c3c")),
                QtGui.QBrush(QtGui.QColor(231, 76, 60, 100))  # Faded red
            )
            
            # Value text (dummy)
            value = self.bar_scene.addText("0.00")
            value.setDefaultTextColor(QtGui.QColor("#7f8c8d"))
            value.setPos(210, y_pos)

    def update_from_brain_state(self, state):
        """Update decision visualization based on brain state"""
        if hasattr(self.tamagotchi_logic, 'get_decision_data'):
            decision_data = self.tamagotchi_logic.get_decision_data()
            self.update_thought_process(decision_data)

    def update_thought_process(self, decision_data):
        """Update all visualizations with new decision data"""
        # Extract key data
        inputs = decision_data.get('inputs', {})
        decision = decision_data.get('final_decision', 'exploring')
        confidence = decision_data.get('confidence', 0.5)
        weights = decision_data.get('weights', {})
        adjusted_weights = decision_data.get('adjusted_weights', {})
        randomness = decision_data.get('randomness', {})
        active_memories = decision_data.get('active_memories', [])
        processing_time = decision_data.get('processing_time', 50)
        
        
        # 1. Update neural network visualization
        self._update_neural_network(inputs, decision, processing_time)
        
        # 2. Update decision output
        self._update_decision_output(decision, confidence, 
                                   self._generate_explanation(decision, weights, adjusted_weights, 
                                                          randomness, active_memories))
        
        # 3. Update radar and bar charts
        self._update_charts(weights, adjusted_weights, randomness, decision)
        
        # 4. Add to thought log if logging is enabled
        if self.is_logging:
            self.add_to_thought_log(decision_data)



    def _update_neural_network(self, inputs, decision, processing_time):
        """Update the neural network visualization"""
        self.neural_scene.clear()
        
        # Background
        self.neural_scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#ffffff")))
        
        # Draw active neural network
        self._draw_neural_nodes(active=True)
        
        # Add processing time indicator
        time_text = self.neural_scene.addText(f"Processing time: {processing_time} ms")
        time_text.setDefaultTextColor(QtGui.QColor("#7f8c8d"))
        time_text.setPos(10, 170)
        
        # Add decision result at output
        result = self.neural_scene.addText(f"Decision: {decision}")
        result.setDefaultTextColor(QtGui.QColor("#2c3e50"))
        result.setPos(230, 60)
        
        # Show active inputs at input layer
        key_inputs = sorted([(k, v) for k, v in inputs.items() 
                           if isinstance(v, (int, float))], 
                          key=lambda x: x[1], reverse=True)[:3]
        
        for i, (factor, value) in enumerate(key_inputs):
            input_text = self.neural_scene.addText(f"{factor}: {int(value)}")
            input_text.setDefaultTextColor(QtGui.QColor("#2c3e50"))
            input_text.setPos(10, 25 + i * 60)

    def _update_decision_output(self, decision, confidence, explanation):
        """Update the decision output display"""
        # Decision text
        self.decision_output.setText(decision.capitalize())
        
        # Decision icon
        icon_path = self._get_decision_icon(decision)
        if QtCore.QFile.exists(icon_path):
            self.decision_icon.setPixmap(QtGui.QPixmap(icon_path).scaled(64, 64))
        
        # Decision explanation
        self.decision_explanation.setHtml(explanation)

    def _get_decision_icon(self, decision):
        """Get icon path for a decision type"""
        # Map decisions to icon paths (use appropriate paths for your application)
        icons = {
            "exploring": ":/icons/exploring.png",
            "eating": ":/icons/eating.png",
            "approaching_rock": ":/icons/approaching.png",
            "throwing_rock": ":/icons/throwing.png",
            "avoiding_threat": ":/icons/avoiding.png",
            "organizing": ":/icons/organizing.png",
            "moving_to_food": ":/icons/eating.png",
            "sleeping": ":/icons/sleeping.png"
        }
        
        # Return default icon if not found
        return icons.get(decision, ":/icons/default.png")

    def _generate_explanation(self, decision, weights, adjusted_weights, randomness, memories):
        """Generate rich HTML explanation for the decision"""
        html = "<div style='font-family: Arial, sans-serif;'>"
        
        # Add specific explanation based on decision type
        if decision == "exploring":
            html += "<p>The squid is <b>exploring</b> its environment due to:</p>"
        elif decision == "eating" or decision == "moving_to_food":
            html += "<p>The squid is <b>seeking food</b> due to:</p>"
        elif decision == "approaching_rock":
            html += "<p>The squid is <b>approaching a rock</b> due to:</p>"
        elif decision == "throwing_rock":
            html += "<p>The squid is <b>throwing a rock</b> due to:</p>"
        elif decision == "avoiding_threat":
            html += "<p>The squid is <b>avoiding a threat</b> due to:</p>"
        elif decision == "organizing":
            html += "<p>The squid is <b>organizing decorations</b> due to:</p>"
        elif decision == "sleeping":
            html += "<p>The squid is <b>sleeping</b> due to:</p>"
        else:
            html += f"<p>The squid is <b>{decision}</b> due to:</p>"
        
        # Get the weight for this decision and top competing decisions
        decision_weight = adjusted_weights.get(decision, 0)
        competing = [(k, v) for k, v in adjusted_weights.items() 
                   if k != decision and v > 0]
        competing.sort(key=lambda x: x[1], reverse=True)
        
        # Factors that contributed to this decision
        html += "<ul>"
        
        # Base weight
        base = weights.get(decision, 0)
        html += f"<li>Base neural weight: <b>{base:.2f}</b></li>"
        
        # Personality adjustment
        if abs(decision_weight - base) > 0.01:
            direction = "increased" if decision_weight > base else "decreased"
            html += f"<li>Personality {direction} weight by: <b>{abs(decision_weight - base):.2f}</b></li>"
        
        # Random factor
        if decision in randomness:
            random_factor = randomness[decision]
            direction = "boosted" if random_factor > 1 else "reduced"
            html += f"<li>Random factor {direction} decision by: <b>{abs(random_factor - 1):.2f}</b></li>"
        
        # Relevant memories
        if memories:
            html += f"<li>Influenced by {len(memories)} active memories</li>"
        
        html += "</ul>"
        
        # Show competing decisions
        if competing:
            html += "<p>Competing decisions:</p><ul>"
            for action, weight in competing[:2]:  # Show top 2 competing decisions
                difference = decision_weight - weight
                html += f"<li><b>{action}</b>: {weight:.2f} (difference: {difference:.2f})</li>"
            html += "</ul>"
        
        html += "</div>"
        return html

    def _update_charts(self, weights, adjusted_weights, randomness, selected_decision):
        """Update both the radar chart and bar chart"""
        # 1. Update radar chart
        self._update_radar_chart(adjusted_weights, selected_decision)
        
        # 2. Update bar chart
        self._update_bar_chart(weights, adjusted_weights, randomness, selected_decision)

    def _update_radar_chart(self, weights, selected_decision):
        """Update the radar chart visualization"""
        self.radar_scene.clear()
        
        # Background
        self.radar_scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#ffffff")))
        
        # Draw radar chart outline
        self._draw_radar_outline()
        
        # Center position and radius
        center_x, center_y = 150, 100
        radius = 70
        
        # Get normalized weights for radar chart
        max_weight = max(weights.values()) if weights else 1.0
        normalized_weights = {k: min(v / max_weight, 1.0) for k, v in weights.items()}
        
        # Action mapping to positions (6 axes)
        action_mapping = {
            "exploring": 0,
            "eating": 1,
            "approaching_rock": 2,
            "throwing_rock": 3, 
            "avoiding_threat": 4,
            "organizing": 5
        }
        
        # Create points for the radar polygon
        points = []
        for action, normalized in normalized_weights.items():
            if action in action_mapping:
                idx = action_mapping[action]
                angle = idx * 60 * (math.pi / 180)  # Convert to radians
                distance = normalized * radius
                x = center_x + distance * math.cos(angle)  # Use math.cos instead of QtCore.qCos
                y = center_y + distance * math.sin(angle)  # Use math.sin instead of QtCore.qSin
                points.append(QtCore.QPointF(x, y))
        
        # Draw polygon if we have points
        if points:
            # Create a polygon and draw it
            polygon = QtGui.QPolygonF(points)
            
            # Draw filled polygon with semi-transparency
            self.radar_scene.addPolygon(
                polygon,
                QtGui.QPen(QtGui.QColor("#3498db"), 2),
                QtGui.QBrush(QtGui.QColor(52, 152, 219, 100))  # Semi-transparent blue
            )
            
            # Highlight points
            for point in points:
                self.radar_scene.addEllipse(
                    point.x() - 4, point.y() - 4, 8, 8,
                    QtGui.QPen(QtGui.QColor("#2980b9")),
                    QtGui.QBrush(QtGui.QColor("#3498db"))
                )
            
            # Highlight the selected decision on the radar
            if selected_decision in action_mapping:
                idx = action_mapping[selected_decision]
                angle = idx * 60 * (math.pi / 180)
                distance = normalized_weights.get(selected_decision, 0) * radius
                x = center_x + distance * math.cos(angle)
                y = center_y + distance * math.sin(angle)
                
                # Add highlight circle
                self.radar_scene.addEllipse(
                    x - 6, y - 6, 12, 12,
                    QtGui.QPen(QtGui.QColor("#e74c3c"), 2),
                    QtGui.QBrush(QtGui.QColor(231, 76, 60, 150))
                )

    def _update_bar_chart(self, weights, adjusted_weights, randomness, selected_decision):
        """Update the bar chart visualization"""
        self.bar_scene.clear()
        
        # Background
        self.bar_scene.setBackgroundBrush(QtGui.QBrush(QtGui.QColor("#ffffff")))
        
        # Get max weight for scaling
        all_values = list(weights.values()) + list(adjusted_weights.values())
        max_weight = max(all_values) if all_values else 1.0
        scale_factor = 200 / max_weight  # Scale to fit 200px width
        
        # Sort actions by adjusted weight
        sorted_actions = sorted(adjusted_weights.items(), 
                             key=lambda x: x[1], reverse=True)
        
        # Create color brushes
        base_brush = QtGui.QBrush(QtGui.QColor("#3498db"))
        adjusted_brush = QtGui.QBrush(QtGui.QColor("#e74c3c"))
        random_brush = QtGui.QBrush(QtGui.QColor("#f39c12"))
        
        # Stroke pens
        normal_pen = QtGui.QPen(QtGui.QColor(0, 0, 0, 50))
        highlight_pen = QtGui.QPen(QtGui.QColor("#2c3e50"), 2)
        
        # Draw each action bar
        for i, (action, adj_weight) in enumerate(sorted_actions):
            y_pos = 30 + i * 30
            
            # Action label
            label = self.bar_scene.addText(action)
            label.setDefaultTextColor(QtGui.QColor("#2c3e50"))
            label.setPos(10, y_pos)
            
            # Base weight bar
            base_weight = weights.get(action, 0)
            base_width = base_weight * scale_factor
            
            # Use highlight pen for selected decision
            pen = highlight_pen if action == selected_decision else normal_pen
            
            base_bar = self.bar_scene.addRect(
                100, y_pos, base_width, 15,
                pen, base_brush
            )
            
            # Adjusted weight bar
            adj_width = adj_weight * scale_factor
            adj_bar = self.bar_scene.addRect(
                100, y_pos + 15, adj_width, 5,
                pen, adjusted_brush
            )
            
            # Random factor indicator (small triangle at end of bar)
            if action in randomness:
                random_factor = randomness[action]
                # Draw triangle at the end of adjusted bar
                random_x = 100 + adj_width
                random_y = y_pos + 7.5
                
                triangle = QtGui.QPolygonF([
                    QtCore.QPointF(random_x, random_y - 7.5),
                    QtCore.QPointF(random_x + 10, random_y),
                    QtCore.QPointF(random_x, random_y + 7.5)
                ])
                
                self.bar_scene.addPolygon(triangle, pen, random_brush)
            
            # Value text
            value = self.bar_scene.addText(f"{adj_weight:.2f}")
            value.setDefaultTextColor(QtGui.QColor("#2c3e50"))
            value.setPos(100 + adj_width + 15, y_pos)

    def toggle_logging(self):
        """Toggle decision logging on/off"""
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
        """Add the current decision process to the thought log with rich formatting"""
        if not self.is_logging:
            return
            
        timestamp = time.strftime("%H:%M:%S")
        decision = decision_data.get('final_decision', 'unknown')
        confidence = decision_data.get('confidence', 0.0)
        
        # Color coding based on decision type
        color_map = {
            "exploring": "#3498db",
            "eating": "#2ecc71", 
            "moving_to_food": "#2ecc71",
            "approaching_rock": "#9b59b6",
            "throwing_rock": "#e67e22",
            "avoiding_threat": "#e74c3c",
            "organizing": "#f1c40f",
            "sleeping": "#34495e"
        }
        
        decision_color = color_map.get(decision, "#7f8c8d")
        
        # Create HTML entry
        entry = f"""
        <div style="margin: 5px 0; padding: 8px; border-left: 4px solid {decision_color}; 
                   background-color: rgba({', '.join(str(int(c)) for c in QtGui.QColor(decision_color).getRgb()[:-1])}, 0.1);">
            <div style="display: flex; justify-content: space-between;">
                <span style="font-weight: bold; color: {decision_color};">{decision.capitalize()}</span>
                <span style="color: #7f8c8d;">{timestamp}</span>
            </div>
            <div style="margin-top: 5px;">
                Confidence: <span style="font-weight: bold;">{int(confidence * 100)}%</span>
            </div>
        """
        
        # Add key details
        weights = decision_data.get('weights', {})
        adjusted_weights = decision_data.get('adjusted_weights', {})
        
        # Show top competing decisions
        competing = [(k, v) for k, v in adjusted_weights.items() 
                   if k != decision and v > 0]
        competing.sort(key=lambda x: x[1], reverse=True)
        
        if competing:
            entry += """
            <div style="margin-top: 5px; font-size: 0.9em;">
                <span style="color: #7f8c8d;">Competing options:</span>
                <span>"""
            
            for i, (action, weight) in enumerate(competing[:2]):
                if i > 0:
                    entry += ", "
                entry += f"{action} ({weight:.2f})"
            
            entry += "</span></div>"
        
        # Close the entry
        entry += "</div>"
        
        # Add to displayed log
        self.thought_log_text.append(entry)
        
        # Save to log list
        self.thought_log.append({
            'timestamp': timestamp,
            'decision': decision,
            'data': decision_data
        })
        
        # Scroll to bottom
        self.thought_log_text.verticalScrollBar().setValue(
            self.thought_log_text.verticalScrollBar().maximum()
        )

    def view_thought_logs(self):
        """Open a window to view captured decision logs"""
        if not self.thought_log:
            QtWidgets.QMessageBox.information(
                self, 
                "No Logs Available", 
                "No decision logs have been captured yet.\n\n"
                "Start logging by clicking the 'Start Logging' button "
                "and perform some actions with your squid to generate logs!"
            )
            return

        log_viewer = RecentThoughtsDialog(self.thought_log, self)
        log_viewer.exec_()

    def filter_thought_log(self):
        """Filter the thought log based on selected decision type"""
        filter_text = self.log_filter.currentText()
        
        if filter_text == "All Decisions":
            # Redisplay all logs
            self.thought_log_text.clear()
            for log_entry in self.thought_log:
                # Re-add each entry to display
                decision_data = log_entry['data']
                self.add_to_thought_log(decision_data)
        else:
            # Filter logs by decision type
            self.thought_log_text.clear()
            for log_entry in self.thought_log:
                decision = log_entry['data'].get('final_decision', '').lower()
                if filter_text.lower() in decision:
                    # Re-add matching entries
                    self.add_to_thought_log(log_entry['data'])
                    
    def _clear_layout(self, layout):
        """Utility to clear all widgets from a layout"""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()