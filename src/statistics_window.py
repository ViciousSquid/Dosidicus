from PyQt5 import QtCore, QtGui, QtWidgets
import time, json, math, random, os
from .localisation import Localisation


class StatBox(QtWidgets.QWidget):
    """A single stat display box with label and value."""
    def __init__(self, label_key, parent=None):
        super().__init__(parent)
        self.loc = Localisation.instance()
        self.label_key = label_key
        
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            value_font_size, label_font_size = 18, 11
            box_width, box_height = 85, 70
        else:
            value_font_size, label_font_size = 28, 16
            box_width, box_height = 120, 100

        self.value_label = QtWidgets.QLabel("0")
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        self.value_label.setStyleSheet(
            f"font-size:{value_font_size}px;font-weight:bold;"
            "border:2px solid black;background-color:white;"
        )
        layout.addWidget(self.value_label)

        self.value_edit = QtWidgets.QLineEdit()
        self.value_edit.setAlignment(QtCore.Qt.AlignCenter)
        self.value_edit.setStyleSheet(
            f"font-size:{value_font_size}px;font-weight:bold;"
            "border:2px solid black;background-color:white;"
        )
        self.value_edit.hide()
        layout.addWidget(self.value_edit)

        # Use localised label
        self.name_label = QtWidgets.QLabel(self.loc.get(label_key))
        self.name_label.setAlignment(QtCore.Qt.AlignCenter)
        self.name_label.setStyleSheet(f"font-size:{label_font_size}px;font-weight:bold;")
        layout.addWidget(self.name_label)
        self.setFixedSize(box_width, box_height)

    def set_value(self, value):
        self.value_label.setText(str(int(value)))
        self.value_edit.setText(str(int(value)))

    def get_value(self):
        return int(self.value_edit.text())

    def set_editable(self, editable):
        self.value_label.setVisible(not editable)
        self.value_edit.setVisible(editable)
    
    def update_label(self):
        """Update the label text (for language changes)"""
        self.name_label.setText(self.loc.get(self.label_key))


