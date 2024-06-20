import sys
from PyQt5 import QtWidgets

from ui import Ui
from tamagotchi_logic import TamagotchiLogic
from squid import Squid

def main():
    app = QtWidgets.QApplication(sys.argv)

    window = QtWidgets.QMainWindow()
    ui = Ui(window)
    squid = Squid(ui, None)  # Create the Squid instance first
    tamagotchi_logic = TamagotchiLogic(ui, squid)  # Pass the Squid instance to TamagotchiLogic

    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()