from dataclasses import dataclass, field
from typing import Tuple
from enum import Enum


class AnimationStyleName(Enum):
    """Available animation style names."""
    VIBRANT = "vibrant"
    SUBTLE = "subtle"
    #NEURAL = "neural"
    DESIGNER = "designer"
    NONE = "none"


@dataclass
class AnimationStyle:
    """
    Base animation style configuration with vibrant defaults.
    Contains all visual parameters for connection and neuron animations.
    
    DEFAULTS: Matches the 'Vibrant' style.
    """
    # ===== STYLE METADATA =====
    name: str = "vibrant"
    display_name: str = "Default"
    description: str = "Living connections that breathe and pulse organically"
    
    # ===== CONNECTION LINE APPEARANCE =====
    # Vibrant defaults
    line_base_width: float = 1.3
    line_colour_positive: Tuple[int, int, int] = (40, 200, 80)      # Lush green
    line_colour_negative: Tuple[int, int, int] = (220, 70, 70)      # Warm red
    line_alpha: int = 180                                          # Base alpha (modulated by pulse)
    use_thick_lines: bool = False                                 # False for vibrant (uses glow instead)
    
    # ===== STRESS-ANXIETY CONNECTION (special red dashed line) =====
    stress_anxiety_width: float = 3.5
    stress_anxiety_colour: Tuple[int, int, int] = (255, 50, 50)
    stress_anxiety_dashed: bool = True
    
    # ===== PULSE / TRAVELLING DOT ANIMATION =====
    # Disabled in Vibrant (replaced by ambient pulse)
    pulse_enabled: bool = False                                     
    pulse_colour: Tuple[int, int, int] = (255, 255, 0)             # Yellow dot
    pulse_alpha: int = 200
    pulse_duration: float = 3.0                                     # Tuned for 10 FPS (slower)
    pulse_speed: float = 1.0                                        # 0-1 range for travel
    pulse_diameter: float = 6.0                                     # pixels (before scale)
    
    # ===== GLOW EFFECT (during weight change animations) =====
    glow_enabled: bool = True
    glow_colour: Tuple[int, int, int] = (255, 255, 150)
    glow_alpha: int = 60
    glow_fade_threshold: float = 0.7                                # fade out after this progress
    
    # ===== NEURON HOVER EFFECTS =====
    hover_enabled: bool = True
    hover_scale: float = 1.25                                       # expand on hover
    hover_animation_duration: float = 0.5                           # Slower for 10 FPS smoothness
    
    # ===== NEURON ACTIVITY HIGHLIGHT =====
    activity_highlight_enabled: bool = True
    activity_highlight_colour: Tuple[int, int, int] = (255, 255, 0)
    activity_highlight_alpha: int = 150
    activity_pulse_speed: float = 1.5                              # Slower Hz for 10 FPS
    
    # ===== NEUROGENESIS HIGHLIGHT =====
    neurogenesis_highlight_colour: Tuple[int, int, int] = (255, 215, 0)  # Gold
    neurogenesis_highlight_alpha: int = 200
    neurogenesis_highlight_duration: float = 5.0                    # seconds
    
    # ===== VIBRANT STYLE: AMBIENT PULSING =====
    # When enabled, connections gently "breathe" at random individual rates
    ambient_pulse_enabled: bool = True
    ambient_pulse_width_range: Tuple[float, float] = (0.7, 1.5)    # Width oscillates 70%-150%
    ambient_pulse_alpha_range: Tuple[int, int] = (120, 220)        # Alpha oscillates
    ambient_pulse_freq_range: Tuple[float, float] = (0.1, 0.25)    # Very slow breathing for 10 FPS
    ambient_pulse_phase_drift: float = 0.05                         # Subtle phase wandering
    
    # ===== SUBTLE STYLE: COMMUNICATION GLOWS =====
    # Enabled in Vibrant
    comm_glow_enabled: bool = True
    comm_glow_colour: Tuple[int, int, int] = (247, 181, 57)        # Warm gold/orange for Vibrant
    comm_glow_alpha: int = 200
    comm_glow_size: float = 8.0                                     
    comm_glow_tail_length: float = 0.2                             
    comm_glow_speed_range: Tuple[float, float] = (2.0, 3.5)        # 2-3.5s duration (~80px/s)
    comm_glow_fade_in: float = 0.1                                  # 0-1, fade in portion
    comm_glow_fade_out: float = 0.25                                # 0-1, fade out portion
    comm_glow_spawn_on_activity: bool = True                        # spawn when neurons active
    comm_glow_spawn_on_weight_change: bool = True                   # spawn on weight changes
    comm_glow_max_per_connection: int = 2                           # max simultaneous glows per line
    
    # ===== NEURAL STYLE: ACTIVATION PULSES =====
    # Disabled in Vibrant
    neural_pulse_enabled: bool = False
    neural_pulse_duration: float = 2.0                              # Slower: 2.0s duration
    neural_pulse_width: float = 8.0                                 # Thicker pulse for visibility
    neural_pulse_colour_positive: Tuple[int, int, int] = (180, 230, 255)  # Soft cyan glow
    neural_pulse_colour_negative: Tuple[int, int, int] = (255, 180, 150)  # Soft warm glow
    neural_weight_thickness: bool = False                           # scale line width by weight
    neural_weight_thickness_mult: float = 3.5                       # weight multiplier for thickness
    neural_base_colour_positive: Tuple[int, int, int] = (100, 200, 255)   # Cyan for excitatory
    neural_base_colour_negative: Tuple[int, int, int] = (255, 120, 100)   # Red for inhibitory
    neural_base_alpha: int = 180                                    # Base connection alpha
    
    # ===== BACKGROUND COLOUR =====
    background_colour: Tuple[int, int, int] = (248, 248, 245)      # Warmer Vibrant background

    # ===== WEIGHT-BASED THICKNESS (Used by Subtle) =====
    weight_thickness_enabled: bool = False
    weight_thickness_min: float = 1.0
    weight_thickness_max: float = 9.0
    weight_thickness_power: float = 1.0
    
    # ===== SCROLLING DOTS (Used by Subtle) =====
    scroll_enabled: bool = False
    scroll_dot_count: int = 3
    scroll_dot_size: float = 6.0
    scroll_dot_colour: Tuple[int, int, int] = (255, 255, 255)
    scroll_dot_alpha: int = 200
    scroll_speed_range: Tuple[float, float] = (1.5, 4.0)
    scroll_random_offsets: bool = True


