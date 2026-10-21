"""The game is drawn light, whatever the system theme.

Its windows are designed light: a white tank, a light brain canvas, pastel
memory cards, light boxes in its HTML. With the system in a dark theme (macOS
dark mode, a dark Windows or Linux desktop) only part of that follows the
system - the window and the text turn dark and white - and the rest does not,
so text came out white on pastel and white on white. In a dark theme the game
therefore uses Qt's Fusion style with its standard light palette, so every
window is drawn in the colours it was designed in. In a light theme nothing
changes: the native style stays.
"""
from PyQt5 import QtGui, QtWidgets


def is_dark(palette):
    """A dark theme: dark window colour behind light text."""
    return palette.color(QtGui.QPalette.Window).lightness() < 128


def keep_light(app):
    """Draw the game light if the system theme is dark. True if it did."""
    if not is_dark(app.palette()):
        return False
    fusion = QtWidgets.QStyleFactory.create('Fusion')
    app.setStyle(fusion)
    app.setPalette(fusion.standardPalette())
    return True
