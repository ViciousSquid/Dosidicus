import os
from PyQt5 import QtCore, QtGui, QtWidgets

class Ui:
    def __init__(self, window):
        self.window = window
        self.window.setWindowTitle("Squid Tamagotchi")

        self.window_width = 1280
        self.window_height = 800

        self.window.resize(self.window_width, self.window_height)

        self.scene = QtWidgets.QGraphicsScene()
        self.view = QtWidgets.QGraphicsView(self.scene)
        self.window.setCentralWidget(self.view)

        self.label = QtWidgets.QLabel("Squiddy")
        self.label.setStyleSheet("font-size: 20px; font-weight: bold; color: white; background-color: black;")
        self.label.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft | QtCore.Qt.AlignmentFlag.AlignTop)
        self.label.setGeometry(10, 10, 100, 30)
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
        self.rect_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255)))  # White fill
        self.rect_item.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), 2))  # Black border
        self.scene.addItem(self.rect_item)

        self.button_strip = QtWidgets.QWidget()
        self.button_strip.setGeometry(0, self.window_height - 70, self.window_width, 70)
        self.scene.addWidget(self.button_strip)

        self.button_strip_layout = QtWidgets.QHBoxLayout()
        self.button_strip.setLayout(self.button_strip_layout)

        self.button_style = "font-size: 16px; font-weight: bold; color: white; background-color: black;"

        self.button_a = QtWidgets.QPushButton("A")
        self.button_a.setStyleSheet(self.button_style)
        self.button_a.setGeometry(50, 0, 100, 40)
        self.button_strip_layout.addWidget(self.button_a)

        self.button_b = QtWidgets.QPushButton("B")
        self.button_b.setStyleSheet(self.button_style)
        self.button_b.setGeometry(self.window_width // 2 - 50, 0, 100, 40)
        self.button_strip_layout.addWidget(self.button_b)

        self.button_c = QtWidgets.QPushButton("C")
        self.button_c.setStyleSheet(self.button_style)
        self.button_c.setGeometry(self.window_width - 150, 0, 100, 40)
        self.button_strip_layout.addWidget(self.button_c)