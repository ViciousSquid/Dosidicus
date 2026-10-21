"""
Portable DisplayScaling for the achievements plugin.
Keep this file in the same folder as main.py

The plugin's sizes were laid out for a 1920x1080 screen - and its scale
factor was never initialised, so it stayed 1.0 everywhere. On Windows and
Linux that is what the sizes were designed for. On a Mac, Qt measures
everything in points, and a 14" MacBook Pro is only 1512x982 points: a
650-point-tall dialog took two thirds of the screen and the toast covered a
corner of the tank.

The factor is now the screen's size in Qt's own units against 1920x1080,
never above 1.0. A 1080p (or larger) Windows/Linux screen gets exactly the
sizes it always had; a smaller one - a Mac's point-sized screen, or a 1366x768
laptop - gets everything shrunk to the same proportion of the screen.
"""

import re


class DisplayScaling:
    """
    Utility class that computes a single scale-factor from the size of the
    screen the game is on versus the design screen (1920 x 1080).
    All UI measurements are then multiplied by this factor.
    """

    DESIGN_WIDTH = 1920
    DESIGN_HEIGHT = 1080
    _scale_factor = None

    @classmethod
    def initialize(cls, current_width: int, current_height: int) -> None:
        """Set the factor from a screen size in Qt's units (points on a Mac)."""
        width_ratio = current_width / cls.DESIGN_WIDTH
        height_ratio = current_height / cls.DESIGN_HEIGHT
        cls._scale_factor = max(0.5, min(1.0, width_ratio, height_ratio))

    @classmethod
    def _ensure(cls) -> float:
        """Initialise from the primary screen the first time a size is asked
        for; 1.0 if there is no screen to measure yet."""
        if cls._scale_factor is None:
            try:
                from PyQt5 import QtWidgets
                app = QtWidgets.QApplication.instance()
                screen = app.primaryScreen() if app is not None else None
                if screen is None:
                    return 1.0
                size = screen.size()
                cls.initialize(size.width(), size.height())
            except Exception:
                return 1.0
        return cls._scale_factor

    @classmethod
    def scale(cls, value: int | float) -> int:
        """Scale an integer or float pixel value."""
        return int(value * cls._ensure())

    @classmethod
    def font_size(cls, size: int) -> int:
        """Return a font size guaranteed to be at least 8 pt."""
        return max(8, cls.scale(size))

    @classmethod
    def get_scale_factor(cls) -> float:
        return cls._ensure()

    @classmethod
    def scale_css(cls, css_string: str) -> str:
        """Replace font-size:Xpx with scaled value inside a CSS snippet."""
        pattern = r'font-size:\s*(\d+)px'
        def _repl(m: re.Match) -> str:
            return f"font-size:{cls.font_size(int(m.group(1)))}px"
        return re.sub(pattern, _repl, css_string)
