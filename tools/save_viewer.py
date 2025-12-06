"""
Dosidicus Save File Viewer v2.0
A comprehensive GUI tool for viewing, analyzing, and converting save files
"""

import sys
import os
import json
import zipfile
import uuid
import base64
from datetime import datetime
from PyQt5 import QtCore, QtGui, QtWidgets

class NetworkRenderingMixin:
    """Mixin providing static network rendering methods"""
    
    @staticmethod
    def draw_connections_static(painter, neuron_positions, weights, neuron_states, 
                                excluded_neurons=None, scale=1.0, 
                                line_width=1.5, show_weights=False):
        """Static version of connection drawing without animations"""
        if excluded_neurons is None:
            excluded_neurons = set()
            
        # Pre-calculate scaled positions
        scaled_positions = {}
        for name, (x, y) in neuron_positions.items():
            if name not in excluded_neurons:
                scaled_positions[name] = (x * scale, y * scale)
        
        # Draw connections
        for (src, dst), weight in weights.items():
            if src not in scaled_positions or dst not in scaled_positions:
                continue
                
            x1, y1 = scaled_positions[src]
            x2, y2 = scaled_positions[dst]
            
            # Determine color and style based on weight
            if weight > 0:
                # Excitatory: Green
                color = QtGui.QColor(0, int(200 * min(weight, 1.0)), 0, 180)
                pen_style = QtCore.Qt.SolidLine
            else:
                # Inhibitory: Red
                color = QtGui.QColor(int(200 * min(abs(weight), 1.0)), 0, 0, 180)
                pen_style = QtCore.Qt.DashLine if abs(weight) < 0.3 else QtCore.Qt.SolidLine
            
            # Line thickness based on weight magnitude
            thickness = max(1.0, line_width * (1.0 + abs(weight) * 2.0))
            
            painter.setPen(QtGui.QPen(color, thickness, pen_style))
            painter.drawLine(QtCore.QLineF(x1, y1, x2, y2))
            
            # Draw weight labels if enabled
            if show_weights and abs(weight) > 0.1:
                midpoint = QtCore.QPointF((x1 + x2) / 2, (y1 + y2) / 2)
                font = painter.font()
                font.setPointSize(int(8 * scale))
                painter.setFont(font)
                
                text = f"{weight:.2f}"
                font_metrics = painter.fontMetrics()
                text_width = font_metrics.horizontalAdvance(text)
                
                painter.setBrush(QtGui.QBrush(QtGui.QColor(30, 30, 30, 200)))
                painter.setPen(QtCore.Qt.NoPen)
                rect = QtCore.QRectF(midpoint.x() - text_width/2 - 4, 
                                   midpoint.y() - 8, text_width + 8, 16)
                painter.drawRect(rect)
                
                painter.setPen(QtGui.QColor(220, 220, 220))
                painter.drawText(rect, QtCore.Qt.AlignCenter, text)
    
    @staticmethod
    def draw_neurons_static(painter, neuron_positions, neuron_states, 
                           visible_neurons=None, excluded_neurons=None,
                           scale=1.0, base_font_size=8):
        """Static neuron drawing with improved label sizing"""
        if visible_neurons is None:
            visible_neurons = set(neuron_positions.keys())
        if excluded_neurons is None:
            excluded_neurons = set()
            
        # Font for labels - smaller and more compact
        label_font = QtGui.QFont("Arial", int(base_font_size * scale))
        label_font.setBold(True)
        painter.setFont(label_font)
        font_metrics = painter.fontMetrics()
        
        for name, pos in neuron_positions.items():
            if name in excluded_neurons or name not in visible_neurons:
                continue
                
            x, y = pos[0] * scale, pos[1] * scale
            
            # Get neuron value for color
            value = neuron_states.get(name, 50)
            if isinstance(value, (int, float)):
                # Color based on activation (green->yellow->red)
                normalized = max(0, min(1, value / 100.0))
                if normalized > 0.7:
                    color = QtGui.QColor(76, 175, 80)  # Green
                elif normalized > 0.4:
                    color = QtGui.QColor(255, 193, 7)  # Yellow
                else:
                    color = QtGui.QColor(244, 67, 54)   # Red
            else:
                color = QtGui.QColor(150, 150, 150)    # Default for non-numeric
                
            # Draw neuron circle
            radius = 20 * scale
            painter.setBrush(QtGui.QBrush(color))
            painter.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0), max(1, int(2 * scale))))
            painter.drawEllipse(QtCore.QPointF(x, y), radius, radius)
            
            # Draw neuron name below - with DYNAMIC width calculation
            display_name = name.replace('_', ' ').title()
            text_width = font_metrics.horizontalAdvance(display_name)
            
            # WIDER text field to prevent cutoff
            padding = 12 * scale  # Increased padding
            rect_width = text_width + (padding * 2)
            rect_height = font_metrics.height() + 6  # Increased height
            
            text_rect = QtCore.QRectF(
                x - rect_width / 2,
                y + radius + 5 * scale,
                rect_width,
                rect_height
            )
            
            # Draw text background for better readability
            painter.setBrush(QtGui.QBrush(QtGui.QColor(26, 26, 26, 220)))
            painter.setPen(QtCore.Qt.NoPen)
            painter.drawRect(text_rect)
            
            # Draw text
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
            font = QtGui.QFont("Arial", int(10 * scale))
            font.setBold(True)
            painter.setFont(font)
            painter.setPen(QtGui.QColor(150, 150, 170))
            painter.drawText(QtCore.QPointF(20, rect_top + 20), name)


# =============================================================================
# GLOBAL SCALING SYSTEM
# =============================================================================

class ScaleManager:
    """Manages global UI scaling"""
    _scale = 1.5  # DEFAULT 150%
    _callbacks = []

    @classmethod
    def scale(cls):
        return cls._scale

    @classmethod
    def set_scale(cls, scale):
        cls._scale = scale
        for callback in cls._callbacks:
            try:
                callback(scale)
            except:
                pass

    @classmethod
    def register_callback(cls, callback):
        cls._callbacks.append(callback)

    @classmethod
    def font_size(cls, base_size):
        return int(base_size * cls._scale)

    @classmethod
    def size(cls, base_size):
        return int(base_size * cls._scale)


# =============================================================================
# COLLAPSIBLE SECTION WIDGET
# =============================================================================

class CollapsibleSection(QtWidgets.QWidget):
    """A collapsible section widget with header and content"""

    def __init__(self, title, parent=None, start_expanded=True):
        super().__init__(parent)
        self.is_expanded = start_expanded
        self.title = title

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self.header = QtWidgets.QPushButton()
        self.update_header()
        self.header.setStyleSheet(self.get_header_style())
        self.header.clicked.connect(self.toggle)
        layout.addWidget(self.header)

        self.content = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content)
        self.content_layout.setContentsMargins(12, 8, 12, 8)
        self.content.setStyleSheet("background-color: #1e1e1e;")
        self.content.setVisible(self.is_expanded)
        layout.addWidget(self.content)

    def get_header_style(self):
        s = ScaleManager.scale()
        return f"""
            QPushButton {{
                background-color: #2d5a7b;
                color: white;
                border: none;
                padding: {int(10 * s)}px {int(14 * s)}px;
                text-align: left;
                font-weight: bold;
                font-size: {int(14 * s)}px;
            }}
            QPushButton:hover {{
                background-color: #3d6a8b;
            }}
        """

    def update_header(self):
        arrow = "▼" if self.is_expanded else "▶"
        self.header.setText(f"{arrow}  {self.title}")

    def toggle(self):
        self.is_expanded = not self.is_expanded
        self.content.setVisible(self.is_expanded)
        self.update_header()

    def add_widget(self, widget):
        self.content_layout.addWidget(widget)


# =============================================================================
# KEY-VALUE ROW WIDGET
# =============================================================================

