"""
brain_render_worker.py - Offscreen rendering worker for brain visualization

Renders the neural network visualization to a QImage in a background thread,
then the main thread just blits that image. This dramatically improves UI
responsiveness by moving expensive drawing operations off the main thread.

Usage:
    1. Create BrainRenderWorker with reference to brain widget
    2. Call request_render() when state changes
    3. Connect to render_complete signal to receive the rendered QImage
    4. In paintEvent, just draw the cached image
"""

import time
import math
import re
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from PyQt5.QtCore import QThread, pyqtSignal, QMutex, QMutexLocker, QWaitCondition, QSize, Qt, QPointF, QRectF
from PyQt5.QtGui import QImage, QPainter, QColor, QPen, QBrush, QFont, QPolygonF


@dataclass
class RenderState:
    """Snapshot of all data needed to render the brain"""
    # Neuron data
    neuron_positions: Dict[str, Tuple[float, float]] = field(default_factory=dict)
    neuron_states: Dict[str, float] = field(default_factory=dict)
    state_colors: Dict[str, Tuple[int, int, int]] = field(default_factory=dict)
    neuron_shapes: Dict[str, str] = field(default_factory=dict)
    
    # Pre-calculated localized labels
    neuron_labels: Dict[str, str] = field(default_factory=dict)
    
    # Connection data
    weights: Dict[Tuple[str, str], float] = field(default_factory=dict)
    communication_events: Dict[str, float] = field(default_factory=dict)
    
    # Visibility
    visible_neurons: set = field(default_factory=set)
    excluded_neurons: set = field(default_factory=set)
    
    # Animation state
    link_opacities: Dict[Tuple[str, str], float] = field(default_factory=dict)
    animation_time: float = 0.0
    
    # [NEW] Active weight animations for Hebbian learning
    weight_animations: List[Dict] = field(default_factory=list)
    
    # Display settings
    show_weights: bool = False
    is_tutorial_mode: bool = False
    
    # ===== ANIMATION STYLE PARAMETERS =====
    # Base visual settings
    anim_background_colour: Tuple[int, int, int] = (30, 30, 40)
    anim_line_base_width: float = 1.0
    anim_line_col_pos: Tuple[int, int, int] = (100, 255, 100)
    anim_line_col_neg: Tuple[int, int, int] = (255, 100, 100)
    anim_line_alpha: int = 180
    anim_line_style: int = 0  # Qt.SolidLine
    
    # Weight-based thickness
    weight_thickness_enabled: bool = False
    weight_thickness_min: float = 1.0
    weight_thickness_max: float = 2.0
    weight_thickness_power: float = 1.0
    
    # Scroll settings
    scroll_enabled: bool = False
    scroll_dot_count: int = 3
    scroll_dot_size: float = 6.0
    scroll_dot_colour: Tuple[int, int, int] = (255, 255, 255)
    scroll_dot_alpha: int = 200
    scroll_speed_range: Tuple[float, float] = (1.5, 4.0)
    
    # Pulse effects
    anim_pulse_enabled: bool = True
    anim_pulse_colour: Tuple[int, int, int] = (255, 255, 255)
    anim_pulse_alpha: int = 180
    anim_pulse_diameter: float = 8.0
    
    # Glow effects
    anim_glow_enabled: bool = True
    anim_glow_colour: Tuple[int, int, int] = (255, 255, 200)
    anim_glow_alpha: int = 60
    anim_glow_fade_threshold: float = 0.5
    
    # Communication glow
    anim_comm_glow_enabled: bool = False
    
    # Layers
    layers: List[Dict] = field(default_factory=list)
    
    # Widget size
    width: int = 1024
    height: int = 768
    
    # Hover state
    hovered_neuron: Optional[str] = None
    hover_value_display_active: bool = False
    
    # Font settings
    neuron_label_font_size: int = 6
    
    # Timestamp for cache invalidation
    timestamp: float = field(default_factory=time.time)


