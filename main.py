#  ENTRY POINT for Dosidicus
# by Rufus Pearce (ViciousSquid)  |  July 2024  |  MIT License
# https://github.com/ViciousSquid/Dosidicus

import sys
from PyQt5 import QtWidgets

from ui import Ui
from tamagotchi_logic import TamagotchiLogic
from squid import Squid

def main():
    app = QtWidgets.QApplication(sys.argv)

    # Create the main window
    main_window = QtWidgets.QMainWindow()

    # Create the Ui instance
    ui = Ui(main_window, None)

    # Create the Squid instance and pass the Ui instance
    squid = Squid(ui, None)

    # Create the Tamagotchi logic instance and pass the squid object and the Ui instance
    tamagotchi_logic = TamagotchiLogic(ui, squid)

    # Set the tamagotchi_logic in the Squid instance
    squid.tamagotchi_logic = tamagotchi_logic

    # Set the tamagotchi_logic in the Ui instance
    ui.tamagotchi_logic = tamagotchi_logic

    # Connect Load and Save actions
    ui.load_action.triggered.connect(tamagotchi_logic.load_game)
    ui.save_action.triggered.connect(lambda: tamagotchi_logic.save_game(squid, tamagotchi_logic))

    # Show the main window
    main_window.show()

    # Start the application event loop
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()