from PyQt5 import QtCore, QtGui, QtWidgets

class ConsoleOutput:
    def __init__(self, text_edit):
        self.text_edit = text_edit

    def write(self, text):
        cursor = self.text_edit.textCursor()
        format = QtGui.QTextCharFormat()

        if text.startswith("Previous value:"):
            format.setForeground(QtGui.QColor("red"))
        elif text.startswith("New value:"):
            format.setForeground(QtGui.QColor("green"))
        else:
            format.setForeground(QtGui.QColor("black"))

        cursor.insertText(text, format)
        self.text_edit.setTextCursor(cursor)
        self.text_edit.ensureCursorVisible()

    def flush(self):
        pass

