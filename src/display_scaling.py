
class DisplayScaling:
    """The game's sizes are in real pixels, as Qt draws on Windows and Linux.

    A Retina Mac draws in points - two real pixels each - and reports its
    screen in points too (a 14" MacBook Pro is 1512x982 points, 3024x1964
    pixels). Taken as pixels, that made the Mac a small 1080p screen: the
    window shrank while every sprite kept its pixel size in points, twice its
    size on screen, so the squid filled a third of the tank. Here the screen
    is measured in real pixels and every size is turned back into points, so a
    Retina Mac looks as the game was designed. Where Qt draws in pixels the
    ratio is 1 and nothing changes.
    """
    DESIGN_WIDTH = 2880
    DESIGN_HEIGHT = 1920

    #: The tank window as designed, on the design screen - and the slightly
    #: larger share of the screen it takes on one no wider than 1920.
    DESIGN_WINDOW = (1344, 936)
    SMALL_WINDOW = (1440, 960)
    _window_base = DESIGN_WINDOW

    # Default scale factor (1.0 means no scaling)
    _scale_factor = 1.0
    #: Real pixels per point on the game's screen (2 on a Retina Mac).
    _ratio = 1.0
    _small_screen = False
    
    @classmethod
    def initialize(cls, current_width, current_height, ratio=1.0):
        """current_width/height as the screen reports them (points); ratio its
        devicePixelRatio."""
        cls._ratio = max(1.0, float(ratio or 1.0))
        current_width, current_height = current_width * cls._ratio, current_height * cls._ratio
        width_ratio = current_width / cls.DESIGN_WIDTH
        height_ratio = current_height / cls.DESIGN_HEIGHT
        base_scale_factor = min(width_ratio, height_ratio)
        
        cls._window_base = cls.SMALL_WINDOW if current_width <= 1920 else cls.DESIGN_WINDOW
        cls._small_screen = current_width <= 1920 and current_height <= 1080
        if cls._small_screen:
            cls._scale_factor = base_scale_factor * 0.85 / cls._ratio
            print(f"1080p display detected: applying 85% scaling (factor={cls._scale_factor:.2f})")
        else:
            cls._scale_factor = base_scale_factor / cls._ratio
            print(f"High resolution display ({current_width:.0f}x{current_height:.0f}): standard scaling (factor={cls._scale_factor:.2f})")

    @classmethod
    def initialize_for(cls, screen, available=False):
        """Initialise from a QScreen: its size (or available area) and ratio."""
        # The same on every system for the same screen: the screen's size,
        # or its size less one fixed allowance for a taskbar or dock - never
        # what this system's own bars happen to leave (src/desktop_style.py).
        from .desktop_style import screen_size, usable_size
        width, height, ratio = screen_size(screen)
        if available:
            width, height = usable_size(screen)
        cls.initialize(width, height, ratio)

    @classmethod
    def screen_pixels(cls, screen):
        """A QScreen's size in real pixels."""
        from .desktop_style import screen_size
        width, height, ratio = screen_size(screen)
        return int(width * ratio), int(height * ratio)

    @classmethod
    def window_size(cls):
        """The tank window's size on this screen."""
        return cls.scale(cls._window_base[0]), cls.scale(cls._window_base[1])

    @classmethod
    def tank_scale(cls):
        """How large the tank is drawn on this screen, against its design:
        1 on the design screen, about a half on a 1080p one. Everything that
        lives in the tank - the squid, food, rocks, eggs, ink - is drawn at
        this scale, so the tank is one picture, larger or smaller, and a
        squid takes up the same share of it on every screen. (The squid used
        to be 70% on a 1080p screen and the food full size, in a tank at 48%:
        a squid half as tall as its tank.)"""
        return cls._window_base[0] * cls._scale_factor / cls.DESIGN_WINDOW[0]

    @classmethod
    def points(cls, pixels):
        """A size designed in pixels of the design tank, as drawn here."""
        return max(1, int(round(pixels * cls.tank_scale())))

    @classmethod
    def to_points(cls, pixmap):
        """A sprite of the tank, at the size the tank is drawn here."""
        scale = cls.tank_scale()
        if abs(scale - 1.0) < 1e-6 or pixmap is None or pixmap.isNull():
            return pixmap
        from PyQt5 import QtCore
        return pixmap.scaled(cls.points(pixmap.width()), cls.points(pixmap.height()),
                             QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

    @classmethod
    def squid_scale(cls):
        """How a squid's images are scaled: with the tank."""
        return cls.tank_scale()
    
    @classmethod
    def scale(cls, value):
        return int(value * cls._scale_factor)
        
    @classmethod
    def font_size(cls, size):
        scaled = cls.scale(size)
        return max(10, scaled)
    
    @classmethod
    def get_scale_factor(cls):
        return cls._scale_factor
        
    @classmethod
    def scale_css(cls, css_string):
        import re
        pattern = r'font-size:\s*(\d+)px'
        def replace_size(match):
            original_size = int(match.group(1))
            scaled_size = cls.font_size(original_size)
            return f'font-size: {scaled_size}px'
        return re.sub(pattern, replace_size, css_string)
