"""A squid's colour: the tint a player gives it on the About tab.

One way of drawing it, used for the squid in its own tank and for the same
squid seen in somebody else's - so a pink squid is the same pink wherever it
is - and one way of writing it down to send to another tank.
"""
from typing import Any, Optional, Tuple

#: How strongly the tint covers the drawing (0-255): the lines show through.
STRENGTH = 120


def rgb_of(colour) -> Optional[Tuple[int, int, int]]:
    """(r, g, b) of a QColor or a 3-sequence; None for no tint or nonsense.

    What arrives from another tank is checked here too: three whole numbers
    from 0 to 255, or it is no colour at all.
    """
    if colour is None:
        return None
    if hasattr(colour, 'isValid') and hasattr(colour, 'red'):
        if not colour.isValid():
            return None
        return int(colour.red()), int(colour.green()), int(colour.blue())
    if isinstance(colour, (list, tuple)) and len(colour) >= 3:
        parts = colour[:3]
        if all(isinstance(part, int) and not isinstance(part, bool) and 0 <= part <= 255
               for part in parts):
            return tuple(parts)
    return None


def tinted(pixmap, colour: Any):
    """`pixmap` washed with `colour`, keeping its shape and its lines.
    The pixmap itself if there is no colour."""
    rgb = rgb_of(colour)
    if rgb is None or pixmap is None or pixmap.isNull():
        return pixmap
    from PyQt5 import QtCore, QtGui
    result = QtGui.QPixmap(pixmap.size())
    result.setDevicePixelRatio(pixmap.devicePixelRatio())
    result.fill(QtCore.Qt.transparent)
    painter = QtGui.QPainter(result)
    painter.drawPixmap(0, 0, pixmap)
    # SourceAtop: paint only where the squid already is.
    painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceAtop)
    painter.fillRect(result.rect(), QtGui.QColor(rgb[0], rgb[1], rgb[2], STRENGTH))
    painter.end()
    return result


__all__ = ['STRENGTH', 'rgb_of', 'tinted']
