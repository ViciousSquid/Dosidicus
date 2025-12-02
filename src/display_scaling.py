# Create new file: display_scaling.py
class DisplayScaling:
    DESIGN_WIDTH = 2880
    DESIGN_HEIGHT = 1920
    _scale_factor = 1.0
    
    # Default scale factor (1.0 means no scaling)
    _scale_factor = 1.0
    
    @classmethod
    def initialize(cls, current_width, current_height):
        width_ratio = current_width / cls.DESIGN_WIDTH
        height_ratio = current_height / cls.DESIGN_HEIGHT
        base_scale_factor = min(width_ratio, height_ratio)
        
        if current_width <= 1920 and current_height <= 1080:
            cls._scale_factor = base_scale_factor * 0.85
            print(f"1080p display detected: applying 85% scaling (factor={cls._scale_factor:.2f})")
        else:
            cls._scale_factor = base_scale_factor
            print(f"High resolution display ({current_width}x{current_height}): standard scaling (factor={cls._scale_factor:.2f})")
    
    @classmethod
    def scale(cls, value):
        return int(value * cls._scale_factor)
        
    @classmethod
    def font_size(cls, size):
        scaled = cls.scale(size)
        return max(8, scaled)
    
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