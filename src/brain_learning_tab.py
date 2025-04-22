from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
import random
import time

class NeuralNetworkVisualizerTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
    
        # Ensure brain_widget is not None
        if brain_widget is None:
            print("WARNING: Brain widget is None. Creating a placeholder.")
            from .brain_widget import BrainWidget
            brain_widget = BrainWidget()

        # Call parent's __init__
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        
        # Explicit attribute initialization
        self.countdown_label = None
        self.countdown_timer = None
        self.activity_log = None
        self.tab_widget = None  # Updated to use tab widget
        self.edu_views = {}     # Dictionary to store QTextEdit for each tab
        self.current_countdown = 30
        self.learning_history = []
        self.recent_pairs = []
        
        self.setup_ui()

    def pre_load_data(self):
        """Pre-load data and initialize UI elements to make tab responsive on first click"""
        # Update educational content for each tab
        if hasattr(self, 'edu_views'):
            for tab_name, edu_view in self.edu_views.items():
                self.update_educational_content(tab_name=tab_name)
        
        # Pre-initialize any visualizations
        if hasattr(self, 'activity_log'):
            # Add placeholder entry to initialize rendering
            self.activity_log.insertHtml(
                '<div style="color: #555; font-style: italic; padding: 10px;">Learning system ready.</div>'
            )
        
        # Pre-compute any expensive operations that would happen on first tab selection
        if hasattr(self, 'brain_widget') and hasattr(self.brain_widget, 'weights'):
            # Process some sample data to initialize any visualizations
            sample_state = self.brain_widget.state.copy() if hasattr(self.brain_widget, 'state') else {}
            self.update_from_brain_state(sample_state)

    def create_custom_button(self, text, callback, color, font_size=18):
        """Create a button with custom styling"""
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        button.setStyleSheet(f"""
            QPushButton {{
                font-size: {font_size}px;
                padding: 4px 12px;
                border-radius: 6px;
                font-weight: 500;
                border: 2px solid {color};
                background-color: {color};
                color: white;
                min-width: 120px;
                height: 30px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color, 20)};
                border: 2px solid {self.darken_color(color, 20)};
            }}
        """)
        button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        return button

    def setup_ui(self):
        
        # Remove existing widgets from the layout
        if hasattr(self, '_layout'):
            while self.layout.count():
                item = self.layout.takeAt(0)
                if item.widget():
                    widget = item.widget()
                    self.layout.removeWidget(widget)
                    widget.deleteLater()

        # Main vertical layout
        main_layout = QtWidgets.QVBoxLayout()
        self.layout.addLayout(main_layout)

        # Splitter for main content
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(splitter)

        # Left panel - Activity Log
        log_container = QtWidgets.QWidget()
        log_layout = QtWidgets.QVBoxLayout(log_container)
        
        self.activity_log = QtWidgets.QTextEdit()
        self.activity_log.setReadOnly(True)
        self.activity_log.setStyleSheet("""
            QTextEdit {
                background-color: #f5f7fa;
                border: 2px solid #e1e5eb;
                border-radius: 12px;
                padding: 20px;
                font-size: 18px;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
        """)
        log_layout.addWidget(QtWidgets.QLabel(
            "<h1 style='font-size: 28px; margin-bottom: 15px; color: #2c3e50; font-weight: 600;'>🧠 Neural Activity Log</h1>"
        ))
        log_layout.addWidget(self.activity_log)

        # Right panel - Educational Content with Tabs
        edu_container = QtWidgets.QWidget()
        edu_layout = QtWidgets.QVBoxLayout(edu_container)
        
        # Add tab widget
        self.tab_widget = QtWidgets.QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 2px solid #e1e5eb;
                border-radius: 12px;
                background-color: #ffffff;
            }
            QTabBar::tab {
                background: #f8f9fa;
                border: 1px solid #e1e5eb;
                padding: 10px 20px;
                margin-right: 5px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: 16px;
                color: #2c3e50;
            }
            QTabBar::tab:selected {
                background: #ffffff;
                border-bottom: none;
                font-weight: 600;
            }
            QTabBar::tab:hover {
                background: #e9ecef;
            }
        """)
        
        # Create tabs
        tabs = ['Overview', 'Mechanics']
        for tab_name in tabs:
            tab_widget = QtWidgets.QWidget()
            tab_layout = QtWidgets.QVBoxLayout(tab_widget)
            
            edu_view = QtWidgets.QTextEdit()
            edu_view.setReadOnly(True)
            edu_view.setStyleSheet("""
                QTextEdit {
                    background-color: #ffffff;
                    border: none;
                    padding: 25px;
                    font-size: 18px;
                    font-family: 'Segoe UI', Arial, sans-serif;
                }
            """)
            tab_layout.addWidget(edu_view)
            self.edu_views[tab_name] = edu_view
            self.tab_widget.addTab(tab_widget, tab_name)
        
        edu_layout.addWidget(QtWidgets.QLabel(
            "<h1 style='font-size: 28px; margin-bottom: 15px; color: #2c3e50; font-weight: 600;'>📚 Learning Guide</h1>"
        ))
        edu_layout.addWidget(self.tab_widget)

        # Add to splitter
        splitter.addWidget(log_container)
        splitter.addWidget(edu_container)
        splitter.setSizes([600, 500])

        # Bottom layout for countdown label
        bottom_layout = QtWidgets.QHBoxLayout()
        self.countdown_label = QtWidgets.QLabel("Next: 30s")
        self.countdown_label.setFixedHeight(40)
        self.countdown_label.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: 500;
                color: #4dabf7;
                padding: 4px 12px;
                background-color: #f8f9fa;
                border-radius: 6px;
                border: 1px solid #e1e5eb;
                margin-right: 10px;
                min-width: 100px;
                text-align: center;
            }
        """)
        bottom_layout.addWidget(self.countdown_label)
        bottom_layout.addStretch()  # Push countdown label to the left
        main_layout.addLayout(bottom_layout)

        # Ensure splitter takes remaining space
        main_layout.setStretch(0, 1)  # Splitter gets all available space
        main_layout.setStretch(1, 0)  # Bottom layout gets minimum space

        # Setup countdown timer
        self.countdown_timer = QtCore.QTimer(self)
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)

        # Set initial content
        self.update_educational_content()


    def setup_timer(self):
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)

    def update_countdown(self):
        try:
            # Ensure countdown_label exists
            if not hasattr(self, 'countdown_label') or self.countdown_label is None:
                print("Countdown label not initialized")
                return

            # Try to get countdown from brain widget
            if hasattr(self, 'brain_widget') and hasattr(self.brain_widget, 'hebbian_countdown_seconds'):
                self.current_countdown = self.brain_widget.hebbian_countdown_seconds
            else:
                # Fallback to default countdown
                self.current_countdown = 30
            
            # Update label
            self.countdown_label.setText(f"Next: {self.current_countdown}s")
            
            # Color styling based on countdown
            if self.current_countdown <= 5:
                self.countdown_label.setStyleSheet("""
                    QLabel {
                        color: #e74c3c;
                        background-color: #f8f9fa;
                        border: 1px solid #e1e5eb;
                        font-size: 18px;
                        font-weight: 500;
                        padding: 4px 12px;
                        border-radius: 6px;
                    }
                """)
            else:
                self.countdown_label.setStyleSheet("""
                    QLabel {
                        color: #4dabf7;
                        background-color: #f8f9fa;
                        border: 1px solid #e1e5eb;
                        font-size: 18px;
                        font-weight: 500;
                        padding: 4px 12px;
                        border-radius: 6px;
                    }
                """)
        except Exception as e:
            print(f"Error in update_countdown: {e}")

    def darken_color(self, hex_color, percent):
        """Darken a hex color by specified percentage"""
        color = QtGui.QColor(hex_color)
        return color.darker(100 + percent).name()

    def create_neuron_card(self, neuron_name, is_left=True):
        """Create a playing card style neuron display with improved contrast"""
        colors = {
            "hunger": "#f39c12",
            "happiness": "#2ecc71",
            "cleanliness": "#3498db",
            "sleepiness": "#9b59b6",
            "satisfaction": "#e74c3c",
            "anxiety": "#f1c40f",
            "curiosity": "#1abc9c"
        }
        
        base_color = colors.get(neuron_name.split('_')[0], "#4dabf7")
        gradient = f"linear-gradient(135deg, {self.lighten_color(base_color, 20)}, {base_color})"
        
        return f"""
        <div style='flex: 1; text-align: center; padding: 20px; 
                    background: {gradient}; 
                    border-radius: 12px; 
                    border: 2px solid {self.darken_color(base_color, 15)};
                    box-shadow: 0 4px 8px rgba(0,0,0,0.1);
                    color: #2c3e50;
                    font-size: 22px; 
                    font-weight: 600;
                    margin-{'right' if is_left else 'left'}: 10px;'>
            {neuron_name}
        </div>
        """

    def lighten_color(self, hex_color, percent):
        """Lighten a hex color by specified percentage"""
        color = QtGui.QColor(hex_color)
        return color.lighter(100 + percent).name()

    def add_log_entry(self, message, pair=None, weight_change=None):
        from .display_scaling import DisplayScaling
        
        timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
        
        if message.startswith("🟢") or message.startswith("🔴"):
            message = message[2:].strip()
        
        # Base card HTML with increased margin for vertical gap
        entry = f"""
        <div style='margin-bottom: {DisplayScaling.scale(30)}px; border-radius: {DisplayScaling.scale(12)}px; overflow: hidden;
                box-shadow: 0 {DisplayScaling.scale(3)}px {DisplayScaling.scale(12)}px rgba(0,0,0,0.1);'>
        """
        
        # Add timestamp header
        entry += f"""
            <div style='background-color: #2c3e50; color: white; padding: {DisplayScaling.scale(12)}px {DisplayScaling.scale(15)}px; 
                    font-size: {DisplayScaling.font_size(14)}px;'>
               <br> 🕒 {timestamp} 
            </div>
        """
        
        # Add connection visualization if we have a pair
        if pair:
            weight = getattr(self.brain_widget, 'weights', {}).get(pair, 0)
            is_positive = weight > 0
            
            # Determine colors based on connection type
            bg_color = "#e8f5e9" if is_positive else "#ffebee"  # Pastel green or red
            text_color = "#2e7d32" if is_positive else "#c62828"  # Darker green or red
            icon = "🟢" if is_positive else "🔴"
            arrow = "→" if is_positive else "⊣"
            
            # Main card content with requested format and scaled sizes
            entry += f"""
            <div style='background-color: {bg_color}; padding: {DisplayScaling.scale(15)}px; color: #333;'>
                <div style='font-size: {DisplayScaling.font_size(20)}px; font-weight: bold; margin-bottom: {DisplayScaling.scale(12)}px;'>
                    {icon} {message}
                </div>
                
                <div style='font-size: {DisplayScaling.font_size(22)}px; font-weight: bold; text-align: center; margin: {DisplayScaling.scale(15)}px 0;'>
                    {pair[0]} & {pair[1]}
                </div>
                
                <div style='font-size: {DisplayScaling.font_size(26)}px; text-align: center; color: {text_color}; margin: {DisplayScaling.scale(12)}px 0;'>
                    {arrow} {weight:.2f}
                </div>
            </div>
            """
        else:
            # Simple message without pair
            entry += f"""
            <div style='background-color: #f5f5f5; padding: {DisplayScaling.scale(15)}px;'>
                <div style='color: #2c3e50; font-size: {DisplayScaling.font_size(18)}px;'>
                    {message}
                </div>
            </div>
            """
        
        # Close the entry div
        entry += "</div>"
        
        # Insert the formatted entry
        self.activity_log.insertHtml(entry)
        
        # Update tracking
        if pair:
            if not hasattr(self, 'learning_history'):
                self.learning_history = []
            if not hasattr(self, 'recent_pairs'):
                self.recent_pairs = []
                
            self.learning_history.append(pair)
            self.recent_pairs.append(pair)
            self.update_educational_content(pair=pair)
        
        # Auto-scroll
        self.activity_log.verticalScrollBar().setValue(
            self.activity_log.verticalScrollBar().maximum()
        )

    def clear_log(self):
        self.activity_log.clear()
        self.recent_pairs = []
        self.update_educational_content()
        self.add_log_entry("📭 Log cleared")

    def update_educational_content(self, pair=None, tab_name=None):
        # Define content for each tab
        tab_contents = {
            'Overview': """
                <div style='font-size: 18px; line-height: 1.6; color: #4a5568;'>
                    <div style='display: flex; align-items: center; margin-bottom: 15px;'>
                        <div style='font-size: 28px; margin-right: 15px;'>⚡</div>
                        <div><b>"Neurons that fire together, wire together"</b></div>
                    </div>
                    <p style='margin-bottom: 20px;'>
                        Hebbian learning is a simple rule used in artificial neural networks to help them learn patterns. When two neurons activate at the same time, the connection (or weight) between them gets stronger. If they activate separately, the connection weakens. This process allows the network to associate related ideas, like linking 'hunger' to 'satisfaction' when the squid is fed, without complex calculations like those used in other methods.
                    </p>
                    <ul style='list-style-type: none; padding-left: 0;'>
                        <li style='display: flex; align-items: center; margin-bottom: 10px;'>
                            <span style='font-size: 24px; margin-right: 10px;'>🟢</span>
                            <span><b>Excitatory Connections:</b> Positive weights (0.0–1.0) make neurons more likely to activate together.</span>
                        </li>
                        <li style='display: flex; align-items: center; margin-bottom: 10px;'>
                            <span style='font-size: 24px; margin-right: 10px;'>🔴</span>
                            <span><b>Inhibitory Connections:</b> Negative weights (-1.0–0.0) reduce the chance of neurons activating together.</span>
                        </li>
                    </ul>
                </div>
            """,
            'Mechanics': """
                <div style='font-size: 18px; line-height: 1.6; color: #4a5568;'>
                    <p style='margin-bottom: 20px;'>
                        Hebbian learning updates the connection strength (weight) between neurons based on their activity. When two neurons activate together, their connection strengthens; if they activate separately, it weakens. This process helps the network learn patterns, like associating 'curiosity' with 'anxiety' in the squid's brain.
                    </p>
                    <h3 style='color: #2c3e50; font-size: 20px; margin: 15px 0 10px;'>The Learning Rule</h3>
                    <p style='margin-bottom: 15px;'>
                        The basic Hebbian rule can be written as: <b>Δw = η * x * y</b>, where:
                    </p>
                    <ul style='list-style-type: none; padding-left: 0;'>
                        <li style='display: flex; align-items: center; margin-bottom: 10px;'>
                            <span style='font-size: 24px; margin-right: 10px;'>🔢</span>
                            <span><b>Δw</b> is the change in weight between two neurons.</span>
                        </li>
                        <li style='display: flex; align-items: center; margin-bottom: 10px;'>
                            <span style='font-size: 24px; margin-right: 10px;'>⚙️</span>
                            <span><b>η</b> (eta) is the learning rate, controlling how fast the weight changes.</span>
                        </li>
                        <li style='display: flex; align-items: center; margin-bottom: 10px;'>
                            <span style='font-size: 24px; margin-right: 10px;'>🔥</span>
                            <span><b>x</b> and <b>y</b> are the activation values of the two neurons (e.g., 1 if active, 0 if not).</span>
                        </li>
                    </ul>
                    <p style='margin: 15px 0;'>
                        <b>Example:</b> If 'hunger' and 'satisfaction' both activate (x=1, y=1) with η=0.1, the weight increases by 0.1. If only one activates (x=1, y=0), the weight doesn't change. Over time, this strengthens connections for related patterns.
                    </p>
                </div>
            """
        }

        # Add recent pair visualization if provided
        pair_html = ""
        if pair:
            weight = getattr(self.brain_widget, 'weights', {}).get(pair, 0)
            weight_color = "#2ecc71" if weight > 0 else "#e74c3c"
            
            pair_html = f"""
                <div style='margin: 25px 0;'>
                    <div style='font-size: 20px; color: #4a5568; margin-bottom: 15px;'>
                        Current Learning Pair:
                    </div>
                    <div style='display: flex; justify-content: center; gap: 20px;'>
                        {self.create_neuron_card(pair[0], True)}
                        <div style='display: flex; flex-direction: column; justify-content: center; 
                                    align-items: center; gap: 5px;'>
                            <div style='font-size: 28px; color: #4dabf7;'>⇄</div>
                            <div style='font-size: 18px; color: {weight_color}; font-weight: 600;'>
                                {weight:.2f}
                            </div>
                        </div>
                        {self.create_neuron_card(pair[1], False)}
                    </div>
                </div>
            """

        # Update specific tab or all tabs
        tabs_to_update = [tab_name] if tab_name else self.edu_views.keys()
        for tab_name in tabs_to_update:
            edu_view = self.edu_views[tab_name]
            html = f"""
                <div style='margin-bottom: 30px;'>
                    <div style='background: #ffffff; border-radius: 12px; padding: 25px; 
                                box-shadow: 0 4px 12px rgba(0,0,0,0.08);'>
                        <h2 style='color: #2c3e50; margin: 0 0 20px 0; font-size: 24px; font-weight: 600;'>
                            🧬 Hebbian Learning - {tab_name}
                        </h2>
                        {tab_contents[tab_name]}
                        {pair_html}
                    </div>
                </div>
            """
            edu_view.setHtml(html)

    def update_from_brain_state(self, state):
        if hasattr(self.brain_widget, 'recently_updated_neuron_pairs'):
            for pair in self.brain_widget.recently_updated_neuron_pairs:
                if pair not in self.learning_history:
                    self.learning_history.append(pair)
                    weight = getattr(self.brain_widget, 'weights', {}).get(pair, 0)
                    
                    # Determine if weight increased or decreased
                    prev_weight = self.brain_widget.weights.get(pair, 0)
                    weight_change = None
                    if weight > prev_weight:
                        weight_change = "increase"
                    elif weight < prev_weight:
                        weight_change = "decrease"
                    
                    weight_type = "strengthened" if weight > 0 else "weakened"
                    weight_icon = "🟢" if weight > 0 else "🔴"
                    
                    self.add_log_entry(
                        f"{weight_icon} <b>New connection {weight_type}</b><br>"
                        f"{weight:.2f}</span>", 
                        pair,
                        weight_change
                    )

    def simulate_learning(self):
        sample_pairs = [
            ("hunger", "satisfaction"),
            ("curiosity", "anxiety"),
            ("happiness", "cleanliness")
        ]
        for pair in sample_pairs:
            if not hasattr(self.brain_widget, 'weights'):
                self.brain_widget.weights = {}
            
            prev_weight = self.brain_widget.weights.get(pair, 0)
            self.brain_widget.weights[pair] = random.uniform(-1, 1)
            weight = self.brain_widget.weights[pair]
            
            # Determine if weight increased or decreased
            weight_change = None
            if weight > prev_weight:
                weight_change = "increase"
            elif weight < prev_weight:
                weight_change = "decrease"
            
            weight_type = "strengthened" if weight > 0 else "weakened"
            weight_icon = "🟢" if weight > 0 else "🔴"
            
            self.add_log_entry(
                f"🧪 <b>Simulated learning</b> ({weight_type})<br>"
                f"{weight:.2f}</span>", 
                pair,
                weight_change
            )
        self.update_educational_content(pair=sample_pairs[-1])