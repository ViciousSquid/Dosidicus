import sys
from PyQt5 import QtWidgets

from ui import Ui
from tamagotchi_logic import TamagotchiLogic
from squid import Squid
from brain import Brain
from brain_debug_tool import BrainDebugTool

def main():
    app = QtWidgets.QApplication(sys.argv)

    # Create the main window and the brain
    main_window = QtWidgets.QMainWindow()
    brain = Brain()  # Create an instance of the Brain class

    # Create and set up the main UI
    ui = Ui(main_window, brain)
    tamagotchi_logic = TamagotchiLogic(ui, None)
    squid = Squid(ui, tamagotchi_logic)
    tamagotchi_logic.squid = squid

    # Show the main window
    main_window.show()

    # Create and show the Brain Debug Tool
    debug_tool = BrainDebugTool(brain)
    debug_tool.show()

    # Start the application event loop
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()