import os
from PyQt5 import QtCore, QtGui, QtWidgets

class Ui:
    def __init__(self, window):
        self.window = window
        self.window.setWindowTitle("Dosidicus")

        self.window_width = 1280
        self.window_height = 800

        self.window.resize(self.window_width, self.window_height)

        self.scene = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.window.setCentralWidget(self.view)

        self.setup_menu_bar()

        self.label = QtWidgets.QLabel("Dosidicus Electronicae")
        self.label.setStyleSheet("font-size: 20px; font-weight: bold; color: white; background-color: black;")
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        self.label.setGeometry(10, 10, 250, 30)
        self.scene.addWidget(self.label)

        self.feeding_message = QtWidgets.QLabel("Squid requires feeding")
        self.feeding_message.setStyleSheet("font-size: 16px; font-weight: bold; color: white; background-color: black;")
        self.feeding_message.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.feeding_message.setGeometry(0, self.window_height - 30, self.window_width, 30)
        self.feeding_message.hide()
        self.scene.addWidget(self.feeding_message)

        self.feeding_message_animation = QtCore.QPropertyAnimation(self.feeding_message, b"opacity")
        self.feeding_message_animation.setDuration(1000)
        self.feeding_message_animation.setStartValue(0)
        self.feeding_message_animation.setEndValue(1)

        self.scene.setSceneRect(0, 0, self.window_width, self.window_height)

        self.rect_item = QtWidgets.QGraphicsRectItem(50, 50, self.window_width - 100, self.window_height - 100)
        self.rect_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        self.rect_item.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 2))
        self.scene.addItem(self.rect_item)

        self.button_strip = QtWidgets.QWidget()
        self.button_strip.setGeometry(0, self.window_height - 70, self.window_width, 70)
        self.scene.addWidget(self.button_strip)

        self.button_strip_layout = QtWidgets.QHBoxLayout()
        self.button_strip.setLayout(self.button_strip_layout)

        self.button_style = "font-size: 16px; font-weight: bold; color: white; background-color: black;"

        self.button_a = QtWidgets.QPushButton("")
        self.button_a.setStyleSheet(self.button_style)
        self.button_a.setGeometry(50, 0, 100, 40)
        self.button_strip_layout.addWidget(self.button_a)

        self.button_b = QtWidgets.QPushButton("")
        self.button_b.setStyleSheet(self.button_style)
        self.button_b.setGeometry(self.window_width // 2 - 50, 0, 100, 40)
        self.button_strip_layout.addWidget(self.button_b)

        self.button_c = QtWidgets.QPushButton("")
        self.button_c.setStyleSheet(self.button_style)
        self.button_c.setGeometry(self.window_width - 150, 0, 100, 40)
        self.button_strip_layout.addWidget(self.button_c)

    def setup_menu_bar(self):
        menu_bar = self.window.menuBar()

        actions_menu = menu_bar.addMenu('ACTIONS')

        self.feed_action = QtWidgets.QAction('Feed', self.window)
        actions_menu.addAction(self.feed_action)

        options_menu = menu_bar.addMenu('Debug Options')

        self.debug_action = QtWidgets.QAction('Toggle Debug Mode', self.window)
        self.debug_action.setCheckable(True)
        options_menu.addAction(self.debug_action)

        self.view_cone_action = QtWidgets.QAction('Toggle View Cone', self.window)
        self.view_cone_action.setCheckable(True)
        options_menu.addAction(self.view_cone_action)

        help_menu = menu_bar.addMenu('Help')

        about_action = QtWidgets.QAction('About', self.window)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def handle_window_resize(self, event):
        self.window_width = event.size().width()
        self.window_height = event.size().height()
        self.scene.setSceneRect(0, 0, self.window_width, self.window_height)
        self.button_strip.setGeometry(0, self.window_height - 70, self.window_width, 70)

        self.rect_item.setRect(50, 50, self.window_width - 100, self.window_height - 100)

        self.feeding_message.setGeometry(0, self.window_height - 30, self.window_width, 30)

    def show_message(self, message):
        self.feeding_message.setText(message)
        self.feeding_message.show()
        self.feeding_message_animation.setDirection(QtCore.QAbstractAnimation.ForwardDirection)
        self.feeding_message_animation.start()

    def show_about_dialog(self):
        about_message = ("<h2>Dosidicus Electronicae</h2>"
                         "<p>Research project</p>"
                         "<p>Version 1.0</p>"
                         "<p>https://github.com/ViciousSquid/Dosidicus")
        QtWidgets.QMessageBox.about(self.window, "About", about_message)