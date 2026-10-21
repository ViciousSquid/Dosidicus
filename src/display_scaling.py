
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
        size = screen.availableGeometry() if available else screen.size()
        cls.initialize(size.width(), size.height(), screen.devicePixelRatio())

    @classmethod
    def screen_pixels(cls, screen):
        """A QScreen's size in real pixels."""
        ratio = max(1.0, float(screen.devicePixelRatio() or 1.0))
        return int(screen.size().width() * ratio), int(screen.size().height() * ratio)

    @classmethod
    def points(cls, pixels):
        """A size the game gives in real pixels, in points."""
        return max(1, int(round(pixels / cls._ratio)))

    @classmethod
    def to_points(cls, pixmap):
        """A sprite drawn at its pixel size, as many points as it has pixels
        on screen."""
        if cls._ratio == 1.0 or pixmap is None or pixmap.isNull():
            return pixmap
        from PyQt5 import QtCore
        return pixmap.scaled(cls.points(pixmap.width()), cls.points(pixmap.height()),
                             QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

    @classmethod
    def squid_scale(cls):
        """How a squid's images are scaled: 70% on a 1080p screen, in points."""
        return (0.7 if cls._small_screen else 1.0) / cls._ratio
    
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
