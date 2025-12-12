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
    
    # Connection data
    weights: Dict[Tuple[str, str], float] = field(default_factory=dict)
    communication_events: Dict[str, float] = field(default_factory=dict)
    
    # Visibility
    visible_neurons: set = field(default_factory=set)
    excluded_neurons: set = field(default_factory=set)
    
    # Animation state
    link_opacities: Dict[Tuple[str, str], float] = field(default_factory=dict)
    animation_time: float = 0.0
    
    # Display settings
    show_weights: bool = False
    is_tutorial_mode: bool = False
    
    # Animation style parameters
    anim_background_colour: Tuple[int, int, int] = (30, 30, 40)
    anim_line_col_pos: Tuple[int, int, int] = (100, 255, 100)
    anim_line_col_neg: Tuple[int, int, int] = (255, 100, 100)
    anim_pulse_enabled: bool = True
    anim_pulse_colour: Tuple[int, int, int] = (255, 255, 255)
    anim_pulse_alpha: int = 180
    anim_pulse_diameter: float = 8.0
    anim_glow_enabled: bool = True
    anim_glow_colour: Tuple[int, int, int] = (255, 255, 200)
    anim_glow_alpha: int = 60
    anim_glow_fade_threshold: float = 0.5
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
        self._min_render_interval = 1.0 / 30.0  # 30 FPS max
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
        print("🎨 BrainRenderWorker started")
        
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
                    print(f"🎨 Render error: {e}")
                    import traceback
                    traceback.print_exc()
        
        print("🎨 BrainRenderWorker stopped")
    
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
    
    def _draw_connections(self, painter: QPainter, state: RenderState, scale: float):
        """Draw all neural connections"""
        current_time = state.animation_time
        
        for (src, dst), weight in state.weights.items():
            # Skip if neurons not visible
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
            
            # Calculate animation state
            src_val = state.neuron_states.get(src, 50)
            activity = abs(src_val - 50) / 50.0
            
            # Check communication events
            animating = False
            progress = 1.0
            if src in state.communication_events:
                event_time = state.communication_events[src]
                elapsed = current_time - event_time
                if elapsed < 0.5:  # 500ms animation
                    animating = True
                    progress = elapsed / 0.5
            
            # Calculate line properties
            base_alpha = int(180 * opacity)
            line_width = max(1, int((1 + abs(weight) * 2) * scale))
            
            # Determine color
            if animating and activity > 0.3:
                anim_alpha = int(base_alpha * (1 - progress * 0.5))
                if weight > 0:
                    color = QColor(*state.anim_line_col_pos, anim_alpha)
                else:
                    color = QColor(*state.anim_line_col_neg, anim_alpha)
            else:
                if weight > 0:
                    color = QColor(0, int(255 * abs(weight)), 0, base_alpha)
                else:
                    color = QColor(int(255 * abs(weight)), 0, 0, base_alpha)
            
            # Line style
            pen_style = Qt.DashLine if weight < 0 else Qt.SolidLine
            if abs(weight) < 0.1:
                pen_style = Qt.DotLine
            
            painter.setPen(QPen(color, line_width, pen_style))
            painter.drawLine(start, end)
            
            # Draw pulse if animating
            if state.anim_pulse_enabled and animating and progress < 1.0:
                pulse_x = start.x() + progress * (end.x() - start.x())
                pulse_y = start.y() + progress * (end.y() - start.y())
                pulse_size = state.anim_pulse_diameter * scale * (1 - progress ** 2)
                
                painter.setBrush(QBrush(QColor(*state.anim_pulse_colour, state.anim_pulse_alpha)))
                painter.setPen(Qt.NoPen)
                painter.drawEllipse(QPointF(pulse_x, pulse_y), pulse_size, pulse_size)
            
            # Draw glow if enabled
            if state.anim_glow_enabled and animating and progress < state.anim_glow_fade_threshold:
                glow_progress = progress / state.anim_glow_fade_threshold
                glow_width = line_width + 4 * scale * (1 - glow_progress)
                glow_color = QColor(*state.anim_glow_colour, state.anim_glow_alpha)
                painter.setPen(QPen(glow_color, glow_width, pen_style))
                painter.drawLine(start, end)
    
    def _draw_neurons(self, painter: QPainter, state: RenderState, scale: float):
        """Draw all neurons"""
        # Setup font - use config value directly
        font = QFont("Arial", state.neuron_label_font_size)
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()
        
        radius = 20 * scale
        
        BINARY_NEURONS = {
            'can_see_food', 'is_eating', 'is_sleeping', 'is_sick',
            'pursuing_food', 'is_fleeing', 'is_startled',
            'external_stimulus', 'plant_proximity'
        }
        
        for name, pos in state.neuron_positions.items():
            if name in state.excluded_neurons:
                continue
            if name not in state.visible_neurons:
                continue
            
            x, y = pos
            raw_value = state.neuron_states.get(name, 50)
            
            # Determine shape
            shape = state.neuron_shapes.get(name, 'circle')
            
            # Binary neurons - draw as squares
            if name in BINARY_NEURONS:
                value = 100.0 if float(raw_value) > 50 else 0.0
                is_active = value > 50
                color = QColor(0, 255, 0) if is_active else QColor(255, 0, 0)
                
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(0, 0, 0), max(1, int(2 * scale))))
                size = radius * 1.8
                painter.drawRect(QRectF(x - size/2, y - size/2, size, size))
            
            elif shape == 'diamond':
                color = QColor(*state.state_colors.get(name, (152, 251, 152)))
                self._draw_polygon(painter, x, y, 4, radius, color, rotation=0)
            
            elif shape == 'square':
                color = QColor(*state.state_colors.get(name, (152, 251, 152)))
                self._draw_polygon(painter, x, y, 4, radius, color, rotation=45)
            
            elif shape == 'triangle':
                color = QColor(*state.state_colors.get(name, (255, 255, 150)))
                self._draw_polygon(painter, x, y, 3, radius, color)
            
            else:  # circle
                # Get color from state_colors or calculate from value
                if name in state.state_colors:
                    color = QColor(*state.state_colors[name])
                else:
                    color = QColor(64, 64, 64)
                
                painter.setBrush(QBrush(color))
                painter.setPen(QPen(QColor(0, 0, 0), max(1, int(2 * scale))))
                painter.drawEllipse(QPointF(x, y), radius, radius)
            
            # Draw label
            display_name = name.replace("_", " ").title()
            text_width = fm.horizontalAdvance(display_name)
            padding = 10 * scale
            rect_width = text_width + padding * 2
            rect_height = fm.height() + 4
            
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
            
            # Draw hover value if applicable
            if state.hovered_neuron == name and state.hover_value_display_active:
                value = state.neuron_states.get(name, 50)
                if name == 'can_see_food':
                    value_str = "ON" if value > 50 else "OFF"
                else:
                    value_str = f"{value:.1f}"
                
                hover_font = QFont("Arial", 16, QFont.Bold)
                painter.setFont(hover_font)
                hfm = painter.fontMetrics()
                
                badge_width = hfm.horizontalAdvance(value_str) + 24
                badge_height = hfm.height() + 12
                badge_y = y - 50
                
                badge_rect = QRectF(
                    x - badge_width / 2,
                    badge_y - badge_height / 2,
                    badge_width,
                    badge_height
                )
                
                painter.setBrush(QBrush(QColor(40, 40, 50, 230)))
                painter.setPen(QPen(QColor(100, 200, 255), 2))
                painter.drawRoundedRect(badge_rect, 8, 8)
                
                painter.setPen(QColor(255, 255, 255))
                painter.drawText(badge_rect, Qt.AlignCenter, value_str)
                
                # Reset font
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
    state = RenderState()
    
    # Copy neuron data
    state.neuron_positions = dict(brain_widget.neuron_positions)
    state.neuron_states = dict(brain_widget.state)
    state.state_colors = dict(getattr(brain_widget, 'state_colors', {}))
    state.neuron_shapes = dict(getattr(brain_widget, 'neuron_shapes', {}))
    
    # Copy connection data
    state.weights = dict(brain_widget.weights)
    state.communication_events = dict(getattr(brain_widget, 'communication_events', {}))
    
    # Copy visibility
    state.visible_neurons = set(getattr(brain_widget, 'visible_neurons', brain_widget.neuron_positions.keys()))
    state.excluded_neurons = set(getattr(brain_widget, 'excluded_neurons', []))
    
    # Copy animation state
    state.link_opacities = dict(getattr(brain_widget, '_link_opacities', {}))
    state.animation_time = time.time()
    
    # Copy display settings
    state.show_weights = getattr(brain_widget, 'show_weights', False)
    state.is_tutorial_mode = getattr(brain_widget, 'is_tutorial_mode', False)
    
    # Copy animation style parameters
    state.anim_background_colour = getattr(brain_widget, 'anim_background_colour', (30, 30, 40))
    state.anim_line_col_pos = getattr(brain_widget, 'anim_line_col_pos', (100, 255, 100))
    state.anim_line_col_neg = getattr(brain_widget, 'anim_line_col_neg', (255, 100, 100))
    state.anim_pulse_enabled = getattr(brain_widget, 'anim_pulse_enabled', True)
    state.anim_pulse_colour = getattr(brain_widget, 'anim_pulse_colour', (255, 255, 255))
    state.anim_pulse_alpha = getattr(brain_widget, 'anim_pulse_alpha', 180)
    state.anim_pulse_diameter = getattr(brain_widget, 'anim_pulse_diameter', 8.0)
    state.anim_glow_enabled = getattr(brain_widget, 'anim_glow_enabled', True)
    state.anim_glow_colour = getattr(brain_widget, 'anim_glow_colour', (255, 255, 200))
    state.anim_glow_alpha = getattr(brain_widget, 'anim_glow_alpha', 60)
    state.anim_glow_fade_threshold = getattr(brain_widget, 'anim_glow_fade_threshold', 0.5)
    state.anim_comm_glow_enabled = getattr(brain_widget, 'anim_comm_glow_enabled', False)
    
    # Copy layers
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
