"""How the brain is drawn: layers, connections, neurons and their labels.

Everything here paints from state the brain already holds; nothing in this
module changes a weight or an activation.
"""
import re
import time
import math
from PyQt5 import QtCore, QtGui
from .brain_constants import (
    NEURON_HIGHLIGHT_FACTOR,
)
from .localisation import Localisation
from .brain_constants import NEURON_RADIUS, BINARY_NEURONS  # noqa: F811

# Performance tracking for Task Manager
try:
    from .task_manager import perf_tracker
    _PERF_TRACKING_AVAILABLE = True
except ImportError:
    _PERF_TRACKING_AVAILABLE = False


class BrainPaintingMixin:
    """Part of BrainWidget (see brain_widget.py); not used on its own."""

    def _draw_comm_glows_for_connection(self, painter, scale, conn_key, start_point, end_point):
        """
        Draw all communication glow packets traveling along a connection.
        Each glow is a soft glowing orb that travels from source to target.
        """
        # Check both directions for packets
        reverse_key = (conn_key[1], conn_key[0])
        
        for key, direction in [(conn_key, 1), (reverse_key, -1)]:
            if key not in self._comm_glow_packets:
                continue
            
            packets = self._comm_glow_packets[key]
            
            for packet in packets:
                progress = packet['progress']
                
                # Calculate fade based on position (fade in at start, fade out at end)
                if progress < self.anim_comm_glow_fade_in:
                    # Fade in
                    alpha_mult = progress / self.anim_comm_glow_fade_in
                elif progress > (1.0 - self.anim_comm_glow_fade_out):
                    # Fade out
                    alpha_mult = (1.0 - progress) / self.anim_comm_glow_fade_out
                else:
                    alpha_mult = 1.0
                
                # Clamp alpha multiplier
                alpha_mult = max(0.0, min(1.0, alpha_mult))
                
                # Calculate position along the line
                if direction == 1:
                    # Forward direction
                    glow_x = start_point.x() + progress * (end_point.x() - start_point.x())
                    glow_y = start_point.y() + progress * (end_point.y() - start_point.y())
                else:
                    # Reverse direction (packet traveling backward)
                    glow_x = end_point.x() + progress * (start_point.x() - end_point.x())
                    glow_y = end_point.y() + progress * (start_point.y() - end_point.y())
                
                glow_pos = QtCore.QPointF(glow_x, glow_y)
                
                # Draw the glow with multiple layers for soft appearance
                glow_size = self.anim_comm_glow_size * scale
                r, g, b = self.anim_comm_glow_colour
                
                # Outer glow (larger, more transparent)
                outer_alpha = int(self.anim_comm_glow_alpha * 0.3 * alpha_mult)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(r, g, b, outer_alpha)))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(glow_pos, glow_size * 1.5, glow_size * 1.5)
                
                # Middle glow
                mid_alpha = int(self.anim_comm_glow_alpha * 0.6 * alpha_mult)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(r, g, b, mid_alpha)))
                painter.drawEllipse(glow_pos, glow_size, glow_size)
                
                # Inner core (brightest)
                inner_alpha = int(self.anim_comm_glow_alpha * alpha_mult)
                # Slightly whiter core
                core_r = min(255, r + 50)
                core_g = min(255, g + 50)
                core_b = min(255, b + 50)
                painter.setBrush(QtGui.QBrush(QtGui.QColor(core_r, core_g, core_b, inner_alpha)))
                painter.drawEllipse(glow_pos, glow_size * 0.5, glow_size * 0.5)
                
                # Draw tail (trailing glow particles)
                if self.anim_comm_glow_tail_length > 0:
                    tail_steps = 3
                    for i in range(1, tail_steps + 1):
                        tail_progress = progress - (self.anim_comm_glow_tail_length * i / tail_steps)
                        if tail_progress < 0:
                            continue
                        
                        # Calculate tail position
                        if direction == 1:
                            tail_x = start_point.x() + tail_progress * (end_point.x() - start_point.x())
                            tail_y = start_point.y() + tail_progress * (end_point.y() - start_point.y())
                        else:
                            tail_x = end_point.x() + tail_progress * (start_point.x() - end_point.x())
                            tail_y = end_point.y() + tail_progress * (start_point.y() - end_point.y())
                        
                        tail_pos = QtCore.QPointF(tail_x, tail_y)
                        
                        # Tail gets smaller and more transparent
                        tail_size = glow_size * 0.6 * (1.0 - i / (tail_steps + 1))
                        tail_alpha = int(outer_alpha * (1.0 - i / (tail_steps + 1)))
                        
                        painter.setBrush(QtGui.QBrush(QtGui.QColor(r, g, b, tail_alpha)))
                        painter.drawEllipse(tail_pos, tail_size, tail_size)

    def _draw_neural_connections(self, painter, scale):
        """
        Draw connections in Neural style with weight-based thickness
        and traveling activation pulses.
        """
        if not self.show_links:
            return
        
        current_time = time.time()
        duration = self.anim_neural_pulse_duration
        
        # Pre-calculate scaled positions
        scaled_positions = {}
        for name, (x, y) in self.neuron_positions.items():
            if name not in self.excluded_neurons:
                scaled_positions[name] = (x * scale, y * scale)
        
        # === 1. Draw all static connections (base layer) ===
        for (src, dst), weight in self.weights.items():
            if src not in scaled_positions or dst not in scaled_positions:
                continue
            
            x1, y1 = scaled_positions[src]
            x2, y2 = scaled_positions[dst]
            
            # Base opacity from toggle fade system
            base_opacity = self._link_opacities.get((src, dst), 1.0)
            if base_opacity <= 0:
                continue
            
            # Weight-based thickness
            if self.anim_neural_weight_thickness:
                thickness = max(1.0, abs(weight) * self.anim_neural_weight_thickness_mult)
            else:
                thickness = self.anim_line_base_width
            pen_width = max(1, int(thickness * scale))
            
            # Color based on weight sign
            alpha = int(self.anim_neural_base_alpha * base_opacity)
            if weight >= 0:
                r, g, b = self.anim_neural_base_colour_pos
            else:
                r, g, b = self.anim_neural_base_colour_neg
            
            color = QtGui.QColor(r, g, b, alpha)
            pen = QtGui.QPen(color, pen_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
            painter.setPen(pen)
            painter.drawLine(QtCore.QLineF(x1, y1, x2, y2))
        
        # === 2. Draw activation pulses on top (traveling lights) ===
        for (src, dst), pulses in self._neural_pulses.items():
            if src not in scaled_positions or dst not in scaled_positions:
                continue
            
            x1, y1 = scaled_positions[src]
            x2, y2 = scaled_positions[dst]
            
            for pulse in pulses:
                elapsed = current_time - pulse['start_time']
                progress = elapsed / duration
                
                if progress > 1.0:
                    continue
                
                # Sinusoidal fade (glow in → peak → fade out)
                opacity = math.sin(progress * math.pi)
                
                # Get pulse color
                r, g, b = pulse['color']
                final_alpha = int(255 * opacity * 0.95)
                
                pulse_color = QtGui.QColor(r, g, b, final_alpha)
                
                # Thick glowing pulse line
                pulse_width = max(1, int(self.anim_neural_pulse_width * scale))
                pen = QtGui.QPen(pulse_color, pulse_width, QtCore.Qt.SolidLine, QtCore.Qt.RoundCap)
                painter.setPen(pen)
                
                # Traveling light effect - pulse moves along connection
                segment_progress = progress * 1.35
                if segment_progress <= 1.0:
                    # First phase: light travels from source toward destination
                    t = min(1.0, segment_progress)
                    px = x1 + t * (x2 - x1)
                    py = y1 + t * (y2 - y1)
                    painter.drawLine(QtCore.QLineF(x1, y1, px, py))
                else:
                    # Second phase: light "drains" toward destination
                    t = min(1.0, segment_progress - 0.35)
                    px = x1 + t * (x2 - x1)
                    py = y1 + t * (y2 - y1)
                    painter.drawLine(QtCore.QLineF(px, py, x2, y2))

    def _get_cached_font(self, size, bold=False):
        """Return cached QFont to avoid recreation every paint."""
        key = (size, bold)
        if key not in self._cached_fonts:
            font = QtGui.QFont("Fio UI", size)
            if bold:
                font.setBold(True)
            self._cached_fonts[key] = font
        return self._cached_fonts[key]

    def _get_cached_pen(self, color_tuple, width=1):
        """Return cached QPen to avoid recreation every paint."""
        key = (*color_tuple, width)
        if key not in self._cached_pens:
            color = QtGui.QColor(*color_tuple[:3])
            if len(color_tuple) > 3:
                color.setAlpha(color_tuple[3])
            self._cached_pens[key] = QtGui.QPen(color, width)
        return self._cached_pens[key]

    def draw_layers(self, painter, scale):
        """Draw background rectangles for custom layers (matches BrainDesigner)."""
        if not self.layers:                       # ← already stored by load_brain_state
            return

        for layer in self.layers:
            y_pos   = layer.get('y_position', 0)
            name    = layer.get('name', 'Layer')
            l_type  = layer.get('layer_type', 'hidden')

            # ---- same metrics as BrainDesigner ----
            rect_height = 120
            rect_top    = y_pos - rect_height / 2
            rect_left   = -200
            rect_width  = 2000

            # ---- same colours / alpha ----
            if l_type == 'input':
                color = QtGui.QColor(200, 255, 200, 80)
                border_color = QtGui.QColor(150, 220, 150, 120)
            elif l_type == 'output':
                color = QtGui.QColor(255, 200, 200, 80)
                border_color = QtGui.QColor(220, 150, 150, 120)
            else:   # hidden
                color = QtGui.QColor(230, 230, 255, 80)
                border_color = QtGui.QColor(200, 200, 240, 120)

            # ---- filled background ----
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(QtCore.QRectF(rect_left, rect_top,
                                         rect_width, rect_height))

            # ---- top & bottom border lines ----
            painter.setPen(QtGui.QPen(border_color, 2))
            painter.drawLine(QtCore.QLineF(rect_left, rect_top,
                                         rect_left + rect_width, rect_top))
            painter.drawLine(QtCore.QLineF(rect_left, rect_top + rect_height,
                                         rect_left + rect_width, rect_top + rect_height))

            # ---- layer label ----
            font = painter.font()
            font.setPointSize(int(10 * scale))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(100, 100, 120))
            painter.drawText(QtCore.QPointF(10, rect_top + 20),
                           f"{name} ({l_type})")

    def draw_connections(self, painter, scale):
        """
        Draw connections with extended 2-second weight-change animations.
        Links are forced INVISIBLE while core neurons are still being revealed.
        Includes special visualization for Stress->Anxiety inhibitory links.
        """
        if not self.show_links:
            return

        # ===== PERFORMANCE FIX: Skip if widget is hidden =====
        if not self.isVisible():
            return

        # ===== PERFORMANCE TRACKING =====
        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            _conn_start = time.perf_counter()

        # absolutely no connections until every core neuron is completely revealed (tutorial mode guard). 
        if self.is_tutorial_mode and len(self.visible_neurons) < len(self.original_neurons):
            return
        
        # ===== NEURAL STYLE: Use dedicated neural renderer =====
        if self.anim_neural_pulse_enabled:
            self._draw_neural_connections(painter, scale)
            return

        current_time = time.time()
        connections_drawn = 0
        connections_skipped = 0

        for key, weight in self.weights.items():
            if not isinstance(key, tuple) or len(key) != 2:
                continue
            source, target = key

            # skip tutorial-only connections when not in tutorial
            tutorial_mode = getattr(self.parent(), 'tutorial_active', False)
            is_tutorial_conn = (source.startswith('tutorial_neuron_') or
                                target.startswith('tutorial_neuron_'))
            if is_tutorial_conn and not tutorial_mode:
                continue

            # skip if either neuron is still revealing (tutorial safety)
            if self.is_tutorial_mode and (
                    not self.is_neuron_revealed(source) or
                    not self.is_neuron_revealed(target)):
                connections_skipped += 1
                continue

            if (source not in self.neuron_positions or
                target not in self.neuron_positions or
                source in self.excluded_neurons or
                target in self.excluded_neurons):
                continue

            # skip connections involving non-visible core neurons (tutorial)
            if self.is_tutorial_mode:
                if source in self.original_neurons and source not in self.visible_neurons:
                    connections_skipped += 1
                    continue
                if target in self.original_neurons and target not in self.visible_neurons:
                    connections_skipped += 1
                    continue

            start = self.neuron_positions[source]
            end   = self.neuron_positions[target]
            start_point = QtCore.QPointF(float(start[0]), float(start[1]))
            end_point   = QtCore.QPointF(float(end[0]),   float(end[1]))

            # === SPECIAL STYLING: Stress -> Anxiety (Dotted Red with Moving Arrows) ===
            # Detect connection between any stress neuron and anxiety
            is_stress_to_anxiety = (
                (source.lower().startswith('stress') and target.lower() == 'anxiety') or
                (target.lower().startswith('stress') and source.lower() == 'anxiety'))
            
            if is_stress_to_anxiety:
                # 1. Draw Dotted Red Line
                # Use a bright red color to indicate inhibitory/stress signal
                pen = QtGui.QPen(QtGui.QColor(255, 60, 60)) 
                pen.setWidth(max(2, int(3 * scale))) # Thicker than normal for visibility
                pen.setStyle(QtCore.Qt.DotLine)
                painter.setPen(pen)
                painter.drawLine(start_point, end_point)
                
                # 2. Draw Moving Arrows (Flowing towards Anxiety)
                # Determine which end is Anxiety
                if target.lower() == 'anxiety':
                    actual_start = start_point
                    actual_end = end_point
                else:
                    actual_start = end_point
                    actual_end = start_point
                
                # Vector math for the line
                dx = actual_end.x() - actual_start.x()
                dy = actual_end.y() - actual_start.y()
                length = math.sqrt(dx*dx + dy*dy)
                
                if length > 0:
                    # Unit vector
                    ux = dx / length
                    uy = dy / length
                    
                    # Arrow animation parameters
                    arrow_spacing = 40 * scale   # Distance between arrows
                    speed = 60 * scale           # Pixels per second
                    
                    # Offset based on time to create movement
                    offset = (current_time * speed) % arrow_spacing
                    
                    painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 0, 0)))
                    painter.setPen(QtCore.Qt.NoPen)
                    
                    current_dist = offset
                    while current_dist < length:
                        # Calculate position of arrow center on the line
                        ax = actual_start.x() + ux * current_dist
                        ay = actual_start.y() + uy * current_dist
                        
                        # Draw triangle (Arrowhead)
                        arrow_size = 6 * scale
                        
                        # Perpendicular vector for arrowhead width
                        px = -uy * arrow_size
                        py = ux * arrow_size
                        
                        # Tip of arrow (pointing forward)
                        tip_x = ax + ux * arrow_size
                        tip_y = ay + uy * arrow_size
                        
                        # Base corners of arrow
                        base_x = ax - ux * arrow_size
                        base_y = ay - uy * arrow_size
                        
                        points = [
                            QtCore.QPointF(tip_x, tip_y),
                            QtCore.QPointF(base_x + px, base_y + py),
                            QtCore.QPointF(base_x - px, base_y - py)
                        ]
                        painter.drawPolygon(QtGui.QPolygonF(points))
                        
                        current_dist += arrow_spacing

                # Skip standard drawing logic for this connection
                connections_drawn += 1
                continue

            # === STANDARD CONNECTION DRAWING ===
            anim_weight = weight
            base_width  = self.anim_line_base_width * scale
            line_width  = base_width
            pen_style   = QtCore.Qt.SolidLine
            animating   = False
            pulse_progress = 0.0

            # check for active weight-change animations (2-second window)
            for anim in self.weight_animations:
                if anim['pair'] == key:
                    elapsed = current_time - anim['start_time']
                    if elapsed < anim['duration']:
                        progress = elapsed / anim['duration']
                        anim_weight = anim['start_weight'] + progress * (
                            anim['end_weight'] - anim['start_weight'])

                        # growing / shrinking line width
                        if progress < 0.5:
                            line_width = base_width + (6.0 * scale * progress * 2)
                        else:
                            line_width = base_width + (6.0 * scale * (1 - progress) * 2)

                        pulse_progress = progress * anim['pulse_speed']
                        animating = True
                        break

            # colour & alpha
            if animating:
                r, g, b = anim['color']
                alpha = int(255 * (1 - pulse_progress ** 2))
                color = QtGui.QColor(r, g, b, alpha)
            else:
                base_alpha = int(self._link_opacities.get(key, 0.0) * 255)
                
                # ===== VIBRANT STYLE: Apply ambient pulse =====
                if self.anim_ambient_pulse_enabled and base_alpha > 0:
                    pulse_state = self._get_or_create_ambient_pulse(key)
                    phase = pulse_state['phase']
                    
                    # Sinusoidal oscillation (0 to 1 range)
                    pulse_factor = (math.sin(phase) + 1.0) / 2.0
                    
                    # Interpolate width
                    w_min, w_max = self.anim_ambient_pulse_width_range
                    width_mult = w_min + pulse_factor * (w_max - w_min)
                    line_width = base_width * width_mult
                    
                    # Interpolate alpha
                    a_min, a_max = self.anim_ambient_pulse_alpha_range
                    pulse_alpha = int(a_min + pulse_factor * (a_max - a_min))
                    # Combine with base opacity
                    final_alpha = int((base_alpha / 255.0) * pulse_alpha)
                    
                    if weight > 0:
                        color = QtGui.QColor(self.anim_line_col_pos[0], 
                                           self.anim_line_col_pos[1], 
                                           self.anim_line_col_pos[2], final_alpha)
                    else:
                        color = QtGui.QColor(self.anim_line_col_neg[0], 
                                           self.anim_line_col_neg[1], 
                                           self.anim_line_col_neg[2], final_alpha)
                else:
                    # Standard coloring (classic style or opacity 0)
                    color = (QtGui.QColor(0, int(255 * abs(weight)), 0, base_alpha) if weight > 0 else
                            QtGui.QColor(int(255 * abs(weight)), 0, 0, base_alpha))

            # line style
            if is_tutorial_conn and tutorial_mode:
                color = QtGui.QColor(255, 255, 0, 180)
                line_width = 3
                pen_style = QtCore.Qt.DashLine
            else:
                pen_style = (QtCore.Qt.DashLine if weight < 0 else
                            QtCore.Qt.SolidLine)
                if abs(anim_weight) < 0.1:
                    pen_style = QtCore.Qt.DotLine

            painter.setPen(QtGui.QPen(color, line_width, pen_style))
            painter.drawLine(start_point, end_point)

            # pulse circle travelling along the wire (uses animation style params)
            if self.anim_pulse_enabled and animating and pulse_progress < 1.0:
                pulse_pos = pulse_progress
                pulse_x = start_point.x() + pulse_pos * (end_point.x() - start_point.x())
                pulse_y = start_point.y() + pulse_pos * (end_point.y() - start_point.y())
                pulse_size = self.anim_pulse_diameter * scale * (1 - pulse_progress ** 2)

                painter.setBrush(QtGui.QBrush(QtGui.QColor(*self.anim_pulse_colour, self.anim_pulse_alpha)))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(pulse_x, pulse_y),
                                    pulse_size, pulse_size)

            # glow around the line (uses animation style params)
            if self.anim_glow_enabled and animating and progress < self.anim_glow_fade_threshold:
                glow_progress = progress / self.anim_glow_fade_threshold
                glow_width = line_width + 4 * scale * (1 - glow_progress)
                glow_color = QtGui.QColor(*self.anim_glow_colour, self.anim_glow_alpha)
                painter.setPen(QtGui.QPen(glow_color, glow_width, pen_style))
                painter.drawLine(start_point, end_point)
            
            # ===== SUBTLE STYLE: Draw communication glow packets =====
            if self.anim_comm_glow_enabled:
                self._draw_comm_glows_for_connection(
                    painter, scale, key, start_point, end_point
                )

            # weight text (optional)
            if self.show_weights and abs(weight) > 0.1:
                # Calculate angle for rotation
                dx = end_point.x() - start_point.x()
                dy = end_point.y() - start_point.y()
                angle_deg = math.degrees(math.atan2(dy, dx))
                
                # Ensure text is readable (not upside down)
                if angle_deg > 90:
                    angle_deg -= 180
                elif angle_deg < -90:
                    angle_deg += 180

                midpoint = QtCore.QPointF((start_point.x() + end_point.x()) / 2,
                                        (start_point.y() + end_point.y()) / 2)
                
                text_str = f"{weight:.2f}"
                
                # Font config
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
                
                # Draw background pill
                rect = QtCore.QRectF(-text_w/2 - padding, -text_h/2, 
                                     text_w + padding*2, text_h)
                
                painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 220)))
                painter.setPen(QtGui.QPen(QtGui.QColor(100, 100, 100, 150), 1))
                painter.drawRoundedRect(rect, 4, 4)
                
                # Draw text
                text_color = QtGui.QColor(0, 100, 0) if weight >= 0 else QtGui.QColor(150, 0, 0)
                painter.setPen(text_color)
                painter.drawText(rect, QtCore.Qt.AlignCenter, text_str)
                
                painter.restore()

            connections_drawn += 1

        # debug guard: warn only when something looks wrong
        if connections_drawn == 0 and len(self.weights) > 0:
            print(f"🔴 NO CONNECTIONS DRAWN! tutorial_mode={self.is_tutorial_mode}, "
                f"visible_neurons={len(self.visible_neurons)}, original_neurons={len(self.original_neurons)}, "
                f"total_weights={len(self.weights)}, skipped={connections_skipped}")
        
        # ===== END PERFORMANCE TRACKING =====
        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            _conn_elapsed = (time.perf_counter() - _conn_start) * 1000
            perf_tracker.record("draw_connections", _conn_elapsed)

    def _draw_connection_highlight(self, painter):
        if not self.hovered_connection:
            return

        u, v = self.hovered_connection
        if u not in self.neuron_positions or v not in self.neuron_positions:
            return

        scale, offset_x, indicator_space, _fit = self._view_transform()

        pos1 = self.neuron_positions[u]
        pos2 = self.neuron_positions[v]

        # Apply Transform: Logical * Scale + Offset = Screen
        x1 = pos1[0] * scale + offset_x
        y1 = pos1[1] * scale + indicator_space
        x2 = pos2[0] * scale + offset_x
        y2 = pos2[1] * scale + indicator_space

        p1 = QtCore.QPointF(x1, y1)
        p2 = QtCore.QPointF(x2, y2)

        # Draw Glow/Highlight
        painter.save()
        # Yellow, thick, slightly transparent
        pen = QtGui.QPen(QtGui.QColor(255, 255, 0, 200), 6 * scale)
        pen.setCapStyle(QtCore.Qt.RoundCap)
        painter.setPen(pen)
        painter.drawLine(p1, p2)
        
        # Label (Weight Value)
        weight = self.weights.get(self.hovered_connection, 0.0)
        mid = (p1 + p2) / 2
        
        font = painter.font()
        font.setPointSize(max(10, int(12 * scale)))
        font.setBold(True)
        painter.setFont(font)
        
        label = f"{weight:.2f}"
        fm = painter.fontMetrics()
        w = fm.horizontalAdvance(label) + 10
        h = fm.height() + 4
        r = QtCore.QRectF(mid.x() - w/2, mid.y() - h/2, w, h)
        
        painter.setPen(QtCore.Qt.NoPen)
        painter.setBrush(QtGui.QColor(0, 0, 0, 180))
        painter.drawRoundedRect(r, 4, 4)
        
        painter.setPen(QtGui.QColor(255, 255, 0))
        painter.drawText(r, QtCore.Qt.AlignCenter, label)
        
        painter.restore()

    # ------------------------------------------------------------------
    # Binary neuron detection
    # ------------------------------------------------------------------
    # ------------------------------------------------------------------

    def paintEvent(self, event):
        """
        Optimized paintEvent that uses cached offscreen render.
        
        The heavy rendering is done in BrainRenderWorker. This method
        just blits the cached image and draws any overlay elements
        that need to be responsive (like hover effects).
        """
        # Performance tracking
        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            _paint_start = time.perf_counter()
            perf_tracker.increment("paint_calls")
        
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Draw cached render if available
        if self._cached_render and not self._cached_render.isNull():
            # The frame is rendered at the screen's pixel ratio (2 on a Retina
            # Mac), so its own width and height are in pixels; its size in
            # points is what has to match the widget.
            cached = self._cached_render
            dpr = max(1.0, float(self.devicePixelRatioF()))
            img_dpr = max(1.0, float(cached.devicePixelRatio()))
            if (int(round(cached.width() / img_dpr)) != self.width() or
                int(round(cached.height() / img_dpr)) != self.height() or
                abs(img_dpr - dpr) > 1e-3):
                # Request new render at correct size
                self._render_dirty = True
                # Draw scaled version for now
                scaled = cached.scaled(
                    int(round(self.width() * dpr)), int(round(self.height() * dpr)),
                    QtCore.Qt.KeepAspectRatio,
                    QtCore.Qt.SmoothTransformation
                )
                scaled.setDevicePixelRatio(dpr)
                painter.drawImage(0, 0, scaled)
            else:
                painter.drawImage(0, 0, cached)
        else:
            # No cached render yet - draw background and request render
            bg_color = QtGui.QColor(*self.anim_background_colour)
            painter.fillRect(self.rect(), bg_color)
            self._render_dirty = True
        
        # Draw overlay elements that need immediate response
        self._draw_overlays(painter)
        
        painter.end()
        
        # Performance tracking
        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            _paint_elapsed = (time.perf_counter() - _paint_start) * 1000
            perf_tracker.record("paint_event", _paint_elapsed)

    def _draw_overlays(self, painter):
        """
        Draw overlay elements that need immediate response.
        These are drawn on top of the cached render.
        """
        # Tutorial glow effect
        if getattr(self, 'tutorial_glow_active', False):
            self._draw_tutorial_glow(painter)
        
        # Connection Highlight
        if self.hovered_connection:
            self._draw_connection_highlight(painter)

        # Neurogenesis highlights
        if hasattr(self, 'neurogenesis_highlight'):
            nh = self.neurogenesis_highlight
            if nh.get('neuron') and time.time() - nh.get('start_time', 0) < nh.get('duration', 0):
                self._draw_neurogenesis_highlight(painter)
        
        # Drag preview if dragging a neuron
        if getattr(self, 'dragging', False) and getattr(self, 'dragged_neuron', None):
            self._draw_drag_preview(painter)

    def _draw_tutorial_glow(self, painter):
        """Draw tutorial glow border effect"""
        opacity = getattr(self, '_tutorial_glow_opacity', 0.0)
        if opacity > 0:
            glow_color = QtGui.QColor(255, 215, 0, int(150 * opacity))
            pen = QtGui.QPen(glow_color, 4)
            painter.setPen(pen)
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawRect(self.rect().adjusted(2, 2, -2, -2))

    def _draw_neurogenesis_highlight(self, painter):
        """Draw highlight around newly created neurons"""
        # Calculate scale (same as in render worker)
        scale, offset_x, indicator_space, _fit = self._view_transform()

        nh = self.neurogenesis_highlight
        neuron_name = nh.get('neuron')
        if neuron_name and neuron_name in self.neuron_positions:
            pos = self.neuron_positions[neuron_name]
            x = pos[0] * scale + offset_x
            y = pos[1] * scale + indicator_space
            
            # Pulsing effect
            elapsed = time.time() - nh.get('start_time', 0)
            pulse = 0.5 + 0.5 * math.sin(elapsed * 4)
            
            radius = self.neuron_radius * NEURON_HIGHLIGHT_FACTOR * scale * (1 + pulse * 0.2)
            alpha = int(200 * (1 - elapsed / nh.get('duration', 1)))
            
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0, alpha), 3))
            painter.setBrush(QtCore.Qt.NoBrush)
            painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)

    def _draw_drag_preview(self, painter):
        """Draw preview when dragging a neuron (runs at full framerate)"""
        if not self.dragged_neuron or self.dragged_neuron not in self.neuron_positions:
            return

        # 1. The view, as the render worker draws it
        scale, offset_x, offset_y, fit = self._view_transform()
        
        # 2. Prepare single-neuron state for static drawing
        name = self.dragged_neuron
        pos = self.neuron_positions[name]
        val = self.state.get(name, 50)
        
        temp_positions = {name: pos}
        temp_states = {name: val}
        
        # 3. Draw the neuron immediately (bypassing cached 10fps render)
        # Note: We don't clear the background, so we draw ON TOP of the cached frame.
        # This might cause a slight 'trail' behind the moving neuron if the background 
        # refresh is slow, but it guarantees the neuron stays stuck to the mouse cursor.
        
        # Check if it has a custom shape
        shape = self.neuron_shapes.get(name, 'circle')
        
        x = pos[0] * scale
        y = pos[1] * scale
        # As the render worker sizes it: logical size times max(1, fit).
        radius = self.neuron_radius * max(1.0, fit) * scale
        
        # Temporarily set painter to high quality
        painter.save()
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        # x, y are relative to the canvas origin; the canvas sits at the
        # view offset (it was drawn at the widget's corner, off to the left
        # of the neuron being dragged whenever the canvas was centred).
        painter.translate(offset_x, offset_y)
        
        # Use existing shape drawing logic
        if shape == 'diamond':
            self.draw_diamond_neuron(painter, x, y, radius, name, scale)
        elif shape == 'square':
            self.draw_square_neuron(painter, x, y, radius, name, scale)
        elif shape == 'triangle':
            self.draw_triangular_neuron(painter, x, y, radius, name, scale)
        elif shape == 'hexagon' and self.is_connector_neuron(name):
            self.draw_hexagon_neuron(painter, x, y, radius, name, scale)
        elif shape == 'hexagon':      # a social neuron: a named hexagon
            self._draw_polygon_neuron(painter, x, y, 6, radius,
                                      QtGui.QColor(*self.state_colors.get(name, (255, 160, 200))),
                                      name, scale, rotation=0)
        else:
            # Standard/Continuous or Binary
            # Explicitly call the static method from the Mixin class
            NetworkRenderingMixin.draw_neurons_static(
                painter, temp_positions, temp_states,
                visible_neurons={name}, 
                scale=scale, 
                base_font_size=self.neuron_label_font_size,
                neuron_radius=self.neuron_radius
            )
            
        painter.restore()

    def draw_neurons(self, painter, scale=1.0):
        """Main neuron drawing routine."""
        # ------------------------------------------------------------------
        # Explicit list of true binary (on/off) neurons
        # ------------------------------------------------------------------
        BINARY_NEURONS = {
            "can_see_food", "is_eating", "is_sleeping",
            "is_sick", "is_fleeing", "pursuing_food", "is_startled",
            "external_stimulus", "can_see_plant"
        }

        # Font size for labels - use config value directly
        label_font = QtGui.QFont("Fio UI", self.neuron_label_font_size)
        label_font.setBold(True)
        painter.setFont(label_font)
        font_metrics = painter.fontMetrics()

        for name, pos in self.neuron_positions.items():
            if name not in self.visible_neurons and not self.is_tutorial_mode:
                continue
            if name in self.excluded_neurons:
                continue

            x_logical, y_logical = pos
            x = x_logical * scale
            y = y_logical * scale
            radius = self.neuron_radius * scale

            # Check shape early
            shape = self.neuron_shapes.get(name, 'circle')

            # --- BINARY NEURONS (always squares) ---
            if name in BINARY_NEURONS or name == "can_see_food":
                raw_value = self.state.get(name, 0)
                
                # Value calculation logic
                value = 100.0 if float(raw_value) > 50 else 0.0
                is_active = value > 50
                color = QtGui.QColor(0, 255, 0) if is_active else QtGui.QColor(255, 0, 0)

                # Draw Square
                painter.setBrush(QtGui.QBrush(color))
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), max(1, int(2 * scale))))
                
                size = radius * 1.8 
                rect = QtCore.QRectF(x - size/2, y - size/2, size, size)
                painter.drawRect(rect)

                # [NEW] Draw Checkmark or Cross inside
                symbol = "✓" if is_active else "✗"
                
                painter.save()
                symbol_font = QtGui.QFont("Fio UI", int(size * 0.7))
                symbol_font.setBold(True)
                painter.setFont(symbol_font)
                painter.setPen(QtGui.QColor(0, 0, 0)) # Black text
                painter.drawText(rect, QtCore.Qt.AlignCenter, symbol)
                painter.restore()

                if name == "can_see_food":
                    # Custom "Small Black Label" Logic for can_see_food
                    
                    # Get Localised Name
                    from .localisation import Localisation
                    loc = Localisation.instance()
                    display_name = loc.get(name)
                    if display_name == name: display_name = name.replace("_", " ").title()

                    # Smaller Font (0.75x)
                    small_font = painter.font()
                    small_font.setPointSize(max(4, int(self.neuron_label_font_size * 0.75 * scale)))
                    painter.setFont(small_font)
                    fm = painter.fontMetrics()

                    text_width = fm.horizontalAdvance(display_name)
                    padding = 4 * scale
                    rect_width = text_width + padding * 2
                    rect_height = fm.height() + 2

                    text_rect = QtCore.QRectF(
                        x - rect_width / 2,
                        y + size/2 + 4 * scale,
                        rect_width,
                        rect_height
                    )

                    # Black Background
                    painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0))) 
                    painter.setPen(QtCore.Qt.NoPen)
                    painter.drawRoundedRect(text_rect, 2, 2)

                    # White Text
                    painter.setPen(QtGui.QColor(255, 255, 255))
                    painter.drawText(text_rect, QtCore.Qt.AlignCenter, display_name)

                    # Restore Font
                    painter.setFont(label_font)
                else:
                    # Standard Label for other binary neurons
                    self._draw_standard_label(painter, name, x, y, scale, self.neuron_label_font_size)
                
                continue

            # --- SHAPE-BASED NEURONS ---
            elif shape == 'hexagon' and not self.is_connector_neuron(name):
                # A social neuron: a hexagon with its name, not a relay.
                color = QtGui.QColor(*self.state_colors.get(name, (255, 160, 200)))
                self._draw_polygon_neuron(painter, x, y, 6, radius, color, name, scale, rotation=0)
                continue

            elif shape == 'hexagon':
                # --- HEXAGON LOGIC ---
                color = QtGui.QColor(*self.state_colors.get(name, (160, 32, 240)))
                
                # Draw hexagon
                painter.save()
                painter.translate(x, y)
                
                sides = 6
                polygon = QtGui.QPolygonF()
                angle_step = 360.0 / sides
                for i in range(sides):
                    angle = math.radians(i * angle_step - 90)
                    polygon.append(QtCore.QPointF(radius * math.cos(angle), 
                                                radius * math.sin(angle)))
                
                painter.setBrush(QtGui.QBrush(color))
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
                painter.drawPolygon(polygon)
                
                # Draw 'C' inside
                font = QtGui.QFont("Fio UI", int(14 * scale))
                font.setBold(True)
                painter.setFont(font)
                painter.setPen(QtGui.QColor(255, 255, 255))
                
                rect_size = radius * 2
                rect = QtCore.QRectF(-radius, -radius, rect_size, rect_size)
                painter.drawText(rect, QtCore.Qt.AlignCenter, "c")
                painter.restore()
                
                # SKIP External Label for connectors
                continue
            
            elif shape == 'diamond':
                color = QtGui.QColor(*self.state_colors.get(name, (152, 251, 152)))
                self._draw_polygon_neuron(painter, x, y, 4, radius, color, name, scale, rotation=0)
                continue
            
            elif shape == 'square':
                color = QtGui.QColor(*self.state_colors.get(name, (152, 251, 152)))
                self._draw_polygon_neuron(painter, x, y, 4, radius, color, name, scale, rotation=45)
                continue
            
            elif shape == 'triangle':
                color = QtGui.QColor(*self.state_colors.get(name, (255, 255, 150)))
                self._draw_polygon_neuron(painter, x, y, 3, radius, color, name, scale, rotation=0)
                continue
            
            else:  # circle (default)
                # Color logic
                raw_value = self.state.get(name, 0)
                value = float(raw_value) if isinstance(raw_value, (int, float, bool)) else 50.0
                value = max(0, min(100, value))
                
                if name in self.state_colors:
                    color = QtGui.QColor(*self.state_colors[name])
                else:
                    # The colour of the row it sits on - see
                    # brain_constants.ROW_COLORS.
                    from .brain_constants import neuron_row_color
                    color = QtGui.QColor(*neuron_row_color(name))

                # Draw Circle
                painter.setBrush(QtGui.QBrush(color))
                painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), max(1, int(2 * scale))))
                painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)

                # Draw Label
                self._draw_standard_label(painter, name, x, y, scale, self.neuron_label_font_size)

    def _draw_standard_label(self, painter, name, x, y, scale, font_size=None):
        """Draw a standard neuron label with improved localisation fallback."""
        loc = Localisation.instance()

        if font_size is None:
            font_size = self.neuron_label_font_size

        label_font = QtGui.QFont("Fio UI", int(font_size * scale))
        label_font.setBold(True)
        painter.setFont(label_font)
        font_metrics = painter.fontMetrics()

        # Primary: exact key
        display_name = loc.get(name)

        # Fallback 1: try space-separated version
        if display_name == name:  # Means no translation found
            space_key = name.replace("_", " ")
            display_name = loc.get(space_key, default=None)
            if display_name is None:
                display_name = space_key  # Use spaces for readability

        # Fallback 2: neurogenesis pattern (e.g., novelty_1 → Novelty 1)
        if display_name == name or display_name == name.replace("_", " "):
            match = re.match(r"^([a_z]+)_(\d+)$", name)
            if match:
                base = match.group(1)
                idx = match.group(2)
                base_loc = loc.get(base)
                if base_loc != base:  # Found translation for base
                    display_name = f"{base_loc} {idx}"
                else:
                    display_name = f"{base.capitalize()} {idx}"

        # Final fallback: clean title case
        if display_name == name:
            display_name = name.replace("_", " ").title()

        text_width = font_metrics.horizontalAdvance(display_name)
        padding = 10 * scale
        rect_width = text_width + padding * 2
        rect_height = font_metrics.height() + 4

        text_rect = QtCore.QRectF(
            x - rect_width / 2,
            y + (self.neuron_radius * scale) + 4 * scale,
            rect_width,
            rect_height,
        )

        painter.setBrush(QtGui.QBrush(QtGui.QColor(26, 26, 26, 200)))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(text_rect, 4, 4)

        painter.setPen(QtGui.QColor(224, 224, 224))
        painter.drawText(text_rect, QtCore.Qt.AlignCenter, display_name)

    def draw_binary_neuron(self, painter, x, y, value, label, scale=1.0):
        color = (0, 0, 0) if value else (255, 255, 255)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(*color))); painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
        x_scaled, y_scaled, size = int(x * scale), int(y * scale), int(30 * scale)
        painter.drawRect(x_scaled - size//2, y_scaled - size//2, size, size)
        font = painter.font(); font.setPointSize(max(4, int(5 * scale))); painter.setFont(font)  # Reduced from 6, added max
        label_width, label_height = int(150 * scale), int(20 * scale)
        painter.drawText(x_scaled - label_width//2, y_scaled + int(30 * scale), label_width, label_height, QtCore.Qt.AlignCenter, label)

    def draw_circular_neuron(self, painter, name, pos, value, scale=1.0, visible_neurons=None, excluded_neurons=None):
        """Fixed version with correct excluded_neurons handling."""
        if visible_neurons is None:
            visible_neurons = self.visible_neurons
        if excluded_neurons is None:
            excluded_neurons = self.excluded_neurons

        if name in excluded_neurons or name not in visible_neurons:
            return

        # Reuse static method for consistency
        temp_states = {name: value}
        temp_positions = {name: pos}
        
        NetworkRenderingMixin.draw_neurons_static(
            painter, temp_positions, temp_states,
            visible_neurons={name}, excluded_neurons=excluded_neurons,
            scale=scale, base_font_size=self.neuron_label_font_size,
            neuron_radius=self.neuron_radius
        )

    def draw_triangular_neuron(self, painter, x, y, radius, label, scale=1.0, alpha=255):
        """Draw a triangular neuron with given radius"""
        color = QtGui.QColor(*self.state_colors.get(label, (255, 255, 150)))
        self._draw_polygon_neuron(painter, x, y, 3, radius, color, label, scale, alpha=alpha)

    def draw_hexagon_neuron(self, painter, x, y, radius, label, scale=1.0, alpha=255):
        """Draw a purple hexagon neuron with a 'C' inside and NO external label"""
        # 1. Setup Painter
        painter.save()
        painter.translate(x, y)
        
        # Color setup (Purple)
        color_tuple = self.state_colors.get(label, (160, 32, 240))
        color = QtGui.QColor(*color_tuple)
        color.setAlpha(min(255, max(0, alpha)))
        
        pen_color = QtGui.QColor(0, 0, 0)
        pen_color.setAlpha(min(255, max(0, alpha)))

        painter.setBrush(QtGui.QBrush(color))
        painter.setPen(QtGui.QPen(pen_color))

        # 2. Draw Hexagon Polygon
        sides = 6
        polygon = QtGui.QPolygonF()
        angle_step = 360.0 / sides
        for i in range(sides):
            angle = math.radians(i * angle_step - 90)
            polygon.append(QtCore.QPointF(radius * math.cos(angle), 
                                        radius * math.sin(angle)))
        painter.drawPolygon(polygon)

        # 3. Draw the 'C' inside
        font_size = int(14 * scale)
        font = QtGui.QFont("Fio UI", font_size)
        font.setBold(True)
        painter.setFont(font)
        
        # White text
        painter.setPen(QtGui.QColor(255, 255, 255, min(255, max(0, alpha))))
        
        rect_size = radius * 2
        rect = QtCore.QRectF(-radius, -radius, rect_size, rect_size)
        painter.drawText(rect, QtCore.Qt.AlignCenter, "c")

        painter.restore()

    def _draw_polygon_neuron(self, painter, x, y, sides, radius, color, label, scale,
                            rotation=0, alpha=255):
        painter.save()
        painter.translate(x, y)
        painter.rotate(rotation)

        alpha = max(0, min(255, alpha))            # ← clamp
        colored = QtGui.QColor(color)
        colored.setAlpha(alpha)

        pen_color = QtGui.QColor(0, 0, 0)
        pen_color.setAlpha(alpha)

        painter.setBrush(QtGui.QBrush(colored))
        painter.setPen(QtGui.QPen(pen_color))

        polygon = QtGui.QPolygonF()
        angle_step = 360.0 / sides
        for i in range(sides):
            angle = math.radians(i * angle_step - 90)
            polygon.append(QtCore.QPointF(radius * math.cos(angle),
                                        radius * math.sin(angle)))
        painter.drawPolygon(polygon)
        painter.restore()
        self._draw_neuron_label(painter, x, y, label, radius, scale, alpha)

    def _draw_neuron_label(self, painter, x, y, name, radius, scale, alpha=255):
        """Draw neuron label with robust localisation fallback."""
        loc = Localisation.instance()

        font = QtGui.QFont("Fio UI", int(self.neuron_label_font_size * scale))
        font.setBold(True)
        painter.setFont(font)
        fm = painter.fontMetrics()

        # Step 1: Try exact key
        label = loc.get(name)

        # Step 2: Try space-separated key
        if label == name:
            space_key = name.replace("_", " ")
            label = loc.get(space_key)
            if label == space_key:
                label = None  # Mark as not found

        # Step 3: Neurogenesis pattern
        if not label:
            import re
            match = re.match(r"^([a-z_]+)_(\d+)$", name)
            if match:
                base_key = match.group(1)
                num = match.group(2)
                base_label = loc.get(base_key)
                if base_label != base_key:
                    label = f"{base_label} {num}"
                else:
                    label = f"{base_key.replace('_', ' ').title()} {num}"

        # Final fallback
        if not label:
            label = name.replace("_", " ").title()

        text_width = fm.horizontalAdvance(label)
        padding = 10 * scale
        
        # Position label below the neuron (y + radius + padding)
        rect_y = y + radius + (5 * scale)
        
        rect = QtCore.QRectF(
            x - text_width / 2 - padding,
            rect_y,
            text_width + padding * 2,
            fm.height() + 6
        )

        # Apply alpha transparency
        bg_alpha = min(180, alpha)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 0, 0, bg_alpha)))
        painter.setPen(QtCore.Qt.NoPen)
        painter.drawRoundedRect(rect, 6, 6)

        text_color = QtGui.QColor(255, 255, 255)
        text_color.setAlpha(alpha)
        painter.setPen(text_color)
        painter.drawText(rect, QtCore.Qt.AlignCenter, label)

    def draw_neurogenesis_highlights(self, painter, scale):
        if (self.neurogenesis_highlight['neuron'] and time.time() - self.neurogenesis_highlight['start_time'] < self.neurogenesis_highlight['duration']):
            pos = self.neuron_positions.get(self.neurogenesis_highlight['neuron'])
            if pos:
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 0), int(3 * scale))); painter.setBrush(QtCore.Qt.NoBrush); radius = int(self.neuron_radius * NEURON_HIGHLIGHT_FACTOR * scale)
                x, y, width, height = int(pos[0] - radius), int(pos[1] - radius), int(radius * 2), int(radius * 2)
                painter.drawEllipse(x, y, width, height)

    def draw_square_neuron(self, painter, x, y, radius, label, scale=1.0, alpha=255):
        """Draw a square neuron with given radius"""
        color = QtGui.QColor(*self.state_colors.get(label, (152, 251, 152)))
        self._draw_polygon_neuron(painter, x, y, 4, radius, color, label, scale, rotation=45, alpha=alpha)

    def draw_diamond_neuron(self, painter, x, y, radius, label, scale=1.0, alpha=255):
        """Draw a diamond-shaped neuron with given radius"""
        color = QtGui.QColor(*self.state_colors.get(label, (152, 251, 152)))
        self._draw_polygon_neuron(painter, x, y, 4, radius, color, label, scale, rotation=0, alpha=alpha)

    def draw_strength_multiplier(self, painter, scale):
        """
        Draw strength multipliers on neurons that have been strengthened.
        Displays as "2.5x" above strengthened neurons with a badge.
        """
        if not hasattr(self, 'enhanced_neurogenesis'):
            return
        
        current_time = time.time()
        
        # Save painter state to avoid interfering with other drawings
        painter.save()
        
        for name, neuron in self.enhanced_neurogenesis.functional_neurons.items():
            # Verify attribute exists and neuron is strengthened
            if not hasattr(neuron, 'strength_multiplier'):
                continue
                
            if neuron.strength_multiplier <= 1.0 or name not in self.neuron_positions:
                continue
            
            pos = self.neuron_positions[name]
            x, y = pos
            
            # Position ABOVE the neuron (in logical coordinates)
            label_y = y - 45  # Don't scale Y offset - already in logical space
            
            # Format multiplier text
            multiplier_text = f"{neuron.strength_multiplier:.1f}x"  # FIX: typo here
            
            # Create font with proper scaling
            font = QtGui.QFont()
            font.setPointSize(int(9 * scale))
            font.setBold(True)
            painter.setFont(font)
            
            # Draw background circle/badge
            font_metrics = painter.fontMetrics()
            text_width = font_metrics.horizontalAdvance(multiplier_text)
            badge_radius = max(12 * scale, (text_width / 2) + 5 * scale)
            
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 215, 0, 220)))
            painter.setPen(QtGui.QPen(QtGui.QColor(139, 105, 20), max(1, int(2 * scale))))
            painter.drawEllipse(QtCore.QPointF(x, label_y), badge_radius, badge_radius)
            
            # Draw text
            painter.setPen(QtGui.QColor(0, 0, 0))
            painter.drawText(
                int(x - text_width / 2),
                int(label_y - font_metrics.height() / 2),
                int(text_width),
                int(font_metrics.height()),
                QtCore.Qt.AlignCenter,
                multiplier_text
            )
            
            # Optional: Add star indicator
            star_radius = 8 * scale
            star_x = x + self.neuron_radius * scale
            star_y = y - self.neuron_radius * scale
            
            painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 215, 0, 200)))
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 165, 0), max(1, int(2 * scale))))
            painter.drawEllipse(QtCore.QPointF(star_x, star_y), star_radius, star_radius)
        
        painter.restore()


