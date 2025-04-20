# Create new file: display_scaling.py
class DisplayScaling:
    """Global utility for handling display scaling across different resolutions"""
    
    # Reference design resolution
    DESIGN_WIDTH = 2880
    DESIGN_HEIGHT = 1920
    
    # Default scale factor (1.0 means no scaling)
    _scale_factor = 1.0
    
    @classmethod
    def initialize(cls, current_width, current_height):
        """Initialize scaling based on current screen dimensions"""
        # Calculate scale factor (smaller value means smaller UI elements)
        width_ratio = current_width / cls.DESIGN_WIDTH
        height_ratio = current_height / cls.DESIGN_HEIGHT
        
        # Use the smaller ratio to ensure everything fits
        base_scale_factor = min(width_ratio, height_ratio)
        
        # Apply resolution-specific adjustments
        if current_width <= 1920 and current_height <= 1080:
            # For 1080p, reduce by additional 15% to avoid oversized elements
            cls._scale_factor = base_scale_factor * 0.85
            print(f"1080p display detected: applying 85% scaling (factor={cls._scale_factor:.2f})")
        else:
            cls._scale_factor = base_scale_factor
            print(f"High resolution display: standard scaling (factor={cls._scale_factor:.2f})")
    
    @classmethod
    def scale(cls, value):
        """Scale a size value based on current display scaling"""
        return int(value * cls._scale_factor)
        
    @classmethod
    def font_size(cls, size):
        """Scale a font size with a minimum threshold to keep text readable"""
        scaled = cls.scale(size)
        # Ensure minimum readable font size (8pt)
        return max(8, scaled)
    
    @classmethod
    def get_scale_factor(cls):
        """Get the current scale factor"""
        return cls._scale_factor
        
    @classmethod
    def scale_css(cls, css_string):
        """Scale font sizes in CSS strings"""
        import re
        
        # Find all font-size declarations
        pattern = r'font-size:\s*(\d+)px'
        
        def replace_size(match):
            original_size = int(match.group(1))
            scaled_size = cls.font_size(original_size)
            return f'font-size: {scaled_size}px'
        
        # Replace all font sizes with scaled versions
        return re.sub(pattern, replace_size, css_string)