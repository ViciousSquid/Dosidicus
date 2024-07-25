from PyQt5 import QtCore, QtGui, QtWidgets

class StatisticsWindow(QtWidgets.QWidget):
    def __init__(self, squid):
        super().__init__()
        self.squid = squid

        self.setWindowTitle("Statistics")
        self.setGeometry(100, 100, 300, 350)
        self.setWindowFlags(QtCore.Qt.Window | QtCore.Qt.WindowStaysOnTopHint)

        layout = QtWidgets.QVBoxLayout()
        self.statistic_inputs = {
            "hunger": QtWidgets.QLineEdit(),
            "sleepiness": QtWidgets.QLineEdit(),
            "happiness": QtWidgets.QLineEdit(),
            "cleanliness": QtWidgets.QLineEdit(),
        }

        font = QtGui.QFont()
        font.setPointSize(9)  # Set the desired font size

        for key, input_field in self.statistic_inputs.items():
            label = QtWidgets.QLabel(key.capitalize() + ":")
            label.setFont(font)  # Set the font for the label
            layout.addWidget(label)
            input_field.setFont(font)  # Set the font for the input field
            input_field.setReadOnly(True)  # Set input fields to read-only by default
            layout.addWidget(input_field)

        self.statistic_labels = {
            "is_sleeping": QtWidgets.QLabel(),
            "direction": QtWidgets.QLabel(),
            "position": QtWidgets.QLabel(),
        }

        for label in self.statistic_labels.values():
            label.setFont(font)  # Set the font for the label
            layout.addWidget(label)

        # Add the apply button
        self.apply_button = QtWidgets.QPushButton("Apply")
        self.apply_button.setFont(font)  # Set the font for the button
        self.apply_button.clicked.connect(self.apply_statistic_changes)
        self.apply_button.setEnabled(False)  # Disable the apply button by default
        layout.addWidget(self.apply_button)

        self.setLayout(layout)

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
            for key, input_field in self.statistic_inputs.items():
                input_field.setText(str(int(getattr(self.squid, key))))

            self.statistic_labels["is_sleeping"].setText(f"Sleeping: {self.squid.is_sleeping}")
            self.statistic_labels["direction"].setText(f"Direction: {self.squid.squid_direction}")
            self.statistic_labels["position"].setText(f"Position: ({int(self.squid.squid_x)}, {int(self.squid.squid_y)})")

    def closeEvent(self, event):
        # Hide the window instead of closing it
        self.hide()
        event.ignore()