from PyQt5 import QtCore, QtGui, QtWidgets
from .display_scaling import DisplayScaling
from .localisation import loc 
import time


class EnhancedBrainTooltips:
    """Scale-aware tooltips for every neuron."""

    def __init__(self, brain_widget):
        self.brain_widget = brain_widget
        self.current_tooltip_neuron = None
        self.last_tooltip_time = 0
        self.tooltip_delay = 0.3  # seconds

    # ------------------------------------------------------------------
    # Safe helpers for optional FunctionalNeuronData attributes
    # ------------------------------------------------------------------
    def _get_creation_time(self, func_neuron):
        if hasattr(func_neuron, 'creation_context'):
            return func_neuron.creation_context.timestamp
        return time.time()

    def _get_last_activated(self, func_neuron):
        return getattr(func_neuron, 'last_activated', 0)

    def _get_neuron_type(self, func_neuron):
        if hasattr(func_neuron, "neuron_type"):
            return func_neuron.neuron_type
        if hasattr(func_neuron, "specialization"):
            return func_neuron.specialization
        return loc("tooltip_functional", default="functional")

    # ------------------------------------------------------------------
    # Public entry point — keeps old signature for compatibility
    # ------------------------------------------------------------------
    def show_tooltip_for_position(self, event):
        """Legacy entry — we ignore event.pos() and use neuron centre."""
        neuron_name = self.brain_widget.get_neuron_at_pos(event.pos())
        if neuron_name:
            self.show_tooltip_for_neuron(neuron_name, event.pos())
        else:
            QtWidgets.QToolTip.hideText()
            self.current_tooltip_neuron = None

    # ------------------------------------------------------------------
    # New scale-aware tooltip
    # ------------------------------------------------------------------
    
    def show_tooltip_for_neuron(self, neuron_name, _unused_pos):
        """Show tooltip exactly above the neuron, matching paintEvent coordinates."""
        if not neuron_name:
            self.hide_tooltip()
            return

        # Binary neurons will show ON/OFF, continuous neurons show numeric values.

        # 1. Get neuron's logical position
        x_logic, y_logic = self.brain_widget.neuron_positions[neuron_name]
        
        # 2. Calculate layout scale EXACTLY as paintEvent/render worker does
        indicator_space = 0 
        base_width = 1024
        base_height = 768 - indicator_space
        
        # Use dimensions from the widget
        widget_width = self.brain_widget.width()
        widget_height = self.brain_widget.height()
        
        scale_x = widget_width / base_width
        scale_y = (widget_height - indicator_space) / max(1, base_height)
        scale = max(0.01, min(scale_x, scale_y))
        
        offset_x = 0
        if scale_x > scale_y:
            content_width = base_width * scale
            offset_x = (widget_width - content_width) / 2
        
        # 3. Transform logical coordinates to widget coordinates
        # Formula: Logical * Scale + Offset
        widget_x = int(x_logic * scale + offset_x)
        widget_y = int(y_logic * scale + indicator_space)
        
        # 4. Position tooltip 40px above neuron (visual offset - NOT scaled)
        tooltip_pos_widget = QtCore.QPoint(widget_x, widget_y - 40)
        
        # 5. Convert to global screen coordinates for QToolTip
        tooltip_pos_global = self.brain_widget.mapToGlobal(tooltip_pos_widget)
        
        # 6. Generate and show tooltip (scale only the HTML content)
        html = self._generate_tooltip(neuron_name)
        scaled_html = DisplayScaling.scale_css(html)
        
        QtWidgets.QToolTip.showText(tooltip_pos_global, scaled_html, self.brain_widget)
        self.current_tooltip_neuron = neuron_name

    def hide_tooltip(self):
        QtWidgets.QToolTip.hideText()
        self.current_tooltip_neuron = None

    def _generate_tooltip(self, neuron_name):
        bw = self.brain_widget
        is_functional = (
            hasattr(bw, 'enhanced_neurogenesis') and
            neuron_name in bw.enhanced_neurogenesis.functional_neurons
        )
        return (
            self._generate_functional_tooltip(neuron_name)
            if is_functional
            else self._generate_basic_tooltip(neuron_name)
        )

    def _generate_functional_tooltip(self, neuron_name):
        bw = self.brain_widget
        current_value = bw.state.get(neuron_name, 50)
        
        val_display = f"{current_value:.1f}"
        
        return f"""
        <div style='background-color: black; color: white; padding: 1px; 
                    font-family: Arial; font-size: 30px; font-weight: bold; 
                    border-radius: 1px; min-width: 60px; text-align: center;'>
            {val_display}
        </div>
        """

    def _is_binary_neuron(self, neuron_name):
        """
        Check if a neuron is binary (outputs only 0 or 100).
        
        Priority order (first explicit value wins):
        1. neuron_details from loaded brain file (most authoritative)
        2. neurons dict with is_binary field
        3. BINARY_NEURONS constant
        4. Known binary sensors (hardcoded fallback)
        
        We do NOT use brain_widget.is_binary_neuron() as it may have incorrect logic.
        """
        bw = self.brain_widget
        
        # Priority 1: Check neuron_details (from loaded brain JSON) - MOST AUTHORITATIVE
        if hasattr(bw, 'neuron_details') and neuron_name in bw.neuron_details:
            details = bw.neuron_details[neuron_name]
            if isinstance(details, dict) and 'is_binary' in details:
                return details['is_binary']
        
        # Priority 2: Check neurons dict (alternative storage in some brain formats)
        if hasattr(bw, 'neurons') and neuron_name in bw.neurons:
            neuron_data = bw.neurons[neuron_name]
            if isinstance(neuron_data, dict) and 'is_binary' in neuron_data:
                return neuron_data['is_binary']
        
        # Priority 3: Check config's neuron definitions
        if hasattr(bw, 'config') and bw.config:
            try:
                neurons_config = bw.config.get_neurogenesis_config().get('neurons', {})
                if neuron_name in neurons_config:
                    neuron_cfg = neurons_config[neuron_name]
                    if 'is_binary' in neuron_cfg:
                        return neuron_cfg['is_binary']
            except:
                pass
        
        # Priority 4: Check BINARY_NEURONS constant
        try:
            from .brain_constants import BINARY_NEURONS
            if neuron_name in BINARY_NEURONS:
                return True
        except ImportError:
            pass
        
        # Priority 5: Known binary sensors (hardcoded fallback for core sensors)
        # NOTE: plant_proximity is NOT in this list - it's continuous!
        KNOWN_BINARY = {
            'can_see_food', 'is_eating', 'is_sleeping', 'is_sick',
            'pursuing_food', 'is_fleeing', 'is_startled'
        }
        if neuron_name in KNOWN_BINARY:
            return True
        
        # Default: assume continuous (not binary)
        return False

    def _generate_basic_tooltip(self, neuron_name):
        bw = self.brain_widget
        current_value = bw.state.get(neuron_name, 0)
        
        # Check if this is a binary neuron using comprehensive check
        is_binary = self._is_binary_neuron(neuron_name)
        
        if is_binary:
            # For binary neurons, show localized ON/OFF
            val_display = loc("state_on") if current_value > 50 else loc("state_off")
        else:
            # For continuous neurons (including plant_proximity), show numeric value
            val_display = f"{current_value:.1f}"
        
        # Minimal black rectangle with white text (matching weight overlay style)
        return f"""
        <div style='background-color: black; color: white; padding: 10px; 
                    font-family: Arial; font-size: 28px; font-weight: bold; 
                    border-radius: 5px; min-width: 60px; text-align: center;'>
            {val_display}
        </div>
        """

    # ------------------------------------------------------------------
    # Helpers 
    # ------------------------------------------------------------------
    def _get_connection_summary(self, neuron_name):
        bw = self.brain_widget
        incoming = [(b, w) for (a, b), w in bw.weights.items() if a == neuron_name]
        outgoing = [(b, w) for (a, b), w in bw.weights.items() if b == neuron_name]
        top_in = sorted(incoming, key=lambda x: abs(x[1]), reverse=True)[:3]
        top_out = sorted(outgoing, key=lambda x: abs(x[1]), reverse=True)[:3]
        
        lbl_conn_header = loc("tooltip_connections_header")
        # Ensure we pass named arguments for formatting
        conn_stats = loc("tooltip_connections_stats", incoming=len(incoming), outgoing=len(outgoing))
        
        lbl_top_in = loc("tooltip_top_incoming")
        lbl_top_out = loc("tooltip_top_outgoing")

        html = f"<div style='margin: 8px 0;'>"
        html += f"<div style='color: #666; font-size: {DisplayScaling.font_size(12)}px; margin-bottom: 4px;'>"
        html += f"<b>{lbl_conn_header}:</b> {conn_stats}</div>"

        if top_in:
            html += f"<div style='font-size: {DisplayScaling.font_size(14)}px; margin-left: 8px;'>"
            html += f"⬅️ <b>{lbl_top_in}:</b><br>"
            for src, wt in top_in:
                arrow, color = ("→", "#4CAF50") if wt > 0 else ("⊣", "#f44336")
                html += f"<span style='color: {color};'>{src} {arrow} {wt:.2f}</span><br>"
            html += "</div>"

        if top_out:
            html += f"<div style='font-size: {DisplayScaling.font_size(14)}px; margin-left: 8px; margin-top: 4px;'>"
            html += f"➡️ <b>{lbl_top_out}:</b><br>"
            for tgt, wt in top_out:
                arrow, color = ("→", "#4CAF50") if wt > 0 else ("⊣", "#f44336")
                html += f"<span style='color: {color};'>{arrow} {tgt} {wt:.2f}</span><br>"
            html += "</div>"

        html += "</div>"
        return html

    def _get_utility_color(self, utility):
        if utility > 0.7:
            return "#4CAF50"
        elif utility > 0.4:
            return "#FFC107"
        elif utility > 0.2:
            return "#FF9800"
        return "#F44336"

    def _get_activation_color(self, activation):
        deviation = abs(activation - 50)
        return "#F44336" if deviation > 30 else "#FF9800" if deviation > 15 else "#4CAF50"

    def _get_utility_indicator(self, utility):
        if utility > 0.7:
            return "⭐⭐⭐"
        elif utility > 0.4:
            return "⭐⭐"
        elif utility > 0.2:
            return "⭐"
        return "⚠️"
