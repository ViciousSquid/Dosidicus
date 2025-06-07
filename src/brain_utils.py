from PyQt5 import QtCore, QtGui, QtWidgets

class ConsoleOutput:
    """Writes text to a QtGui.QTextEdit.

    Attributes:
        text_edit: The QtGui.QTextEdit to write to.
    """
def __init__(self, text_edit):
        """Initializes the object with a text edit instance.

        Args:
            text_edit: The text edit instance to be associated with this object.
        """
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

