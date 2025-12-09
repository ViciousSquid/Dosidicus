"""
animation_styles.py
Centralised animation styles for BrainWidget connection and neuron animations.
Swap or edit these dataclasses to change the visual style without touching renderer code.

Style 1 (Vibrant): Living, breathing connections that pulse organically (default)
Style 2 (Subtle): Communication glows travel along connections like neural signals
Style 3 (Neural): Synaptic activation pulses with weight-scaled connections
Style 4 (Designer): Fat weight-scaled lines with traveling orbs (matches Brain Designer)
Style 5 (None): Static connections with no animation effects
"""

from dataclasses import dataclass, field
from typing import Tuple
from enum import Enum


class AnimationStyleName(Enum):
    """Available animation style names."""
    VIBRANT = "vibrant"
    SUBTLE = "subtle"
    NEURAL = "neural"
    DESIGNER = "designer"
    NONE = "none"


@dataclass
class AnimationStyle:
    """
    Base animation style configuration with vibrant defaults.
    Contains all visual parameters for connection and neuron animations.
    """
    # ===== STYLE METADATA =====
    name: str = "vibrant"
    display_name: str = "Default"
    description: str = "Living connections that breathe and pulse organically"
    
    # ===== CONNECTION LINE APPEARANCE =====
    line_base_width: float = 1.3
    line_colour_positive: Tuple[int, int, int] = (40, 200, 80)      # Lush green
    line_colour_negative: Tuple[int, int, int] = (220, 70, 70)      # Warm red
    line_alpha: int = 180                                          # Base alpha (modulated by pulse)
    use_thick_lines: bool = True                                  # Glow effect on animations
    
    # ===== STRESS-ANXIETY CONNECTION (special red dashed line) =====
    stress_anxiety_width: float = 3.5
    stress_anxiety_colour: Tuple[int, int, int] = (255, 50, 50)
    stress_anxiety_dashed: bool = True
    
    # ===== PULSE / TRAVELLING DOT ANIMATION =====
    pulse_enabled: bool = False                                     # Disabled for vibrant
    pulse_colour: Tuple[int, int, int] = (255, 255, 0)             # Yellow dot
    pulse_alpha: int = 200
    pulse_duration: float = 2.0                                     # seconds
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
    hover_animation_duration: float = 0.2                           # seconds
    
    # ===== NEURON ACTIVITY HIGHLIGHT =====
    activity_highlight_enabled: bool = True
    activity_highlight_colour: Tuple[int, int, int] = (255, 255, 0)
    activity_highlight_alpha: int = 150
    activity_pulse_speed: float = 10.0                              # Hz
    
    # ===== NEUROGENESIS HIGHLIGHT =====
    neurogenesis_highlight_colour: Tuple[int, int, int] = (255, 215, 0)  # Gold
    neurogenesis_highlight_alpha: int = 200
    neurogenesis_highlight_duration: float = 5.0                    # seconds
    
    # ===== VIBRANT STYLE: AMBIENT PULSING =====
    # When enabled, connections gently "breathe" at random individual rates
    ambient_pulse_enabled: bool = True
    ambient_pulse_width_range: Tuple[float, float] = (0.7, 1.5)    # Width oscillates 70%-150%
    ambient_pulse_alpha_range: Tuple[int, int] = (120, 220)        # Alpha oscillates
    ambient_pulse_freq_range: Tuple[float, float] = (0.2, 0.6)     # Slow, organic breathing
    ambient_pulse_phase_drift: float = 0.05                         # Subtle phase wandering
    
    # ===== SUBTLE STYLE: COMMUNICATION GLOWS =====
    # When enabled, glowing packets travel along connections during communication
    comm_glow_enabled: bool = False
    comm_glow_colour: Tuple[int, int, int] = (180, 220, 255)       # Soft blue-white
    comm_glow_alpha: int = 180
    comm_glow_size: float = 12.0                                    # diameter in pixels
    comm_glow_tail_length: float = 0.15                             # 0-1, how much of line is tail
    comm_glow_speed_range: Tuple[float, float] = (0.4, 1.2)        # seconds to traverse
    comm_glow_fade_in: float = 0.1                                  # 0-1, fade in portion
    comm_glow_fade_out: float = 0.2                                 # 0-1, fade out portion
    comm_glow_spawn_on_activity: bool = True                        # spawn when neurons active
    comm_glow_spawn_on_weight_change: bool = True                   # spawn on weight changes
    comm_glow_max_per_connection: int = 3                           # max simultaneous glows per line
    
    # ===== NEURAL STYLE: ACTIVATION PULSES =====
    # Traveling light pulses along connections during neural communication
    neural_pulse_enabled: bool = False
    neural_pulse_duration: float = 0.9                              # seconds for full travel
    neural_pulse_width: float = 7.0                                 # pulse line thickness
    neural_pulse_colour_positive: Tuple[int, int, int] = (180, 230, 255)  # Soft cyan glow
    neural_pulse_colour_negative: Tuple[int, int, int] = (255, 180, 150)  # Soft warm glow
    neural_weight_thickness: bool = False                           # scale line width by weight
    neural_weight_thickness_mult: float = 3.5                       # weight multiplier for thickness
    neural_base_colour_positive: Tuple[int, int, int] = (100, 200, 255)   # Cyan for excitatory
    neural_base_colour_negative: Tuple[int, int, int] = (255, 120, 100)   # Red for inhibitory
    neural_base_alpha: int = 180                                    # Base connection alpha