class KeyValueRow(QtWidgets.QWidget):
    """A row displaying a key-value pair with optional copy button"""

    def __init__(self, key, value, copy_button=False, indent=0, parent=None):
        super().__init__(parent)
        self.value_text = str(value)
        s = ScaleManager.scale()

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(indent, int(3 * s), 0, int(3 * s))

        self.key_label = QtWidgets.QLabel(f"{key}:")
        self.key_label.setStyleSheet(f"color: #7fbadc; font-weight: bold; min-width: {int(180 * s)}px; font-size: {int(13 * s)}px;")
        layout.addWidget(self.key_label)

        self.value_label = QtWidgets.QLabel(self.value_text)
        self.value_label.setStyleSheet(f"color: #e0e0e0; font-size: {int(13 * s)}px;")
        self.value_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        self.value_label.setWordWrap(True)
        layout.addWidget(self.value_label, 1)

        if copy_button:
            copy_btn = QtWidgets.QPushButton("📋 Copy")
            copy_btn.setFixedSize(int(70 * s), int(28 * s))
            copy_btn.setToolTip("Copy to clipboard")
            copy_btn.setStyleSheet(f"""
                QPushButton {{
                    background-color: #3d6a8b;
                    border: none;
                    border-radius: {int(4 * s)}px;
                    font-size: {int(11 * s)}px;
                    color: white;
                }}
                QPushButton:hover {{ background-color: #4d7a9b; }}
            """)
            copy_btn.clicked.connect(self.copy_to_clipboard)
            layout.addWidget(copy_btn)

    def copy_to_clipboard(self):
        clipboard = QtWidgets.QApplication.clipboard()
        clipboard.setText(self.value_text)
        s = ScaleManager.scale()
        self.value_label.setStyleSheet(f"color: #90EE90; font-size: {int(13 * s)}px;")
        QtCore.QTimer.singleShot(500, lambda: self.value_label.setStyleSheet(f"color: #e0e0e0; font-size: {int(13 * s)}px;"))


# =============================================================================
# NEURON VALUE WIDGET (with visual bar)
# =============================================================================

class NeuronValueWidget(QtWidgets.QWidget):
    """Widget showing a neuron value with a visual bar"""

    def __init__(self, name, value, parent=None):
        super().__init__(parent)
        s = ScaleManager.scale()
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, int(3 * s), 0, int(3 * s))

        display_name = name.replace('_', ' ').title()
        name_label = QtWidgets.QLabel(display_name)
        name_label.setStyleSheet(f"color: #b0b0b0; min-width: {int(140 * s)}px; font-size: {int(13 * s)}px;")
        layout.addWidget(name_label)

        if isinstance(value, (int, float)):
            bar_container = QtWidgets.QWidget()
            bar_container.setFixedHeight(int(20 * s))
            bar_container.setStyleSheet(f"background-color: #333; border-radius: {int(4 * s)}px;")
            bar_layout = QtWidgets.QHBoxLayout(bar_container)
            bar_layout.setContentsMargins(2, 2, 2, 2)

            bar = QtWidgets.QWidget()
            bar.setFixedHeight(int(16 * s))

            if value >= 70:
                color = "#4CAF50"
            elif value >= 40:
                color = "#FFC107"
            else:
                color = "#F44336"

            bar.setStyleSheet(f"background-color: {color}; border-radius: {int(3 * s)}px;")
            bar_width = int(min(100, max(0, value)) * s * 1.8)
            bar.setFixedWidth(bar_width)
            bar_layout.addWidget(bar)
            bar_layout.addStretch()

            layout.addWidget(bar_container, 1)

            value_label = QtWidgets.QLabel(f"{int(value)}")
            value_label.setStyleSheet(f"color: #e0e0e0; min-width: {int(50 * s)}px; font-size: {int(14 * s)}px; font-weight: bold;")
            value_label.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
            layout.addWidget(value_label)
        else:
            value_label = QtWidgets.QLabel(str(value))
            value_label.setStyleSheet(f"color: #e0e0e0; font-size: {int(13 * s)}px;")
            layout.addWidget(value_label, 1)


# =============================================================================
# DECORATION WIDGET
# =============================================================================