class StatisticsWindow(QtWidgets.QWidget):
    def __init__(self, squid, arcade_font_path=None, show_decorations_callback=None):
        super().__init__()
        self.squid = squid
        self.show_decorations_callback = show_decorations_callback
        self.loc = Localisation.instance()

        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()

        self.setWindowTitle(self.loc.get("statistics"))
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)
        self.move(0, 0)

        # ---------------- score state ---------------------------------
        self.score         = 0
        self.display_score = 0
        self.combo_level   = 1
        self.combo_timer   = 0
        self.last_food_time= 0

        # ---------------- font ----------------------------------------
        if arcade_font_path and os.path.isfile(arcade_font_path):
            font_path = arcade_font_path
        else:
            font_path = os.path.join(os.path.dirname(__file__), "arcade.ttf")

        if os.path.isfile(font_path):
            font_id = QtGui.QFontDatabase.addApplicationFont(font_path)
            families = QtGui.QFontDatabase.applicationFontFamilies(font_id)
            font = QtGui.QFont(families[0], 40)
        else:
            font = QtGui.QFont("Arial", 40, QtGui.QFont.Bold)

        # ---------------- score label ---------------------------------
        self.score_label = QtWidgets.QLabel("00000")
        self.score_label.setAlignment(QtCore.Qt.AlignCenter)
        self.score_label.setFont(font)
        self.score_label.setStyleSheet("color:#000000;")

        # ---------------- window sizing -------------------------------
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            window_width, window_height = 320, 420
            main_spacing, grid_spacing = 6, 6
            status_font_size, score_font_size = 18, 20
        else:
            window_width, window_height = 450, 600
            main_spacing, grid_spacing = 10, 10
            status_font_size, score_font_size = 24, 32

        self.setFixedSize(window_width, window_height)

        # ---------------- layout --------------------------------------
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(main_spacing)

        grid_layout = QtWidgets.QGridLayout()
        grid_layout.setSpacing(grid_spacing)
        main_layout.addLayout(grid_layout)

        # Create stat boxes with localisation keys
        self.stat_boxes = {
            "hunger": StatBox("hunger"),
            "happiness": StatBox("happiness"),
            "cleanliness": StatBox("cleanliness"),
            "sleepiness": StatBox("sleepiness"),
            "health": StatBox("health"),
            "satisfaction": StatBox("satisfaction"),
            "curiosity": StatBox("curiosity"),
            "anxiety": StatBox("anxiety"),
        }

        grid_layout.addWidget(self.stat_boxes["health"],       0, 0)
        grid_layout.addWidget(self.stat_boxes["hunger"],       0, 1)
        grid_layout.addWidget(self.stat_boxes["happiness"],    0, 2)
        grid_layout.addWidget(self.stat_boxes["cleanliness"],  1, 0)
        grid_layout.addWidget(self.stat_boxes["sleepiness"],   1, 1)

        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        main_layout.addWidget(separator)

        new_neurons_layout = QtWidgets.QHBoxLayout()
        new_neurons_layout.setSpacing(10 if window_width > 320 else 6)
        main_layout.addLayout(new_neurons_layout)
        new_neurons_layout.addWidget(self.stat_boxes["satisfaction"])
        new_neurons_layout.addWidget(self.stat_boxes["curiosity"])
        new_neurons_layout.addWidget(self.stat_boxes["anxiety"])

        self.status_label = QtWidgets.QLabel()
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet(f"font-size:{status_font_size}px;")
        main_layout.addWidget(self.status_label)

        # State indicator pills container
        self.state_pills_container = QtWidgets.QWidget()
        self.state_pills_layout = QtWidgets.QHBoxLayout(self.state_pills_container)
        self.state_pills_layout.setSpacing(10)
        self.state_pills_layout.setContentsMargins(0, 5, 0, 5)
        self.state_pills_layout.addStretch()
        
        # Create up to 3 pill labels
        self.state_pills = []
        for i in range(3):
            pill = QtWidgets.QLabel()
            pill.setAlignment(QtCore.Qt.AlignCenter)
            pill.setMinimumHeight(30 if window_width <= 320 else 40)
            pill.setStyleSheet("""
                QLabel {
                    color: white;
                    font-size: 16px;
                    font-weight: bold;
                    border-radius: 5px;
                    padding: 5px 10px;
                }
            """)
            pill.hide()
            self.state_pills.append(pill)
            self.state_pills_layout.addWidget(pill)
        
        self.state_pills_layout.addStretch()
        main_layout.addWidget(self.state_pills_container)

        main_layout.addWidget(self.score_label)

        self.apply_button = QtWidgets.QPushButton(self.loc.get("apply_changes"))
        self.apply_button.clicked.connect(self.apply_changes)
        self.apply_button.hide()
        main_layout.addWidget(self.apply_button)

        # smooth ticker
        self.roll_timer = QtCore.QTimer(self, timeout=self._tick, interval=16)
        self.roll_timer.start()
        
        # Setup decorations window shortcut
        self.setup_decorations_shortcut()
        

    # ------------------------------------------------------------------

    def setup_decorations_shortcut(self):
        """Setup keyboard shortcut for decorations window (T key)"""
        if self.show_decorations_callback:
            self.decorations_shortcut = QtWidgets.QShortcut(
                QtGui.QKeySequence(QtCore.Qt.Key_T), 
                self
            )
            self.decorations_shortcut.activated.connect(self.show_decorations_callback)
    
    def _tick(self):
        # Update score display with smooth animation
        diff = self.score - self.display_score
        if abs(diff) > 0:
            step = math.copysign(max(1, abs(diff) // 8), diff)
            self.display_score += step
            self.display_score = max(0, min(99999, self.display_score))
            self.score_label.setText(f"{int(self.display_score):05d}")

        # Update combo timer
        if self.combo_timer > 0:
            self.combo_timer -= 1
        else:
            self.combo_level = 1

        # Continuously update all statistics from squid
        self.update_statistics()

    # -------------- external award -----------------------------------
    def award(self, base):
        now = time.time()
        # food chaining
        if base == 100:
            if now - self.last_food_time < 2.0:
                self.combo_level = min(3, self.combo_level + 1)
            else:
                self.combo_level = 1
            self.last_food_time = now
            self.combo_timer = 600
        # poop - no combo change
        elif base == 25:
            pass

        total = int(base * self.combo_level)
        self.score += total
        self.score = max(0, min(9999, self.score))

    def set_score(self, value):
        """Directly set the score value (used for loading saves)"""
        self.score = max(0, min(9999, int(value)))
        self.display_score = self.score
        self.score_label.setText(f"{int(self.display_score):04d}")

    def update_score(self):
        """Update the score display (called by tamagotchi_logic)"""
        self.score_label.setText(f"{int(self.display_score):04d}")

    # -------------- specific helpers ---------------------------------
    def add_score_for_food_eaten(self):
        self.award(100)

    def add_score_for_neuron_creation(self):
        self.award(500)

    def deduct_score_for_startle(self):
        self.award(-50)

    def add_score_for_poop_cleaned(self, count):
        self.award(25 * count)

    # -------------- original interface ---------------------------------
    def update_statistics(self):
        if self.squid is not None:
            for key, box in self.stat_boxes.items():
                if hasattr(self.squid, key):
                    box.set_value(getattr(self.squid, key))
            self.status_label.setText(f"{self.loc.get('status')}: {self.squid.status}")
            self._update_state_pill()

    def _update_state_pill(self):
        """Update the state indicator pills to match the brain network view states (up to 3)"""
        if self.squid is None:
            for pill in self.state_pills:
                pill.hide()
            return

        # Collect all active states (matches brain_widget.py logic)
        active_states = []
        
        # Check states in priority order with localised text
        if getattr(self.squid, 'is_fleeing', False):
            active_states.append((self.loc.get("fleeing"), "rgb(220, 20, 60)"))
        if getattr(self.squid, 'is_startled', False):
            active_states.append((self.loc.get("startled"), "rgb(255, 165, 0)"))
        if getattr(self.squid, 'pursuing_food', False):
            active_states.append((self.loc.get("pursuing_food"), "rgb(60, 179, 113)"))
        if getattr(self.squid, 'is_eating', False) or 'eating' in self.squid.status.lower():
            active_states.append((self.loc.get("eating"), "rgb(46, 204, 113)"))
        if getattr(self.squid, 'is_sleeping', False):
            active_states.append((self.loc.get("sleeping"), "rgb(142, 68, 173)"))
        if 'rock' in self.squid.status.lower() or 'play' in self.squid.status.lower():
            active_states.append((self.loc.get("playing"), "rgb(241, 196, 15)"))
        if 'hiding' in self.squid.status.lower():
            active_states.append((self.loc.get("hiding"), "rgb(22, 160, 133)"))
        if getattr(self.squid, 'anxiety', 0) > 70 or 'anxious' in self.squid.status.lower():
            active_states.append((self.loc.get("anxious"), "rgb(231, 76, 60)"))
        if getattr(self.squid, 'curiosity', 0) > 80 or 'curious' in self.squid.status.lower():
            active_states.append((self.loc.get("curious"), "rgb(52, 152, 219)"))
        
        # Display up to 3 states
        states_to_show = active_states[:3]
        
        # Update each pill
        for i, pill in enumerate(self.state_pills):
            if i < len(states_to_show):
                state_text, state_color = states_to_show[i]
                pill.setText(state_text)
                pill.setStyleSheet(f"""
                    QLabel {{
                        color: white;
                        background-color: {state_color};
                        font-size: 14px;
                        font-weight: bold;
                        border-radius: 5px;
                        padding: 5px 10px;
                    }}
                """)
                pill.show()
            else:
                pill.hide()

    def set_debug_mode(self, enabled):
        for key, box in self.stat_boxes.items():
            if key not in {"satisfaction", "curiosity", "anxiety"}:
                box.set_editable(enabled)
        self.apply_button.setVisible(enabled)

    def apply_changes(self):
        if self.squid is not None:
            for key, box in self.stat_boxes.items():
                if hasattr(self.squid, key):
                    setattr(self.squid, key, box.get_value())
        self.update_statistics()

    def closeEvent(self, event):
        event.accept()