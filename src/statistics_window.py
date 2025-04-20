from PyQt5 import QtCore, QtGui, QtWidgets

class StatBox(QtWidgets.QWidget):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        
        # Get screen resolution
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()
        
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        # Resolution-specific styling
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            # 1080p - significantly smaller text and box
            value_font_size = 18  # Reduced from 22
            label_font_size = 11  # Reduced from 14
            box_width = 85       # Reduced from 100
            box_height = 70      # Reduced from 80
        else:
            # Higher resolutions - original sizes
            value_font_size = 28
            label_font_size = 16
            box_width = 120
            box_height = 100

        self.value_label = QtWidgets.QLabel("0")
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        self.value_label.setStyleSheet(f"font-size: {value_font_size}px; font-weight: bold; border: 2px solid black; background-color: white;")
        layout.addWidget(self.value_label)

        self.value_edit = QtWidgets.QLineEdit()
        self.value_edit.setAlignment(QtCore.Qt.AlignCenter)
        self.value_edit.setStyleSheet(f"font-size: {value_font_size}px; font-weight: bold; border: 2px solid black; background-color: white;")
        self.value_edit.hide()  # Initially hidden
        layout.addWidget(self.value_edit)

        name_label = QtWidgets.QLabel(label)
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setStyleSheet(f"font-size: {label_font_size}px; font-weight: bold;")
        layout.addWidget(name_label)

        self.setFixedSize(box_width, box_height)

    def set_value(self, value):
        self.value_label.setText(str(int(value)))
        self.value_edit.setText(str(int(value)))

    def get_value(self):
        return int(self.value_edit.text())

    def set_editable(self, editable):
        self.value_label.setVisible(not editable)
        self.value_edit.setVisible(editable)

class StatisticsWindow(QtWidgets.QWidget):
    def __init__(self, squid):
        super().__init__()
        self.squid = squid

        # Get screen resolution
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()

        self.setWindowTitle("Statistics")
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)

        # Set position to top-left corner
        self.move(0, 0)

        # Resolution-specific window sizing
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            # Much smaller window for 1080p
            window_width = 320  # Reduced from 380
            window_height = 420  # Reduced from 500
        else:
            # Original sizes for higher resolutions
            window_width = 450
            window_height = 600

        # Set window size
        self.setFixedSize(window_width, window_height)

        # Layout setup
        main_layout = QtWidgets.QVBoxLayout(self)
        
        # Adjust layout spacing for 1080p
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            main_layout.setSpacing(6)  # Reduced from 10
        else:
            main_layout.setSpacing(10)

        grid_layout = QtWidgets.QGridLayout()
        
        # Adjust grid spacing for 1080p
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            grid_layout.setSpacing(6)  # Reduced from 10
        else:
            grid_layout.setSpacing(10)
            
        main_layout.addLayout(grid_layout)

        self.stat_boxes = {
            "hunger": StatBox("Hunger"),
            "happiness": StatBox("Happiness"),
            "cleanliness": StatBox("Cleanliness"),
            "sleepiness": StatBox("Sleepiness"),
            "health": StatBox("Health"),
            "satisfaction": StatBox("Satisfaction"),
            "curiosity": StatBox("Curiosity"),
            "anxiety": StatBox("Anxiety")
        }

        # Add stat boxes to the grid
        grid_layout.addWidget(self.stat_boxes["health"], 0, 0)
        grid_layout.addWidget(self.stat_boxes["hunger"], 0, 1)
        grid_layout.addWidget(self.stat_boxes["happiness"], 0, 2)
        grid_layout.addWidget(self.stat_boxes["cleanliness"], 1, 0)
        grid_layout.addWidget(self.stat_boxes["sleepiness"], 1, 1)

        # Add a separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        main_layout.addWidget(separator)

        new_neurons_layout = QtWidgets.QHBoxLayout()
        
        # Adjust neuron layout spacing for 1080p
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            new_neurons_layout.setSpacing(10)  # Reduced from 15
        else:
            new_neurons_layout.setSpacing(15)
            
        main_layout.addLayout(new_neurons_layout)
        new_neurons_layout.addWidget(self.stat_boxes["satisfaction"])
        new_neurons_layout.addWidget(self.stat_boxes["curiosity"])
        new_neurons_layout.addWidget(self.stat_boxes["anxiety"])

        # Status label
        self.status_label = QtWidgets.QLabel()
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        
        # Resolution-specific styling for status label
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            self.status_label.setStyleSheet("font-size: 18px;")  # Reduced from 24px
        else:
            self.status_label.setStyleSheet("font-size: 24px;")
            
        main_layout.addWidget(self.status_label)

        # Resolution-specific styling for score label
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            score_font_size = 20  # Reduced from 24
        else:
            score_font_size = 32  # Original size

        self.score_label = QtWidgets.QLabel("Score: 0")
        self.score_label.setAlignment(QtCore.Qt.AlignCenter)
        self.score_label.setStyleSheet(f"font-size: {score_font_size}px; font-weight: bold;")
        main_layout.addWidget(self.score_label)

        # Apply button (initially hidden)
        self.apply_button = QtWidgets.QPushButton("Apply Changes")
        self.apply_button.clicked.connect(self.apply_changes)
        self.apply_button.hide()
        
        # Size the apply button appropriately for 1080p
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            self.apply_button.setStyleSheet("font-size: 14px;")  # Reduced from 18px
        else:
            self.apply_button.setStyleSheet("font-size: 18px;")
            
        main_layout.addWidget(self.apply_button)

    def update_statistics(self):
        if self.squid is not None:
            for key, box in self.stat_boxes.items():
                if hasattr(self.squid, key):
                    box.set_value(getattr(self.squid, key))
            self.status_label.setText(f"Status: {self.squid.status}")
            self.update_score()

    def set_debug_mode(self, enabled):
        for key, box in self.stat_boxes.items():
            if key not in ["satisfaction", "curiosity", "anxiety"]:  # Exclude these attributes from being editable
                box.set_editable(enabled)
        self.apply_button.setVisible(enabled)

    def apply_changes(self):
        if self.squid is not None:
            for key, box in self.stat_boxes.items():
                if hasattr(self.squid, key):
                    setattr(self.squid, key, box.get_value())
        self.update_statistics()

    def update_score(self):
        if self.squid is not None:
            curiosity_factor = self.squid.curiosity / 100
            anxiety_factor = 1 - self.squid.anxiety / 100
            happiness_factor = self.squid.happiness / 100
            health_factor = self.squid.health / 100

            base_score = curiosity_factor * anxiety_factor * 100
            multiplier = (happiness_factor + health_factor) / 2

            if self.squid.is_sick or self.squid.hunger >= 80 or self.squid.happiness <= 20:
                multiplier = -multiplier

            if self.squid.health == 0:
                base_score -= 200

            final_score = int(base_score * multiplier)
            self.score_label.setText(f"Score: {final_score}")

    def closeEvent(self, event):
        event.accept()