# =============================================================================
# NETWORK RENDERING MIXIN (Add to brain_widget.py)
# =============================================================================

class NetworkRenderingMixin:
    """
    Mixin providing static network rendering methods extracted from BrainWidget.
    Used by both BrainWidget and save viewer's NetworkCanvas for consistent visuals.
    """
    
    @staticmethod
    def draw_connections(self, painter, scale):
        """Draw connections with extended 2-second weight-change animations.
        Links are forced INVISIBLE while core neurons are still being revealed."""
        if not self.show_links:
            return

        # ===== PERFORMANCE FIX: Skip if widget is hidden =====
        if not self.isVisible():
            return

        # ===== PERFORMANCE TRACKING =====
        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            _conn_start = time.perf_counter()

        # absolutely no connections until every core neuron is completely revealed (tutorial mode guard). 
        if self.is_tutorial_mode and len(self.visible_neurons) < len(self.original_neurons):
            return
        
        # ===== NEURAL STYLE: Use dedicated neural renderer =====
        if self.anim_neural_pulse_enabled:
            self._draw_neural_connections(painter, scale)
            return

        current_time = time.time()
        connections_drawn = 0
        connections_skipped = 0

        for key, weight in self.weights.items():
            if not isinstance(key, tuple) or len(key) != 2:
                continue
            source, target = key

            # skip tutorial-only connections when not in tutorial
            tutorial_mode = getattr(self.parent(), 'tutorial_active', False)
            is_tutorial_conn = (source.startswith('tutorial_neuron_') or
                                target.startswith('tutorial_neuron_'))
            if is_tutorial_conn and not tutorial_mode:
                continue

            # skip if either neuron is still revealing (tutorial safety)
            if self.is_tutorial_mode and (
                    not self.is_neuron_revealed(source) or
                    not self.is_neuron_revealed(target)):
                connections_skipped += 1
                continue

            if (source not in self.neuron_positions or
                target not in self.neuron_positions or
                source in self.excluded_neurons or
                target in self.excluded_neurons):
                continue

            # skip connections involving non-visible core neurons (tutorial)
            if self.is_tutorial_mode:
                if source in self.original_neurons and source not in self.visible_neurons:
                    connections_skipped += 1
                    continue
                if target in self.original_neurons and target not in self.visible_neurons:
                    connections_skipped += 1
                    continue

            start = self.neuron_positions[source]
            end   = self.neuron_positions[target]
            start_point = QtCore.QPointF(float(start[0]), float(start[1]))
            end_point   = QtCore.QPointF(float(end[0]),   float(end[1]))

            # special styling:  Stress ↔ Anxiety  (uses animation style params)
            is_stress_to_anxiety = (
                (source.lower().startswith('stress') and target.lower() == 'anxiety') or
                (target.lower().startswith('stress') and source.lower() == 'anxiety'))
            if is_stress_to_anxiety:
                pen = QtGui.QPen(QtGui.QColor(*self.anim_stress_colour))
                pen.setWidth(int(self.anim_stress_width))
                if self.anim_stress_dashed:
                    pen.setStyle(QtCore.Qt.DashLine)
                painter.setPen(pen)
                painter.drawLine(start_point, end_point)
                continue   # skip default drawing for this pair

            # default appearance (uses animation style params)
            anim_weight = weight
            base_width  = self.anim_line_base_width * scale
            line_width  = base_width
            pen_style   = QtCore.Qt.SolidLine
            animating   = False
            pulse_progress = 0.0

            # check for active weight-change animations (2-second window)
            for anim in self.weight_animations:
                if anim['pair'] == key:
                    elapsed = current_time - anim['start_time']
                    if elapsed < anim['duration']:
                        progress = elapsed / anim['duration']
                        anim_weight = anim['start_weight'] + progress * (
                            anim['end_weight'] - anim['start_weight'])

                        # growing / shrinking line width
                        if progress < 0.5:
                            line_width = base_width + (6.0 * scale * progress * 2)
                        else:
                            line_width = base_width + (6.0 * scale * (1 - progress) * 2)

                        pulse_progress = progress * anim['pulse_speed']
                        animating = True
                        break

            # colour & alpha
            if animating:
                r, g, b = anim['color']
                alpha = int(255 * (1 - pulse_progress ** 2))
                color = QtGui.QColor(r, g, b, alpha)
            else:
                base_alpha = int(self._link_opacities.get(key, 0.0) * 255)
                
                # ===== VIBRANT STYLE: Apply ambient pulse =====
                if self.anim_ambient_pulse_enabled and base_alpha > 0:
                    pulse_state = self._get_or_create_ambient_pulse(key)
                    phase = pulse_state['phase']
                    
                    # Sinusoidal oscillation (0 to 1 range)
                    pulse_factor = (math.sin(phase) + 1.0) / 2.0
                    
                    # Interpolate width
                    w_min, w_max = self.anim_ambient_pulse_width_range
                    width_mult = w_min + pulse_factor * (w_max - w_min)
                    line_width = base_width * width_mult
                    
                    # Interpolate alpha
                    a_min, a_max = self.anim_ambient_pulse_alpha_range
                    pulse_alpha = int(a_min + pulse_factor * (a_max - a_min))
                    # Combine with base opacity
                    final_alpha = int((base_alpha / 255.0) * pulse_alpha)
                    
                    if weight > 0:
                        color = QtGui.QColor(self.anim_line_col_pos[0], 
                                           self.anim_line_col_pos[1], 
                                           self.anim_line_col_pos[2], final_alpha)
                    else:
                        color = QtGui.QColor(self.anim_line_col_neg[0], 
                                           self.anim_line_col_neg[1], 
                                           self.anim_line_col_neg[2], final_alpha)
                else:
                    # Standard coloring (classic style or opacity 0)
                    color = (QtGui.QColor(0, int(255 * abs(weight)), 0, base_alpha) if weight > 0 else
                            QtGui.QColor(int(255 * abs(weight)), 0, 0, base_alpha))

            # line style
            if is_tutorial_conn and tutorial_mode:
                color = QtGui.QColor(255, 255, 0, 180)
                line_width = 3
                pen_style = QtCore.Qt.DashLine
            else:
                pen_style = (QtCore.Qt.DashLine if weight < 0 else
                            QtCore.Qt.SolidLine)
                if abs(anim_weight) < 0.1:
                    pen_style = QtCore.Qt.DotLine

            painter.setPen(QtGui.QPen(color, line_width, pen_style))
            painter.drawLine(start_point, end_point)

            # pulse circle travelling along the wire (uses animation style params)
            if self.anim_pulse_enabled and animating and pulse_progress < 1.0:
                pulse_pos = pulse_progress
                pulse_x = start_point.x() + pulse_pos * (end_point.x() - start_point.x())
                pulse_y = start_point.y() + pulse_pos * (end_point.y() - start_point.y())
                pulse_size = self.anim_pulse_diameter * scale * (1 - pulse_progress ** 2)

                painter.setBrush(QtGui.QBrush(QtGui.QColor(*self.anim_pulse_colour, self.anim_pulse_alpha)))
                painter.setPen(QtCore.Qt.NoPen)
                painter.drawEllipse(QtCore.QPointF(pulse_x, pulse_y),
                                    pulse_size, pulse_size)

            # glow around the line (uses animation style params)
            if self.anim_glow_enabled and animating and progress < self.anim_glow_fade_threshold:
                glow_progress = progress / self.anim_glow_fade_threshold
                glow_width = line_width + 4 * scale * (1 - glow_progress)
                glow_color = QtGui.QColor(*self.anim_glow_colour, self.anim_glow_alpha)
                painter.setPen(QtGui.QPen(glow_color, glow_width, pen_style))
                painter.drawLine(start_point, end_point)
            
            # ===== SUBTLE STYLE: Draw communication glow packets =====
            if self.anim_comm_glow_enabled:
                self._draw_comm_glows_for_connection(
                    painter, scale, key, start_point, end_point
                )

            # weight text (optional)
            if self.show_weights and abs(weight) > 0.1:
                # Calculate angle for rotation
                dx = end_point.x() - start_point.x()
                dy = end_point.y() - start_point.y()
                angle_deg = math.degrees(math.atan2(dy, dx))
                
                # Ensure text is readable (not upside down)
                if angle_deg > 90:
                    angle_deg -= 180
                elif angle_deg < -90:
                    angle_deg += 180

                midpoint = QtCore.QPointF((start_point.x() + end_point.x()) / 2,
                                        (start_point.y() + end_point.y()) / 2)
                
                text_str = f"{weight:.2f}"
                
                # Font config
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
                
                # Draw background pill
                rect = QtCore.QRectF(-text_w/2 - padding, -text_h/2, 
                                     text_w + padding*2, text_h)
                
                painter.setBrush(QtGui.QBrush(QtGui.QColor(255, 255, 255, 220)))
                painter.setPen(QtGui.QPen(QtGui.QColor(100, 100, 100, 150), 1))
                painter.drawRoundedRect(rect, 4, 4)
                
                # Draw text
                text_color = QtGui.QColor(0, 100, 0) if weight >= 0 else QtGui.QColor(150, 0, 0)
                painter.setPen(text_color)
                painter.drawText(rect, QtCore.Qt.AlignCenter, text_str)
                
                painter.restore()

            connections_drawn += 1

        # debug guard: warn only when something looks wrong
        if connections_drawn == 0 and len(self.weights) > 0:
            print(f"🔴 NO CONNECTIONS DRAWN! tutorial_mode={self.is_tutorial_mode}, "
                f"visible_neurons={len(self.visible_neurons)}, original_neurons={len(self.original_neurons)}, "
                f"total_weights={len(self.weights)}, skipped={connections_skipped}")
        
        # ===== END PERFORMANCE TRACKING =====
        if _PERF_TRACKING_AVAILABLE and perf_tracker.enabled:
            _conn_elapsed = (time.perf_counter() - _conn_start) * 1000
            perf_tracker.record("draw_connections", _conn_elapsed)
    
    @staticmethod
    def draw_neurons_static(
        painter, neuron_positions, neuron_states,
        visible_neurons=None, excluded_neurons=None,
        scale=1.0, base_font_size=6, neuron_radius=NEURON_RADIUS):
        """
        Static neuron drawing with full localisation fallback support.
        """
        from .localisation import Localisation
        loc = Localisation.instance()

        if visible_neurons is None:
            visible_neurons = set(neuron_positions.keys())
        if excluded_neurons is None:
            excluded_neurons = set()

        label_font = QtGui.QFont("Fio UI", int(base_font_size * scale))
        label_font.setBold(True)
        painter.setFont(label_font)
        font_metrics = painter.fontMetrics()

        for name, pos in neuron_positions.items():
            if name in excluded_neurons or name not in visible_neurons:
                continue

            raw_value = neuron_states.get(name, 0)

            # Determine color and value (binary vs continuous)
            if name in BINARY_NEURONS:
                value = 100.0 if float(raw_value) > 50 else 0.0
                is_active = value > 50
                color = QtGui.QColor(0, 255, 0) if is_active else QtGui.QColor(255, 0, 0)
            else:
                value = float(raw_value) if isinstance(raw_value, (int, float, bool)) else 50.0
                value = max(0, min(100, value))
                normalized = value / 100.0
                if normalized > 0.7:
                    color = QtGui.QColor(76, 175, 80)
                elif normalized > 0.4:
                    color = QtGui.QColor(255, 193, 7)
                else:
                    color = QtGui.QColor(244, 67, 54)

            x = pos[0] * scale
            y = pos[1] * scale
            radius = neuron_radius * scale

            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), max(1, int(2 * scale))))
            painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)

            # === Localisation with multi-level fallback ===
            display_name = loc.get(name)

            # Fallback 1: space-separated key
            if display_name == name:
                space_key = name.replace("_", " ")
                display_name = loc.get(space_key)
                if display_name == space_key:
                    display_name = None

            # Fallback 2: neurogenesis numbered neuron
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

            # Final fallback
            if not display_name:
                display_name = name.replace("_", " ").title()

            text_width = font_metrics.horizontalAdvance(display_name)
            padding = 10 * scale
            rect_width = text_width + padding * 2
            rect_height = font_metrics.height() + 4

            text_rect = QtCore.QRectF(
                x - rect_width / 2,
                y + radius + 5 * scale,
                rect_width,
                rect_height,
            )

            painter.setBrush(QtGui.QBrush(QtGui.QColor(26, 26, 26, 200)))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRoundedRect(text_rect, 4, 4)

            painter.setPen(QtGui.QColor(224, 224, 224))
            painter.drawText(text_rect, QtCore.Qt.AlignCenter, display_name)

    
    @staticmethod
    def draw_layers_static(painter, layers, scale=1.0):
        """Draw layer background rectangles if layer structure exists"""
        if not layers:
            return
            
        for layer in layers:
            y_pos = layer.get('y_position', 0)
            name = layer.get('name', 'Layer')
            layer_type = layer.get('layer_type', 'hidden')
            
            # Logical dimensions (match brain_widget's coordinate system)
            rect_height = 120
            rect_top = (y_pos - rect_height / 2)
            rect_left = -200  # Extend beyond visible area
            rect_width = 2000
            
            # Determine layer color based on type
            if layer_type == 'input':
                color = QtGui.QColor(220, 255, 220, 30)
                border_color = QtGui.QColor(180, 220, 180, 60)
            elif layer_type == 'output':
                color = QtGui.QColor(255, 220, 220, 30)
                border_color = QtGui.QColor(220, 180, 180, 60)
            else:  # hidden
                color = QtGui.QColor(230, 230, 255, 40)
                border_color = QtGui.QColor(200, 200, 240, 60)
            
            # Draw rectangle
            rect = QtCore.QRectF(rect_left, rect_top, rect_width, rect_height)
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtGui.QPen(border_color, 1, QtCore.Qt.DashLine))
            painter.drawRect(rect)
            
            # Draw label
            font = QtGui.QFont("Fio UI", int(10 * scale))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(150, 150, 170))
            painter.drawText(QtCore.QPointF(20, rect_top + 20), name)
