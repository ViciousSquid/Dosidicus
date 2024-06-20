from PyQt5 import QtCore, QtGui, QtWidgets

class TamagotchiLogic:
    def __init__(self, ui, squid):
        self.ui = ui
        self.squid = squid  # Store the Squid instance

        self.hunger_level = 0
        self.happiness_level = 50
        self.discipline_level = 50
        self.cleanliness_level = 50
        self.lights_on = True

        self.ui.button_a.clicked.connect(self.button_a_clicked)
        self.ui.button_b.clicked.connect(self.button_b_clicked)
        self.ui.button_c.clicked.connect(self.button_c_clicked)

        self.ui.window.resizeEvent = self.handle_window_resize

        self.update_stats()

    def handle_window_resize(self, event):
        self.ui.window_width = event.size().width()
        self.ui.window_height = event.size().height()
        self.ui.scene.setSceneRect(0, 0, self.ui.window_width, self.ui.window_height)
        self.ui.button_strip.setGeometry(0, self.ui.window_height - 70, self.ui.window_width, 70)

        # Update the squid's preferred vertical range
        self.squid.update_preferred_vertical_range()

    def button_a_clicked(self):
        pass

    def button_b_clicked(self):
        pass

    def button_c_clicked(self):
        pass

    def update_stats(self):
        self.hunger_level = min(100, self.hunger_level + 1)
        self.happiness_level = max(0, self.happiness_level - 1)
        self.discipline_level = max(0, self.discipline_level - 1)
        self.cleanliness_level = max(0, self.cleanliness_level - 1)

        if self.hunger_level >= 80:
            self.show_feeding_message()

        QtCore.QTimer.singleShot(5000, self.update_stats)

    def show_feeding_message(self):
        self.ui.feeding_message.show()
        self.ui.feeding_message_animation.setDirection(QtCore.QAbstractAnimation.ForwardDirection)
        self.ui.feeding_message_animation.start()