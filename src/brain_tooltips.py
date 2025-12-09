
from PyQt5 import QtCore, QtGui, QtWidgets
from .display_scaling import DisplayScaling
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
        return "functional"

    # ------------------------------------------------------------------
    # Public entry point – keeps old signature for compatibility
    # ------------------------------------------------------------------
    def show_tooltip_for_position(self, event):
        """Legacy entry – we ignore event.pos() and use neuron centre."""
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

        # 1. Get neuron's logical position
        x_logic, y_logic = self.brain_widget.neuron_positions[neuron_name]
        
        # 2. Calculate layout scale EXACTLY as paintEvent does
        widget_width = self.brain_widget.width()
        widget_height = self.brain_widget.height()
        
        # Match paintEvent's indicator space calculation
        indicator_y_position = 10
        fixed_indicator_area_height = 0
        indicator_space_at_top = indicator_y_position + fixed_indicator_area_height
        
        base_width_logical = 1024
        base_height_logical = 768 - indicator_space_at_top
        if base_height_logical <= 0:
            base_height_logical = 1
        
        scale_x = widget_width / base_width_logical
        
        drawable_height_for_neurons = widget_height - indicator_space_at_top
        if drawable_height_for_neurons <= 0:
            drawable_height_for_neurons = 1
            
        scale_y = drawable_height_for_neurons / base_height_logical
        scale_y = max(0.01, scale_y)
        
        # Use the smaller scale to maintain aspect ratio
        scale = max(0.01, min(scale_x, scale_y))
        
        # 3. Transform logical coordinates to widget coordinates
        # This matches: painter.translate(0, indicator_space_at_top); painter.scale(scale, scale)
        widget_x = int(x_logic * scale)
        widget_y = int(y_logic * scale + indicator_space_at_top)
        
        # 4. Handle horizontal centering if width is the limiting factor
        if scale_x > scale_y:
            content_width = base_width_logical * scale
            offset_x = (widget_width - content_width) / 2
            widget_x += int(offset_x)
        
        # 5. Position tooltip 40px above neuron (visual offset - NOT scaled)
        tooltip_pos_widget = QtCore.QPoint(widget_x, widget_y - 40)
        
        # 6. Convert to global screen coordinates for QToolTip
        tooltip_pos_global = self.brain_widget.mapToGlobal(tooltip_pos_widget)
        
        # 7. Generate and show tooltip (scale only the HTML content)
        html = self._generate_tooltip(neuron_name)
        scaled_html = DisplayScaling.scale_css(html)
        
        QtWidgets.QToolTip.showText(tooltip_pos_global, scaled_html, self.brain_widget)
        self.current_tooltip_neuron = neuron_name

    def hide_tooltip(self):
        QtWidgets.QToolTip.hideText()
        self.current_tooltip_neuron = None

    # ------------------------------------------------------------------
    # HTML generators – now use scaled min-width
    # ------------------------------------------------------------------
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
        fn = bw.enhanced_neurogenesis.functional_neurons[neuron_name]
        current_value = bw.state.get(neuron_name, 50)

        # time formatting
        seconds_ago = int(time.time() - self._get_last_activated(fn))
        last_active = (
            f"{seconds_ago}s ago" if seconds_ago < 60 else
            f"{seconds_ago // 60}m ago" if seconds_ago < 3600 else
            f"{seconds_ago // 3600}h ago"
        )
        age_seconds = time.time() - self._get_creation_time(fn)
        age = (
            f"{int(age_seconds)}s" if age_seconds < 60 else
            f"{int(age_seconds / 60)}m" if age_seconds < 3600 else
            f"{int(age_seconds / 3600)}h" if age_seconds < 86400 else
            f"{int(age_seconds / 86400)}d"
        )

        utility_color = self._get_utility_color(fn.utility_score)
        activation_color = self._get_activation_color(current_value)

        min_width = DisplayScaling.scale(300)  # STEP-3

        return f"""
        <div style='font-family: Arial, sans-serif; padding: 8px; min-width: {min_width}px;'>
            <h3 style='margin: 0 0 8px 0; color: #333; border-bottom: 2px solid #4CAF50;'>
                {neuron_name}
            </h3>
            <div style='background: #f5f5f5; padding: 6px; margin: 4px 0; border-radius: 4px;'>
                <b>🎯 Specialization:</b><br>
                <span style='color: #555; font-style: italic;'>{fn.specialization}</span>
            </div>
            <table style='width: 100%; margin: 8px 0;' cellpadding='3'>
                <tr><td style='color: #666;'>Type:</td><td><b>{self._get_neuron_type(fn)}</b></td></tr>
                <tr><td style='color: #666;'>Current:</td><td><span style='color: {activation_color}; font-weight: bold;'>{current_value:.1f}</span></td></tr>
                <tr><td style='color: #666;'>Utility:</td><td><span style='color: {utility_color}; font-weight: bold;'>{fn.utility_score:.2f}</span>{self._get_utility_indicator(fn.utility_score)}</td></tr>
                <tr><td style='color: #666;'>Activations:</td><td>{fn.activation_count}</td></tr>
                <tr><td style='color: #666;'>Last Active:</td><td>{last_active}</td></tr>
                <tr><td style='color: #666;'>Age:</td><td>{age}</td></tr>
            </table>
            {self._get_connection_summary(neuron_name)}
            <div style='margin-top: 8px; padding-top: 8px; border-top: 1px solid #ddd; color: #888; font-size: {DisplayScaling.font_size(12)}px;'>
                💡 Double-click to inspect • Right-click for options
            </div>
        </div>
        """


    def _generate_basic_tooltip(self, neuron_name):
        bw = self.brain_widget
        current_value = bw.state.get(neuron_name, 50)
        is_core = neuron_name in bw.original_neuron_positions
        shape = bw.neuron_shapes.get(neuron_name, 'circle')
        activation_color = self._get_activation_color(current_value)

        if neuron_name == 'can_see_food':
            val_display = "OFF" if current_value > 50 else "ON"
        else:
            val_display = f"{current_value:.1f}"

        min_width = DisplayScaling.scale(250)

        return f"""
        <div style='font-family: Arial, sans-serif; padding: 8px; min-width: {min_width}px;'>
            <h3 style='margin: 0 0 8px 0; color: #333; border-bottom: 2px solid #2196F3;'>
                {neuron_name}
            </h3>
            <table style='width: 100%;' cellpadding='3'>
                <tr><td style='color: #666;'>Type:</td><td><b>{'Core' if is_core else 'Generated'}</b></td></tr>
                <tr><td style='color: #666;'>Current:</td><td><span style='color: {activation_color}; font-weight: bold;'>{val_display}</span></td></tr>
            </table>
            {self._get_connection_summary(neuron_name)}
            <div style='margin-top: 8px; padding-top: 8px; border-top: 1px solid #ddd; color: #888; font-size: {DisplayScaling.font_size(12)}px;'>
                💡 Double-click to inspect • Right-click for options
            </div>
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

        html = f"<div style='margin: 8px 0;'>"
        html += f"<div style='color: #666; font-size: {DisplayScaling.font_size(12)}px; margin-bottom: 4px;'>"
        html += f"<b>Connections:</b> {len(incoming)} in, {len(outgoing)} out</div>"

        if top_in:
            html += f"<div style='font-size: {DisplayScaling.font_size(14)}px; margin-left: 8px;'>"
            html += "⬅️ <b>Top Incoming:</b><br>"
            for src, wt in top_in:
                arrow, color = ("→", "#4CAF50") if wt > 0 else ("⊣", "#f44336")
                html += f"<span style='color: {color};'>{src} {arrow} {wt:.2f}</span><br>"
            html += "</div>"

        if top_out:
            html += f"<div style='font-size: {DisplayScaling.font_size(14)}px; margin-left: 8px; margin-top: 4px;'>"
            html += "➡️ <b>Top Outgoing:</b><br>"
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