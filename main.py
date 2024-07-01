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
    
    # Create the Tamagotchi logic and Squid instances
    tamagotchi_logic = TamagotchiLogic(ui, None)
    squid = Squid(ui, tamagotchi_logic)
    
    # Set the squid in the TamagotchiLogic
    tamagotchi_logic.squid = squid

    # Show the main window
    main_window.show()

    # Start the application event loop
    sys.exit(app.exec_())

if __name__ == '__main__':
    main()