@dataclass  
class VibrantStyle(AnimationStyle):
    """
    Style 1: Vibrant - Living, breathing connections.
    Each connection pulses at its own organic rhythm, creating an 
    "alive" feel like a biological neural network.
    """
    name: str = "vibrant"
    display_name: str = "Default"
    description: str = "Living connections that breathe and pulse organically"
    
    # Slightly thicker base lines for visibility
    line_base_width: float = 1.3
    line_colour_positive: Tuple[int, int, int] = (40, 200, 80)      # Lush green
    line_colour_negative: Tuple[int, int, int] = (220, 70, 70)      # Warm red
    line_alpha: int = 180                                            # Base alpha (modulated by pulse)
    use_thick_lines: bool = False
    
    # Brighter stress connection
    stress_anxiety_width: float = 3.5
    stress_anxiety_colour: Tuple[int, int, int] = (255, 50, 50)
    
    # Disable the old weight-change pulse (replaced by ambient pulse)
    pulse_enabled: bool = False
    
    # Keep glow for weight changes
    glow_enabled: bool = True
    glow_colour: Tuple[int, int, int] = (255, 255, 150)
    glow_alpha: int = 60
    
    # Enable hover effects for interactivity
    hover_enabled: bool = True
    hover_scale: float = 1.25
    hover_animation_duration: float = 0.2
    
    # Warmer background
    background_colour: Tuple[int, int, int] = (248, 248, 245)
    
    # ===== VIBRANT'S SIGNATURE: AMBIENT PULSING =====
    # Each connection breathes at its own rate
    ambient_pulse_enabled: bool = True
    ambient_pulse_width_range: Tuple[float, float] = (0.7, 1.5)
    ambient_pulse_alpha_range: Tuple[int, int] = (120, 220)
    ambient_pulse_freq_range: Tuple[float, float] = (0.2, 0.6)
    ambient_pulse_phase_drift: float = 0.05

    # ===== Communication glows =====
    comm_glow_enabled: bool = True
    comm_glow_colour: Tuple[int, int, int] = (247, 181, 57)
    comm_glow_alpha: int = 200
    comm_glow_size: float = 4.0
    comm_glow_tail_length: float = 0.15
    comm_glow_speed_range: Tuple[float, float] = (0.8, 1.5)  # Pulse Speed
    comm_glow_fade_in: float = 0.1
    comm_glow_fade_out: float = 0.25
    comm_glow_spawn_on_activity: bool = True
    comm_glow_spawn_on_weight_change: bool = True
    comm_glow_max_per_connection: int = 1  # ← Less frequent: only 1 glow per link


