"""
Enhanced Canvas Utilities for Brain Designer

Additional visual feedback for wiring operations and activation display.
"""

from PyQt5.QtWidgets import (
    QGraphicsItem, QGraphicsEllipseItem, QGraphicsTextItem, 
    QGraphicsRectItem, QGraphicsPathItem, QToolTip
)
from PyQt5.QtCore import Qt, QPointF, QRectF, QTimer
from PyQt5.QtGui import (
    QPainter, QPen, QBrush, QColor, QFont, QFontMetrics,
    QPainterPath, QRadialGradient, QLinearGradient
)

import math


class WiringPreviewItem(QGraphicsItem):
    """
    Enhanced preview of a connection being dragged.
    Shows validity feedback, snapping, and weight preview.
    """
    
    def __init__(self, start_pos: QPointF, parent=None):
        super().__init__(parent)
        self.start_pos = start_pos
        self.end_pos = start_pos
        self.is_valid = False
        self.target_name = ""
        self.preview_weight = 0.5
        self.is_snapped = False
        
        # Animation
        self.pulse_phase = 0.0
        
        self.setZValue(100)  # Above everything
    
    def set_end(self, pos: QPointF, is_valid: bool = False, 
                target_name: str = "", snapped: bool = False):
        """Update the end position and validity state."""
        self.end_pos = pos
        self.is_valid = is_valid
        self.target_name = target_name
        self.is_snapped = snapped
        self.update()
    
    def boundingRect(self) -> QRectF:
        return QRectF(self.start_pos, self.end_pos).normalized().adjusted(-50, -50, 50, 50)
    
    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Determine colors
        if self.is_valid and self.is_snapped:
            # Valid and snapped to target
            color = QColor(50, 205, 50)  # Green
            glow_color = QColor(50, 205, 50, 80)
            style = Qt.SolidLine
        elif self.is_valid:
            # Valid but not snapped
            color = QColor(100, 180, 100)
            glow_color = QColor(100, 180, 100, 60)
            style = Qt.DashLine
        else:
            # Invalid or dragging in open space
            color = QColor(255, 215, 0)  # Gold
            glow_color = QColor(255, 215, 0, 60)
            style = Qt.DashLine
        
        # Draw glow
        painter.setPen(QPen(glow_color, 12, Qt.SolidLine, Qt.RoundCap))
        painter.drawLine(self.start_pos, self.end_pos)
        
        # Draw main line
        painter.setPen(QPen(color, 3, style, Qt.RoundCap))
        painter.drawLine(self.start_pos, self.end_pos)
        
        # Draw arrowhead at end
        line_vec = self.end_pos - self.start_pos
        length = math.sqrt(line_vec.x()**2 + line_vec.y()**2)
        if length > 10:
            angle = math.atan2(line_vec.y(), line_vec.x())
            arrow_size = 15
            
            p1 = self.end_pos - QPointF(
                math.cos(angle + 0.5) * arrow_size,
                math.sin(angle + 0.5) * arrow_size
            )
            p2 = self.end_pos - QPointF(
                math.cos(angle - 0.5) * arrow_size,
                math.sin(angle - 0.5) * arrow_size
            )
            
            painter.setBrush(QBrush(color))
            painter.setPen(Qt.NoPen)
            path = QPainterPath()
            path.moveTo(self.end_pos)
            path.lineTo(p1)
            path.lineTo(p2)
            path.closeSubpath()
            painter.drawPath(path)
        
        # Draw target label if snapped
        if self.is_snapped and self.target_name:
            mid = (self.start_pos + self.end_pos) / 2
            
            # Background
            font = QFont("Arial", 10, QFont.Bold)
            painter.setFont(font)
            fm = QFontMetrics(font)
            
            label = f"→ {self.target_name.replace('_', ' ').title()}"
            text_width = fm.horizontalAdvance(label)
            text_height = fm.height()
            
            rect = QRectF(mid.x() - text_width/2 - 8, mid.y() - text_height/2 - 4,
                         text_width + 16, text_height + 8)
            
            bg_color = QColor(50, 50, 50, 200) if not self.is_valid else QColor(30, 100, 30, 200)
            painter.setBrush(QBrush(bg_color))
            painter.setPen(Qt.NoPen)
            painter.drawRoundedRect(rect, 5, 5)
            
            # Text
            painter.setPen(Qt.white)
            painter.drawText(rect, Qt.AlignCenter, label)


