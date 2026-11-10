"""The window that shows a squid's journey (View > Journey).

All of the content comes from src/life_journey.py, which reads the live squid;
this is only the frame around it. It refreshes while it is open, so a
milestone reached while the player is looking at it ticks itself off.
"""
from PyQt5 import QtCore, QtWidgets

from .life_journey import gather_facts, render_html
from .localisation import loc


class JourneyWindow(QtWidgets.QDialog):
    def __init__(self, tamagotchi_logic, parent=None):
        super().__init__(parent)
        self.logic = tamagotchi_logic
        self.setWindowTitle(loc('journey_title', default="Your squid's journey"))
        self.resize(520, 640)

        layout = QtWidgets.QVBoxLayout(self)
        self.view = QtWidgets.QTextBrowser(self)
        self.view.setOpenExternalLinks(False)
        layout.addWidget(self.view)

        close = QtWidgets.QPushButton(loc('close', default="Close"), self)
        close.clicked.connect(self.hide)
        layout.addWidget(close, alignment=QtCore.Qt.AlignRight)

        self._timer = QtCore.QTimer(self)
        self._timer.timeout.connect(self.refresh)
        self.refresh()

    def refresh(self):
        """Re-read the squid, keeping the reader's place on the page."""
        bar = self.view.verticalScrollBar()
        position = bar.value()
        try:
            html = render_html(gather_facts(self.logic))
        except Exception as exc:      # never take the game down for a window
            html = f"<p>The journey could not be read just now ({type(exc).__name__}).</p>"
        self.view.setHtml(html)
        bar.setValue(position)

    def showEvent(self, event):
        self.refresh()
        self._timer.start(5000)
        super().showEvent(event)

    def hideEvent(self, event):
        self._timer.stop()
        super().hideEvent(event)
