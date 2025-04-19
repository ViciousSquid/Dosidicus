from PyQt5 import QtCore, QtGui, QtWidgets

class StatBox(QtWidgets.QWidget):
    def __init__(self, label, parent=None):
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)

        self.value_label = QtWidgets.QLabel("0")
        self.value_label.setAlignment(QtCore.Qt.AlignCenter)
        self.value_label.setStyleSheet("font-size: 28px; font-weight: bold; border: 2px solid black; background-color: white;")
        layout.addWidget(self.value_label)

        self.value_edit = QtWidgets.QLineEdit()
        self.value_edit.setAlignment(QtCore.Qt.AlignCenter)
        self.value_edit.setStyleSheet("font-size: 28px; font-weight: bold; border: 2px solid black; background-color: white;")
        self.value_edit.hide()  # Initially hidden
        layout.addWidget(self.value_edit)

        name_label = QtWidgets.QLabel(label)
        name_label.setAlignment(QtCore.Qt.AlignCenter)
        name_label.setStyleSheet("font-size: 16px; font-weight: bold;")
        layout.addWidget(name_label)

        self.setFixedSize(120, 100)  # Increased size to accommodate larger text

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

        self.setWindowTitle("Statistics")
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)

        # Set the initial position to top-left corner
        self.move(0, 0)

        # Set the initial dimensions (adjusted for larger text and boxes)
        self.setFixedSize(450, 600)  # Width: 450px, Height: 600px

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(10)

        grid_layout = QtWidgets.QGridLayout()
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
        grid_layout.addWidget(self.stat_boxes["hunger"], 0, 0)
        grid_layout.addWidget(self.stat_boxes["happiness"], 0, 1)
        grid_layout.addWidget(self.stat_boxes["health"], 0, 2)
        grid_layout.addWidget(self.stat_boxes["cleanliness"], 1, 0)
        grid_layout.addWidget(self.stat_boxes["sleepiness"], 1, 1)

        # Add a separator
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        separator.setFrameShadow(QtWidgets.QFrame.Sunken)
        main_layout.addWidget(separator)

        new_neurons_layout = QtWidgets.QHBoxLayout()
        new_neurons_layout.setSpacing(15)
        main_layout.addLayout(new_neurons_layout)
        new_neurons_layout.addWidget(self.stat_boxes["satisfaction"])
        new_neurons_layout.addWidget(self.stat_boxes["curiosity"])
        new_neurons_layout.addWidget(self.stat_boxes["anxiety"])

        # Status label
        self.status_label = QtWidgets.QLabel()
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        self.status_label.setStyleSheet("font-size: 24px;")
        main_layout.addWidget(self.status_label)

        # Score label
        self.score_label = QtWidgets.QLabel("Score: 0")
        self.score_label.setAlignment(QtCore.Qt.AlignCenter)
        self.score_label.setStyleSheet("font-size: 32px; font-weight: bold;")
        main_layout.addWidget(self.score_label)

        # Apply button (initially hidden)
        self.apply_button = QtWidgets.QPushButton("Apply Changes")
        self.apply_button.clicked.connect(self.apply_changes)
        self.apply_button.hide()
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