@dataclass
class SubtleStyle(AnimationStyle):
    """
    Style 2: Subtle - Neural signal visualization.
    Soft glowing packets travel along connections when neurons communicate,
    like signals flowing through a biological network. Each glow travels
    independently creating organic, chaotic but smooth movement.
    """
    name: str = "subtle"
    display_name: str = "Synapses"
    description: str = "Neural signals flow as glowing packets along connections"
    
    # Thinner, more muted base lines to let glows stand out
    line_base_width: float = 0.7
    line_colour_positive: Tuple[int, int, int] = (100, 160, 100)    # Muted sage green
    line_colour_negative: Tuple[int, int, int] = (160, 100, 100)    # Muted dusty rose
    line_alpha: int = 100                                            # Lower alpha, glows add brightness
    use_thick_lines: bool = False
    
    # Softer stress connection
    stress_anxiety_width: float = 2.0
    stress_anxiety_colour: Tuple[int, int, int] = (180, 90, 90)
    
    # Disable old pulse system
    pulse_enabled: bool = False
    
    # Subtle glow on weight changes
    glow_enabled: bool = True
    glow_colour: Tuple[int, int, int] = (200, 220, 255)
    glow_alpha: int = 40
    
    # Enable gentle hover
    hover_enabled: bool = True
    hover_scale: float = 1.12
    hover_animation_duration: float = 0.3
    
    # Activity highlights more subtle
    activity_highlight_alpha: int = 100
    activity_pulse_speed: float = 6.0
    
    # Cool, calm background
    background_colour: Tuple[int, int, int] = (242, 244, 248)
    
    # No ambient pulsing for subtle
    ambient_pulse_enabled: bool = False
    
    # ===== SUBTLE'S SIGNATURE: COMMUNICATION GLOWS =====
    # Glowing packets travel along connections, visualizing neural signals
    comm_glow_enabled: bool = True
    comm_glow_colour: Tuple[int, int, int] = (160, 200, 255)       # Soft electric blue
    comm_glow_alpha: int = 200
    comm_glow_size: float = 10.0                                    # Glow diameter
    comm_glow_tail_length: float = 0.2                              # 20% of line trails behind
    comm_glow_speed_range: Tuple[float, float] = (0.6, 1.8)        # Variable speeds (chaotic)
    comm_glow_fade_in: float = 0.1                                  # Quick fade in
    comm_glow_fade_out: float = 0.25                                # Gentle fade out
    comm_glow_spawn_on_activity: bool = True                        # Spawn when neuron active
    comm_glow_spawn_on_weight_change: bool = True                   # Spawn on learning
    comm_glow_max_per_connection: int = 4                           # Allow multiple glows


@dataclass
class NeuralStyle(AnimationStyle):
    """
    Style 3: Neural - Synaptic activation visualization.
    Features weight-based line thickness and traveling activation pulses
    that flow along connections during neural communication. Lines glow
    with cyan for excitatory and warm red for inhibitory connections.
    """
    name: str = "neural"
    display_name: str = "Heatmap"
    description: str = "Highlights most active connections"
    
    # Base lines are colored by weight sign, thickness by weight magnitude
    line_base_width: float = 1.0                                    # Minimum width
    line_colour_positive: Tuple[int, int, int] = (100, 200, 255)    # Soft cyan
    line_colour_negative: Tuple[int, int, int] = (255, 120, 100)    # Soft coral
    line_alpha: int = 180
    use_thick_lines: bool = False
    
    # Softer stress connection (matches the style)
    stress_anxiety_width: float = 3.0
    stress_anxiety_colour: Tuple[int, int, int] = (255, 100, 100)
    
    # Disable old pulse systems - neural style has its own
    pulse_enabled: bool = True
    glow_enabled: bool = False
    
    # Enable hover for interactivity
    hover_enabled: bool = True
    hover_scale: float = 1.2
    hover_animation_duration: float = 0.15
    
    # Neutral background
    background_colour: Tuple[int, int, int] = (245, 247, 250)
    
    # No ambient pulse or comm glows
    ambient_pulse_enabled: bool = False
    comm_glow_enabled: bool = False
    
    # ===== NEURAL'S SIGNATURE: ACTIVATION PULSES =====
    # Traveling light pulses with sinusoidal fade, weight-scaled thickness
    neural_pulse_enabled: bool = True
    neural_pulse_duration: float = 0.9                              # Fast, snappy pulses
    neural_pulse_width: float = 7.0                                 # Thick glowing pulse
    neural_pulse_colour_positive: Tuple[int, int, int] = (180, 230, 255)  # Bright cyan glow
    neural_pulse_colour_negative: Tuple[int, int, int] = (255, 180, 150)  # Warm coral glow
    neural_weight_thickness: bool = True                            # Enable weight-based thickness
    neural_weight_thickness_mult: float = 3.5                       # Thickness = weight * this
    neural_base_colour_positive: Tuple[int, int, int] = (100, 200, 255)
    neural_base_colour_negative: Tuple[int, int, int] = (255, 120, 100)
    neural_base_alpha: int = 180


