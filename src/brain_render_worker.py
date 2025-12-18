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


# Custom neuron coloir constant
CUSTOM_NEURON_COLOR = (54, 15, 90)


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
    
    # Custom neurons tracking
    custom_neurons: set = field(default_factory=set)
    
    # Animation state
    link_opacities: Dict[Tuple[str, str], float] = field(default_factory=dict)
    animation_time: float = 0.0
    
    # Active weight animations for Hebbian learning
    weight_animations: List[Dict] = field(default_factory=list)

    # Toggle for unicode direction arrows
    show_directions: bool = True
    
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
                    
                    # Update cached image
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
                    print(f"🔴 BrainRenderWorker error: {e}")
                    import traceback
                    traceback.print_exc()
        
        print("🧠 BrainRenderWorker stopped")
    
    def _render_frame(self, state: RenderState) -> QImage:
        image = QImage(state.width, state.height, QImage.Format_ARGB32)
        image.fill(QColor(*state.anim_background_colour))
        
        painter = QPainter(image)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # ORIGINAL SCALING LOGIC
        base_width, base_height = 1024, 768
        scale_x = state.width / base_width
        scale_y = state.height / base_height
        scale = min(scale_x, scale_y)
        
        offset_x = (state.width - (base_width * scale)) / 2
        painter.translate(offset_x, 0)
        painter.scale(scale, scale) # Now 1 unit = 1 pixel on a 1024x768 screen

        # Draw everything using base coordinates (no manual * scale needed)
        self._draw_layers(painter, state, 1.0)
        self._draw_connections(painter, state, 1.0)
        self._draw_neurons(painter, state, 1.0)
        painter.end()
        return image
    
    def _draw_layers(self, painter: QPainter, state: RenderState, scale: float):
        """Draw layer backgrounds"""
        if not state.layers:
            return
            
        for layer in state.layers:
            y_pos = layer.get('y_position', 0) * scale
            name = layer.get('name', 'Layer')
            layer_type = layer.get('layer_type', 'hidden')
            
            rect_height = 120 * scale
            rect_top = y_pos - rect_height / 2
            rect_left = -200 * scale
            rect_width = 2000 * scale
            
            # Determine layer color based on type
            if layer_type == 'input':
                color = QColor(220, 255, 220, 30)
                border_color = QColor(180, 220, 180, 60)
            elif layer_type == 'output':
                color = QColor(255, 220, 220, 30)
                border_color = QColor(220, 180, 180, 60)
            else:
                color = QColor(230, 230, 255, 40)
                border_color = QColor(200, 200, 240, 60)
            
            rect = QRectF(rect_left, rect_top, rect_width, rect_height)
            painter.setBrush(QBrush(color))
            painter.setPen(QPen(border_color, 1, Qt.DashLine))
            painter.drawRect(rect)
            
            # Draw label
            font = QFont("Arial", int(10 * scale))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QColor(150, 150, 170))
            painter.drawText(QPointF(20 * scale, rect_top + 20 * scale), name)
    
    def _draw_connections(self, painter: QPainter, state: RenderState, scale: float):
        """
        Draw all neural connections with specific overrides for active animations.
        """
        current_time = state.animation_time
        
        # 1. Map animations to connection keys for O(1) lookup
        # active_anims = { (n1, n2): anim_data }
        active_anims = {}
        for anim in state.weight_animations:
            # Check if animation is still running
            elapsed = current_time - anim['start_time']
            if elapsed < anim['duration']:
                pair = tuple(sorted(anim['pair'])) # Ensure consistent key sorting
                active_anims[pair] = anim

        for (src, dst), weight in state.weights.items():
            if src not in state.visible_neurons or dst not in state.visible_neurons:
                continue
            if src in state.excluded_neurons or dst in state.excluded_neurons:
                continue
            if src not in state.neuron_positions or dst not in state.neuron_positions:
                continue
            
            src_pos = state.neuron_positions[src]
            dst_pos = state.neuron_positions[dst]
            start = QPointF(src_pos[0], src_pos[1])
            end = QPointF(dst_pos[0], dst_pos[1])
            
            # Check for active animation on this specific pair
            # We sort to match the key format used above
            pair_key = tuple(sorted((src, dst)))
            anim = active_anims.get(pair_key)

            if anim:
                # --- ANIMATION OVERRIDE ---
                # Calculate pulse (0.0 to 1.0)
                elapsed = current_time - anim['start_time']
                progress = elapsed / anim['duration']
                
                # Sine wave pulse for "breathing" effect
                pulse = (math.sin(progress * math.pi * 4) + 1) / 2  # 0 to 1
                
                # Make it THICK and BRIGHT
                base_width = 4.0 + (pulse * 4.0) # Pulse between 4px and 8px width
                
                # Use the custom color passed from Hebbian event
                r, g, b = anim.get('color', (255, 255, 0))
                
                # High alpha to ensure visibility
                line_color = QColor(r, g, b, 230)
                
                painter.setPen(QPen(line_color, base_width * scale, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(start, end)
                
                # Optional: Draw a glow around it
                glow_color = QColor(r, g, b, 100)
                painter.setPen(QPen(glow_color, (base_width + 6) * scale, Qt.SolidLine, Qt.RoundCap))
                painter.drawLine(start, end)
                
                continue # Skip standard drawing for this link

            # --- STANDARD DRAWING (Only if not animating) ---
            opacity = state.link_opacities.get((src, dst), 1.0)
            if opacity < 0.01: continue
            
            abs_weight = abs(weight)
            max_t = state.weight_thickness_max if state.weight_thickness_enabled else 15.0
            base_thickness = state.anim_line_base_width + (abs_weight * (max_t - state.anim_line_base_width))
            
            if weight >= 0:
                line_color = QColor(*state.anim_line_col_pos)
                pen_style = Qt.SolidLine
            else:
                line_color = QColor(*state.anim_line_col_neg)
                pen_style = Qt.DashLine 
                
            line_color.setAlpha(int(state.anim_line_alpha * opacity))

            painter.setPen(QPen(line_color, base_thickness, pen_style, Qt.RoundCap))
            painter.drawLine(start, end)
            
            # Draw Unicode Direction Arrow (➤) at midpoint if enabled
            dx = end.x() - start.x()
            dy = end.y() - start.y()
            length = math.sqrt(dx * dx + dy * dy)
            
            if state.show_directions and length > 60: 
                self._draw_direction_arrow(painter, start, end, line_color, opacity, scale, current_time)
    
    def _draw_direction_arrow(self, painter: QPainter, start: QPointF, end: QPointF, 
                           line_color: QColor, opacity: float, scale: float, anim_time: float):
        """Draws a color-matched ➤ that jumps positions every 1 second."""
        # Retro 1FPS logic: Position jumps to a new segment every 1.0 seconds
        discrete_time = math.floor(anim_time)
        # This cycles the arrow through 4 distinct positions (0.2, 0.4, 0.6, 0.8)
        progress = 0.2 + (discrete_time % 4) * 0.2 
        
        mid_x = start.x() + progress * (end.x() - start.x())
        mid_y = start.y() + progress * (end.y() - start.y())
        
        dx, dy = end.x() - start.x(), end.y() - start.y()
        angle_deg = math.degrees(math.atan2(dy, dx))
        
        painter.save()
        painter.translate(mid_x, mid_y)
        painter.rotate(angle_deg)
        
        # Set font and use the line_color (matches connection color)
        font = QFont("Arial", max(10, int(14 * scale)))
        font.setBold(True)
        painter.setFont(font)
        painter.setPen(line_color) # Same color as the connection line
        
        # Draw arrow character with no background
        painter.drawText(QRectF(-10, -10, 20, 20), Qt.AlignCenter, "➤")
        painter.restore()
    
    def _draw_weight_label(self, painter: QPainter, start: QPointF, end: QPointF, 
                           weight: float, scale: float):
        """Draw weight label on connection"""
        midpoint = QPointF((start.x() + end.x()) / 2, (start.y() + end.y()) / 2)
        
        dx = end.x() - start.x()
        dy = end.y() - start.y()
        angle_deg = math.degrees(math.atan2(dy, dx))
        
        if angle_deg > 90:
            angle_deg -= 180
        elif angle_deg < -90:
            angle_deg += 180
        
        text_str = f"{weight:.2f}"
        font_size = max(7, int(8 * scale))
        padding = 4 * scale
        
        font = QFont("Arial", font_size)
        font.setBold(True)
        painter.setFont(font)
        
        fm = painter.fontMetrics()
        text_w = fm.horizontalAdvance(text_str)
        text_h = fm.height()
        
        painter.save()
        painter.translate(midpoint)
        painter.rotate(angle_deg)
        
        rect = QRectF(-text_w/2 - padding, -text_h/2, text_w + padding*2, text_h)
        
        painter.setBrush(QBrush(QColor(255, 255, 255, 220)))
        painter.setPen(QPen(QColor(100, 100, 100, 150), 1))
        painter.drawRoundedRect(rect, 4, 4)
        
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

            x, y = pos[0] * scale, pos[1] * scale
            raw_value = state.neuron_states.get(name, 50)
            shape = state.neuron_shapes.get(name, 'circle')
            
            # Check if this is a custom neuron
            is_custom = name in state.custom_neurons
            
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
                                pulse_size_multiplier = 1.0 + (1.0 - pulse_phase) * 0.5
                                is_active_connector = True
                                break

            # --- MANDATORY OVERRIDE FOR CUSTOM NEURONS ---
            # Ensures #360F5A purple circles are drawn regardless of neurogenesis status
            if is_custom and name not in BINARY_NEURONS and not name.startswith('connector_'):
                color = QColor(54, 15, 90)  # Purple #360F5A
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(0, 0, 0), max(1, int(2 * scale))))
                painter.drawEllipse(QPointF(x, y), radius, radius)
                
                # Draw standard label
                display_name = state.neuron_labels.get(name, name.replace("_", " ").title())
                
                # Use smaller font for custom/neurogenesis neurons
                effective_size = state.neuron_label_font_size * 0.75
                label_font = QFont("Arial", int(effective_size * scale))
                label_font.setBold(True)
                painter.setFont(label_font)
                
                text_width = painter.fontMetrics().horizontalAdvance(display_name)
                padding = 10 * scale
                rect_width = text_width + padding * 2
                rect_height = painter.fontMetrics().height() + 4
                text_rect = QRectF(x - rect_width / 2, y + radius + 5 * scale, rect_width, rect_height)

                painter.setBrush(QBrush(QColor(60, 40, 80, 220))) # Purple tinted bg
                painter.setPen(Qt.NoPen)
                painter.drawRoundedRect(text_rect, 4, 4)
                painter.setPen(QColor(224, 224, 224))
                painter.drawText(text_rect, Qt.AlignCenter, display_name)
                
                # Add star indicator
                if not animation_color:
                    self._draw_custom_indicator(painter, x, y, radius, scale)
                continue 

            # ---------- BINARY NEURONS ----------
            if name in BINARY_NEURONS:
                value = 100.0 if float(raw_value) > 50 else 0.0
                is_active = value > 50
                
                if animation_color:
                    color = animation_color
                else:
                    color = QColor(0, 255, 0) if is_active else QColor(255, 0, 0)

                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(0, 0, 0), max(1, int(2 * scale))))
                size = radius * 1.8
                rect = QRectF(x - size/2, y - size/2, size, size)
                painter.drawRect(rect)

                # Draw Symbol inside Binary Neuron
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
                    small_font = QFont(font)
                    small_font.setPointSize(max(4, int(state.neuron_label_font_size * 0.75 * scale)))
                    painter.setFont(small_font)
                    sfm = painter.fontMetrics()
                    text_width = sfm.horizontalAdvance(display_name)
                    padding = 4 * scale
                    rect_width = text_width + padding * 2
                    rect_height = sfm.height() + 2
                    text_rect = QRectF(x - rect_width / 2, y + size/2 + 3 * scale, rect_width, rect_height)
                    painter.setBrush(QBrush(QColor(0, 0, 0)))
                    painter.setPen(Qt.NoPen)
                    painter.drawRoundedRect(text_rect, 2, 2)
                    painter.setPen(QColor(255, 255, 255))
                    painter.drawText(text_rect, Qt.AlignCenter, display_name)
                    painter.setFont(font)
                continue

            # ---------- DIAMOND ----------
            if shape == 'diamond':
                if animation_color:
                    color = animation_color
                else:
                    color = QColor(*state.state_colors.get(name, (152, 251, 152)))
                self._draw_polygon(painter, x, y, 4, radius, color, rotation=0)

            # ---------- SQUARE ----------
            elif shape == 'square':
                if animation_color:
                    color = animation_color
                else:
                    color = QColor(*state.state_colors.get(name, (152, 251, 152)))
                self._draw_polygon(painter, x, y, 4, radius, color, rotation=45)

            # ---------- TRIANGLE ----------
            elif shape == 'triangle':
                if animation_color:
                    color = animation_color
                else:
                    color = QColor(*state.state_colors.get(name, (255, 255, 150)))
                self._draw_polygon(painter, x, y, 3, radius, color)

            # ---------- PENTAGON ----------
            elif shape == 'pentagon':
                if animation_color:
                    color = animation_color
                else:
                    color = QColor(*state.state_colors.get(name, (147, 112, 219)))
                self._draw_polygon(painter, x, y, 5, radius, color, rotation=0)

            # ---------- CONNECTOR (HEXAGON) ----------
            elif shape == 'hexagon' or name.startswith('connector_'):
                if animation_color:
                    color = animation_color
                    self._draw_polygon(painter, x, y, 6, radius * pulse_size_multiplier, 
                                    color, rotation=0)
                elif is_active_connector:
                    pulse_color = QColor(255, 255, 255, connector_pulse_alpha)
                    self._draw_polygon(painter, x, y, 6, radius * pulse_size_multiplier, 
                                    pulse_color, rotation=0)
                    
                    if connector_pulse_alpha > 128:
                        glow_pen = QPen(QColor(255, 255, 255, connector_pulse_alpha // 2), 3)
                        painter.setPen(glow_pen)
                        painter.setBrush(Qt.NoBrush)
                        painter.drawEllipse(QPointF(x, y), radius * 1.5, radius * 1.5)
                else:
                    color = QColor(0, 0, 0)
                    self._draw_polygon(painter, x, y, 6, radius, color, rotation=0)

                painter.save()
                c_font = QFont("Arial", int(14 * scale))
                c_font.setBold(True)
                painter.setFont(c_font)
                if (is_active_connector and connector_pulse_alpha > 200) or animation_color:
                    painter.setPen(QColor(255, 255, 255, 255))
                else:
                    painter.setPen(QColor(255, 255, 255, 200))
                rect = QRectF(x - radius, y - radius, radius * 2, radius * 2)
                painter.drawText(rect, Qt.AlignCenter, "c")
                painter.restore()
                continue

            # ---------- DEFAULT CIRCLE ----------
            else:
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
            display_name = state.neuron_labels.get(name, name.replace("_", " ").title())
            is_neurogenesis = name not in CORE_NEURONS
            effective_size = state.neuron_label_font_size * 0.75 if is_neurogenesis else state.neuron_label_font_size
            
            label_font = QFont("Arial", int(effective_size * scale))
            label_font.setBold(True)
            painter.setFont(label_font)
            local_fm = painter.fontMetrics()

            text_width = local_fm.horizontalAdvance(display_name)
            padding = 10 * scale
            rect_width = text_width + padding * 2
            rect_height = local_fm.height() + 4
            text_rect = QRectF(x - rect_width / 2, y + radius + 5 * scale, rect_width, rect_height)

            painter.setBrush(QBrush(QColor(26, 26, 26, 200)))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(text_rect, 4, 4)
            painter.setPen(QColor(224, 224, 224))
            painter.drawText(text_rect, Qt.AlignCenter, display_name)
            painter.setFont(font)

    
    def _draw_polygon(self, painter: QPainter, x: float, y: float, 
                      sides: int, radius: float, color: QColor, rotation: float = 0):
        """Draw a polygon neuron shape"""
        painter.save()
        painter.translate(x, y)
        painter.rotate(rotation)
        
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(QColor(0, 0, 0), 2))
        
        polygon = QPolygonF()
        angle_step = 360.0 / sides
        for i in range(sides):
            angle = math.radians(i * angle_step - 90)
            polygon.append(QPointF(radius * math.cos(angle), radius * math.sin(angle)))
        
        painter.drawPolygon(polygon)
        painter.restore()
    
    def _draw_custom_indicator(self, painter: QPainter, x: float, y: float, 
                                radius: float, scale: float):
        """Draw a small star indicator for custom neurons"""
        painter.save()
        
        # Position in upper-right corner
        indicator_x = x + radius * 0.7
        indicator_y = y - radius * 0.7
        indicator_size = 6 * scale
        
        # Draw small filled star
        painter.setPen(Qt.NoPen)
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        
        star = QPolygonF()
        outer_r = indicator_size
        inner_r = indicator_size * 0.4
        for i in range(10):
            angle = math.radians(i * 36 - 90)
            r = outer_r if i % 2 == 0 else inner_r
            star.append(QPointF(
                indicator_x + r * math.cos(angle),
                indicator_y + r * math.sin(angle)
            ))
        
        painter.drawPolygon(star)
        painter.restore()
    
    def _get_neuron_animation_color(self, state: RenderState, name: str, 
                                     current_time: float) -> Optional[QColor]:
        """Check if neuron has an active Hebbian animation and return pulse color"""
        for anim in state.weight_animations:
            if anim['neuron1'] == name or anim['neuron2'] == name:
                elapsed = current_time - anim['start_time']
                if 0 <= elapsed < anim['duration']:
                    # Calculate pulse intensity
                    progress = elapsed / anim['duration']
                    # Pulse starts bright, fades out
                    intensity = 1.0 - progress
                    
                    # Use bright cyan/purple for Hebbian learning
                    r = int(100 + 155 * intensity)
                    g = int(200 + 55 * intensity)
                    b = int(255)
                    
                    return QColor(r, g, b)
        
        return None


def create_render_state_from_widget(brain_widget) -> RenderState:
    """
    Helper function to create a RenderState from a BrainWidget instance.
    Call this from the main thread before requesting a render.
    """
    from .localisation import Localisation
    loc = Localisation.instance()

    state = RenderState()

    # Sync the directions toggle from the main widget
    state.show_directions = getattr(brain_widget, 'show_directions', True)
    
    # Copy neuron data
    state.neuron_positions = dict(brain_widget.neuron_positions)
    state.neuron_states = dict(brain_widget.state)
    state.state_colors = dict(getattr(brain_widget, 'state_colors', {}))
    state.neuron_shapes = dict(getattr(brain_widget, 'neuron_shapes', {}))
    
    # --- CRITICAL: Copy custom neurons set ---
    state.custom_neurons = set(getattr(brain_widget, 'custom_neurons', set()))
    
    # --- Pre-calculate Localized Labels on Main Thread ---
    labels = {}
    visible = getattr(brain_widget, 'visible_neurons', brain_widget.neuron_positions.keys())
    excluded = getattr(brain_widget, 'excluded_neurons', set())
    
    for name in state.neuron_positions.keys():
        if name in excluded:
            continue
        display_name = loc.get(name)
        if display_name == name:
            space_key = name.replace("_", " ")
            display_name = loc.get(space_key)
            if display_name == space_key:
                display_name = None
        if not display_name:
            match = re.match(r"^([a-z_]+)_(\d+)$", name)
            if match:
                base, idx = match.group(1), match.group(2)
                base_loc = loc.get(base)
                display_name = f"{base_loc} {idx}" if base_loc != base else f"{base.replace('_', ' ').title()} {idx}"
        if not display_name:
            display_name = name.replace("_", " ").title()
        labels[name] = display_name
    
    state.neuron_labels = labels
    state.weights = dict(brain_widget.weights)
    state.communication_events = dict(getattr(brain_widget, 'communication_events', {}))
    state.visible_neurons = set(visible)
    state.excluded_neurons = set(excluded)
    state.link_opacities = dict(getattr(brain_widget, '_link_opacities', {}))
    state.animation_time = time.time()
    state.weight_animations = [dict(anim) for anim in getattr(brain_widget, 'weight_animations', [])]
    state.show_weights = getattr(brain_widget, 'show_weights', False)
    state.is_tutorial_mode = getattr(brain_widget, 'is_tutorial_mode', False)
    
    # Animation and Visual Params
    state.anim_background_colour = getattr(brain_widget, 'anim_background_colour', (30, 30, 40))
    state.anim_line_base_width = getattr(brain_widget, 'anim_line_base_width', 1.0)
    state.anim_line_col_pos = getattr(brain_widget, 'anim_line_col_pos', (100, 255, 100))
    state.anim_line_col_neg = getattr(brain_widget, 'anim_line_col_neg', (255, 100, 100))
    state.anim_line_alpha = getattr(brain_widget, 'anim_line_alpha', 180)
    state.anim_line_style = getattr(brain_widget, 'anim_line_style', 0)
    
    # Thickness and Glow
    state.weight_thickness_enabled = getattr(brain_widget, 'weight_thickness_enabled', False)
    state.weight_thickness_max = getattr(brain_widget, 'weight_thickness_max', 2.0)
    state.anim_pulse_enabled = getattr(brain_widget, 'anim_pulse_enabled', True)
    state.anim_glow_enabled = getattr(brain_widget, 'anim_glow_enabled', True)
    
    # Layers and Size
    state.layers = list(getattr(brain_widget, 'layers', []))
    state.width = brain_widget.width()
    state.height = brain_widget.height()
    state.neuron_label_font_size = getattr(brain_widget, 'neuron_label_font_size', 6)
    
    return state