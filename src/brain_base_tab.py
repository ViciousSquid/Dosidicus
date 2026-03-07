from PyQt5 import QtCore, QtGui, QtWidgets
from .display_scaling import DisplayScaling

class BrainBaseTab(QtWidgets.QWidget):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        super().__init__(parent)
        self.parent = parent
        self.tamagotchi_logic = tamagotchi_logic
        self.brain_widget = brain_widget
        self.config = config
        self.debug_mode = debug_mode
        self.layout = QtWidgets.QVBoxLayout()
        self.setLayout(self.layout)

        # Set an explicit base font so all child widgets inherit a consistent
        # size regardless of platform defaults (important for Nuitka builds
        # where Qt may resolve a smaller system font than CPython does).
        base_font = QtGui.QFont()
        base_font.setPointSize(DisplayScaling.font_size(10))
        self.setFont(base_font)

    def set_tamagotchi_logic(self, tamagotchi_logic):
        """Update the tamagotchi_logic reference"""
        #print(f"BrainBaseTab.set_tamagotchi_logic: {tamagotchi_logic is not None}")
        self.tamagotchi_logic = tamagotchi_logic
        
    def update_from_brain_state(self, state):
        """Update tab based on brain state - override in subclasses"""
        pass
        
    def create_button(self, text, callback, color):
        """Common utility for creating consistent buttons"""
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        button.setStyleSheet(f"background-color: {color}; border: 1px solid black; padding: 5px;")
        button.setFixedSize(200, 50)
        return button
    
    


