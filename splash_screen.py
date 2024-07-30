from PyQt5 import QtCore, QtGui, QtWidgets
import os

class SplashScreen(QtWidgets.QWidget):
    finished = QtCore.pyqtSignal()
    second_frame = QtCore.pyqtSignal()  # New signal for second frame

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        self.frame_index = 0
        self.frames = []
        
        for i in range(1, 7):
            image_path = os.path.join("images", "egg", f"anim0{i}.jpg")
            if os.path.exists(image_path):
                pixmap = QtGui.QPixmap(image_path)
                if not pixmap.isNull():
                    self.frames.append(pixmap)
                else:
                    print(f"Failed to load image: {image_path}")
            else:
                print(f"Image file not found: {image_path}")
        
        if not self.frames:
            print("No frames were loaded successfully.")
            self.label = QtWidgets.QLabel("No images loaded", self)
            self.setFixedSize(256, 256)
        else:
            self.label = QtWidgets.QLabel(self)
            self.label.setPixmap(self.frames[0])
            self.setFixedSize(self.frames[0].size())
        
        self.timer = QtCore.QTimer(self)
        self.timer.timeout.connect(self.next_frame)
        self.timer.start(2000)  # 2 seconds between frames

    def next_frame(self):
        self.frame_index += 1
        if self.frame_index < len(self.frames):
            self.label.setPixmap(self.frames[self.frame_index])
            if self.frame_index == 1:  # Second frame (index 1)
                self.second_frame.emit()  # Emit signal for second frame
        elif self.frame_index == len(self.frames):
            # Last frame shown, schedule hiding
            QtCore.QTimer.singleShot(2000, self.end_animation)
        else:
            self.timer.stop()

    def end_animation(self):
        print("A squid has hatched!")
        print("You'll need to look after him...")
        self.hide()
        self.finished.emit()

    def showEvent(self, event):
        self.move(self.parent().rect().center() - self.rect().center())
        super().showEvent(event)