@dataclass
class DesignerStyle(AnimationStyle):
    """
    Style 5: Designer - Matches the Brain Designer visualization.
    Features weight-scaled line thickness (fat lines for strong connections),
    dashed lines for inhibitory connections, and traveling pulse orbs.
    Mimics the SmartConnectionItem rendering from designer_canvas.py.
    """
    name: str = "designer"
    display_name: str = "Designer"
    description: str = "Fat weight-scaled lines with traveling orbs (matches Brain Designer)"
    
    # ===== CONNECTION LINE APPEARANCE =====
    # Designer uses: base_thickness = 2.0 + (abs_weight * 20.0)
    # We set base_width low, thickness scaling is handled via neural_weight_thickness
    line_base_width: float = 2.0
    line_colour_positive: Tuple[int, int, int] = (50, 205, 50)     # Lime green (matches designer)
    line_colour_negative: Tuple[int, int, int] = (220, 20, 60)     # Crimson red (matches designer)
    line_alpha: int = 255                                          # Full opacity
    use_thick_lines: bool = True
    
    # Stress-anxiety inherits standard handling
    stress_anxiety_width: float = 4.0
    stress_anxiety_colour: Tuple[int, int, int] = (255, 50, 50)
    stress_anxiety_dashed: bool = True
    
    # ===== DESIGNER'S SIGNATURE: WEIGHT-SCALED THICKNESS + PULSE ORBS =====
    # Disable ambient pulse (we use designer-style traveling orbs instead)
    ambient_pulse_enabled: bool = False
    
    # Enable neural-style weight thickness (this gives us the fat lines)
    neural_weight_thickness: bool = True
    neural_weight_thickness_mult: float = 20.0  # 2px base + weight * 20 = up to 22px
    neural_base_colour_positive: Tuple[int, int, int] = (50, 205, 50)
    neural_base_colour_negative: Tuple[int, int, int] = (220, 20, 60)
    neural_base_alpha: int = 255
    
    # Enable traveling pulse orbs (designer's animated dot)
    pulse_enabled: bool = True
    pulse_colour: Tuple[int, int, int] = (255, 255, 255)          # White core
    pulse_alpha: int = 255
    pulse_duration: float = 3.0                                    # Slower travel
    pulse_speed: float = 0.6                                       # Moderate speed
    pulse_diameter: float = 10.0                                   # Larger orb
    
    # Communication glows styled as designer orbs
    comm_glow_enabled: bool = True
    comm_glow_colour: Tuple[int, int, int] = (255, 255, 255)      # White glow center
    comm_glow_alpha: int = 220
    comm_glow_size: float = 12.0                                   # Matches designer orb_size
    comm_glow_tail_length: float = 0.0                             # No tail, just orb
    comm_glow_speed_range: Tuple[float, float] = (2.0, 3.5)       # Steady travel
    comm_glow_fade_in: float = 0.05                                # Quick fade in
    comm_glow_fade_out: float = 0.1                                # Quick fade out
    comm_glow_spawn_on_activity: bool = True
    comm_glow_spawn_on_weight_change: bool = True
    comm_glow_max_per_connection: int = 2                          # Allow multiple orbs
    
    # No neural pulse (we use comm_glow for orbs)
    neural_pulse_enabled: bool = False
    
    # Keep glow effect for weight changes
    glow_enabled: bool = True
    glow_colour: Tuple[int, int, int] = (255, 255, 100)
    glow_alpha: int = 80
    glow_fade_threshold: float = 0.7
    
    # Enable hover for interactivity
    hover_enabled: bool = True
    hover_scale: float = 1.15
    hover_animation_duration: float = 0.15
    
    # Activity highlight
    activity_highlight_enabled: bool = True
    activity_highlight_colour: Tuple[int, int, int] = (255, 255, 150)
    activity_highlight_alpha: int = 180
    activity_pulse_speed: float = 8.0
    
    # Neurogenesis highlight (gold flash)
    neurogenesis_highlight_colour: Tuple[int, int, int] = (255, 215, 0)
    neurogenesis_highlight_alpha: int = 220
    neurogenesis_highlight_duration: float = 5.0
    
    # Background - neutral gray like designer
    background_colour: Tuple[int, int, int] = (248, 248, 248)