@dataclass
class VibrantStyle(AnimationStyle):
    """
    Style 1: Vibrant - Living, breathing connections.
    Each connection pulses at its own organic rhythm, creating an 
    "alive" feel like a biological neural network. Tuned for 10 FPS.
    """
    name: str = "vibrant"
    display_name: str = "Default"
    description: str = "Living connections that breathe and pulse organically"
    
    # Explicitly matches defaults, listed here for clarity
    line_base_width: float = 1.3
    line_colour_positive: Tuple[int, int, int] = (40, 200, 80)
    line_colour_negative: Tuple[int, int, int] = (220, 70, 70)
    
    # Vibrant features
    ambient_pulse_enabled: bool = True
    comm_glow_enabled: bool = True
    
    # Disable conflicting styles
    pulse_enabled: bool = False
    neural_pulse_enabled: bool = False
    scroll_enabled: bool = False


@dataclass
class SubtleStyle(AnimationStyle):
    """
    Style 2: Flow - Scrolling dotted connections with weight-based thickness.
    Features green (positive) and red (negative) dotted lines with 
    continuously scrolling white dots. Line thickness scales with connection strength.
    """
    name: str = "subtle"
    display_name: str = "Flow"
    description: str = "Scrolling dotted lines with weight-based thickness"
    
    background_colour: Tuple[int, int, int] = (255, 255, 255)     # Pure white
    
    # Dotted lines
    line_base_width: float = 1.0
    line_colour_positive: Tuple[int, int, int] = (0, 200, 0)
    line_colour_negative: Tuple[int, int, int] = (200, 0, 0)
    line_alpha: int = 255
    line_style: int = 1                                            # Qt.DotLine
    
    # Weight-based thickness
    weight_thickness_enabled: bool = True
    
    # Scrolling dots
    scroll_enabled: bool = True
    scroll_dot_colour: Tuple[int, int, int] = (255, 255, 255)
    
    # Disable Pulse/Glow
    pulse_enabled: bool = False
    glow_enabled: bool = False
    ambient_pulse_enabled: bool = False
    comm_glow_enabled: bool = False
    neural_pulse_enabled: bool = False


