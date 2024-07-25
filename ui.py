import os
from PyQt5 import QtCore, QtGui, QtWidgets

class Ui:
    def __init__(self, window):
        self.window = window
        self.window.setWindowTitle("Dosidicus")

        self.window_width = 1280
        self.window_height = 820

        self.window.resize(self.window_width, self.window_height)

        self.scene = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.view.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.view.setViewportUpdateMode(QtWidgets.QGraphicsView.FullViewportUpdate)
        self.window.setCentralWidget(self.view)

        self.setup_menu_bar()

        self.title_text = "Dosidicus Electronicae"
        self.label = QtWidgets.QLabel(self.title_text)
        self.label.setStyleSheet("font-size: 20px; font-weight: bold; color: white; background-color: black;")
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        self.label.setGeometry(10, 10, 250, 30)
        self.label.mouseDoubleClickEvent = self.start_rename
        self.scene.addWidget(self.label)

        self.title_input = QtWidgets.QLineEdit()
        self.title_input.setStyleSheet("font-size: 20px; font-weight: bold; color: white; background-color: black;")
        self.title_input.setGeometry(10, 10, 250, 30)
        self.title_input.hide()
        self.title_input.editingFinished.connect(self.finish_rename)
        self.scene.addWidget(self.title_input)

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

        self.points_label = QtWidgets.QLabel("Points: ")
        self.points_label.setStyleSheet("font-size: 22px; color: white; background-color: black;")
        self.points_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignRight | QtCore.Qt.AlignmentFlag.AlignTop)
        self.points_label.setGeometry(self.window_width - 150, 10, 140, 30)
        self.scene.addWidget(self.points_label)

        self.points_value_label = QtWidgets.QLabel("0")
        self.points_value_label.setStyleSheet("font-size: 22px; font-weight: bold; color: white; background-color: black;")
        self.points_value_label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        self.points_value_label.setGeometry(self.window_width - 90, 10, 80, 30)
        self.scene.addWidget(self.points_value_label)

    def setup_menu_bar(self):
        self.menu_bar = self.window.menuBar()

        file_menu = self.menu_bar.addMenu('File')
        self.load_action = QtWidgets.QAction('Load', self.window)
        self.save_action = QtWidgets.QAction('Save', self.window)
        file_menu.addAction(self.load_action)
        file_menu.addAction(self.save_action)

        actions_menu = self.menu_bar.addMenu('Actions')

        self.feed_action = QtWidgets.QAction('Feed', self.window)
        actions_menu.addAction(self.feed_action)

        self.clean_action = QtWidgets.QAction('Clean', self.window)
        actions_menu.addAction(self.clean_action)

        self.medicine_action = QtWidgets.QAction('Give Medicine', self.window)
        actions_menu.addAction(self.medicine_action)

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

        self.points_label.setGeometry(self.window_width - 150, 10, 140, 30)
        self.points_value_label.setGeometry(self.window_width - 90, 10, 80, 30)

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

    def update_points(self, points):
        self.points_value_label.setText(str(points))

    def start_rename(self, event):
        self.title_input.setText(self.title_text)
        self.title_input.show()
        self.label.hide()
        self.title_input.setFocus()
        self.title_input.selectAll()

    def finish_rename(self):
        new_title = self.title_input.text().strip()
        if new_title:
            self.title_text = new_title
            self.label.setText(self.title_text)
        self.label.show()
        self.title_input.hide()