from PyQt5 import QtCore, QtGui, QtWidgets

class StatisticsWindow(QtWidgets.QWidget):
    def __init__(self, squid):
        super().__init__()
        self.squid = squid

        self.setWindowTitle("Statistics")
        self.setGeometry(100, 100, 300, 450)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)

        self.layout = QtWidgets.QVBoxLayout()  # Changed to instance variable

        # Create a label for the health value
        self.health_label = QtWidgets.QLabel()
        self.health_label.setFont(QtGui.QFont("Arial", 11, QtGui.QFont.Bold))
        self.layout.addWidget(self.health_label)

        self.statistic_inputs = {
            "hunger": QtWidgets.QLineEdit(),
            "sleepiness": QtWidgets.QLineEdit(),
            "happiness": QtWidgets.QLineEdit(),
            "cleanliness": QtWidgets.QLineEdit(),
        }

        font = QtGui.QFont()
        font.setPointSize(10)  # Set the desired font size

        for key, input_field in self.statistic_inputs.items():
            label = QtWidgets.QLabel(key.capitalize() + ":")
            label.setFont(font)  # Set the font for the label
            self.layout.addWidget(label)
            input_field.setFont(font)  # Set the font for the input field
            input_field.setReadOnly(True)  # Set input fields to read-only by default
            self.layout.addWidget(input_field)

        self.statistic_labels = {
            "is_sleeping": QtWidgets.QLabel(),
            "direction": QtWidgets.QLabel(),
            "position": QtWidgets.QLabel(),
            "status": QtWidgets.QLabel(),
            "is_sick": QtWidgets.QLabel(),
        }

        for label in self.statistic_labels.values():
            label.setFont(font)  # Set the font for the label
            self.layout.addWidget(label)

        # Add the apply button
        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.setFont(font)  # Set the font for the button
        self.apply_button.clicked.connect(self.apply_statistic_changes)
        self.apply_button.setVisible(False)  # Initially hide the button
        self.layout.addWidget(self.apply_button)

        self.setLayout(self.layout)

    def apply_statistic_changes(self):
        if self.squid is not None:
            for key, input_field in self.statistic_inputs.items():
                try:
                    value = int(input_field.text())
                    setattr(self.squid, key, value)
                except ValueError:
                    pass

    def update_statistics(self):
        if self.squid is not None:
            # Update the health label
            self.health_label.setText(f"Health: {int(self.squid.health)}")

            for key, input_field in self.statistic_inputs.items():
                input_field.setText(str(int(getattr(self.squid, key))))

            self.statistic_labels["is_sleeping"].setText(f"Sleeping: {self.squid.is_sleeping}")
            self.statistic_labels["direction"].setText(f"Direction: {self.squid.squid_direction}")
            self.statistic_labels["position"].setText(f"Position: ({int(self.squid.squid_x)}, {int(self.squid.squid_y)})")
            self.statistic_labels["status"].setText(f"Status: {self.squid.status}")
            self.statistic_labels["is_sick"].setText(f"Sick: {self.squid.is_sick}")

    def set_debug_mode(self, enabled):
        for input_field in self.statistic_inputs.values():
            input_field.setReadOnly(not enabled)
        self.apply_button.setVisible(enabled)

    def closeEvent(self, event):
        # Hide the window instead of closing it
        self.hide()
        event.ignore()