@dataclass
class NeuralStyle(AnimationStyle):
    """
    Style 3: Neural - Synaptic activation visualization.
    Features weight-based line thickness and traveling activation pulses.
    """
    name: str = "neural"
    display_name: str = "Pink & Blue"
    description: str = "Highlights most active connections"
    
    line_base_width: float = 1.0
    line_colour_positive: Tuple[int, int, int] = (100, 200, 255)
    line_colour_negative: Tuple[int, int, int] = (255, 120, 100)
    line_alpha: int = 180
    use_thick_lines: bool = False
    
    #background_colour: Tuple[int, int, int] = (245, 247, 250)
    
    # Disable Pulse/Glow
    ambient_pulse_enabled: bool = False
    comm_glow_enabled: bool = False
    
    # Enable Neural Pulse
    neural_pulse_enabled: bool = True
    neural_weight_thickness: bool = True


@dataclass
class DesignerStyle(AnimationStyle):
    """
    Style 4: Structural - Heavy schematic view (Monochrome).
    Features extremely thick, weight-scaled lines with no movement.
    Connections are strictly Black (positive) or Grey (negative).
    """
    name: str = "designer"
    display_name: str = "Structural"
    description: str = "Heavy, static black & white schematic view"
    
    # ===== HEAVY, SOLID MONOCHROME LINES =====
    line_base_width: float = 4.0
    line_colour_positive: Tuple[int, int, int] = (0, 0, 0)          # Black
    line_colour_negative: Tuple[int, int, int] = (160, 160, 160)    # Grey
    line_alpha: int = 255                                           # Full opacity
    use_thick_lines: bool = True
    
    # Aggressive thickness scaling based on weight
    neural_weight_thickness: bool = True
    neural_weight_thickness_mult: float = 15.0                      # +15px at max weight
    neural_base_colour_positive: Tuple[int, int, int] = (0, 0, 0)   # Black
    neural_base_colour_negative: Tuple[int, int, int] = (160, 160, 160) # Grey
    neural_base_alpha: int = 255
    
    # Stress connection (Solid Black block)
    stress_anxiety_width: float = 6.0
    stress_anxiety_colour: Tuple[int, int, int] = (0, 0, 0)
    stress_anxiety_dashed: bool = False                             
    
    # ===== ZERO ANIMATION =====
    ambient_pulse_enabled: bool = False
    pulse_enabled: bool = False
    comm_glow_enabled: bool = False
    neural_pulse_enabled: bool = False
    glow_enabled: bool = False
    
    # Technical background
    #background_colour: Tuple[int, int, int] = (240, 240, 240)       # Light Grey
    
    # Minimal interactivity
    hover_enabled: bool = True
    hover_scale: float = 1.05
    hover_animation_duration: float = 0.2
    
    # Minimal highlighting (Greyscale)
    activity_highlight_enabled: bool = False
    neurogenesis_highlight_colour: Tuple[int, int, int] = (100, 100, 100) # Dark Grey
    neurogenesis_highlight_alpha: int = 50


