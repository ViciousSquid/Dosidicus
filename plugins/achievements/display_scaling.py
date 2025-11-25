"""
Portable copy of DisplayScaling for the Achievements plugin.
Keep this file in the same folder as main.py
"""

import re

class DisplayScaling:
    """
    Utility class that computes a single scale-factor from the current
    screen resolution versus the design resolution (2880 × 1920).
    All UI measurements are then multiplied by this factor.
    """

    DESIGN_WIDTH  = 2880
    DESIGN_HEIGHT = 1920
    _scale_factor = 1.0

    @classmethod
    def initialize(cls, current_width: int, current_height: int) -> None:
        """Call once after we know the real screen size."""
        width_ratio  = current_width  / cls.DESIGN_WIDTH
        height_ratio = current_height / cls.DESIGN_HEIGHT
        base_scale   = min(width_ratio, height_ratio)

        # Slightly smaller UI on 1080p screens
        if current_width <= 1920 and current_height <= 1080:
            cls._scale_factor = base_scale * 0.85
        else:
            cls._scale_factor = base_scale

    @classmethod
    def scale(cls, value: int | float) -> int:
        """Scale an integer or float pixel value."""
        return int(value * cls._scale_factor)

    @classmethod
    def font_size(cls, size: int) -> int:
        """Return a font size guaranteed to be at least 8 pt."""
        return max(8, cls.scale(size))

    @classmethod
    def get_scale_factor(cls) -> float:
        return cls._scale_factor

    @classmethod
    def scale_css(cls, css_string: str) -> str:
        """Replace font-size:Xpx with scaled value inside a CSS snippet."""
        pattern = r'font-size:\s*(\d+)px'
        def _repl(m: re.Match) -> str:
            return f"font-size:{cls.font_size(int(m.group(1)))}px"
        return re.sub(pattern, _repl, css_string)