class BrainRenderWorker(QThread):
    """
    Background worker that renders brain visualization to QImage.
    
    Signals:
        render_complete: Emitted when a new frame is ready
            - QImage: The rendered frame
            - float: Render time in ms
    """
    
    render_complete = pyqtSignal(QImage, float)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        
        # Thread control
        self._running = True
        self._render_requested = False
        
        # State mutex
        self._state_mutex = QMutex()
        self._render_condition = QWaitCondition()
        
        # Current render state
        self._render_state: Optional[RenderState] = None
        
        # Cached image
        self._cached_image: Optional[QImage] = None
        self._last_render_time = 0.0
        
        # Rendering frequency control
        self._min_render_interval = 1.0 / 10.0  # 10 FPS max
        self._last_render_request = 0.0
        
        # Performance stats
        self._render_count = 0
        self._total_render_time = 0.0
    
    def stop(self):
        """Stop the worker thread gracefully"""
        self._running = False
        self._state_mutex.lock()
        self._render_condition.wakeAll()
        self._state_mutex.unlock()
    
    def request_render(self, state: RenderState):
        """
        Request a new render with the given state.
        
        Throttles requests to prevent overwhelming the thread.
        """
        current_time = time.time()
        
        # Throttle render requests
        if current_time - self._last_render_request < self._min_render_interval:
            return
        
        self._last_render_request = current_time
        
        with QMutexLocker(self._state_mutex):
            self._render_state = state
            self._render_requested = True
            self._render_condition.wakeOne()
    
    def get_cached_image(self) -> Optional[QImage]:
        """Get the most recently rendered image (thread-safe)"""
        with QMutexLocker(self._state_mutex):
            return self._cached_image
    
    def get_stats(self) -> Dict[str, Any]:
        """Get rendering statistics"""
        avg_time = self._total_render_time / max(1, self._render_count)
        return {
            'render_count': self._render_count,
            'avg_render_time_ms': avg_time,
            'last_render_time_ms': self._last_render_time
        }
    
    def run(self):
        """Main worker loop"""
        print("🧠 BrainRenderWorker started")
        
        while self._running:
            state_to_render = None
            
            # Wait for render request
            self._state_mutex.lock()
            try:
                if not self._render_requested and self._running:
                    # Wait up to 100ms for a render request
                    self._render_condition.wait(self._state_mutex, 100)
                
                if self._render_requested and self._render_state:
                    state_to_render = self._render_state
                    self._render_requested = False
            finally:
                self._state_mutex.unlock()
            
            # Perform render if we have state
            if state_to_render:
                start_time = time.perf_counter()
                
                try:
                    image = self._render_frame(state_to_render)
                    
                    # Cache the image
                    with QMutexLocker(self._state_mutex):
                        self._cached_image = image
                    
                    # Calculate render time
                    render_time = (time.perf_counter() - start_time) * 1000
                    self._last_render_time = render_time
                    self._render_count += 1
                    self._total_render_time += render_time
                    
                    # Emit signal with rendered image
                    self.render_complete.emit(image, render_time)
                    
                except Exception as e:
                    print(f"🧠 Render error: {e}")
                    import traceback
                    traceback.print_exc()
        
        print("🧠 BrainRenderWorker stopped")
    
    def _render_frame(self, state: RenderState) -> QImage:
        """Render a complete frame to QImage"""
        # Create image with proper size
        image = QImage(state.width, state.height, QImage.Format_ARGB32)
        image.fill(QColor(*state.anim_background_colour))
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.setRenderHint(QPainter.TextAntialiasing)
        
        try:
            # Calculate scaling (same logic as brain_widget)
            indicator_space = 0  # No indicator pills
            base_width = 1024
            base_height = 768 - indicator_space
            
            scale_x = state.width / base_width
            scale_y = (state.height - indicator_space) / max(1, base_height)
            scale = max(0.01, min(scale_x, scale_y))
            
            # Center horizontally
            offset_x = 0
            if scale_x > scale_y:
                content_width = base_width * scale
                offset_x = (state.width - content_width) / 2
            
            painter.translate(offset_x, indicator_space)
            painter.scale(scale, scale)
            
            # Draw layers
            self._draw_layers(painter, state, 1.0)
            
            # Draw connections
            self._draw_connections(painter, state, scale)
            
            # Draw neurons
            self._draw_neurons(painter, state, scale)
            
        finally:
            painter.end()
        
        return image
    
    def _draw_layers(self, painter: QPainter, state: RenderState, scale: float):
        """Draw layer background rectangles"""
        if not state.layers:
            return
        
        for layer in state.layers:
            y_pos = layer.get('y_position', 0)
            name = layer.get('name', 'Layer')
            layer_type = layer.get('layer_type', 'hidden')
            
            rect_height = 120
            rect_top = y_pos - rect_height / 2
            rect_left = -200
            rect_width = 2000
            
            # Layer colors
            if layer_type == 'input':
                color = QColor(220, 255, 220, 30)
                border = QColor(180, 220, 180, 60)
            elif layer_type == 'output':
                color = QColor(255, 220, 220, 30)
                border = QColor(220, 180, 180, 60)
            else:
                color = QColor(230, 230, 255, 40)
                border = QColor(200, 200, 240, 60)
            
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(border, 1, Qt.DashLine))
            painter.drawRect(QRectF(rect_left, rect_top, rect_width, rect_height))
    
    def _get_neuron_animation_color(self, state: RenderState, neuron_name: str, current_time: float):
        """
        Check if a neuron is currently involved in an active weight animation.
        Returns a QColor with pulsing alpha if active, None otherwise.
        """
        for anim in state.weight_animations:
            # Check if this neuron is part of the animation pair
            if (anim.get('neuron1') == neuron_name or anim.get('neuron2') == neuron_name):
                elapsed = current_time - anim['start_time']
                duration = anim['duration']
                
                if 0 <= elapsed < duration:
                    progress = elapsed / duration
                    
                    # Create pulsing alpha effect (fade in and out)
                    # Use sine wave for smooth pulsing
                    pulse_factor = math.sin(progress * math.pi)
                    
                    # Get the animation color
                    r, g, b = anim['color']
                    
                    # Set alpha based on pulse factor (0-255 range)
                    alpha = int(255 * pulse_factor)
                    
                    return QColor(r, g, b, alpha)
        
        return None
    
    def _draw_connections(self, painter: QPainter, state: RenderState, scale: float):
        """
        Draw all neural connections with scrolling arrow animations for Hebbian learning.
        Includes specific coloring for excitatory (green) vs inhibitory (red) weights
        and weight-based thickness clamping (max 15px or style-defined).
        """
        current_time = state.animation_time
        
        for (src, dst), weight in state.weights.items():
            # Skip if neurons not visible or excluded
            if src not in state.visible_neurons or dst not in state.visible_neurons:
                continue
            if src in state.excluded_neurons or dst in state.excluded_neurons:
                continue
            if src not in state.neuron_positions or dst not in state.neuron_positions:
                continue
            
            # Get positions
            src_pos = state.neuron_positions[src]
            dst_pos = state.neuron_positions[dst]
            
            start = QPointF(src_pos[0], src_pos[1])
            end = QPointF(dst_pos[0], dst_pos[1])
            
            # Get link opacity
            key = (src, dst)
            opacity = state.link_opacities.get(key, 1.0)
            if opacity < 0.01:
                continue
            
            # ===== CHECK FOR ACTIVE HEBBIAN ANIMATION =====
            active_anim = None
            active_anim_progress = 0.0
            
            for anim in state.weight_animations:
                # Check match (undirected)
                if anim['pair'] == (src, dst) or anim['pair'] == (dst, src):
                    elapsed = current_time - anim['start_time']
                    duration = anim['duration']
                    
                    if 0 <= elapsed < duration:
                        active_anim = anim
                        active_anim_progress = elapsed / duration
                        break
            
            # ===== WEIGHT-BASED THICKNESS & COLOR =====
            abs_weight = abs(weight)
            
            # 1. Base thickness calculation:
            # Scale weight (0.0 to 1.0) to a range
            # Define max pixel thickness for strongest connections based on style
            if state.weight_thickness_enabled:
                MAX_THICKNESS = state.weight_thickness_max
            else:
                MAX_THICKNESS = 15.0
            
            # Calculate thickness: Base + (Weight * Scalar), clamped to MAX_THICKNESS
            # Ensure we don't have negative range if base > max
            thickness_range = max(0.0, MAX_THICKNESS - state.anim_line_base_width)
            calculated_thickness = state.anim_line_base_width + (abs_weight * thickness_range)
            
            # Clamp rigidly to MAX_THICKNESS
            base_thickness = min(calculated_thickness, MAX_THICKNESS)
            
            # 2. Determine Color (Excitatory vs Inhibitory)
            if weight >= 0:
                # Excitatory = Green (using positive color from state)
                base_color = QColor(*state.anim_line_col_pos)
            else:
                # Inhibitory = Red (using negative color from state)
                base_color = QColor(*state.anim_line_col_neg)
            
            # Apply Opacity
            base_color.setAlpha(int(state.anim_line_alpha * opacity))

            # Base styling
            line_width = base_thickness * scale
            pen_style = Qt.SolidLine 
            
            # Dashed line for negative, Dotted for very weak (optional visual aid)
            if weight < 0:
                pen_style = Qt.DashLine
            if abs_weight < 0.1:
                pen_style = Qt.DotLine
            
            # ===== ANIMATED LINE STYLING (during Hebbian cycle) =====
            # Initialize current_thickness with base value
            current_thickness = base_thickness
            line_color = base_color
            
            if active_anim:
                # Connection becomes bright during Hebbian cycle
                r, g, b = active_anim['color']
                line_color = QColor(r, g, b, 255)
                
                # Line thickness pulses during animation
                anim_max_thickness = (MAX_THICKNESS + 3.0) * scale
                
                pulse_factor = math.sin(active_anim_progress * math.pi)
                current_thickness = base_thickness + (pulse_factor * (anim_max_thickness - base_thickness))
                
                pen_style = Qt.SolidLine  # Always solid during animation
            
            line_width = max(1, int(current_thickness * scale))
            
            painter.setPen(QPen(line_color, line_width, pen_style, Qt.RoundCap))
            painter.drawLine(start, end)
            
            # ===== DRAW SCROLLING ARROWS FOR MOVEMENT ILLUSION =====
            if active_anim and active_anim_progress < 1.0:
                # Calculate direction vector and angle
                dx = end.x() - start.x()
                dy = end.y() - start.y()
                length = math.sqrt(dx*dx + dy*dy)
                
                if length > 10:  # Only draw arrows on longer connections
                    # Normalize direction
                    dir_x = dx / length
                    dir_y = dy / length
                    
                    # Arrow size
                    arrow_size = 12.0 * scale
                    
                    # Draw 4 arrows at different positions (trail effect)
                    arrow_positions = [0.20, 0.40, 0.60, 0.80]
                    
                    # Offset based on animation progress to create movement
                    progress_offset = active_anim_progress * 0.8
                    
                    for i, base_pos in enumerate(arrow_positions):
                        # Calculate actual position offset by progress
                        pos_offset = (base_pos + progress_offset) % 1.0
                        
                        # Arrow center point
                        center_x = start.x() + pos_offset * dx
                        center_y = start.y() + pos_offset * dy
                        
                        # Alpha fades for trail effect (255, 191, 128, 64)
                        alpha = int(255 * (1.0 - (i * 0.25)))
                        
                        # Create arrow polygon (pointing along the line)
                        arrow = QPolygonF()
                        
                        # Arrow points in direction of connection
                        # Front point
                        point_x = center_x + dir_x * arrow_size
                        point_y = center_y + dir_y * arrow_size
                        arrow.append(QPointF(point_x, point_y))
                        
                        # Back left
                        back_x = center_x - dir_x * arrow_size * 0.5
                        back_y = center_y - dir_y * arrow_size * 0.5
                        left_x = back_x - dir_y * arrow_size * 0.5
                        left_y = back_y + dir_x * arrow_size * 0.5
                        arrow.append(QPointF(left_x, left_y))
                        
                        # Back right
                        right_x = back_x + dir_y * arrow_size * 0.5
                        right_y = back_y - dir_x * arrow_size * 0.5
                        arrow.append(QPointF(right_x, right_y))
                        
                        # Fill arrow with color
                        arrow_color = QColor(line_color)
                        arrow_color.setAlpha(alpha)
                        painter.setBrush(QBrush(arrow_color))
                        painter.setPen(QPen(arrow_color, 1))
                        painter.drawPolygon(arrow)
            
            # ===== DRAW WEIGHT TEXT =====
            if state.show_weights and abs_weight > 0.1:
                # Calculate angle for rotation
                dx = end.x() - start.x()
                dy = end.y() - start.y()
                angle_deg = math.degrees(math.atan2(dy, dx))
                
                # Ensure text is readable
                if angle_deg > 90:
                    angle_deg -= 180
                elif angle_deg < -90:
                    angle_deg += 180
                
                midpoint = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
                text_str = f"{weight:.2f}"
                
                font_size = max(7, int(8 * scale))
                padding = 4 * scale
                
                font = painter.font()
                font.setPointSize(font_size)
                font.setBold(True)
                painter.setFont(font)
                
                fm = painter.fontMetrics()
                text_w = fm.horizontalAdvance(text_str)
                text_h = fm.height()
                
                painter.save()
                painter.translate(midpoint)
                painter.rotate(angle_deg)
                
                rect = QRectF(-text_w/2 - padding, -text_h/2, 
                            text_w + padding*2, text_h)
                
                painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
                painter.setPen(QPen(QColor(100, 100, 100, 150), 1))
                painter.drawRoundedRect(rect, 4, 4)
                
                # Text color matches line color logic
                text_color = QColor(0, 100, 0) if weight >= 0 else QColor(150, 0, 0)
                painter.setPen(text_color)
                painter.drawText(rect, Qt.AlignCenter, text_str)
                
                painter.restore()
                
    
    def _draw_neurons(self, painter: QPainter, state: RenderState, scale: float):
        """Draw all neurons with localized labels, connector relay animations, and Hebbian pulse effects"""
        from .brain_constants import BINARY_NEURONS
        
        # Hardcoded list of core neurons to determine font sizing
        CORE_NEURONS = {"hunger", "happiness", "cleanliness", "sleepiness", 
                        "satisfaction", "anxiety", "curiosity", "can_see_food"}

        # Set up default font
        font = QFont("Arial", state.neuron_label_font_size)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()

        radius = 20 * scale
        current_time = state.animation_time

        for name, pos in state.neuron_positions.items():
            if name in state.excluded_neurons:
                continue
            if name not in state.visible_neurons:
                continue

            x, y = pos
            raw_value = state.neuron_states.get(name, 50)
            shape = state.neuron_shapes.get(name, 'circle')
            
            # ========== CHECK FOR ACTIVE HEBBIAN ANIMATION ==========
            animation_color = self._get_neuron_animation_color(state, name, current_time)
            
            # Check if this neuron is currently being used as a relay in any animation
            is_active_connector = False
            connector_pulse_alpha = 0
            pulse_size_multiplier = 1.0

            for anim in state.weight_animations:
                if anim.get('is_segment') and anim.get('final_target'):
                    # Check if this neuron is the connector in a staggered animation
                    connector_in_anim = (anim['neuron1'] == name or anim['neuron2'] == name)
                    
                    if connector_in_anim:
                        elapsed = current_time - anim['start_time']
                        if 0 <= elapsed < anim['duration']:
                            # Connector becomes bright white when relaying
                            pulse_phase = elapsed / anim['duration']
                            if pulse_phase > 0.7:  # Last part of segment - relay burst
                                connector_pulse_alpha = int(255 * (1.0 - pulse_phase))
                                pulse_size_multiplier = 1.0 + (1.0 - pulse_phase) * 0.5  # Grow 50% at burst
                                is_active_connector = True
                                break

            # ---------- BINARY NEURONS ----------
            if name in BINARY_NEURONS:
                value = 100.0 if float(raw_value) > 50 else 0.0
                is_active = value > 50
                
                # Apply animation color if active
                if animation_color:
                    color = animation_color
                else:
                    color = QColor(0, 255, 0) if is_active else QColor(255, 0, 0)

                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(0, 0, 0), max(1, int(2 * scale))))
                size = radius * 1.8
                rect = QRectF(x - size/2, y - size/2, size, size)
                painter.drawRect(rect)

                # [NEW] Draw Symbol inside Binary Neuron
                symbol = "✓" if is_active else "✗"
                painter.save()
                symbol_font = QFont("Arial", int(size * 0.7))
                symbol_font.setBold(True)
                painter.setFont(symbol_font)
                painter.setPen(QColor(0, 0, 0))
                painter.drawText(rect, Qt.AlignCenter, symbol)
                painter.restore()

                if name == 'can_see_food':
                    display_name = state.neuron_labels.get(name, name)
                    
                    # Smaller Font
                    small_font = QFont(font)
                    small_font.setPointSize(max(4, int(state.neuron_label_font_size * 0.75 * scale)))
                    painter.setFont(small_font)
                    sfm = painter.fontMetrics()

                    # Calculate Dimensions
                    text_width = sfm.horizontalAdvance(display_name)
                    padding = 4 * scale
                    rect_width = text_width + padding * 2
                    rect_height = sfm.height() + 2

                    text_rect = QRectF(
                        x - rect_width / 2,
                        y + size/2 + 3 * scale,
                        rect_width,
                        rect_height
                    )

                    # Draw Black Background
                    painter.setBrush(QBrush(QColor(0, 0, 0)))
                    painter.setPen(Qt.NoPen)
                    painter.drawRoundedRect(text_rect, 2, 2)

                    # Draw White Text
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(text_rect, Qt.AlignCenter, display_name)
                    
                    # Restore standard font
                    painter.setFont(font)

                continue

            # ---------- DIAMOND ----------
            if shape == 'diamond':
                # Apply animation color if active
                if animation_color:
                    color = animation_color
                else:
                    color = QColor(*state.state_colors.get(name, (152, 251, 152)))
                self._draw_polygon(painter, x, y, 4, radius, color, rotation=0)

            # ---------- SQUARE ----------
            elif shape == 'square':
                # Apply animation color if active
                if animation_color:
                    color = animation_color
                else:
                    color = QColor(*state.state_colors.get(name, (152, 251, 152)))
                self._draw_polygon(painter, x, y, 4, radius, color, rotation=45)

            # ---------- TRIANGLE ----------
            elif shape == 'triangle':
                # Apply animation color if active
                if animation_color:
                    color = animation_color
                else:
                    color = QColor(*state.state_colors.get(name, (255, 255, 150)))
                self._draw_polygon(painter, x, y, 3, radius, color)

            # ---------- CONNECTOR (HEXAGON) ----------
            elif shape == 'hexagon' or name.startswith('connector_'):
                # Use bright purple base, but pulse white during animation or apply animation color
                if animation_color:
                    # Hebbian animation takes priority
                    color = animation_color
                    self._draw_polygon(painter, x, y, 6, radius * pulse_size_multiplier, 
                                    color, rotation=0)
                elif is_active_connector:
                    # Pulse with white color during relay
                    pulse_color = QColor(255, 255, 255, connector_pulse_alpha)
                    self._draw_polygon(painter, x, y, 6, radius * pulse_size_multiplier, 
                                    pulse_color, rotation=0)
                    
                    # Add extra glow ring during burst
                    if connector_pulse_alpha > 128:
                        glow_pen = QPen(QColor(255, 255, 255, connector_pulse_alpha // 2), 3)
                        painter.setPen(glow_pen)
                        painter.setBrush(Qt.NoBrush)
                        painter.drawEllipse(QPointF(x, y), radius * 1.5, radius * 1.5)
                else:
                    # Normal black connector appearance
                    color = QColor(0, 0, 0)
                    self._draw_polygon(painter, x, y, 6, radius, color, rotation=0)

                painter.save()
                c_font = QFont("Arial", int(14 * scale))
                c_font.setBold(True)
                painter.setFont(c_font)
                
                # Use white text, but make it brighter during pulse
                if (is_active_connector and connector_pulse_alpha > 200) or animation_color:
                    painter.setPen(QColor(255, 255, 255, 255))
                else:
                    painter.setPen(QColor(255, 255, 255, 200))

                rect = QRectF(x - radius, y - radius, radius * 2, radius * 2)
                painter.drawText(rect, Qt.AlignCenter, "c")
                painter.restore()

                # IMPORTANT: connector neurons do NOT draw external labels
                continue

            # ---------- DEFAULT CIRCLE ----------
            else:
                # Apply animation color if active
                if animation_color:
                    color = animation_color
                elif name in state.state_colors:
                    color = QColor(*state.state_colors[name])
                else:
                    color = QColor(64, 64, 64)

                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(0, 0, 0), max(1, int(2 * scale))))
                painter.drawEllipse(QPointF(x, y), radius, radius)

            # ---------- LABEL ----------
            display_name = state.neuron_labels.get(
                name, name.replace("_", " ").title()
            )

            # [NEW] Font Scaling Logic
            is_neurogenesis = name not in CORE_NEURONS
            effective_size = state.neuron_label_font_size * 0.75 if is_neurogenesis else state.neuron_label_font_size
            
            # Apply font size for this label
            label_font = QFont("Arial", int(effective_size * scale))
            label_font.setBold(True)
            painter.setFont(label_font)
            local_fm = painter.fontMetrics()

            text_width = local_fm.horizontalAdvance(display_name)
            padding = 10 * scale
            rect_width = text_width + padding * 2
            rect_height = local_fm.height() + 4

            text_rect = QRectF(
                x - rect_width / 2,
                y + radius + 5 * scale,
                rect_width,
                rect_height
            )

            painter.setBrush(QBrush(QColor(26, 26, 26, 200)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(text_rect, 4, 4)

            painter.setPen(QColor(224, 224, 224))
            painter.drawText(text_rect, Qt.AlignCenter, display_name)
            
            # Restore base font for next iteration
            painter.setFont(font)

    
    def _draw_polygon(self, painter: QPainter, x: float, y: float, 
                      sides: int, radius: float, color: QColor, rotation: float = 0):
        """Draw a polygon neuron shape"""
        painter.save()
        painter.translate(x, y)
        painter.rotate(rotation)
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(0, 0, 0)))
        
        polygon = QPolygonF()
        angle_step = 360.0 / sides
        for i in range(sides):
            angle = math.radians(i * angle_step - 90)
            polygon.append(QPointF(radius * math.cos(angle), radius * math.sin(angle)))
        
        painter.drawPolygon(polygon)
        painter.restore()


