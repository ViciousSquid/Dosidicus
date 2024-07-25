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
        self.feeding_message_animation.setStartValue(0.0)
        self.feeding_message_animation.setEndValue(1.0)
        self.feeding_message_animation.setDuration(1000)  # 1 second duration

        self.scene.setSceneRect(0, 0, self.window_width, self.window_height)

        self.rect_item = QtWidgets.QGraphicsRectItem(50, 50, self.window_width - 100, self.window_height - 100)
        self.rect_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))
        self.rect_item.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 2))
        self.scene.addItem(self.rect_item)

        self.cleanliness_overlay = QtWidgets.QGraphicsRectItem(50, 50, self.window_width - 100, self.window_height - 100)
        self.cleanliness_overlay.setBrush(QtGui.QBrush(QtGui.QColor(139, 69, 19, 0)))  # Light brown, initially transparent
        self.cleanliness_overlay.setPen(QtGui.QPen(QtCore.Qt.NoPen))
        self.scene.addItem(self.cleanliness_overlay)

    def setup_menu_bar(self):
        self.menu_bar = self.window.menuBar()

        actions_menu = self.menu_bar.addMenu('Actions')

        self.feed_action = QtWidgets.QAction('Feed', self.window)
        actions_menu.addAction(self.feed_action)

        self.clean_action = QtWidgets.QAction('Clean', self.window)
        actions_menu.addAction(self.clean_action)

        options_menu = self.menu_bar.addMenu('Debug')

        self.debug_action = QtWidgets.QAction('Toggle Debug Mode', self.window)
        self.debug_action.setCheckable(True)
        options_menu.addAction(self.debug_action)

        self.view_cone_action = QtWidgets.QAction('Toggle View Cone', self.window)
        self.view_cone_action.setCheckable(True)
        options_menu.addAction(self.view_cone_action)

        help_menu = self.menu_bar.addMenu('Help')

        about_action = QtWidgets.QAction('About', self.window)
        about_action.triggered.connect(self.show_about_dialog)
        help_menu.addAction(about_action)

    def handle_window_resize(self, event):
        self.window_width = event.size().width()
        self.window_height = event.size().height()
        self.scene.setSceneRect(0, 0, self.window_width, self.window_height)

        self.rect_item.setRect(50, 50, self.window_width - 100, self.window_height - 100)
        self.cleanliness_overlay.setRect(50, 50, self.window_width - 100, self.window_height - 100)

        self.feeding_message.setGeometry(0, self.window_height - 30, self.window_width, 30)

    def show_message(self, message):
        self.feeding_message.setText(message)
        self.feeding_message.show()
    
        # Set a timer to hide the message after 3 seconds
        QtCore.QTimer.singleShot(3000, self.feeding_message.hide)
    
        # Force update
        self.feeding_message.update()
        self.scene.update()

    def connect_view_cone_action(self, toggle_function):
        self.view_cone_action.triggered.connect(toggle_function)

    def show_about_dialog(self):
        about_message = ("<h2>Dosidicus Electronicae</h2>"
                         "<p>Research project</p>"
                         "<p>Version 1.0.2</p>"
                         "<p>https://github.com/ViciousSquid/Dosidicus")
        QtWidgets.QMessageBox.about(self.window, "About", about_message)