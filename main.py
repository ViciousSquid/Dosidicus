import sys
from PyQt5 import QtWidgets

from ui import Ui
from tamagotchi_logic import TamagotchiLogic
from squid import Squid
from brain import Brain
from brain_debug_tool import BrainDebugTool

def main():
    app = QtWidgets.QApplication(sys.argv)

    window = QtWidgets.QMainWindow()
    brain = Brain()  # Create an instance of the Brain class
    ui = Ui(window, brain)  # Pass the brain object as an argument to the Ui class constructor
    tamagotchi_logic = TamagotchiLogic(ui, None)  # Pass None for now
    squid = Squid(ui, tamagotchi_logic)  # Create the Squid instance
    tamagotchi_logic.squid = squid  # Set the squid instance in TamagotchiLogic

    window.show()

    debug_tool = BrainDebugTool(brain)
    debug_tool.show()

    sys.exit(app.exec_())

if __name__ == '__main__':
    main()