@dataclass
class NoneStyle(AnimationStyle):
    '''
    Style 5: None - No animations - maximum performance.
    Static connections with weight-based thickness capped at 5px.
    '''
    name: str = 'none'
    display_name: str = 'Thin'
    description: str = 'No animations - maximum performance'
    
    # Disable ALL animation features
    pulse_enabled: bool = False
    glow_enabled: bool = False
    hover_enabled: bool = False
    activity_highlight_enabled: bool = False
    ambient_pulse_enabled: bool = False
    comm_glow_enabled: bool = False
    neural_pulse_enabled: bool = False
    
    # Basic visual settings
    line_base_width: float = 1.0
    
    # Matches Vibrant/Default colors (Green/Red)
    line_colour_positive: Tuple[int, int, int] = (40, 200, 80)
    line_colour_negative: Tuple[int, int, int] = (220, 70, 70)
    line_alpha: int = 180
    use_thick_lines: bool = False
    
    # ===== ENABLE WEIGHT-BASED THICKNESS (Max 5px) =====
    weight_thickness_enabled: bool = True
    weight_thickness_min: float = 1.0
    weight_thickness_max: float = 5.0  # Caps total thickness strictly at 5px
    weight_thickness_power: float = 1.0
    
    stress_anxiety_width: float = 2.0
    stress_anxiety_colour: Tuple[int, int, int] = (255, 100, 100)
    stress_anxiety_dashed: bool = False
    
    #background_colour: Tuple[int, int, int] = (240, 240, 245)
    
    # Zeroing logic for animations
    pulse_colour: Tuple[int, int, int] = (255, 255, 255)
    pulse_alpha: int = 0
    pulse_duration: float = 0
    pulse_speed: float = 0
    pulse_diameter: float = 0
    
    glow_colour: Tuple[int, int, int] = (255, 255, 255)
    glow_alpha: int = 0
    glow_fade_threshold: float = 0
    
    hover_scale: float = 1.0
    hover_animation_duration: float = 0
    
    activity_highlight_colour: Tuple[int, int, int] = (255, 255, 255)
    activity_highlight_alpha: int = 0
    activity_pulse_speed: float = 0
    
    neurogenesis_highlight_colour: Tuple[int, int, int] = (255, 200, 0)
    neurogenesis_highlight_alpha: int = 200
    neurogenesis_highlight_duration: float = 3.0  
    
    ambient_pulse_width_range: Tuple[float, float] = (0, 0)
    ambient_pulse_alpha_range: Tuple[int, int] = (0, 0)
    ambient_pulse_freq_range: Tuple[float, float] = (0, 0)
    ambient_pulse_phase_drift: float = 0
    
    comm_glow_colour: Tuple[int, int, int] = (255, 255, 255)
    comm_glow_alpha: int = 0
    comm_glow_size: float = 0
    comm_glow_tail_length: float = 0
    comm_glow_speed_range: Tuple[float, float] = (0, 0)
    comm_glow_fade_in: float = 0
    comm_glow_fade_out: float = 0
    comm_glow_spawn_on_activity: bool = False
    comm_glow_spawn_on_weight_change: bool = False
    comm_glow_max_per_connection: int = 0
    
    neural_pulse_duration: float = 0
    neural_pulse_width: float = 0
    neural_pulse_colour_positive: Tuple[int, int, int] = (255, 255, 255)
    neural_pulse_colour_negative: Tuple[int, int, int] = (255, 255, 255)
    neural_weight_thickness: bool = False
    neural_weight_thickness_mult: float = 1.0
    neural_base_colour_positive: Tuple[int, int, int] = (100, 200, 100)
    neural_base_colour_negative: Tuple[int, int, int] = (200, 100, 100)
    neural_base_alpha: int = 180


# ===== STYLE REGISTRY =====

ANIMATION_STYLES = {
    'none': NoneStyle,
    'vibrant': VibrantStyle,
    #'subtle': SubtleStyle,
    'neural': NeuralStyle,
    'designer': DesignerStyle,
}

def get_animation_style(name: str) -> AnimationStyle:
    """
    Get an animation style by name.
    
    Args:
        name: Style name ('vibrant', 'subtle', 'neural', 'designer', or 'none')
        
    Returns:
        AnimationStyle instance
        
    Raises:
        KeyError if style name not found
    """
    name_lower = name.lower()
    if name_lower not in ANIMATION_STYLES:
        raise KeyError(f"Unknown animation style: {name}. "
                      f"Available styles: {list(ANIMATION_STYLES.keys())}")
    return ANIMATION_STYLES[name_lower]


def get_available_styles() -> list:
    """Return list of available style names."""
    return list(ANIMATION_STYLES.keys())


def get_style_info() -> list:
    """Return list of (name, display_name, description) for all styles."""
    return [
        (style.name, style.display_name, style.description)
        for style in ANIMATION_STYLES.values()
    ]