def create_render_state_from_widget(brain_widget) -> RenderState:
    """
    Helper function to create a RenderState from a BrainWidget instance.
    Call this from the main thread before requesting a render.
    """
    # Import Localisation here to avoid circular imports at module level
    from .localisation import Localisation
    loc = Localisation.instance()

    state = RenderState()
    
    # Copy neuron data
    state.neuron_positions = dict(brain_widget.neuron_positions)
    state.neuron_states = dict(brain_widget.state)
    state.state_colors = dict(getattr(brain_widget, 'state_colors', {}))
    state.neuron_shapes = dict(getattr(brain_widget, 'neuron_shapes', {}))
    
    # --- Pre-calculate Localized Labels on Main Thread ---
    labels = {}
    
    # We only need to calculate labels for neurons that might be drawn
    visible = getattr(brain_widget, 'visible_neurons', brain_widget.neuron_positions.keys())
    excluded = getattr(brain_widget, 'excluded_neurons', set())
    
    for name in state.neuron_positions.keys():
        if name in excluded:
            continue
            
        # 1. Try exact key lookup
        display_name = loc.get(name)
        
        # 2. Fallback: space-separated key
        if display_name == name:
            space_key = name.replace("_", " ")
            display_name = loc.get(space_key)
            if display_name == space_key:
                display_name = None # Mark as not found yet
        
        # 3. Fallback: Neurogenesis pattern (e.g., novelty_1 -> Novelty 1)
        if not display_name:
            match = re.match(r"^([a-z_]+)_(\d+)$", name)
            if match:
                base = match.group(1)
                idx = match.group(2)
                base_loc = loc.get(base)
                if base_loc != base:
                    display_name = f"{base_loc} {idx}"
                else:
                    display_name = f"{base.replace('_', ' ').title()} {idx}"
        
        # 4. Final Fallback: Title Case
        if not display_name:
            display_name = name.replace("_", " ").title()
            
        labels[name] = display_name
    
    state.neuron_labels = labels
    # -----------------------------------------------------

    # Copy connection data
    state.weights = dict(brain_widget.weights)
    state.communication_events = dict(getattr(brain_widget, 'communication_events', {}))
    
    # Copy visibility
    state.visible_neurons = set(visible)
    state.excluded_neurons = set(excluded)
    
    # Copy animation state
    state.link_opacities = dict(getattr(brain_widget, '_link_opacities', {}))
    state.animation_time = time.time()
    
    # [NEW] Copy active weight animations for Hebbian learning
    state.weight_animations = [dict(anim) for anim in getattr(brain_widget, 'weight_animations', [])]
    
    # Copy display settings
    state.show_weights = getattr(brain_widget, 'show_weights', False)
    state.is_tutorial_mode = getattr(brain_widget, 'is_tutorial_mode', False)
    
    # ===== ANIMATION STYLE PARAMETERS =====
    # Base visual settings
    state.anim_background_colour = getattr(brain_widget, 'anim_background_colour', (30, 30, 40))
    state.anim_line_base_width = getattr(brain_widget, 'anim_line_base_width', 1.0)
    state.anim_line_col_pos = getattr(brain_widget, 'anim_line_col_pos', (100, 255, 100))
    state.anim_line_col_neg = getattr(brain_widget, 'anim_line_col_neg', (255, 100, 100))
    state.anim_line_alpha = getattr(brain_widget, 'anim_line_alpha', 180)
    state.anim_line_style = getattr(brain_widget, 'anim_line_style', 0)  # Qt.SolidLine
    
    # Weight-based thickness
    state.weight_thickness_enabled = getattr(brain_widget, 'weight_thickness_enabled', False)
    state.weight_thickness_min = getattr(brain_widget, 'weight_thickness_min', 1.0)
    state.weight_thickness_max = getattr(brain_widget, 'weight_thickness_max', 2.0)
    state.weight_thickness_power = getattr(brain_widget, 'weight_thickness_power', 1.0)
    
    # Scroll settings
    state.scroll_enabled = getattr(brain_widget, 'anim_scroll_enabled', False)
    state.scroll_dot_count = getattr(brain_widget, 'anim_scroll_dot_count', 3)
    state.scroll_dot_size = getattr(brain_widget, 'anim_scroll_dot_size', 6.0)
    state.scroll_dot_colour = getattr(brain_widget, 'anim_scroll_dot_colour', (255, 255, 255))
    state.scroll_dot_alpha = getattr(brain_widget, 'anim_scroll_dot_alpha', 200)
    state.scroll_speed_range = getattr(brain_widget, 'anim_scroll_speed_range', (1.5, 4.0))
    
    # Pulse effects
    state.anim_pulse_enabled = getattr(brain_widget, 'anim_pulse_enabled', True)
    state.anim_pulse_colour = getattr(brain_widget, 'anim_pulse_colour', (255, 255, 255))
    state.anim_pulse_alpha = getattr(brain_widget, 'anim_pulse_alpha', 180)
    state.anim_pulse_diameter = getattr(brain_widget, 'anim_pulse_diameter', 8.0)
    
    # Glow effects
    state.anim_glow_enabled = getattr(brain_widget, 'anim_glow_enabled', True)
    state.anim_glow_colour = getattr(brain_widget, 'anim_glow_colour', (255, 255, 200))
    state.anim_glow_alpha = getattr(brain_widget, 'anim_glow_alpha', 60)
    state.anim_glow_fade_threshold = getattr(brain_widget, 'anim_glow_fade_threshold', 0.5)
    
    # Communication glow
    state.anim_comm_glow_enabled = getattr(brain_widget, 'anim_comm_glow_enabled', False)
    
    # Layers
    state.layers = list(getattr(brain_widget, 'layers', []))
    
    # Widget size
    state.width = brain_widget.width()
    state.height = brain_widget.height()
    
    # Hover state
    state.hovered_neuron = getattr(brain_widget, 'hovered_neuron', None)
    state.hover_value_display_active = getattr(brain_widget, 'hover_value_display_active', False)
    
    # Font settings
    state.neuron_label_font_size = getattr(brain_widget, 'neuron_label_font_size', 6)
    
    return state