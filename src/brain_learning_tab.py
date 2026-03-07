from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
import random
import time
from .localisation import Localisation

try:
    from display_scaling import DisplayScaling
except ImportError:
    class DisplayScaling:
        @classmethod
        def font_size(cls, size): return size
        @classmethod
        def scale_css(cls, css): return css

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
        self.tab_widget = None
        self.edu_views = {}
        self.current_countdown = 30
        self.learning_history = []
        self.recent_pairs = []

        # Card display areas
        self.learning_scroll = None
        self.learning_content = None
        self.learning_content_layout = None

        # Blink timer for Hebbian label
        self.blink_timer = QtCore.QTimer(self)
        self.blink_timer.setInterval(500)  # 0.5 s toggle
        self.blink_timer.timeout.connect(self._blink_hebbian_label)
        self._blink_visible = True

        self.setup_ui()

    def pre_load_data(self):
        """Pre-load data and initialize UI elements to make tab responsive on first click"""
        # Update educational content for each tab
        if hasattr(self, 'edu_views'):
            for tab_name, edu_view in self.edu_views.items():
                self.update_educational_content(tab_name=tab_name)

        # Pre-initialize learning cards
        if hasattr(self, 'learning_content_layout'):
            # Add placeholder to initialize rendering
            loc = Localisation.instance()
            placeholder = self._create_info_card(
                loc.get("learning_ready"),
                loc.get("learning_ready_desc"),
                "#e3f2fd"
            )
            self.learning_content_layout.addWidget(placeholder)

        # Pre-compute any expensive operations
        if hasattr(self, 'brain_widget') and hasattr(self.brain_widget, 'weights'):
            sample_state = self.brain_widget.state.copy() if hasattr(self.brain_widget, 'state') else {}
            self.update_from_brain_state(sample_state)

    def setup_ui(self):
        loc = Localisation.instance()
        
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

        # Create tab widget for different sections
        self.tab_widget = QtWidgets.QTabWidget()
        tab_font = QtGui.QFont()
        tab_font.setPointSize(DisplayScaling.font_size(11))
        self.tab_widget.setFont(tab_font)
        self.tab_widget.setStyleSheet(f"""
            QTabWidget::pane {{
                border: 2px solid #e1e5eb;
                border-radius: 12px;
                background-color: #f8f9fa;
            }}
            QTabBar::tab {{
                background: #f8f9fa;
                border: 1px solid #e1e5eb;
                padding: 10px 20px;
                min-width: 120px;
                margin-right: 5px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                font-size: {DisplayScaling.font_size(11)}pt;
                color: #2c3e50;
            }}
            QTabBar::tab:selected {{
                background: #ffffff;
                border-bottom: none;
                font-weight: 600;
            }}
            QTabBar::tab:hover {{
                background: #e9ecef;
            }}
        """)

        # ====== LEARNING PAIRS TAB ======
        self.learning_tab = QtWidgets.QWidget()
        learning_tab_layout = QtWidgets.QVBoxLayout(self.learning_tab)

        # Header with title and Hebbian countdown
        header_layout = QtWidgets.QHBoxLayout()
        header_label = QtWidgets.QLabel(
            f"<h2 style='font-size: 24px; color: #2c3e50; font-weight: 600;'>{loc.get('active_learning_pairs')}</h2>"
        )
        header_layout.addWidget(header_label)
        header_layout.addStretch()

        # Hebbian countdown timer label
        self.hebbian_timer_label_learning = QtWidgets.QLabel(f"{loc.get('hebbian_cycle')}: --")
        self.hebbian_timer_label_learning.setStyleSheet("""
            font-size: 16px;
            font-weight: 600;
            color: #2c3e50;
            padding: 5px 10px;
            background-color: #e3f2fd;
            border-radius: 6px;
            border: 1px solid #90caf9;
        """)
        header_layout.addWidget(self.hebbian_timer_label_learning)

        learning_tab_layout.addLayout(header_layout)

        # Scroll area for learning cards
        self.learning_scroll = QtWidgets.QScrollArea()
        self.learning_scroll.setWidgetResizable(True)
        self.learning_scroll.setStyleSheet("""
            QScrollArea {
                border: none;
                background-color: #f8f9fa;
            }
        """)

        self.learning_content = QtWidgets.QWidget()
        self.learning_content_layout = QtWidgets.QVBoxLayout(self.learning_content)
        self.learning_content_layout.setSpacing(15)
        self.learning_content_layout.setContentsMargins(10, 10, 10, 10)
        self.learning_content_layout.addStretch()

        self.learning_scroll.setWidget(self.learning_content)
        learning_tab_layout.addWidget(self.learning_scroll)

        # ====== OVERVIEW TAB ======
        overview_tab = QtWidgets.QWidget()
        overview_layout = QtWidgets.QVBoxLayout(overview_tab)

        overview_scroll = QtWidgets.QScrollArea()
        overview_scroll.setWidgetResizable(True)
        overview_content = QtWidgets.QWidget()
        overview_content_layout = QtWidgets.QVBoxLayout(overview_content)

        # Create overview cards
        overview_card = self._create_educational_card(
            loc.get("hebbian_overview"),
            f"""
            <div style='font-size: 16px; line-height: 1.8; color: #4a5568;'>
                <div style='background: #e3f2fd; padding: 15px; border-radius: 8px; margin-bottom: 15px;'>
                    <div style='font-size: 20px; font-weight: bold; color: #1976d2; margin-bottom: 10px;'>
                        {loc.get("hebbian_quote")}
                    </div>
                    <p>{loc.get("hebbian_principle")}</p>
                </div>

                <p style='margin-bottom: 20px;'>
                    {loc.get("hebbian_explanation")}
                </p>

                <div style='display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin: 20px 0;'>
                    <div style='background: #e8f5e9; padding: 15px; border-radius: 8px; border-left: 4px solid #4caf50;'>
                        <div style='font-weight: bold; color: #2e7d32; margin-bottom: 5px; font-size: 18px;'>{loc.get("excitatory_connections")}</div>
                        <div style='font-size: 14px;'>{loc.get("excitatory_desc")}</div>
                    </div>

                    <div style='background: #ffebee; padding: 15px; border-radius: 8px; border-left: 4px solid #f44336;'>
                        <div style='font-weight: bold; color: #c62828; margin-bottom: 5px; font-size: 18px;'>{loc.get("inhibitory_connections")}</div>
                        <div style='font-size: 14px;'>{loc.get("inhibitory_desc")}</div>
                    </div>
                </div>

                <div style='background: #fff3e0; padding: 15px; border-radius: 8px; margin-top: 20px;'>
                    <div style='font-weight: bold; color: #e65100; margin-bottom: 10px; font-size: 18px;'>{loc.get("in_practice_title")}</div>
                    <p style='margin: 0;'>
                        {loc.get("in_practice_text")}
                    </p>
                </div>
            </div>
            """,
            "#ffffff"
        )
        overview_content_layout.addWidget(overview_card)

        overview_scroll.setWidget(overview_content)
        overview_layout.addWidget(overview_scroll)

        # ====== MECHANICS TAB ======
        mechanics_tab = QtWidgets.QWidget()
        mechanics_layout = QtWidgets.QVBoxLayout(mechanics_tab)

        mechanics_scroll = QtWidgets.QScrollArea()
        mechanics_scroll.setWidgetResizable(True)
        mechanics_content = QtWidgets.QWidget()
        mechanics_content_layout = QtWidgets.QVBoxLayout(mechanics_content)

        mechanics_card = self._create_educational_card(
            loc.get("mechanics_title"),
            f"""
            <div style='font-size: 16px; line-height: 1.8; color: #4a5568;'>
                <p style='margin-bottom: 20px;'>
                    {loc.get("mechanics_intro")}
                </p>

                <div style='background: #f3e5f5; padding: 20px; border-radius: 8px; margin: 20px 0;'>
                    <h3 style='color: #6a1b9a; margin: 0 0 15px 0; font-size: 20px;'>{loc.get("learning_rule_title")}</h3>
                    <div style='background: white; padding: 15px; border-radius: 6px; font-family: monospace; font-size: 18px; text-align: center; margin-bottom: 15px;'>
                        <b>Δw = η × x × y</b>
                    </div>
                    <p style='margin-bottom: 15px;'>{loc.get("where_label")}</p>
                    <ul style='list-style: none; padding: 0;'>
                        <li style='margin-bottom: 12px; padding-left: 10px;'>
                            {loc.get("delta_w_desc")}
                        </li>
                        <li style='margin-bottom: 12px; padding-left: 10px;'>
                            {loc.get("eta_desc")}
                        </li>
                        <li style='margin-bottom: 12px; padding-left: 10px;'>
                            {loc.get("activation_desc")}
                        </li>
                    </ul>
                </div>

                <div style='background: #e8eaf6; padding: 20px; border-radius: 8px; margin: 20px 0;'>
                    <h3 style='color: #3f51b5; margin: 0 0 15px 0; font-size: 20px;'>{loc.get("example_calc_title")}</h3>
                    <div style='background: white; padding: 15px; border-radius: 6px;'>
                        <p style='margin: 0 0 10px 0;'>{loc.get("scenario_label")}</p>
                        <ul style='list-style: none; padding: 0; margin: 10px 0;'>
                            <li>x = 1</li>
                            <li>y = 1</li>
                            <li>η = 0.1</li>
                        </ul>
                        <div style='background: #f5f5f5; padding: 10px; border-radius: 4px; margin: 10px 0;'>
                            <b>Δw = 0.1 × 1 × 1 = 0.1</b>
                        </div>
                        <p style='margin: 10px 0 0 0;'>
                            {loc.get("calc_result")}
                        </p>
                    </div>
                </div>

                <div style='background: #fce4ec; padding: 20px; border-radius: 8px;'>
                    <h3 style='color: #c2185b; margin: 0 0 15px 0; font-size: 20px;'>{loc.get("over_time_title")}</h3>
                    <p style='margin: 0;'>
                        {loc.get("over_time_text")}
                    </p>
                </div>
            </div>
            """,
            "#ffffff"
        )
        mechanics_content_layout.addWidget(mechanics_card)

        mechanics_scroll.setWidget(mechanics_content)
        mechanics_layout.addWidget(mechanics_scroll)

        # Add all tabs
        self.tab_widget.addTab(self.learning_tab, loc.get("learning_pairs_tab"))
        self.tab_widget.addTab(overview_tab, loc.get("overview"))
        self.tab_widget.addTab(mechanics_tab, loc.get("mechanics_tab"))

        main_layout.addWidget(self.tab_widget)

    def _create_educational_card(self, title, content, bg_color):
        """Create an educational information card"""
        card = QtWidgets.QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 12px;
                border: 1px solid #e1e5eb;
            }}
        """)

        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(25, 25, 25, 25)

        # Title
        title_label = QtWidgets.QLabel(f"<h2 style='color: #2c3e50; margin: 0 0 20px 0;'>{title}</h2>")
        card_layout.addWidget(title_label)

        # Content
        content_label = QtWidgets.QTextBrowser()
        content_label.setHtml(content)
        content_label.setOpenExternalLinks(True)
        content_label.setStyleSheet("""
            QTextBrowser {
                background-color: transparent;
                border: none;
                font-size: 16px;
            }
        """)
        card_layout.addWidget(content_label)

        return card

    def _create_info_card(self, title, description, color):
        """Create a simple info card"""
        card = QtWidgets.QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {color};
                border-radius: 10px;
                padding: 15px;
                border: 1px solid #dee2e6;
            }}
        """)

        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setSpacing(8)

        title_label = QtWidgets.QLabel(f"<b style='font-size: {DisplayScaling.font_size(18)}px;'>{title}</b>")
        card_layout.addWidget(title_label)

        desc_label = QtWidgets.QLabel(description)
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet(f"color: #495057; font-size: {DisplayScaling.font_size(14)}px;")
        card_layout.addWidget(desc_label)

        return card

    def _create_learning_pair_card(self, pair, weight, weight_change=None, stdp_meta=None):
        """Create a card displaying a learning pair"""
        loc = Localisation.instance()
        # Determine colors based on weight
        if weight > 0.5:
            border_color = "#4caf50"
            bg_color = "#e8f5e9"
            weight_color = "#2e7d32"
            strength = loc.get("str_excitatory")
        elif weight > 0:
            border_color = "#8bc34a"
            bg_color = "#f1f8e9"
            weight_color = "#558b2f"
            strength = loc.get("weak_excitatory")
        elif weight > -0.5:
            border_color = "#ff9800"
            bg_color = "#fff3e0"
            weight_color = "#e65100"
            strength = loc.get("weak_inhibitory")
        else:
            border_color = "#f44336"
            bg_color = "#ffebee"
            weight_color = "#c62828"
            strength = loc.get("str_inhibitory")

        # Weight change indicator
        change_indicator = ""
        if weight_change == "increase":
            change_indicator = f"<span style='color: #4caf50; font-size: {DisplayScaling.font_size(24)}px; margin-left: 10px;'>↗</span>"
        elif weight_change == "decrease":
            change_indicator = f"<span style='color: #f44336; font-size: {DisplayScaling.font_size(24)}px; margin-left: 10px;'>↘</span>"

        # STDP: resolve directional arrow and LTP/LTD info
        stdp_direction = stdp_meta.get('stdp_direction', 'none') if stdp_meta else 'none'
        if stdp_direction == 'n1_to_n2':
            arrow_char = "→"
        elif stdp_direction == 'n2_to_n1':
            arrow_char = "←"
        else:
            arrow_char = "↔"

        card = QtWidgets.QWidget()
        card.setStyleSheet(f"""
            QWidget {{
                background-color: {bg_color};
                border-radius: 12px;
                border: 2px solid {border_color};
            }}
            QWidget:hover {{
                border: 3px solid {self.darken_color(border_color, 20)};
                background-color: {self.darken_color(bg_color, 5)};
            }}
        """)

        card_layout = QtWidgets.QVBoxLayout(card)
        card_layout.setContentsMargins(25, 20, 25, 20)
        card_layout.setSpacing(10)

        # Top row - connection visualization
        connection_layout = QtWidgets.QHBoxLayout()
        connection_layout.setSpacing(20)

        # Neuron 1 - large and prominent
        neuron1_label = QtWidgets.QLabel(f"<span style='font-size: {DisplayScaling.font_size(24)}px; font-weight: bold; color: #2c3e50;'>{pair[0].upper()}</span>")
        neuron1_label.setAlignment(QtCore.Qt.AlignCenter)
        connection_layout.addWidget(neuron1_label, 1)

        # Arrow and weight - centered
        arrow_widget = QtWidgets.QWidget()
        arrow_layout = QtWidgets.QVBoxLayout(arrow_widget)
        arrow_layout.setSpacing(5)
        arrow_layout.setContentsMargins(0, 0, 0, 0)

        arrow_label = QtWidgets.QLabel(f"<span style='font-size: {DisplayScaling.font_size(36)}px; color: #607d8b;'>{arrow_char}</span>")
        arrow_label.setAlignment(QtCore.Qt.AlignCenter)
        arrow_layout.addWidget(arrow_label)

        weight_display = QtWidgets.QLabel(
            f"<span style='font-size: {DisplayScaling.font_size(20)}px; font-weight: bold; color: {weight_color};'>{weight:.3f}</span>"
        )
        weight_display.setAlignment(QtCore.Qt.AlignCenter)
        arrow_layout.addWidget(weight_display)

        connection_layout.addWidget(arrow_widget, 0)

        # Neuron 2 - large and prominent
        neuron2_label = QtWidgets.QLabel(f"<span style='font-size: {DisplayScaling.font_size(24)}px; font-weight: bold; color: #2c3e50;'>{pair[1].upper()}</span>")
        neuron2_label.setAlignment(QtCore.Qt.AlignCenter)
        connection_layout.addWidget(neuron2_label, 1)

        card_layout.addLayout(connection_layout)

        # STDP badge row (only when STDP contributed a timing signal)
        if stdp_meta and stdp_direction != 'none':
            is_ltp      = stdp_meta.get('is_ltp', False)
            is_ltd      = stdp_meta.get('is_ltd', False)
            stdp_delta  = stdp_meta.get('stdp_delta', 0.0)
            stdp_weight = stdp_meta.get('stdp_weight', 0.0)

            if is_ltp or is_ltd:
                badge_row = QtWidgets.QHBoxLayout()
                badge_row.setSpacing(8)

                # LTP / LTD pill
                if is_ltp:
                    ltp_ltd_color  = "#00897b"
                    ltp_ltd_bg     = "#e0f2f1"
                    ltp_ltd_border = "#80cbc4"
                    ltp_ltd_text   = "⚡ LTP"
                else:
                    ltp_ltd_color  = "#c62828"
                    ltp_ltd_bg     = "#ffebee"
                    ltp_ltd_border = "#ef9a9a"
                    ltp_ltd_text   = "⚡ LTD"

                badge = QtWidgets.QLabel(ltp_ltd_text)
                badge.setStyleSheet(f"""
                    font-size: {DisplayScaling.font_size(14)}px;
                    font-weight: 700;
                    color: {ltp_ltd_color};
                    background: {ltp_ltd_bg};
                    border: 1px solid {ltp_ltd_border};
                    border-radius: 4px;
                    padding: 3px 9px;
                """)
                badge_row.addWidget(badge)

                # Delta value
                sign = "+" if stdp_delta >= 0 else ""
                delta_label = QtWidgets.QLabel(
                    f"<span style='font-size: {DisplayScaling.font_size(14)}px; color: #546e7a;'>"
                    f"STDP Δ {sign}{stdp_delta:.4f} &nbsp;·&nbsp; "
                    f"blend {int(stdp_weight * 100)}% spike-timing</span>"
                )
                badge_row.addWidget(delta_label)
                badge_row.addStretch()

                card_layout.addLayout(badge_row)

        # Bottom row - metadata
        meta_layout = QtWidgets.QHBoxLayout()

        strength_label = QtWidgets.QLabel(
            f"<span style='font-size: {DisplayScaling.font_size(16)}px; font-weight: 600; color: {weight_color};'>{strength}</span>{change_indicator}"
        )
        meta_layout.addWidget(strength_label)

        meta_layout.addStretch()

        timestamp_label = QtWidgets.QLabel(
            f"<span style='color: #6c757d; font-size: {DisplayScaling.font_size(13)}px;'>{time.strftime('%H:%M:%S')}</span>"
        )
        meta_layout.addWidget(timestamp_label)

        card_layout.addLayout(meta_layout)

        return card

    def create_custom_button(self, text, callback, color, font_size=14):
        """Create a button with custom styling"""
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        button.setStyleSheet(f"""
            QPushButton {{
                font-size: {font_size}px;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: 500;
                border: 2px solid {color};
                background-color: {color};
                color: white;
                min-width: 100px;
            }}
            QPushButton:hover {{
                background-color: {self.darken_color(color, 20)};
                border: 2px solid {self.darken_color(color, 20)};
            }}
        """)
        button.setCursor(QtGui.QCursor(QtCore.Qt.PointingHandCursor))
        return button

    def darken_color(self, hex_color, percent):
        """Darken a hex color by a percentage"""
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        r = max(0, int(r * (100 - percent) / 100))
        g = max(0, int(g * (100 - percent) / 100))
        b = max(0, int(b * (100 - percent) / 100))
        return f'#{r:02x}{g:02x}{b:02x}'

    def add_log_entry(self, message, pair=None, weight_change=None, stdp_meta=None):
        """Add a new learning pair card to the display"""
        if pair and hasattr(self, 'learning_content_layout'):
            # Remove placeholder if it exists
            if self.learning_content_layout.count() == 1:
                item = self.learning_content_layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()

            # Get weight
            weight = getattr(self.brain_widget, 'weights', {}).get(pair, 0)

            # Create card
            card = self._create_learning_pair_card(pair, weight, weight_change, stdp_meta)

            # Insert at the top (before stretch)
            self.learning_content_layout.insertWidget(0, card)

            # Keep only last 20 cards
            while self.learning_content_layout.count() > 21:  # 20 cards + 1 stretch
                item = self.learning_content_layout.takeAt(20)
                if item and item.widget():
                    item.widget().deleteLater()

            # Update history
            if pair not in self.learning_history:
                self.learning_history.append(pair)
            self.recent_pairs.append(pair)

    def clear_log(self):
        """Clear all learning pair cards"""
        loc = Localisation.instance()
        if hasattr(self, 'learning_content_layout'):
            while self.learning_content_layout.count() > 1:  # Keep the stretch
                item = self.learning_content_layout.takeAt(0)
                if item and item.widget():
                    item.widget().deleteLater()

        self.recent_pairs = []
        self.learning_history = []

        # Add info card
        placeholder = self._create_info_card(
            loc.get("log_cleared"),
            loc.get("log_cleared_desc"),
            "#e3f2fd"
        )
        self.learning_content_layout.insertWidget(0, placeholder)

    def update_educational_content(self, pair=None, tab_name=None):
        """Update educational content - kept for compatibility"""
        pass

    def update_from_brain_state(self, state):
        """Update display based on brain state changes"""
        if hasattr(self.brain_widget, 'recently_updated_neuron_pairs'):
            for pair in self.brain_widget.recently_updated_neuron_pairs:
                if pair not in self.learning_history:
                    weight = getattr(self.brain_widget, 'weights', {}).get(pair, 0)

                    # Determine weight change
                    prev_weight = self.brain_widget.weights.get(pair, 0)
                    weight_change = None
                    if weight > prev_weight:
                        weight_change = "increase"
                    elif weight < prev_weight:
                        weight_change = "decrease"

                    self.add_log_entry("", pair, weight_change)

        # Sync Hebbian timer from brain_widget
        if hasattr(self.brain_widget, 'hebbian_countdown_seconds'):
            self.update_hebbian_label_learning(self.brain_widget.hebbian_countdown_seconds)

    def update_hebbian_label_learning(self, value):
        """Update the Hebbian countdown label and handle blinking when <5s"""
        loc = Localisation.instance()
        if hasattr(self, 'hebbian_timer_label_learning'):
            # Check if simulation is paused
            is_paused = False
            if hasattr(self, 'tamagotchi_logic') and hasattr(self.tamagotchi_logic, 'simulation_speed'):
                is_paused = (self.tamagotchi_logic.simulation_speed == 0)
            
            # Display PAUSE if paused, otherwise show countdown
            if is_paused:
                self.hebbian_timer_label_learning.setText(f"{loc.get('hebbian_cycle')}: {loc.get('hebbian_paused')}")
                # Stop blinking when paused
                if self.blink_timer.isActive():
                    self.blink_timer.stop()
                self.hebbian_timer_label_learning.setVisible(True)
            else:
                self.hebbian_timer_label_learning.setText(f"{loc.get('hebbian_cycle')}: {value}s")
                
                # Start/stop blinking
                if isinstance(value, int) and value < 5:
                    if not self.blink_timer.isActive():
                        self.blink_timer.start()
                else:
                    if self.blink_timer.isActive():
                        self.blink_timer.stop()
                    # Ensure visible when not blinking
                    self.hebbian_timer_label_learning.setVisible(True)

    def _blink_hebbian_label(self):
        """Toggle visibility of the Hebbian label to create blink effect"""
        self._blink_visible = not self._blink_visible
        self.hebbian_timer_label_learning.setVisible(self._blink_visible)