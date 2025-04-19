import time
import json
import csv
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab

class LearningTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.learning_data = []
        self.initialize_ui()
        
    def initialize_ui(self):
        """Initialize a completely redesigned learning tab with rich, informative content"""
        # Main container layout
        learning_layout = QtWidgets.QVBoxLayout()

        # Increase global font size for entire tab
        self.setStyleSheet("""
            QLabel, QGroupBox, QTextEdit, QPushButton, QLineEdit, QComboBox, QTableWidget {
                font-size: 14px;
            }

            QTableWidget {
                gridline-color: #d0d0d0;
            }
        """)

        # Create header with controls
        header_widget = QtWidgets.QWidget()
        header_layout = QtWidgets.QHBoxLayout(header_widget)
        header_layout.setContentsMargins(10, 10, 10, 5)

        # Create countdown display with stylish formatting
        self.countdown_frame = QtWidgets.QFrame()
        self.countdown_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.countdown_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border-radius: 8px;
                border: 1px solid #d0d0d0;
            }
            QLabel {
                font-size: 16px;
            }
        """)
        countdown_layout = QtWidgets.QVBoxLayout(self.countdown_frame)

        countdown_title = QtWidgets.QLabel("Next Learning Cycle")
        countdown_title.setStyleSheet("font-weight: bold; color: #444; font-size: 16px;")
        countdown_layout.addWidget(countdown_title)

        self.countdown_label = QtWidgets.QLabel("-- seconds")
        self.countdown_label.setStyleSheet("""
            font-size: 24px;
            font-weight: bold;
            color: #2c3e50;
            padding: 5px;
        """)
        self.countdown_label.setAlignment(QtCore.Qt.AlignCenter)
        countdown_layout.addWidget(self.countdown_label)

        # Add the countdown frame to header
        header_layout.addWidget(self.countdown_frame, 2)

        # Add spacer
        header_layout.addSpacing(15)

        # Create interval control with stylish formatting
        interval_frame = QtWidgets.QFrame()
        interval_frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        interval_frame.setStyleSheet("""
            QFrame {
                background-color: #f0f0f0;
                border-radius: 8px;
                border: 1px solid #d0d0d0;
            }
            QLabel {
                font-size: 16px;
            }
        """)
        interval_layout = QtWidgets.QVBoxLayout(interval_frame)

        interval_title = QtWidgets.QLabel("Learning Interval")
        interval_title.setStyleSheet("font-weight: bold; color: #444; font-size: 16px;")
        interval_layout.addWidget(interval_title)

        interval_control = QtWidgets.QHBoxLayout()
        self.interval_spinbox = QtWidgets.QSpinBox()
        self.interval_spinbox.setRange(5, 300)  # 5 sec to 5 min
        self.interval_spinbox.setValue(int(self.config.hebbian.get('learning_interval', 30000) / 1000))
        self.interval_spinbox.setSuffix(" sec")
        self.interval_spinbox.setStyleSheet("""
            QSpinBox {
                font-size: 18px;
                padding: 4px;
                background-color: white;
                border-radius: 4px;
            }
        """)
        self.interval_spinbox.valueChanged.connect(self.update_learning_interval)
        interval_control.addWidget(self.interval_spinbox)

        # Add apply button
        apply_button = QtWidgets.QPushButton("Apply")
        apply_button.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
                padding: 5px 10px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        apply_button.clicked.connect(lambda: self.update_learning_interval(self.interval_spinbox.value()))
        interval_control.addWidget(apply_button)

        interval_layout.addLayout(interval_control)

        # Add the interval frame to header
        header_layout.addWidget(interval_frame, 2)

        # Add header to main layout
        learning_layout.addWidget(header_widget)

        # Add status indicator for learning state
        self.learning_status = QtWidgets.QLabel("Learning Status: Inactive")
        self.learning_status.setStyleSheet("""
            font-size: 16px;
            padding: 5px;
            background-color: #f8f9fa;
            border-radius: 4px;
            border: 1px solid #e9ecef;
            color: #495057;
        """)
        self.learning_status.setAlignment(QtCore.Qt.AlignCenter)
        #learning_layout.addWidget(self.learning_status)

        # Create tab widget for detailed information
        self.learning_tabs = QtWidgets.QTabWidget()

        # Increase font size for tab labels to match subtab style
        self.learning_tabs.setStyleSheet("""
            QTabBar::tab {
                font-size: 16px;
                padding: 8px 16px;
                margin-right: 2px;
            }
        """)

        # Tab 1: Recent Activity
        self.recent_activity_tab = QtWidgets.QWidget()
        recent_layout = QtWidgets.QVBoxLayout(self.recent_activity_tab)

        self.activity_log = QtWidgets.QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setAcceptRichText(True)
        self.activity_log.setStyleSheet("font-size: 16px;")
        recent_layout.addWidget(self.activity_log)

        #self.learning_tabs.addTab(self.recent_activity_tab, "Recent Activity")

        # Tab 2: Neuron Connections
        self.connections_tab = QtWidgets.QWidget()
        connections_layout = QtWidgets.QVBoxLayout(self.connections_tab)

        # Add filter controls
        filter_layout = QtWidgets.QHBoxLayout()
        filter_label = QtWidgets.QLabel("Filter:")
        filter_label.setStyleSheet("font-size: 16px;")
        filter_layout.addWidget(filter_label)

        self.connection_filter = QtWidgets.QComboBox()
        self.connection_filter.addItems(["All Connections", "Strong Positive", "Strong Negative", "Weak Connections", "New Connections"])
        self.connection_filter.setStyleSheet("font-size: 16px;")
        self.connection_filter.currentIndexChanged.connect(self.filter_connections)
        filter_layout.addWidget(self.connection_filter)

        self.connection_search = QtWidgets.QLineEdit()
        self.connection_search.setPlaceholderText("Search neurons...")
        self.connection_search.setStyleSheet("font-size: 16px;")
        self.connection_search.textChanged.connect(self.filter_connections)
        filter_layout.addWidget(self.connection_search)

        connections_layout.addLayout(filter_layout)

        # Create the connection visualization view
        self.connections_view = QtWidgets.QTableWidget()
        self.connections_view.setColumnCount(4)
        self.connections_view.setHorizontalHeaderLabels(["Source", "Target", "Weight", "Trend"])
        self.connections_view.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        self.connections_view.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        self.connections_view.setStyleSheet("""
            QTableWidget {
                font-size: 16px;
            }
            QHeaderView::section {
                font-size: 16px;
                font-weight: bold;
                padding: 5px;
            }
        """)
        self.connections_view.itemSelectionChanged.connect(self.show_connection_details)
        connections_layout.addWidget(self.connections_view)

        # Add section for connection details
        connection_detail_box = QtWidgets.QGroupBox("Connection Details")
        connection_detail_box.setStyleSheet("font-size: 16px;")
        detail_layout = QtWidgets.QVBoxLayout(connection_detail_box)
        self.connection_details = QtWidgets.QTextEdit()
        self.connection_details.setReadOnly(True)
        self.connection_details.setMaximumHeight(200)
        self.connection_details.setStyleSheet("font-size: 16px;")
        detail_layout.addWidget(self.connection_details)
        connections_layout.addWidget(connection_detail_box)

        self.learning_tabs.addTab(self.connections_tab, "Neuron Connections")

        # Tab 3: Weight Heatmap
        self.heatmap_tab = QtWidgets.QWidget()
        heatmap_layout = QtWidgets.QVBoxLayout(self.heatmap_tab)

        # Heatmap view setup
        self.heatmap_view = QtWidgets.QGraphicsView()
        self.heatmap_scene = QtWidgets.QGraphicsScene()
        self.heatmap_view.setScene(self.heatmap_scene)
        self.heatmap_view.setRenderHint(QtGui.QPainter.Antialiasing)
        self.heatmap_view.setMinimumSize(512, 512)

        # Controls layout
        controls_layout = QtWidgets.QHBoxLayout()

        # Refresh button
        self.refresh_heatmap_btn = QtWidgets.QPushButton("Refresh Heatmap")
        self.refresh_heatmap_btn.clicked.connect(self.update_heatmap)
        controls_layout.addWidget(self.refresh_heatmap_btn)

        # Color legend explanation
        legend_label = QtWidgets.QLabel(
            "Color Legend: Blue = Positive weights, Red = Negative weights, Darker = Stronger"
        )
        legend_label.setWordWrap(True)
        controls_layout.addWidget(legend_label)

        # Add components to tab
        heatmap_layout.addLayout(controls_layout)
        heatmap_layout.addWidget(self.heatmap_view)

        # Initialize heatmap if brain widget exists
        if hasattr(self, 'brain_widget'):
            self.update_heatmap()
        else:
            self.heatmap_scene.addText("Waiting for brain initialization...",
                                    QtGui.QFont(),
                                    QtCore.QPointF(50, 50))

        self.learning_tabs.addTab(self.heatmap_tab, "Weight Heatmap")

        # =====================================================================
        self.stats_tab = QtWidgets.QWidget()
        stats_layout = QtWidgets.QVBoxLayout(self.stats_tab)

        # Apply larger font size to all Statistics tab components
        self.stats_tab.setStyleSheet("""
            QGroupBox {
                font-size: 20px;  /* Increase the font size for group boxes */
            }
            QGroupBox::title {
                font-size: 22px;  /* Increase the font size for group box titles */
                font-weight: bold;
            }
            QLabel {
                font-size: 20px;  /* Increase the font size for labels */
            }
            QScrollArea {
                font-size: 20px;  /* Ensure scroll area content also has increased font size */
            }
        """)

        self.stats_scroll = QtWidgets.QScrollArea()
        self.stats_scroll.setWidgetResizable(True)
        self.stats_content = QtWidgets.QWidget()
        self.stats_box_layout = QtWidgets.QVBoxLayout(self.stats_content)

        # Will be populated in update_learning_statistics()

        self.stats_scroll.setWidget(self.stats_content)
        stats_layout.addWidget(self.stats_scroll)

        self.learning_tabs.addTab(self.stats_tab, "Statistics")

        # Add the tabs to the main layout
        learning_layout.addWidget(self.learning_tabs, 1)

        # Control buttons
        buttons_layout = QtWidgets.QHBoxLayout()

        self.force_learn_btn = QtWidgets.QPushButton("Trigger Learning Cycle")
        self.force_learn_btn.setStyleSheet("""
            QPushButton {
                background-color: #2ecc71;
                color: white;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #27ae60;
            }
        """)
        self.force_learn_btn.clicked.connect(self.trigger_learning_cycle)
        #buttons_layout.addWidget(self.force_learn_btn)

        self.export_btn = QtWidgets.QPushButton("Export Data")
        self.export_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.export_btn.clicked.connect(self.export_learning_data)
        buttons_layout.addWidget(self.export_btn)

        self.clear_log_btn = QtWidgets.QPushButton("Clear Log")
        self.clear_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border-radius: 4px;
                padding: 8px;
                font-weight: bold;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
        """)
        self.clear_log_btn.clicked.connect(self.clear_learning_log)
        buttons_layout.addWidget(self.clear_log_btn)

        learning_layout.addLayout(buttons_layout)

        # Create widget to hold the layout
        learning_widget = QtWidgets.QWidget()
        learning_widget.setLayout(learning_layout)
        self.layout.addWidget(learning_widget)

        # Initialize the views
        self.update_connection_table()
        self.update_heatmap()
        self.update_learning_statistics()

        # Initial status update
        self.update_learning_status(self.brain_widget.learning_active)
        
        # Initialize previous weights dictionary for trend tracking
        self._prev_weights = {}

    def update_from_brain_state(self, state):
        """Update based on brain state changes"""
        self.update_learning_status(self.brain_widget.learning_active)
        
        # Only update tables/visualizations occasionally to prevent performance issues
        current_time = time.time()
        if not hasattr(self, 'last_update_time'):
            self.last_update_time = 0
            
        if current_time - self.last_update_time > 5:  # Update every 5 seconds
            self.last_update_time = current_time
            
            if hasattr(self, 'connections_view'):
                self.update_connection_table()
            
            if hasattr(self, 'heatmap_scene'):
                self.update_heatmap()
                
            if hasattr(self, 'stats_box_layout'):
                self.update_learning_statistics()

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
        if hasattr(self.parent, 'hebbian_timer'):
            self.parent.hebbian_timer.setInterval(interval_ms)
            self.brain_widget.last_hebbian_time = time.time()  # Reset countdown
        
        # Log the change
        self.activity_log.append(f"""
        <div style="background-color: #e8f4f8; padding: 8px; margin: 5px; border-radius: 5px;">
            <span style="font-weight: bold;">Learning interval updated</span><br>
            New interval: {seconds} seconds ({interval_ms} ms)
        </div>
        """)

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

        # Updated loop to handle different key formats safely
        for key, weight in sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True):
            # Handle different key formats safely
            if isinstance(key, tuple) and len(key) >= 2:
                source, target = key[0], key[1]
            elif isinstance(key, str) and '_' in key:
                # For string keys that might have been converted from tuples
                parts = key.split('_', 1)  # Split on first underscore only
                source, target = parts[0], parts[1]
            else:
                # Skip invalid keys
                continue

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
            source_item.setFont(QtGui.QFont("Arial", 12))  # Bigger font size
            self.connections_view.setItem(row, 0, source_item)

            # Target neuron
            target_item = QtWidgets.QTableWidgetItem(target)
            if target in self.brain_widget.neurogenesis_data.get('new_neurons', []):
                target_item.setBackground(QtGui.QColor(255, 255, 200))
            target_item.setFont(QtGui.QFont("Arial", 12))  # Bigger font size
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
            weight_item.setFont(QtGui.QFont("Arial", 12))  # Bigger font size
            self.connections_view.setItem(row, 2, weight_item)

            # Trend indicator with emoji arrows
            trend_item = QtWidgets.QTableWidgetItem("—")
            if hasattr(self, '_prev_weights') and (source, target) in self._prev_weights:
                prev = self._prev_weights.get((source, target), 0)
                if weight > prev + 0.01:
                    trend_item = QtWidgets.QTableWidgetItem("⬆️")  # Up emoji arrow
                elif weight < prev - 0.01:
                    trend_item = QtWidgets.QTableWidgetItem("⬇️")  # Down emoji arrow
            trend_item.setFont(QtGui.QFont("Arial", 14))  # Bigger font size
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
        <div style="font-family: Arial, sans-serif;">
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
        self.connection_details.setHtml(details_html)

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
            title_label.setStyleSheet("font-weight: bold; font-size: 16px; color: #212529;")
            title_layout.addWidget(title_label)
            title_layout.addStretch()
            
            box_layout.addLayout(title_layout)
            
            # Add content
            content_widget = QtWidgets.QLabel(content)
            content_widget.setTextFormat(QtCore.Qt.RichText)
            content_widget.setWordWrap(True)
            content_widget.setStyleSheet("font-size: 16px; color: #343a40; margin: 5px;")
            box_layout.addWidget(content_widget)
            
            self.stats_box_layout.addWidget(box)
        
        # 1. Connection Statistics
        # Filter weights to exclude connections involving blacklisted neurons
        # FIXED CODE HERE:
        filtered_weights = {}
        for key, weight in self.brain_widget.weights.items():
            # Handle different key formats safely
            if isinstance(key, tuple) and len(key) >= 2:
                src, dst = key[0], key[1]
            elif isinstance(key, str) and '_' in key:
                # For string keys that might have been converted from tuples
                parts = key.split('_', 1)  # Split on first underscore only
                src, dst = parts[0], parts[1]
            else:
                # Skip invalid keys
                continue
                
            # Only include pairs where neither neuron is excluded
            if src not in excluded_neurons and dst not in excluded_neurons:
                filtered_weights[(src, dst)] = weight
        
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
        all_neurons = self.brain_widget.neuron_positions.keys()
        neurons = [n for n in all_neurons if n not in excluded_neurons]
        original_neurons = [n for n in neurons if n in getattr(self.brain_widget, 'original_neuron_positions', {})]
        new_neurons = [n for n in neurons if n in self.brain_widget.neurogenesis_data.get('new_neurons', [])]
        
        neuron_stats = f"""
        <table style='width:100%; margin-top:5px;'>
            <tr>
                <td style='padding:3px;'><b>Learning-Eligible Neurons:</b></td>
                <td style='padding:3px;'>{len(neurons)}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Original Core Neurons:</b></td>
                <td style='padding:3px;'>{len(original_neurons)}</td>
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

    def clear_learning_log(self):
        """Clear the activity log"""
        reply = QtWidgets.QMessageBox.question(
            self, "Clear Log", 
            "Are you sure you want to clear the learning activity log?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.activity_log.clear()

    def export_learning_data(self):
        """Export learning data with all available information"""
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Learning Data", "", "HTML Files (*.html);;CSV Files (*.csv);;Text Files (*.txt)")
        
        if not file_name:
            return
            
        try:
            if file_name.endswith('.html'):
                self.export_learning_data_html(file_name)
            elif file_name.endswith('.csv'):
                self.export_learning_data_csv(file_name)
            else:
                self.export_learning_data_text(file_name)
                
            # Show success message
            QtWidgets.QMessageBox.information(
                self, "Export Successful", f"Learning data exported to {file_name}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Export Error", f"Error exporting data: {str(e)}")

    def export_learning_data_html(self, file_name):
        """Export learning data as rich HTML report"""
        with open(file_name, 'w') as f:
            # Start HTML document
            f.write("""<!DOCTYPE html>
            <html>
            <head>
                <title>Squid Brain Learning Data</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }
                    h1, h2, h3 { color: #2c3e50; }
                    table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
                    th { background-color: #f2f2f2; }
                    tr:hover { background-color: #f5f5f5; }
                    .positive { color: green; }
                    .negative { color: red; }
                    .stats-box { background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin: 15px 0; }
                    .stats-title { font-weight: bold; font-size: 18px; margin-bottom: 10px; }
                    .heatmap { overflow-x: auto; }
                </style>
            </head>
            <body>
                <h1>Squid Brain Learning Data</h1>
                <p>Export time: """ + time.strftime("%Y-%m-%d %H:%M:%S") + """</p>
            """)
            
            # Learning parameters
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Learning Parameters</div>
                    <table>
                        <tr>
                            <th>Parameter</th>
                            <th>Value</th>
                        </tr>
            """)
            
            if hasattr(self.config, 'hebbian'):
                for param, value in self.config.hebbian.items():
                    if param == 'learning_interval':
                        value = f"{value/1000} seconds"
                    f.write(f"<tr><td>{param}</td><td>{value}</td></tr>")
            
            f.write("""
                    </table>
                </div>
            """)
            
            # Neuron information
            neurons = sorted(self.brain_widget.neuron_positions.keys())
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Neurons</div>
                    <p>Total neurons: """ + str(len(neurons)) + """</p>
                    <table>
                        <tr>
                            <th>Neuron</th>
                            <th>Position</th>
                            <th>Type</th>
                            <th>Current Value</th>
                        </tr>
            """)
            
            for neuron in neurons:
                neuron_type = "Original" if neuron in getattr(self.brain_widget, 'original_neuron_positions', {}) else "New"
                value = self.brain_widget.state.get(neuron, 0)
                position = self.brain_widget.neuron_positions.get(neuron, (0, 0))
                
                f.write(f"""
                    <tr>
                        <td>{neuron}</td>
                        <td>({position[0]:.1f}, {position[1]:.1f})</td>
                        <td>{neuron_type}</td>
                        <td>{value:.1f}</td>
                    </tr>
                """)
            
            f.write("""
                    </table>
                </div>
            """)
            
            # Connection weights
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Connection Weights</div>
                    <p>Total connections: """ + str(len(self.brain_widget.weights)) + """</p>
                    <table>
                        <tr>
                            <th>Source</th>
                            <th>Target</th>
                            <th>Weight</th>
                        </tr>
            """)
            
            for (source, target), weight in sorted(self.brain_widget.weights.items(), key=lambda x: abs(x[1]), reverse=True):
                weight_class = "positive" if weight > 0 else "negative"
                f.write(f"""
                    <tr>
                        <td>{source}</td>
                        <td>{target}</td>
                        <td class="{weight_class}">{weight:.3f}</td>
                    </tr>
                """)
            
            f.write("""
                    </table>
                </div>
            """)
            
            # Simple text-based heatmap
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Weight Heatmap (Text Representation)</div>
                    <p>This is a simplified text representation of the weight matrix.</p>
                    <div class="heatmap">
                        <table>
                            <tr>
                                <th>Source / Target</th>
            """)
            
            # Column headers
            for neuron in neurons:
                f.write(f"<th>{neuron}</th>")
            
            f.write("</tr>")
            
            # Rows with data
            for src in neurons:
                f.write(f"<tr><th>{src}</th>")
                
                for dst in neurons:
                    if src == dst:
                        f.write("<td style='background-color: #f0f0f0;'>—</td>")
                    else:
                        weight = self.brain_widget.weights.get((src, dst), 
                                self.brain_widget.weights.get((dst, src), 0))
                        
                        # Style based on weight
                        if weight > 0:
                            intensity = min(255, int(weight * 255))
                            bg_color = f"rgba(0, {intensity}, 0, 0.2)"
                            text_color = "green"
                        else:
                            intensity = min(255, int(abs(weight) * 255))
                            bg_color = f"rgba({intensity}, 0, 0, 0.2)"
                            text_color = "red"
                        
                        f.write(f"<td style='background-color: {bg_color}; color: {text_color};'>{weight:.2f}</td>")
                
                f.write("</tr>")
            
            f.write("""
                        </table>
                    </div>
                </div>
            """)
            
            # End HTML document
            f.write("""
            </body>
            </html>
            """)

    def export_learning_data_csv(self, file_name):
        """Export learning data as CSV"""
        with open(file_name, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write neurons section
            writer.writerow(["NEURONS"])
            writer.writerow(["Neuron", "Position X", "Position Y", "Type", "Current Value"])
            
            for neuron in sorted(self.brain_widget.neuron_positions.keys()):
                neuron_type = "Original" if neuron in getattr(self.brain_widget, 'original_neuron_positions', {}) else "New"
                value = self.brain_widget.state.get(neuron, 0)
                position = self.brain_widget.neuron_positions.get(neuron, (0, 0))
                
                writer.writerow([neuron, position[0], position[1], neuron_type, value])
            
            # Blank row
            writer.writerow([])
            
            # Write connections section
            writer.writerow(["CONNECTIONS"])
            writer.writerow(["Source", "Target", "Weight"])
            
            for (source, target), weight in sorted(self.brain_widget.weights.items(), key=lambda x: abs(x[1]), reverse=True):
                writer.writerow([source, target, weight])
            
            # Blank row
            writer.writerow([])
            
            # Write learning parameters
            writer.writerow(["LEARNING PARAMETERS"])
            if hasattr(self.config, 'hebbian'):
                for param, value in self.config.hebbian.items():
                    writer.writerow([param, value])

    def export_learning_data_text(self, file_name):
        """Export learning data as plain text"""
        with open(file_name, 'w') as f:
            f.write("SQUID BRAIN LEARNING DATA\n")
            f.write("=========================\n")
            f.write(f"Export time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Learning parameters
            f.write("LEARNING PARAMETERS\n")
            f.write("-----------------\n")
            if hasattr(self.config, 'hebbian'):
                for param, value in self.config.hebbian.items():
                    if param == 'learning_interval':
                        value = f"{value/1000} seconds"
                    f.write(f"{param}: {value}\n")
            
            f.write("\n")
            
            # Neuron information
            neurons = sorted(self.brain_widget.neuron_positions.keys())
            f.write(f"NEURONS ({len(neurons)} total)\n")
            f.write("-----------------\n")
            
            for neuron in neurons:
                neuron_type = "Original" if neuron in getattr(self.brain_widget, 'original_neuron_positions', {}) else "New"
                value = self.brain_widget.state.get(neuron, 0)
                position = self.brain_widget.neuron_positions.get(neuron, (0, 0))
                
                f.write(f"{neuron}: Position ({position[0]:.1f}, {position[1]:.1f}), Type: {neuron_type}, Value: {value:.1f}\n")
            
            f.write("\n")
            
            # Connection weights
            f.write(f"CONNECTION WEIGHTS ({len(self.brain_widget.weights)} total)\n")
            f.write("-----------------\n")
            
            for (source, target), weight in sorted(self.brain_widget.weights.items(), key=lambda x: abs(x[1]), reverse=True):
                f.write(f"{source} → {target}: {weight:.3f}\n")