class DecorationWidget(QtWidgets.QWidget):
    """Widget displaying a decoration with thumbnail and details"""

    def __init__(self, decoration_data, index, parent=None):
        super().__init__(parent)
        s = ScaleManager.scale()
        self.setStyleSheet(f"background-color: #252525; border-radius: {int(6 * s)}px; margin: {int(2 * s)}px;")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(int(10 * s), int(8 * s), int(10 * s), int(8 * s))

        pixmap_data = decoration_data.get('pixmap_data', '')
        if pixmap_data:
            try:
                image_data = base64.b64decode(pixmap_data)
                pixmap = QtGui.QPixmap()
                pixmap.loadFromData(image_data)
                if not pixmap.isNull():
                    scaled = pixmap.scaled(int(48 * s), int(48 * s), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                    thumb_label = QtWidgets.QLabel()
                    thumb_label.setPixmap(scaled)
                    thumb_label.setFixedSize(int(52 * s), int(52 * s))
                    thumb_label.setStyleSheet(f"background-color: #1a1a1a; border-radius: {int(4 * s)}px; padding: {int(2 * s)}px;")
                    layout.addWidget(thumb_label)
            except:
                pass

        info_layout = QtWidgets.QVBoxLayout()
        info_layout.setSpacing(int(2 * s))

        filename = decoration_data.get('filename')
        if filename:
            name = os.path.splitext(os.path.basename(filename))[0]
        else:
            name = f"Decoration {index + 1}"

        name_label = QtWidgets.QLabel(f"<b>{name}</b>")
        name_label.setStyleSheet(f"color: #7fbadc; font-size: {int(13 * s)}px;")
        info_layout.addWidget(name_label)

        pos = decoration_data.get('pos', [0, 0])
        scale_val = decoration_data.get('scale', 1.0)

        details_label = QtWidgets.QLabel(f"Position: ({pos[0]:.0f}, {pos[1]:.0f}) | Scale: {scale_val:.2f}")
        details_label.setStyleSheet(f"color: #888; font-size: {int(11 * s)}px;")
        info_layout.addWidget(details_label)

        if filename:
            path_label = QtWidgets.QLabel(f"Path: {filename}")
            path_label.setStyleSheet(f"color: #666; font-size: {int(10 * s)}px;")
            info_layout.addWidget(path_label)

        layout.addLayout(info_layout, 1)


# =============================================================================
# MEMORY WIDGET
# =============================================================================

class MemoryWidget(QtWidgets.QWidget):
    """Widget displaying a single memory entry"""

    def __init__(self, memory_data, index, parent=None):
        super().__init__(parent)
        s = ScaleManager.scale()
        self.setStyleSheet(f"background-color: #252525; border-radius: {int(6 * s)}px; margin: {int(2 * s)}px; border-left: 3px solid #3d6a8b;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(int(12 * s), int(8 * s), int(10 * s), int(8 * s))
        layout.setSpacing(int(4 * s))

        header_layout = QtWidgets.QHBoxLayout()

        category = memory_data.get('category', 'unknown')
        key = memory_data.get('key', 'Unknown')

        cat_colors = {'behavior': '#9C27B0', 'environment': '#4CAF50', 'food': '#FF9800', 'interaction': '#2196F3', 'decorations': '#E91E63'}
        cat_color = cat_colors.get(category, '#666')

        cat_label = QtWidgets.QLabel(category.upper())
        cat_label.setStyleSheet(f"background-color: {cat_color}; color: white; padding: {int(2 * s)}px {int(8 * s)}px; border-radius: {int(3 * s)}px; font-size: {int(10 * s)}px; font-weight: bold;")
        header_layout.addWidget(cat_label)

        key_label = QtWidgets.QLabel(key.replace('_', ' ').title())
        key_label.setStyleSheet(f"color: #7fbadc; font-weight: bold; font-size: {int(13 * s)}px;")
        header_layout.addWidget(key_label)
        header_layout.addStretch()

        importance = memory_data.get('importance', 0)
        imp_label = QtWidgets.QLabel(f"★ {importance:.1f}")
        imp_label.setStyleSheet(f"color: #FFD700; font-size: {int(11 * s)}px;")
        header_layout.addWidget(imp_label)

        layout.addLayout(header_layout)

        value = memory_data.get('value', '')
        value_label = QtWidgets.QLabel(str(value))
        value_label.setStyleSheet(f"color: #e0e0e0; font-size: {int(12 * s)}px;")
        value_label.setWordWrap(True)
        layout.addWidget(value_label)

        timestamp = memory_data.get('timestamp', 0)
        if timestamp > 1000000000:
            try:
                dt = datetime.fromtimestamp(timestamp)
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = str(timestamp)
        else:
            time_str = "Unknown"

        access_count = memory_data.get('access_count', 0)
        meta_label = QtWidgets.QLabel(f"🕐 {time_str} | Accessed: {access_count}x")
        meta_label.setStyleSheet(f"color: #666; font-size: {int(10 * s)}px;")
        layout.addWidget(meta_label)


# =============================================================================
# NEUROGENESIS NEURON WIDGET
# =============================================================================

class NeurogenesisNeuronWidget(QtWidgets.QWidget):
    """Widget displaying detailed neurogenesis neuron info"""

    def __init__(self, name, neuron_data, parent=None):
        super().__init__(parent)
        s = ScaleManager.scale()
        self.setStyleSheet(f"background-color: #252525; border-radius: {int(6 * s)}px; margin: {int(2 * s)}px; border-left: 3px solid #4CAF50;")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(int(12 * s), int(10 * s), int(10 * s), int(10 * s))
        layout.setSpacing(int(6 * s))

        header_layout = QtWidgets.QHBoxLayout()

        display_name = name.replace('_', ' ').title()
        name_label = QtWidgets.QLabel(f"🧬 {display_name}")
        name_label.setStyleSheet(f"color: #4CAF50; font-weight: bold; font-size: {int(14 * s)}px;")
        header_layout.addWidget(name_label)
        header_layout.addStretch()

        neuron_type = neuron_data.get('neuron_type', 'unknown')
        type_colors = {'stress': '#F44336', 'novelty': '#2196F3', 'reward': '#FFD700', 'personality': '#9C27B0'}
        type_color = type_colors.get(neuron_type, '#666')

        type_label = QtWidgets.QLabel(neuron_type.upper())
        type_label.setStyleSheet(f"background-color: {type_color}; color: white; padding: {int(3 * s)}px {int(10 * s)}px; border-radius: {int(4 * s)}px; font-size: {int(11 * s)}px; font-weight: bold;")
        header_layout.addWidget(type_label)

        layout.addLayout(header_layout)

        stats_layout = QtWidgets.QGridLayout()
        stats_layout.setSpacing(int(8 * s))

        specialization = neuron_data.get('specialization', 'N/A')
        activation_count = neuron_data.get('activation_count', 0)
        utility_score = neuron_data.get('utility_score', 0)
        strength_mult = neuron_data.get('strength_multiplier', 1.0)

        stats = [
            ("Specialization", specialization.replace('_', ' ').title()),
            ("Activations", str(activation_count)),
            ("Utility Score", f"{utility_score:.3f}"),
            ("Strength Mult", f"{strength_mult:.2f}x"),
        ]

        for i, (label, value) in enumerate(stats):
            lbl = QtWidgets.QLabel(f"{label}:")
            lbl.setStyleSheet(f"color: #888; font-size: {int(11 * s)}px;")
            val = QtWidgets.QLabel(value)
            val.setStyleSheet(f"color: #e0e0e0; font-size: {int(11 * s)}px;")
            stats_layout.addWidget(lbl, i // 2, (i % 2) * 2)
            stats_layout.addWidget(val, i // 2, (i % 2) * 2 + 1)

        layout.addLayout(stats_layout)

        context = neuron_data.get('creation_context', {})
        last_activated = neuron_data.get('last_activated', 0)
        if last_activated > 1000000000:
            try:
                dt = datetime.fromtimestamp(last_activated)
                time_str = dt.strftime('%Y-%m-%d %H:%M:%S')
            except:
                time_str = "Unknown"
        else:
            time_str = "Unknown"

        ctx_label = QtWidgets.QLabel(f"Last activated: {time_str} | Trigger: {context.get('trigger_type', 'unknown')}")
        ctx_label.setStyleSheet(f"color: #666; font-size: {int(10 * s)}px;")
        layout.addWidget(ctx_label)


# =============================================================================
# SYNAPTIC WEIGHT WIDGET
# =============================================================================

class SynapticWeightWidget(QtWidgets.QWidget):
    """Widget displaying a synaptic weight connection"""

    def __init__(self, from_neuron, to_neuron, weight, parent=None):
        super().__init__(parent)
        s = ScaleManager.scale()

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(int(8 * s), int(2 * s), int(8 * s), int(2 * s))

        from_label = QtWidgets.QLabel(from_neuron.replace('_', ' ').title())
        from_label.setStyleSheet(f"color: #7fbadc; font-size: {int(12 * s)}px; min-width: {int(120 * s)}px;")
        layout.addWidget(from_label)

        color = "#4CAF50" if weight > 0 else "#F44336"

        arrow_label = QtWidgets.QLabel(" → ")
        arrow_label.setStyleSheet(f"color: {color}; font-size: {int(14 * s)}px; font-weight: bold;")
        layout.addWidget(arrow_label)

        to_label = QtWidgets.QLabel(to_neuron.replace('_', ' ').title())
        to_label.setStyleSheet(f"color: #7fbadc; font-size: {int(12 * s)}px; min-width: {int(120 * s)}px;")
        layout.addWidget(to_label)

        layout.addStretch()

        weight_label = QtWidgets.QLabel(f"{weight:+.3f}")
        weight_label.setStyleSheet(f"color: {color}; font-size: {int(12 * s)}px; font-weight: bold; min-width: {int(60 * s)}px;")
        weight_label.setAlignment(QtCore.Qt.AlignRight)
        layout.addWidget(weight_label)


# =============================================================================
# OVERVIEW TAB
# =============================================================================

class OverviewTab(QtWidgets.QScrollArea):
    """The overview tab showing key save file information"""

    def __init__(self, save_data, parent=None):
        super().__init__(parent)
        self.save_data = save_data
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background-color: #1a1a1a; }")
        self.build_ui()

    def build_ui(self):
        s = ScaleManager.scale()
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(int(14 * s))
        layout.setContentsMargins(int(20 * s), int(20 * s), int(20 * s), int(20 * s))

        save_data = self.save_data
        save_version = self.detect_version(save_data)

        # Header
        header = QtWidgets.QLabel("📋 Save File Overview")
        header.setStyleSheet(f"color: #ffffff; font-size: {int(22 * s)}px; font-weight: bold; padding-bottom: {int(10 * s)}px;")
        layout.addWidget(header)

        # Version Banner
        version_color = "#4CAF50" if save_version == "2.0" else "#FF9800"
        version_banner = QtWidgets.QLabel(f"  Save Format Version: {save_version}  ")
        version_banner.setStyleSheet(f"background-color: {version_color}; color: white; padding: {int(8 * s)}px {int(16 * s)}px; border-radius: {int(4 * s)}px; font-size: {int(14 * s)}px; font-weight: bold;")
        version_banner.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(version_banner)

        # Custom Brain Banner
        custom_brain_data = save_data.get('custom_brain', {})
        if custom_brain_data.get('is_custom_brain'):
            brain_name = custom_brain_data.get('brain_name', 'Custom Neural Network')
            brain_author = custom_brain_data.get('author', '')
            author_text = f" by {brain_author}" if brain_author else ""
            
            custom_banner = QtWidgets.QLabel(f"  🧬 CUSTOM BRAIN: {brain_name}{author_text}  ")
            custom_banner.setStyleSheet(f"background-color: #9C27B0; color: white; padding: {int(10 * s)}px {int(20 * s)}px; border-radius: {int(4 * s)}px; font-size: {int(16 * s)}px; font-weight: bold; border: 2px solid #E1BEE7;")
            custom_banner.setAlignment(QtCore.Qt.AlignCenter)
            layout.addWidget(custom_banner)
            
            # Add custom brain details section
            brain_section = CollapsibleSection("🧬 Custom Brain Details", start_expanded=True)
            brain_section.add_widget(KeyValueRow("Brain Name", brain_name))
            if brain_author:
                brain_section.add_widget(KeyValueRow("Author", brain_author))
            if custom_brain_data.get('version'):
                brain_section.add_widget(KeyValueRow("Version", custom_brain_data.get('version')))
            if custom_brain_data.get('description'):
                brain_section.add_widget(KeyValueRow("Description", custom_brain_data.get('description')))
            
            neuron_count = custom_brain_data.get('neuron_count', 0)
            connection_count = custom_brain_data.get('connection_count', 0)
            brain_section.add_widget(KeyValueRow("Neurons", neuron_count))
            brain_section.add_widget(KeyValueRow("Connections", connection_count))
            
            layout.addWidget(brain_section)

        # Basic Info Section
        basic_section = CollapsibleSection("🦑 Squid Information")

        squid_data = save_data.get('game_state', {}).get('squid', {})

        squid_name = squid_data.get('name')
        if squid_name:
            basic_section.add_widget(KeyValueRow("Name", squid_name))
        else:
            basic_section.add_widget(KeyValueRow("Name", "⚠️ Not saved (v1.0 format)"))

        personality = squid_data.get('personality', 'Unknown')
        personality_emojis = {'timid': '😰', 'adventurous': '🗺️', 'lazy': '😴', 'energetic': '⚡', 'introvert': '🤫', 'greedy': '🍕', 'stubborn': '😤'}
        emoji = personality_emojis.get(personality.lower(), '🦑')
        basic_section.add_widget(KeyValueRow("Personality", f"{emoji} {personality.title()}"))

        stats = save_data.get('statistics', {})
        age_seconds = stats.get('total_age_seconds', 0)
        age_str = self.format_age(age_seconds)
        basic_section.add_widget(KeyValueRow("Age", age_str if age_str != "0s" else "⚠️ Not tracked (v1.0 format)"))

        uuid_val = squid_data.get('uuid')
        if uuid_val:
            basic_section.add_widget(KeyValueRow("UUID", uuid_val, copy_button=True))
        else:
            basic_section.add_widget(KeyValueRow("UUID", "⚠️ Not present (v1.0 format)"))

        is_sick = squid_data.get('is_sick', False)
        health = squid_data.get('health', 100)
        health_str = f"{'🤒 Sick' if is_sick else '✅ Healthy'} ({health}%)"
        basic_section.add_widget(KeyValueRow("Health Status", health_str))

        x = squid_data.get('squid_x', 0)
        y = squid_data.get('squid_y', 0)

        layout.addWidget(basic_section)

        # Neuron Values Section
        neuron_section = CollapsibleSection("🧠 Core Neuron Values")

        neuron_keys = ['hunger', 'happiness', 'cleanliness', 'sleepiness', 'satisfaction', 'anxiety', 'curiosity', 'health']

        for key in neuron_keys:
            if key in squid_data:
                neuron_section.add_widget(NeuronValueWidget(key, squid_data[key]))

        layout.addWidget(neuron_section)

        # Memory Section
        memory_section = CollapsibleSection("💭 Memory System")

        short_term = save_data.get('ShortTerm', [])
        long_term = save_data.get('LongTerm', [])

        memory_section.add_widget(KeyValueRow("Short-term Memories", f"{len(short_term)} entries"))
        memory_section.add_widget(KeyValueRow("Long-term Memories", f"{len(long_term)} entries"))

        if short_term or long_term:
            all_memories = short_term + long_term
            categories = {}
            for mem in all_memories:
                cat = mem.get('category', 'unknown')
                categories[cat] = categories.get(cat, 0) + 1

            if categories:
                cat_label = QtWidgets.QLabel("Categories breakdown:")
                cat_label.setStyleSheet(f"color: #888; font-size: {int(11 * s)}px; margin-top: {int(8 * s)}px;")
                memory_section.add_widget(cat_label)

                for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
                    memory_section.add_widget(KeyValueRow(f"  • {cat.title()}", count, indent=int(12 * s)))

        layout.addWidget(memory_section)

        # Neurogenesis Section
        neuro_section = CollapsibleSection("🧬 Neurogenesis")

        brain_state = save_data.get('brain_state', {})
        enhanced = brain_state.get('enhanced_neurogenesis', {})
        functional_neurons = enhanced.get('functional_neurons', {})

        neuro_section.add_widget(KeyValueRow("Total Neurogenesis Neurons", len(functional_neurons)))
        neuro_section.add_widget(KeyValueRow("Novelty Neurons Created", enhanced.get('novelty_neuron_count', 0)))
        neuro_section.add_widget(KeyValueRow("Created This Session", enhanced.get('neurons_created_this_session', 0)))

        if functional_neurons:
            neurons_label = QtWidgets.QLabel("Active Neurogenesis Neurons:")
            neurons_label.setStyleSheet(f"color: #7fbadc; font-weight: bold; margin-top: {int(10 * s)}px; font-size: {int(13 * s)}px;")
            neuro_section.add_widget(neurons_label)

            for name, data in functional_neurons.items():
                neuro_section.add_widget(NeurogenesisNeuronWidget(name, data))
        else:
            no_neurons = QtWidgets.QLabel("No neurogenesis neurons created yet")
            no_neurons.setStyleSheet(f"color: #888; font-style: italic; font-size: {int(12 * s)}px;")
            neuro_section.add_widget(no_neurons)

        layout.addWidget(neuro_section)

        # Statistics Section (v2 only)
        if stats:
            stats_section = CollapsibleSection("📊 Statistics")

            stat_groups = {
                "Food & Consumption": ['cheese_eaten', 'sushi_eaten', 'poops_created', 'max_poops_cleaned'],
                "Interactions": ['startles_experienced', 'ink_clouds_created', 'times_colour_changed', 'rocks_thrown', 'plants_interacted'],
                "Health & Sleep": ['sickness_episodes', 'total_sleep_time'],
                "Neural Development": ['current_neurons', 'max_neurons_reached', 'novelty_neurons_created', 'stress_neurons_created', 'reward_neurons_created']
            }

            for group_name, keys in stat_groups.items():
                group_label = QtWidgets.QLabel(f"{group_name}:")
                group_label.setStyleSheet(f"color: #7fbadc; font-weight: bold; margin-top: {int(8 * s)}px; font-size: {int(12 * s)}px;")
                stats_section.add_widget(group_label)

                for key in keys:
                    if key in stats:
                        display_key = key.replace('_', ' ').title()
                        stats_section.add_widget(KeyValueRow(f"  {display_key}", stats[key], indent=int(12 * s)))

            layout.addWidget(stats_section)

        # REMOVED: Decorations Section
        # weights = brain_state.get('weights_list', [])
        # if weights:
        #     weights_section = CollapsibleSection(f"⚖️ Synaptic Weights ({len(weights)} connections)", start_expanded=False)
        #     sorted_weights = sorted(weights, key=lambda x: abs(x[2]) if len(x) > 2 else 0, reverse=True)
        #     excitatory = [w for w in sorted_weights if len(w) > 2 and w[2] > 0][:5]
        #     if excitatory:
        #         exc_label = QtWidgets.QLabel("Strongest Excitatory (+):")
        #         exc_label.setStyleSheet(f"color: #4CAF50; font-weight: bold; font-size: {int(12 * s)}px;")
        #         weights_section.add_widget(exc_label)
        #         for w in excitatory:
        #             weights_section.add_widget(SynapticWeightWidget(w[0], w[1], w[2]))
        #     inhibitory = [w for w in sorted_weights if len(w) > 2 and w[2] < 0][:5]
        #     if inhibitory:
        #         inh_label = QtWidgets.QLabel("Strongest Inhibitory (-):")
        #         inh_label.setStyleSheet(f"color: #F44336; font-weight: bold; margin-top: {int(8 * s)}px; font-size: {int(12 * s)}px;")
        #         weights_section.add_widget(inh_label)
        #         for w in inhibitory:
        #             weights_section.add_widget(SynapticWeightWidget(w[0], w[1], w[2]))
        #     layout.add_widget(weights_section)

        # File Info Section
        file_section = CollapsibleSection("📁 Save File Contents", start_expanded=False)

        files_in_save = list(save_data.get('_files', {}).keys())
        file_section.add_widget(KeyValueRow("Files in Archive", len(files_in_save)))

        for fname in sorted(files_in_save):
            size_indicator = "📋" if fname.endswith('.json') else "📝" if fname.endswith('.txt') else "📄"
            file_section.add_widget(KeyValueRow(f"  {size_indicator}", fname, indent=int(12 * s)))

        layout.addWidget(file_section)

        layout.addStretch()
        self.setWidget(container)

    def detect_version(self, save_data):
        files = save_data.get('_files', {})
        squid_data = save_data.get('game_state', {}).get('squid', {})

        has_uuid_file = 'uuid.txt' in files
        has_statistics = 'statistics.json' in files
        has_uuid_field = 'uuid' in squid_data

        if has_uuid_file or has_statistics or has_uuid_field:
            return "2.0"
        return "1.0"

    def format_age(self, seconds):
        if seconds == 0:
            return "0s"

        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0:
            parts.append(f"{minutes}m")
        if secs > 0 or not parts:
            parts.append(f"{secs}s")

        return " ".join(parts)


# =============================================================================
# JSON TREE WIDGET
# =============================================================================

class JsonTreeWidget(QtWidgets.QTreeWidget):
    """Tree widget for displaying JSON data"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setHeaderLabels(["Key", "Value", "Type"])
        self.setAlternatingRowColors(True)
        self.update_style()

    def update_style(self):
        s = ScaleManager.scale()
        self.setStyleSheet(f"""
            QTreeWidget {{
                background-color: #1e1e1e;
                color: #e0e0e0;
                border: none;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: {int(12 * s)}px;
            }}
            QTreeWidget::item {{ padding: {int(5 * s)}px; }}
            QTreeWidget::item:alternate {{ background-color: #252525; }}
            QTreeWidget::item:selected {{ background-color: #2d5a7b; }}
            QHeaderView::section {{
                background-color: #2d2d2d;
                color: #b0b0b0;
                padding: {int(8 * s)}px;
                border: none;
                font-weight: bold;
                font-size: {int(12 * s)}px;
            }}
        """)
        self.setColumnWidth(0, int(280 * s))
        self.setColumnWidth(1, int(400 * s))

    def populate(self, data, raw_mode=False):
        self.clear()
        self._add_items(data, self.invisibleRootItem(), raw_mode)
        self.expandToDepth(0)

    def _add_items(self, data, parent, raw_mode, key_name=""):
        if isinstance(data, dict):
            for key, value in data.items():
                item = QtWidgets.QTreeWidgetItem(parent)
                item.setText(0, str(key))

                if isinstance(value, (dict, list)):
                    count = len(value)
                    item.setText(1, f"[{count} items]" if isinstance(value, list) else f"{{{count} keys}}")
                    item.setText(2, "array" if isinstance(value, list) else "object")
                    item.setForeground(2, QtGui.QColor("#888"))
                    self._add_items(value, item, raw_mode, key)
                else:
                    display_value = self._format_value(key, value, raw_mode)
                    item.setText(1, display_value)
                    item.setText(2, type(value).__name__)
                    item.setForeground(2, QtGui.QColor("#888"))

                    if isinstance(value, bool):
                        item.setForeground(1, QtGui.QColor("#569CD6"))
                    elif isinstance(value, (int, float)):
                        item.setForeground(1, QtGui.QColor("#B5CEA8"))
                    elif value is None:
                        item.setForeground(1, QtGui.QColor("#808080"))
                    else:
                        item.setForeground(1, QtGui.QColor("#CE9178"))

        elif isinstance(data, list):
            for i, value in enumerate(data):
                item = QtWidgets.QTreeWidgetItem(parent)
                item.setText(0, f"[{i}]")

                if isinstance(value, (dict, list)):
                    count = len(value)
                    item.setText(1, f"[{count} items]" if isinstance(value, list) else f"{{{count} keys}}")
                    item.setText(2, "array" if isinstance(value, list) else "object")
                    item.setForeground(2, QtGui.QColor("#888"))
                    self._add_items(value, item, raw_mode)
                else:
                    item.setText(1, str(value))
                    item.setText(2, type(value).__name__)
                    item.setForeground(2, QtGui.QColor("#888"))

    def _format_value(self, key, value, raw_mode):
        if raw_mode:
            return str(value)

        key_lower = key.lower()

        if 'time' in key_lower or 'timestamp' in key_lower:
            if isinstance(value, (int, float)) and value > 1000000000:
                try:
                    dt = datetime.fromtimestamp(value)
                    return dt.strftime("%Y-%m-%d %H:%M:%S")
                except:
                    pass

        if isinstance(value, float):
            if key_lower in ['hunger', 'happiness', 'cleanliness', 'sleepiness', 'satisfaction', 'anxiety', 'curiosity', 'health']:
                return f"{value:.1f}%"
            elif abs(value) < 0.0001:
                return "0"
            elif abs(value - round(value)) < 0.0001:
                return str(int(round(value)))
            else:
                return f"{value:.4f}"

        if isinstance(value, bool):
            return "Yes ✓" if value else "No ✗"

        return str(value)


# =============================================================================
# JSON TAB
# =============================================================================

class JsonTab(QtWidgets.QWidget):
    def __init__(self, filename, data, parent=None):
        super().__init__(parent)
        self.data = data
        self.filename = filename

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.tree = JsonTreeWidget()
        self.tree.populate(data, raw_mode=False)
        layout.addWidget(self.tree)

    def set_raw_mode(self, raw):
        self.tree.populate(self.data, raw_mode=raw)


# =============================================================================
# HUMAN READABLE TAB
# =============================================================================

class HumanReadableTab(QtWidgets.QScrollArea):
    def __init__(self, filename, data, parent=None):
        super().__init__(parent)
        self.filename = filename
        self.data = data
        self.setWidgetResizable(True)
        self.setStyleSheet("QScrollArea { border: none; background-color: #1a1a1a; }")
        self.build_content()

    def build_content(self):
        s = ScaleManager.scale()
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setSpacing(int(12 * s))
        layout.setContentsMargins(int(16 * s), int(16 * s), int(16 * s), int(16 * s))

        if self.filename == 'game_state.json':
            self.build_game_state(self.data, layout)
        elif self.filename == 'brain_state.json':
            self.build_brain_state(self.data, layout)
        elif self.filename == 'statistics.json':
            self.build_statistics(self.data, layout)
        elif self.filename == 'ShortTerm.json':
            self.build_memories(self.data, layout, "Short-term")
        elif self.filename == 'LongTerm.json':
            self.build_memories(self.data, layout, "Long-term")
        elif self.filename == 'achievements.json':
            self.build_achievements(self.data, layout)

        layout.addStretch()
        self.setWidget(container)

    def build_game_state(self, data, layout):
        s = ScaleManager.scale()
        squid_data = data.get('squid', {})
        if squid_data:
            section = CollapsibleSection("🦑 Squid State")
            if 'name' in squid_data:
                section.add_widget(KeyValueRow("Name", squid_data['name'] or "Unnamed"))
            for key in ['hunger', 'happiness', 'cleanliness', 'sleepiness', 'satisfaction', 'anxiety', 'curiosity', 'health']:
                if key in squid_data:
                    section.add_widget(NeuronValueWidget(key, squid_data[key]))
            if 'is_sick' in squid_data:
                section.add_widget(KeyValueRow("Is Sick", "🤒 Yes" if squid_data['is_sick'] else "✅ No"))
            if 'personality' in squid_data:
                section.add_widget(KeyValueRow("Personality", squid_data['personality'].title()))
            if 'uuid' in squid_data:
                section.add_widget(KeyValueRow("UUID", squid_data['uuid'], copy_button=True))
            layout.addWidget(section)

        logic_data = data.get('tamagotchi_logic', {})
        if logic_data:
            section = CollapsibleSection("⚙️ Game Logic State")
            section.add_widget(KeyValueRow("Points/Score", f"{logic_data.get('points', 0):,}"))
            layout.addWidget(section)

        decorations = data.get('decorations', [])
        if decorations:
            section = CollapsibleSection(f"🎨 Decorations ({len(decorations)})")
            for i, dec in enumerate(decorations):
                section.add_widget(DecorationWidget(dec, i))
            layout.addWidget(section)

    def build_brain_state(self, data, layout):
        s = ScaleManager.scale()
        states = data.get('neuron_states', {})
        if states:
            section = CollapsibleSection("🧠 Neuron States")
            for key, value in states.items():
                if isinstance(value, bool):
                    section.add_widget(KeyValueRow(key.replace('_', ' ').title(), "🟢 Active" if value else "⚫ Inactive"))
                elif isinstance(value, (int, float)):
                    section.add_widget(NeuronValueWidget(key, value))
            layout.addWidget(section)

        enhanced = data.get('enhanced_neurogenesis', {})
        if enhanced:
            section = CollapsibleSection("🧬 Enhanced Neurogenesis")
            fn = enhanced.get('functional_neurons', {})
            section.add_widget(KeyValueRow("Functional Neurons", len(fn)))
            if fn:
                for name, neuron_data in fn.items():
                    section.add_widget(NeurogenesisNeuronWidget(name, neuron_data))
            layout.addWidget(section)

        weights = data.get('weights_list', [])
        if weights:
            section = CollapsibleSection(f"⚖️ Synaptic Weights ({len(weights)})")
            sorted_weights = sorted(weights, key=lambda x: abs(x[2]) if len(x) > 2 else 0, reverse=True)[:20]
            for w in sorted_weights:
                if len(w) >= 3:
                    section.add_widget(SynapticWeightWidget(w[0], w[1], w[2]))
            layout.addWidget(section)

    def build_statistics(self, data, layout):
        section = CollapsibleSection("📊 Complete Statistics")
        for key, value in data.items():
            display_key = key.replace('_', ' ').title()
            section.add_widget(KeyValueRow(display_key, value))
        layout.addWidget(section)

    def build_memories(self, data, layout, memory_type):
        s = ScaleManager.scale()
        if not data:
            label = QtWidgets.QLabel(f"No {memory_type.lower()} memories stored.")
            label.setStyleSheet(f"color: #888; font-style: italic; font-size: {int(14 * s)}px;")
            layout.addWidget(label)
            return

        section = CollapsibleSection(f"💭 {memory_type} Memories ({len(data)} entries)")
        for i, memory in enumerate(data[:100]):
            section.add_widget(MemoryWidget(memory, i))
        if len(data) > 100:
            more = QtWidgets.QLabel(f"... and {len(data) - 100} more")
            more.setStyleSheet(f"color: #888; font-style: italic; font-size: {int(11 * s)}px;")
            section.add_widget(more)
        layout.addWidget(section)

    def build_achievements(self, data, layout):
        s = ScaleManager.scale()
        section = CollapsibleSection("🏆 Achievements")
        unlocked = data.get('unlocked', [])
        progress = data.get('progress', {})
        section.add_widget(KeyValueRow("Total Unlocked", len(unlocked)))
        if unlocked:
            for ach in unlocked:
                label = QtWidgets.QLabel(f"  🏆 {ach.replace('_', ' ').title()}")
                label.setStyleSheet(f"color: #e0e0e0; font-size: {int(12 * s)}px;")
                section.add_widget(label)
        if progress:
            excluded_keys = {
                'fed_10_times',
                'fed_50_times',
                'fed_100_times',
                'fed_500_times',
                'cleaned_25_times'
            }
            for key, value in progress.items():
                if key.lower() not in excluded_keys:
                    section.add_widget(KeyValueRow(key.replace('_', ' ').title(), value))


# =============================================================================
# CONVERSION DIALOG
# =============================================================================

class ConversionDialog(QtWidgets.QDialog):
    def __init__(self, save_data, parent=None):
        super().__init__(parent)
        self.save_data = save_data
        self.converted_data = None

        s = ScaleManager.scale()
        self.setWindowTitle("Convert Save File (v1.0 → v2.0)")
        self.setMinimumSize(int(600 * s), int(500 * s))
        self.setStyleSheet("background-color: #1a1a1a; color: #e0e0e0;")
        self.setup_ui()

    def setup_ui(self):
        s = ScaleManager.scale()
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(int(16 * s))
        layout.setContentsMargins(int(20 * s), int(20 * s), int(20 * s), int(20 * s))

        header = QtWidgets.QLabel("🔄 Save File Conversion")
        header.setStyleSheet(f"color: #ffffff; font-size: {int(20 * s)}px; font-weight: bold;")
        layout.addWidget(header)

        info = QtWidgets.QLabel("This will convert your v1.0 save file to v2.0 format.\n\nThe following changes will be made:")
        info.setStyleSheet(f"color: #b0b0b0; font-size: {int(13 * s)}px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        changes_widget = QtWidgets.QWidget()
        changes_widget.setStyleSheet(f"background-color: #252525; border-radius: {int(6 * s)}px; padding: {int(12 * s)}px;")
        changes_layout = QtWidgets.QVBoxLayout(changes_widget)

        changes = [
            ("✅", "Generate unique UUID for squid"),
            ("✅", "Create uuid.txt file"),
            ("✅", "Create statistics.json with default values"),
            ("✅", "Add enhanced_neurogenesis structure to brain_state"),
            ("✅", "Create achievements.json with empty progress"),
            ("⚠️", "Squid name will need to be set manually after loading"),
        ]

        for icon, text in changes:
            row = QtWidgets.QLabel(f"{icon}  {text}")
            row.setStyleSheet(f"color: #e0e0e0; font-size: {int(12 * s)}px; padding: {int(4 * s)}px;")
            changes_layout.addWidget(row)

        layout.addWidget(changes_widget)

        options_label = QtWidgets.QLabel("Options:")
        options_label.setStyleSheet(f"color: #7fbadc; font-weight: bold; font-size: {int(13 * s)}px;")
        layout.addWidget(options_label)

        name_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel("Squid Name (optional):")
        name_label.setStyleSheet(f"color: #b0b0b0; font-size: {int(12 * s)}px;")
        name_layout.addWidget(name_label)

        self.name_input = QtWidgets.QLineEdit()
        self.name_input.setPlaceholderText("Leave empty to set later")
        self.name_input.setStyleSheet(f"QLineEdit {{ background-color: #333; border: 1px solid #555; border-radius: {int(4 * s)}px; padding: {int(8 * s)}px; color: #e0e0e0; font-size: {int(12 * s)}px; }}")
        name_layout.addWidget(self.name_input)
        layout.addLayout(name_layout)

        layout.addStretch()

        btn_layout = QtWidgets.QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.setStyleSheet(f"QPushButton {{ background-color: #555; color: white; border: none; padding: {int(10 * s)}px {int(24 * s)}px; border-radius: {int(4 * s)}px; font-size: {int(13 * s)}px; }} QPushButton:hover {{ background-color: #666; }}")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        convert_btn = QtWidgets.QPushButton("🔄 Convert & Save")
        convert_btn.setStyleSheet(f"QPushButton {{ background-color: #4CAF50; color: white; border: none; padding: {int(10 * s)}px {int(24 * s)}px; border-radius: {int(4 * s)}px; font-size: {int(13 * s)}px; font-weight: bold; }} QPushButton:hover {{ background-color: #5CBF60; }}")
        convert_btn.clicked.connect(self.convert_and_save)
        btn_layout.addWidget(convert_btn)

        layout.addLayout(btn_layout)

    def convert_and_save(self):
        try:
            new_uuid = str(uuid.uuid4())
            squid_name = self.name_input.text().strip() or None
            self.converted_data = self.perform_conversion(new_uuid, squid_name)

            file_path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Converted File", "save_data.zip", "Save Files (*.zip)")

            if file_path:
                self.save_converted(file_path)
                QtWidgets.QMessageBox.information(self, "Success", f"Save file converted successfully!\n\nNew UUID: {new_uuid}\n\nSaved to: {file_path}")
                self.accept()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Conversion failed:\n{str(e)}")

    def perform_conversion(self, new_uuid, squid_name):
        converted = {}

        game_state = self.save_data.get('game_state', {}).copy()
        if 'squid' in game_state:
            game_state['squid'] = game_state['squid'].copy()
            game_state['squid']['uuid'] = new_uuid
            if squid_name:
                game_state['squid']['name'] = squid_name
        converted['game_state'] = game_state

        brain_state = self.save_data.get('brain_state', {}).copy()
        if 'enhanced_neurogenesis' not in brain_state:
            brain_state['enhanced_neurogenesis'] = {
                'functional_neurons': {},
                'experience_buffer': [],
                'novelty_neuron_count': 0,
                'neurons_created_this_session': 0,
                'last_creation_by_type': {},
                'awarded_neurons': []
            }
        if 'functional_neurons' not in brain_state:
            brain_state['functional_neurons'] = {}
        converted['brain_state'] = brain_state

        converted['statistics'] = {
            'total_age_seconds': 0,
            'squid_age_minutes': 0,
            'distance_swam': 0,
            'cheese_eaten': 0,
            'sushi_eaten': 0,
            'poops_created': 0,
            'max_poops_cleaned': 0,
            'startles_experienced': 0,
            'ink_clouds_created': 0,
            'times_colour_changed': 0,
            'rocks_thrown': 0,
            'plants_interacted': 0,
            'total_sleep_time': 0,
            'sickness_episodes': 0,
            'novelty_neurons_created': 0,
            'stress_neurons_created': 0,
            'reward_neurons_created': 0,
            'max_neurons_reached': 0,
            'current_neurons': 7
        }

        converted['ShortTerm'] = self.save_data.get('ShortTerm', [])
        converted['LongTerm'] = self.save_data.get('LongTerm', [])

        converted['achievements'] = {'unlocked': [], 'progress': {}}
        converted['_new_uuid'] = new_uuid

        return converted

    def save_converted(self, file_path):
        with zipfile.ZipFile(file_path, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('game_state.json', json.dumps(self.converted_data['game_state'], indent=4))
            zf.writestr('brain_state.json', json.dumps(self.converted_data['brain_state'], indent=4))
            zf.writestr('statistics.json', json.dumps(self.converted_data['statistics'], indent=4))
            zf.writestr('ShortTerm.json', json.dumps(self.converted_data['ShortTerm'], indent=4))
            zf.writestr('LongTerm.json', json.dumps(self.converted_data['LongTerm'], indent=4))
            zf.writestr('achievements.json', json.dumps(self.converted_data['achievements'], indent=4))
            zf.writestr('uuid.txt', f"SquidSignature    {self.converted_data['_new_uuid']}")


# =============================================================================
# MAIN WINDOW
# =============================================================================

# =============================================================================
# NETWORK VISUALIZATION TAB
# =============================================================================

# In save_viewer.py, update the NetworkVisualizationTab class

class NetworkVisualizationTab(QtWidgets.QWidget):
    """Tab for visualizing the neural network from brain_state"""
    
    def __init__(self, save_data, parent=None):
        super().__init__(parent)
        self.save_data = save_data
        self.build_ui()
    
    def build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        
        # Check if we have brain data
        brain_state = self.save_data.get('brain_state', {})
        custom_brain = self.save_data.get('custom_brain', {})
        
        if not brain_state:
            # No brain data available
            empty_widget = QtWidgets.QWidget()
            empty_layout = QtWidgets.QVBoxLayout(empty_widget)
            empty_layout.setAlignment(QtCore.Qt.AlignCenter)
            
            icon = QtWidgets.QLabel("🧠")
            icon.setStyleSheet("font-size: 64px;")
            icon.setAlignment(QtCore.Qt.AlignCenter)
            empty_layout.addWidget(icon)
            
            label = QtWidgets.QLabel("No brain state data in this save file")
            label.setStyleSheet("color: #888; font-size: 18px;")
            label.setAlignment(QtCore.Qt.AlignCenter)
            empty_layout.addWidget(label)
            
            layout.addWidget(empty_widget)
            return
        
        # Create canvas for visualization with IMPROVED data passing
        self.canvas = NetworkCanvas(brain_state, custom_brain)
        layout.addWidget(self.canvas)
        
        # Add control panel
        controls = QtWidgets.QHBoxLayout()
        
        # Show/hide weight labels
        self.show_weights_cb = QtWidgets.QCheckBox("Show Weight Values")
        self.show_weights_cb.setChecked(True)
        self.show_weights_cb.stateChanged.connect(self.toggle_weights)
        controls.addWidget(self.show_weights_cb)
        
        controls.addStretch()
        layout.addLayout(controls)
    
    def toggle_weights(self, state):
        self.canvas.show_weights = (state == QtCore.Qt.Checked)
        self.canvas.update()


class NetworkCanvas(QtWidgets.QWidget, NetworkRenderingMixin):
    """Enhanced canvas using extracted rendering logic from BrainWidget"""
    
    def __init__(self, brain_state, custom_brain, parent=None):
        super().__init__(parent)
        self.setMinimumSize(800, 600)
        self.setStyleSheet("background-color: #1a1a1a;")
        
        # CRITICAL FIX: Load neuron positions
        self.neuron_positions = brain_state.get('neuron_positions', {})
        if not self.neuron_positions:
            # Fallback: try to reconstruct from state keys
            self.neuron_positions = {k: (100 + i*120, 100) for i, k in enumerate(brain_state.get('state', {}).keys()) if k not in {'is_sick', 'is_eating'}}
        
        # CRITICAL FIX: Convert weights_list to weights dict
        # The save file stores weights as a list: [['n1', 'n2', 0.5], ...]
        # BrainWidget uses a dict: {('n1', 'n2'): 0.5, ...}
        weights_list = brain_state.get('weights_list', [])
        self.weights = {}
        for item in weights_list:
            if isinstance(item, list) and len(item) == 3:
                src, dst, weight = item
                # Ensure the neurons exist in positions before adding weight
                if src in self.neuron_positions and dst in self.neuron_positions:
                    self.weights[(src, dst)] = float(weight)
        
        # Load neuron states
        self.state = brain_state.get('state', {})
        
        # Load layer structure from custom brain if available
        self.layers = []
        if custom_brain and isinstance(custom_brain, dict):
            self.layers = custom_brain.get('layer_structure', [])
        
        # State tracking for performance
        self._cached_scale = 1.0
        self.show_weights = True  # Toggleable in UI if desired
        
    def paintEvent(self, event):
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Fill background
        bg_color = QtGui.QColor(26, 26, 26)
        painter.fillRect(self.rect(), bg_color)
        
        # Calculate scale factor (matching brain_widget coordinate system)
        indicator_space = 60  # Space for status indicators (not used but keeps coords consistent)
        base_width_logical = 1024
        base_height_logical = 768 - indicator_space
        
        scale_x = self.width() / base_width_logical
        drawable_height = self.height() - indicator_space
        scale_y = drawable_height / base_height_logical if drawable_height > 0 else 1.0
        
        scale = max(0.1, min(scale_x, scale_y))
        self._cached_scale = scale
        
        # Transform coordinate system to match brain_widget's logical coords
        painter.translate(0, indicator_space)
        painter.scale(scale, scale)
        
        # Draw layer backgrounds (if custom brain has layer structure)
        self.draw_layers_static(painter, self.layers, 1.0)
        
        # Draw connections FIRST (so they appear behind neurons)
        self.draw_connections_static(
            painter, self.neuron_positions, self.weights, self.state,
            excluded_neurons={'is_sick', 'is_eating', 'is_sleeping', 
                            'pursuing_food', 'direction'},
            scale=1.0, line_width=2.0, show_weights=self.show_weights
        )
        
        # Draw neurons on top
        self.draw_neurons_static(
            painter, self.neuron_positions, self.state,
            visible_neurons=set(self.neuron_positions.keys()),
            excluded_neurons={'is_sick', 'is_eating', 'is_sleeping', 
                            'pursuing_food', 'direction'},
            scale=1.0, 
            base_font_size=7  # SMALLER font size for better fit
        )
        
        # Draw info panel in widget coordinates
        self.draw_info_panel(painter)
        
        painter.restore()
    
    def draw_info_panel(self, painter):
        """Draw network statistics in the corner"""
        painter.save()
        painter.resetTransform()  # Back to widget coordinates
        
        s = self._cached_scale
        stats_text = f"Neurons: {len(self.neuron_positions)} | Connections: {len(self.weights)}"
        
        painter.setPen(QtGui.QColor(180, 180, 180))
        font = QtGui.QFont("Arial", int(9 * s))
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(10, 20, stats_text)
        
        # Draw legend
        legend_y = 40
        painter.setFont(QtGui.QFont("Arial", int(8 * s)))
        
        # Green line + label
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 200, 0), 3))
        painter.drawLine(10, legend_y, 30, legend_y)
        painter.setPen(QtGui.QColor(180, 180, 180))
        painter.drawText(35, legend_y + 5, "Excitatory (+)")
        
        # Red line + label
        painter.setPen(QtGui.QPen(QtGui.QColor(200, 0, 0), 3))
        painter.drawLine(10, legend_y + 20, 30, legend_y + 20)
        painter.setPen(QtGui.QColor(180, 180, 180))
        painter.drawText(35, legend_y + 25, "Inhibitory (-)")
        
        painter.restore()


# =============================================================================
# SAVE VIEWER WINDOW
# =============================================================================

class SaveViewerWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dosidicus Save Viewer v2.0")
        self.setMinimumSize(1000, 750)
        self.save_data = None
        self.json_tabs = {}
        self.current_file_path = None

        self.setup_ui()
        self.apply_style()

    def setup_ui(self):
        s = ScaleManager.scale()
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)

        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # Toolbar
        toolbar = QtWidgets.QWidget()
        toolbar.setFixedHeight(int(60 * s))
        toolbar.setStyleSheet("background-color: #2d2d2d; border-bottom: 1px solid #444;")
        toolbar_layout = QtWidgets.QHBoxLayout(toolbar)
        toolbar_layout.setContentsMargins(int(16 * s), int(10 * s), int(16 * s), int(10 * s))

        self.open_btn = QtWidgets.QPushButton("📂 Open Save File")
        self.open_btn.setStyleSheet(f"QPushButton {{ background-color: #3d6a8b; color: white; border: none; padding: {int(10 * s)}px {int(20 * s)}px; border-radius: {int(5 * s)}px; font-weight: bold; font-size: {int(13 * s)}px; }} QPushButton:hover {{ background-color: #4d7a9b; }}")
        self.open_btn.clicked.connect(self.open_file)
        toolbar_layout.addWidget(self.open_btn)

        self.convert_btn = QtWidgets.QPushButton("🔄 Convert v1→v2")
        self.convert_btn.setEnabled(False)
        self.convert_btn.setStyleSheet(f"QPushButton {{ background-color: #FF9800; color: white; border: none; padding: {int(10 * s)}px {int(20 * s)}px; border-radius: {int(5 * s)}px; font-weight: bold; font-size: {int(13 * s)}px; }} QPushButton:hover {{ background-color: #FFB74D; }} QPushButton:disabled {{ background-color: #555; color: #888; }}")
        self.convert_btn.clicked.connect(self.show_convert_dialog)
        toolbar_layout.addWidget(self.convert_btn)

        self.file_label = QtWidgets.QLabel("No file loaded")
        self.file_label.setStyleSheet(f"color: #888; margin-left: {int(16 * s)}px; font-size: {int(13 * s)}px;")
        toolbar_layout.addWidget(self.file_label)

        toolbar_layout.addStretch()

        # REMOVED: scale_label, scale_slider, scale_value_label

        sep = QtWidgets.QFrame()
        sep.setFrameShape(QtWidgets.QFrame.VLine)
        sep.setStyleSheet("color: #444;")
        toolbar_layout.addWidget(sep)

        self.raw_checkbox = QtWidgets.QCheckBox("Show Raw JSON")
        self.raw_checkbox.setStyleSheet(f"QCheckBox {{ color: #b0b0b0; font-size: {int(12 * s)}px; }} QCheckBox::indicator {{ width: {int(18 * s)}px; height: {int(18 * s)}px; }} QCheckBox::indicator:unchecked {{ background-color: #333; border: 1px solid #555; border-radius: {int(3 * s)}px; }} QCheckBox::indicator:checked {{ background-color: #3d6a8b; border: 1px solid #3d6a8b; border-radius: {int(3 * s)}px; }}")
        self.raw_checkbox.toggled.connect(self.toggle_raw_mode)
        toolbar_layout.addWidget(self.raw_checkbox)

        main_layout.addWidget(toolbar)

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setStyleSheet(f"QTabWidget::pane {{ border: none; background-color: #1a1a1a; }} QTabBar::tab {{ background-color: #2d2d2d; color: #b0b0b0; padding: {int(14 * s)}px {int(28 * s)}px; border: none; border-bottom: 2px solid transparent; font-size: 18px; }} QTabBar::tab:selected {{ background-color: #1a1a1a; color: #ffffff; border-bottom: 2px solid #3d6a8b; }} QTabBar::tab:hover {{ background-color: #353535; }}")
        main_layout.addWidget(self.tabs)

        welcome = QtWidgets.QWidget()
        welcome_layout = QtWidgets.QVBoxLayout(welcome)
        welcome_layout.setAlignment(QtCore.Qt.AlignCenter)

        welcome_icon = QtWidgets.QLabel("🦑")
        welcome_icon.setStyleSheet(f"font-size: {int(64 * s)}px;")
        welcome_icon.setAlignment(QtCore.Qt.AlignCenter)
        welcome_layout.addWidget(welcome_icon)

        welcome_text = QtWidgets.QLabel("Dosidicus Save Viewer")
        welcome_text.setStyleSheet(f"color: #e0e0e0; font-size: {int(24 * s)}px; font-weight: bold;")
        welcome_text.setAlignment(QtCore.Qt.AlignCenter)
        welcome_layout.addWidget(welcome_text)

        welcome_sub = QtWidgets.QLabel("Open a save file (.zip) to view its contents")
        welcome_sub.setStyleSheet(f"color: #666; font-size: {int(14 * s)}px;")
        welcome_sub.setAlignment(QtCore.Qt.AlignCenter)
        welcome_layout.addWidget(welcome_sub)

        self.tabs.addTab(welcome, "🏠 Welcome")

    def apply_style(self):
        s = ScaleManager.scale()
        self.setStyleSheet(f"QMainWindow {{ background-color: #1a1a1a; }} QScrollBar:vertical {{ background-color: #2d2d2d; width: {int(14 * s)}px; border: none; }} QScrollBar::handle:vertical {{ background-color: #555; border-radius: {int(7 * s)}px; min-height: {int(30 * s)}px; margin: {int(2 * s)}px; }} QScrollBar::handle:vertical:hover {{ background-color: #666; }} QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}")

    def on_scale_changed(self, value):
        # REMOVED: no longer used
        pass

    def open_file(self):
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Open Save File", "", "Save Files (*.zip);;All Files (*)")
        if file_path:
            self.load_save_file(file_path)

    def load_save_file(self, file_path):
        try:
            self.save_data = {'_files': {}}
            self.current_file_path = file_path

            with zipfile.ZipFile(file_path, 'r') as zf:
                for fname in zf.namelist():
                    self.save_data['_files'][fname] = True
                    if fname.endswith('.json'):
                        with zf.open(fname) as f:
                            content = f.read().decode('utf-8')
                            if content.strip():
                                key = os.path.splitext(fname)[0]
                                self.save_data[key] = json.loads(content)
                    elif fname == 'uuid.txt':
                        with zf.open(fname) as f:
                            self.save_data['_uuid_txt'] = f.read().decode('utf-8').strip()

            self.populate_tabs()
            s = ScaleManager.scale()
            self.file_label.setText(os.path.basename(file_path))
            self.file_label.setStyleSheet(f"color: #7fbadc; margin-left: {int(16 * s)}px; font-size: {int(13 * s)}px;")

            version = self.detect_version()
            self.convert_btn.setEnabled(version == "1.0")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "Error", f"Failed to load save file:\n{str(e)}")

    def detect_version(self):
        if not self.save_data:
            return "Unknown"
        files = self.save_data.get('_files', {})
        squid_data = self.save_data.get('game_state', {}).get('squid', {})
        if 'uuid.txt' in files or 'statistics.json' in files or 'uuid' in squid_data:
            return "2.0"
        return "1.0"

    def populate_tabs(self):
        self.tabs.clear()
        self.json_tabs.clear()

        overview = OverviewTab(self.save_data)
        self.tabs.addTab(overview, "📋 Overview")

        # Add Network Visualization tab if brain_state exists
        if 'brain_state' in self.save_data:
            network_viz = NetworkVisualizationTab(self.save_data)
            self.tabs.addTab(network_viz, "🕸️ Network")

        raw_mode = self.raw_checkbox.isChecked()

        file_order = ['game_state', 'brain_state', 'custom_brain', 'statistics', 'ShortTerm', 'LongTerm', 'achievements']
        icons = {'game_state': '🦑', 'brain_state': '🧠', 'custom_brain': '🧬', 'statistics': '📊', 'ShortTerm': '💭', 'LongTerm': '🧠', 'achievements': '🏆', 'plugin_data': '🔌'}

        for key in file_order:
            if key in self.save_data and key not in ['_files', '_uuid_txt']:
                filename = f"{key}.json"
                data = self.save_data[key]

                if raw_mode:
                    tab = JsonTab(filename, data)
                else:
                    tab = HumanReadableTab(filename, data)

                icon = icons.get(key, '📄')
                self.tabs.addTab(tab, f"{icon} {key}")
                self.json_tabs[key] = tab

        for key, data in self.save_data.items():
            if key not in file_order and key not in ['_files', '_uuid_txt'] and isinstance(data, (dict, list)):
                filename = f"{key}.json"
                if raw_mode:
                    tab = JsonTab(filename, data)
                else:
                    tab = HumanReadableTab(filename, data)
                icon = icons.get(key, '📄')
                self.tabs.addTab(tab, f"{icon} {key}")
                self.json_tabs[key] = tab

    def toggle_raw_mode(self, raw):
        if self.save_data:
            current_idx = self.tabs.currentIndex()
            self.populate_tabs()
            if current_idx < self.tabs.count():
                self.tabs.setCurrentIndex(current_idx)

    def show_convert_dialog(self):
        if not self.save_data:
            return
        dialog = ConversionDialog(self.save_data, self)
        dialog.exec_()


# =============================================================================
# MAIN
# =============================================================================

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle('Fusion')

    palette = QtGui.QPalette()
    palette.setColor(QtGui.QPalette.Window, QtGui.QColor(26, 26, 26))
    palette.setColor(QtGui.QPalette.WindowText, QtGui.QColor(224, 224, 224))
    palette.setColor(QtGui.QPalette.Base, QtGui.QColor(30, 30, 30))
    palette.setColor(QtGui.QPalette.AlternateBase, QtGui.QColor(37, 37, 37))
    palette.setColor(QtGui.QPalette.Text, QtGui.QColor(224, 224, 224))
    palette.setColor(QtGui.QPalette.Button, QtGui.QColor(45, 45, 45))
    palette.setColor(QtGui.QPalette.ButtonText, QtGui.QColor(224, 224, 224))
    palette.setColor(QtGui.QPalette.Highlight, QtGui.QColor(45, 90, 123))
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))
    app.setPalette(palette)

    window = SaveViewerWindow()
    window.show()

    sys.exit(app.exec_())


if __name__ == '__main__':
    main()