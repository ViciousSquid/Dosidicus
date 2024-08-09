from PyQt5 import QtWidgets, QtCore

class DebugWindow(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent, QtCore.Qt.Window)
        self.setWindowTitle("Debug Window")
        self.setGeometry(100, 100, 400, 300)

        layout = QtWidgets.QVBoxLayout(self)

        # Add debug information displays
        self.info_label = QtWidgets.QLabel("Debug Information:")
        layout.addWidget(self.info_label)

        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        layout.addWidget(self.info_text)

        # Add debug controls
        self.update_button = QtWidgets.QPushButton("Update Debug Info")
        self.update_button.clicked.connect(self.update_debug_info)
        layout.addWidget(self.update_button)

    def update_debug_info(self):
        # This method will be called to update the debug information
        # You can connect this to your main application's data
        pass

# Modify the TamagotchiLogic class to include the debug window
class TamagotchiLogic:
    def __init__(self, user_interface, squid, brain_window):
        # ... (existing initialization code) ...
        self.debug_window = None

    def toggle_debug_mode(self):
        self.debug_mode = not self.debug_mode
        self.statistics_window.set_debug_mode(self.debug_mode)
        print(f"Debug mode {'enabled' if self.debug_mode else 'disabled'}")

        if self.debug_mode:
            if self.debug_window is None:
                self.debug_window = DebugWindow()
            self.debug_window.show()
        else:
            if self.debug_window:
                self.debug_window.hide()

    def update_simulation(self):
        # ... (existing update code) ...
        if self.debug_mode and self.debug_window:
            self.update_debug_window()

    def update_debug_window(self):
        if self.debug_window:
            debug_info = f"Squid Position: ({self.squid.squid_x}, {self.squid.squid_y})\n"
            debug_info += f"Hunger: {self.squid.hunger}\n"
            debug_info += f"Happiness: {self.squid.happiness}\n"
            debug_info += f"Cleanliness: {self.squid.cleanliness}\n"
            debug_info += f"Health: {self.squid.health}\n"
            debug_info += f"Is Sick: {self.squid.is_sick}\n"
            debug_info += f"Is Sleeping: {self.squid.is_sleeping}\n"
            self.debug_window.info_text.setPlainText(debug_info)