@dataclass
class NoneStyle(AnimationStyle):
    '''No animations - maximum performance.'''
    
    name = 'none'
    display_name = 'None'
    description = 'No animations - maximum performance'
    
    # Disable ALL animation features
    pulse_enabled = False
    glow_enabled = False
    hover_enabled = False
    activity_highlight_enabled = False
    ambient_pulse_enabled = False
    comm_glow_enabled = False
    neural_pulse_enabled = False
    
    # Basic visual settings (static only)
    line_base_width = 2
    line_colour_positive = (100, 200, 100, 180)
    line_colour_negative = (200, 100, 100, 180)
    line_alpha = 180
    use_thick_lines = False
    
    stress_anxiety_width = 2
    stress_anxiety_colour = (255, 100, 100, 180)
    stress_anxiety_dashed = False
    
    background_colour = (240, 240, 245)
    
    # All animation values zeroed
    pulse_colour = (255, 255, 255)
    pulse_alpha = 0
    pulse_duration = 0
    pulse_speed = 0
    pulse_diameter = 0
    
    glow_colour = (255, 255, 255)
    glow_alpha = 0
    glow_fade_threshold = 0
    
    hover_scale = 1.0
    hover_animation_duration = 0
    
    activity_highlight_colour = (255, 255, 255)
    activity_highlight_alpha = 0
    activity_pulse_speed = 0
    
    neurogenesis_highlight_colour = (255, 200, 0)
    neurogenesis_highlight_alpha = 200
    neurogenesis_highlight_duration = 3.0  # Keep this so neurogenesis is still visible
    
    # Vibrant-specific (disabled)
    ambient_pulse_width_range = (0, 0)
    ambient_pulse_alpha_range = (0, 0)
    ambient_pulse_freq_range = (0, 0)
    ambient_pulse_phase_drift = 0
    
    # Subtle-specific (disabled)
    comm_glow_colour = (255, 255, 255)
    comm_glow_alpha = 0
    comm_glow_size = 0
    comm_glow_tail_length = 0
    comm_glow_speed_range = (0, 0)
    comm_glow_fade_in = 0
    comm_glow_fade_out = 0
    comm_glow_spawn_on_activity = False
    comm_glow_spawn_on_weight_change = False
    comm_glow_max_per_connection = 0
    
    # Neural-specific (disabled)
    neural_pulse_duration = 0
    neural_pulse_width = 0
    neural_pulse_colour_positive = (255, 255, 255)
    neural_pulse_colour_negative = (255, 255, 255)
    neural_weight_thickness = False
    neural_weight_thickness_mult = 1.0
    neural_base_colour_positive = (100, 200, 100)
    neural_base_colour_negative = (200, 100, 100)
    neural_base_alpha = 180


# ===== STYLE REGISTRY =====

ANIMATION_STYLES = {
    'none': NoneStyle,
    'vibrant': VibrantStyle,
    'subtle': SubtleStyle,
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
    """Return list of (name, display_name, description) tuples for all styles."""
    return [
        (style.name, style.display_name, style.description)
        for style in ANIMATION_STYLES.values()
    ]