class ActivationBadge(QGraphicsItem):
    """
    Badge showing a neuron's current activation value.
    """
    
    def __init__(self, center: QPointF, value: float, 
                 is_binary: bool = False, parent=None):
        super().__init__(parent)
        self.center = center
        self.value = value
        self.is_binary = is_binary
        
        # Position below the neuron
        self.setPos(center.x() - 20, center.y() + 35)
        self.setZValue(5)
    
    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, 40, 18)
    
    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = self.boundingRect()
        
        # Color based on value
        if self.is_binary:
            if self.value > 50:
                color = QColor(50, 205, 50)  # Green = ON
                text = "ON"
            else:
                color = QColor(150, 150, 150)  # Gray = OFF
                text = "OFF"
        else:
            # Gradient from blue (low) to red (high)
            ratio = self.value / 100.0
            if ratio < 0.5:
                # Blue to yellow
                r = int(50 + ratio * 2 * 205)
                g = int(50 + ratio * 2 * 155)
                b = int(200 - ratio * 2 * 150)
            else:
                # Yellow to red
                r = 255
                g = int(205 - (ratio - 0.5) * 2 * 155)
                b = int(50 - (ratio - 0.5) * 2 * 50)
            color = QColor(r, g, b)
            text = f"{self.value:.0f}"
        
        # Background
        painter.setBrush(QBrush(color))
        painter.setPen(QPen(color.darker(120), 1))
        painter.drawRoundedRect(rect, 4, 4)
        
        # Text
        painter.setPen(Qt.white if color.lightness() < 150 else Qt.black)
        painter.setFont(QFont("Arial", 8, QFont.Bold))
        painter.drawText(rect, Qt.AlignCenter, text)


class ConnectionStrengthIndicator(QGraphicsItem):
    """
    Visual indicator of connection strength shown during weight editing.
    """
    
    def __init__(self, pos: QPointF, weight: float, parent=None):
        super().__init__(parent)
        self.weight = weight
        self.setPos(pos)
        self.setZValue(50)
    
    def boundingRect(self) -> QRectF:
        return QRectF(-60, -20, 120, 40)
    
    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        
        rect = QRectF(-55, -15, 110, 30)
        
        # Background
        painter.setBrush(QBrush(QColor(40, 40, 40, 230)))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(rect, 6, 6)
        
        # Weight bar background
        bar_rect = QRectF(-45, 2, 90, 8)
        painter.setBrush(QBrush(QColor(80, 80, 80)))
        painter.drawRoundedRect(bar_rect, 3, 3)
        
        # Weight bar fill
        bar_width = abs(self.weight) * 45
        if self.weight >= 0:
            fill_rect = QRectF(0, 2, bar_width, 8)
            color = QColor(50, 205, 50)
        else:
            fill_rect = QRectF(-bar_width, 2, bar_width, 8)
            color = QColor(220, 50, 50)
        
        painter.setBrush(QBrush(color))
        painter.drawRoundedRect(fill_rect, 3, 3)
        
        # Center line
        painter.setPen(QPen(QColor(150, 150, 150), 1))
        painter.drawLine(QPointF(0, 0), QPointF(0, 12))
        
        # Weight text
        painter.setPen(Qt.white)
        painter.setFont(QFont("Arial", 9, QFont.Bold))
        text = f"{self.weight:+.2f}"
        painter.drawText(QRectF(-50, -14, 100, 14), Qt.AlignCenter, text)


class NeuronHighlightRing(QGraphicsEllipseItem):
    """
    Animated highlight ring for neuron selection/hover states.
    """
    
    def __init__(self, center: QPointF, radius: float, 
                 color: QColor, parent=None):
        super().__init__(
            center.x() - radius - 5,
            center.y() - radius - 5,
            (radius + 5) * 2,
            (radius + 5) * 2,
            parent
        )
        self.center = center
        self.base_radius = radius
        self.highlight_color = color
        self.pulse_phase = 0.0
        
        self.setPen(Qt.NoPen)
        self.setBrush(Qt.NoBrush)
        self.setZValue(0)
    
    def advance_pulse(self):
        self.pulse_phase += 0.1
        if self.pulse_phase > math.pi * 2:
            self.pulse_phase = 0
        self.update()
    
    def paint(self, painter, option, widget):
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Pulsing glow
        pulse = math.sin(self.pulse_phase) * 0.3 + 0.7
        alpha = int(100 * pulse)
        
        glow_color = QColor(
            self.highlight_color.red(),
            self.highlight_color.green(),
            self.highlight_color.blue(),
            alpha
        )
        
        # Outer glow
        gradient = QRadialGradient(self.center, self.base_radius + 15)
        gradient.setColorAt(0.6, glow_color)
        gradient.setColorAt(1.0, QColor(glow_color.red(), glow_color.green(), 
                                        glow_color.blue(), 0))
        
        painter.setBrush(QBrush(gradient))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(self.center, self.base_radius + 15, self.base_radius + 15)
        
        # Ring
        ring_width = 2 + pulse
        painter.setPen(QPen(self.highlight_color, ring_width))
        painter.setBrush(Qt.NoBrush)
        painter.drawEllipse(self.center, self.base_radius + 3, self.base_radius + 3)


def get_weight_color(weight: float) -> QColor:
    """Get color for a connection weight."""
    if weight >= 0:
        # Green gradient for excitatory
        intensity = min(1.0, weight)
        return QColor(
            int(50 + intensity * 0),
            int(150 + intensity * 55),
            int(50 + intensity * 0)
        )
    else:
        # Red gradient for inhibitory
        intensity = min(1.0, abs(weight))
        return QColor(
            int(150 + intensity * 70),
            int(50 + intensity * 0),
            int(50 + intensity * 10)
        )


def format_neuron_name(name: str) -> str:
    """Format a neuron name for display."""
    return name.replace('_', ' ').title()
