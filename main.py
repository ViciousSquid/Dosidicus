import sys
from PyQt5 import QtWidgets

from ui import Ui
from tamagotchi_logic import TamagotchiLogic
from squid import Squid

def main():
    app = QtWidgets.QApplication(sys.argv)

    # Create the main window
    main_window = QtWidgets.QMainWindow()

    # Create and set up the main UI
    ui = Ui(main_window)
    
    # Create the Squid instance
    squid = Squid(ui, None)
    
    # Create the Tamagotchi logic instance and pass the squid object
    tamagotchi_logic = TamagotchiLogic(ui, squid)
    
    # Set the tamagotchi_logic in the Squid instance
    squid.tamagotchi_logic = tamagotchi_logic

    # Set the tamagotchi_logic in the UI instance
    ui.tamagotchi_logic = tamagotchi_logic

    # Connect Load and Save actions
    ui.load_action.triggered.connect(tamagotchi_logic.load_game)
    ui.save_action.triggered.connect(lambda: tamagotchi_logic.save_manager.save_game(squid, tamagotchi_logic))

    # Show the main window
    main_window.show()

    # Start the application event loop
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()