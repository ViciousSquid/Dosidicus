# enhanced_brain_tooltips.py
# Add rich tooltips to brain network view showing functional neuron information

from PyQt5 import QtCore, QtGui, QtWidgets
from .display_scaling import DisplayScaling
import time

class EnhancedBrainTooltips:
    
    def __init__(self, brain_widget):
        self.brain_widget = brain_widget
        self.current_hover_neuron = None
        self.last_tooltip_time = 0
        self.tooltip_delay = 0.3  # seconds
        
    def show_tooltip_for_position(self, event):
        """Show tooltip for neuron at mouse position"""
        neuron = self._get_neuron_at_pos(event.pos())
        #print(f"DBG  hover neuron = {neuron}")               # 1.  found?

        # hover-state change
        if neuron != self.current_hover_neuron:
            self.current_hover_neuron = neuron
            self.last_tooltip_time = time.time()

        elapsed = time.time() - self.last_tooltip_time
        #print(f"DBG  elapsed = {elapsed:.2f}s  delay = {self.tooltip_delay}")  # 2.  gate

        if neuron and elapsed > self.tooltip_delay:
            tooltip_html = self._generate_tooltip(neuron)
            #print(f"DBG  html len = {len(tooltip_html)}")    # 3.  non-empty?
            QtWidgets.QToolTip.showText(event.globalPos(), tooltip_html)
        elif not neuron:
            QtWidgets.QToolTip.hideText()
    
    def _get_neuron_at_pos(self, widget_pos):
        """Use the *same* coordinate mapper that the widget already proved works."""
        return self.brain_widget.get_neuron_at_pos(widget_pos)
    
    def _generate_tooltip(self, neuron_name):
        """Generate rich HTML tooltip for neuron"""
        bw = self.brain_widget
        
        # Check if functional neuron
        is_functional = (hasattr(bw, 'enhanced_neurogenesis') and 
                        neuron_name in bw.enhanced_neurogenesis.functional_neurons)
        
        if is_functional:
            return self._generate_functional_tooltip(neuron_name)
        else:
            return self._generate_basic_tooltip(neuron_name)
    
    def _generate_functional_tooltip(self, neuron_name):
        """Generate detailed tooltip for functional neuron"""
        bw = self.brain_widget
        func_neuron = bw.enhanced_neurogenesis.functional_neurons[neuron_name]

        # Get current state
        current_value = bw.state.get(neuron_name, 50)

        # Calculate time since last activation
        if func_neuron.last_activated > 0:
            seconds_ago = int(time.time() - func_neuron.last_activated)
            if seconds_ago < 60:
                last_active = f"{seconds_ago}s ago"
            elif seconds_ago < 3600:
                last_active = f"{seconds_ago // 60}m ago"
            else:
                last_active = f"{seconds_ago // 3600}h ago"
        else:
            last_active = "Never"

        # Calculate age
        age_seconds = time.time() - func_neuron.creation_context.timestamp
        if age_seconds < 60:
            age = f"{int(age_seconds)}s"
        elif age_seconds < 3600:
            age = f"{int(age_seconds/60)}m"
        elif age_seconds < 86400:
            age = f"{int(age_seconds/3600)}h"
        else:
            age = f"{int(age_seconds/86400)}d"

        # Get utility color
        utility_color = self._get_utility_color(func_neuron.utility_score)
        activation_color = self._get_activation_color(current_value)

        # Build HTML
        html = f"""
        <div style='font-family: Arial, sans-serif; padding: 8px; min-width: 300px;'>
            <h3 style='margin: 0 0 8px 0; color: #333; border-bottom: 2px solid #4CAF50;'>
                {neuron_name}
            </h3>

            <div style='background: #f5f5f5; padding: 6px; margin: 4px 0; border-radius: 4px;'>
                <b>🎯 Specialization:</b><br>
                <span style='color: #555; font-style: italic;'>{func_neuron.specialization}</span>
            </div>

            <table style='width: 100%; margin: 8px 0;' cellpadding='3'>
                <tr>
                    <td style='color: #666;'>Type:</td>
                    <td><b>{func_neuron.neuron_type}</b></td>
                </tr>
                <tr>
                    <td style='color: #666;'>Current:</td>
                    <td><span style='color: {activation_color}; font-weight: bold;'>{current_value:.1f}</span></td>
                </tr>
                <tr>
                    <td style='color: #666;'>Utility:</td>
                    <td>
                        <span style='color: {utility_color}; font-weight: bold;'>
                            {func_neuron.utility_score:.2f}
                        </span>
                        {self._get_utility_indicator(func_neuron.utility_score)}
                    </td>
                </tr>
                <tr>
                    <td style='color: #666;'>Activations:</td>
                    <td>{func_neuron.activation_count}</td>
                </tr>
                <tr>
                    <td style='color: #666;'>Last Active:</td>
                    <td>{last_active}</td>
                </tr>
                <tr>
                    <td style='color: #666;'>Age:</td>
                    <td>{age}</td>
                </tr>
            </table>

            {self._get_connection_summary(neuron_name)}

            <div style='margin-top: 8px; padding-top: 8px; border-top: 1px solid #ddd; color: #888; font-size: {DisplayScaling.font_size(12)}px;'>
                💡 Double-click to inspect • Right-click for options
            </div>
        </div>
        """
        return html
    
    def _generate_basic_tooltip(self, neuron_name):
        """Generate basic tooltip for non-functional neuron"""
        bw = self.brain_widget
        current_value = bw.state.get(neuron_name, 50)
        is_core = neuron_name in bw.original_neuron_positions
        shape = bw.neuron_shapes.get(neuron_name, 'circle')

        activation_color = self._get_activation_color(current_value)

        html = f"""
        <div style='font-family: Arial, sans-serif; padding: 8px; min-width: 250px;'>
            <h3 style='margin: 0 0 8px 0; color: #333; border-bottom: 2px solid #2196F3;'>
                {neuron_name}
            </h3>

            <table style='width: 100%;' cellpadding='3'>
                <tr>
                    <td style='color: #666;'>Type:</td>
                    <td><b>{'Core' if is_core else 'Generated'}</b></td>
                </tr>
                <tr>
                    <td style='color: #666;'>Shape:</td>
                    <td>{shape.capitalize()}</td>
                </tr>
                <tr>
                    <td style='color: #666;'>Current:</td>
                    <td><span style='color: {activation_color}; font-weight: bold;'>{current_value:.1f}</span></td>
                </tr>
            </table>

            {self._get_connection_summary(neuron_name)}

            <div style='margin-top: 8px; padding-top: 8px; border-top: 1px solid #ddd; color: #888; font-size: {DisplayScaling.font_size(12)}px;'>
                💡 Double-click to inspect • Right-click for options
            </div>
        </div>
        """
        return html
    
    def _get_connection_summary(self, neuron_name):
        """Get summary of connections"""
        bw = self.brain_widget

        # Count connections
        incoming = []
        outgoing = []

        for (a, b), w in bw.weights.items():
            if not isinstance(a, str) or not isinstance(b, str):
                continue
            if a == neuron_name:
                outgoing.append((b, w))
            elif b == neuron_name:
                incoming.append((a, w))

        # Get top connections
        top_incoming = sorted(incoming, key=lambda x: abs(x[1]), reverse=True)[:3]
        top_outgoing = sorted(outgoing, key=lambda x: abs(x[1]), reverse=True)[:3]

        html = "<div style='margin: 8px 0;'>"
        html += f"<div style='color: #666; font-size: {DisplayScaling.font_size(12)}px; margin-bottom: 4px;'>"  # ← changed
        html += f"<b>Connections:</b> {len(incoming)} in, {len(outgoing)} out"
        html += "</div>"

        # Top incoming
        if top_incoming:
            html += f"<div style='font-size: {DisplayScaling.font_size(14)}px; margin-left: 8px;'>"  # ← changed
            html += "⬅️ <b>Top Incoming:</b><br>"
            for source, weight in top_incoming:
                arrow = "→" if weight > 0 else "⊣"
                color = "#4CAF50" if weight > 0 else "#f44336"
                html += f"<span style='color: {color};'>{source} {arrow} {weight:.2f}</span><br>"
            html += "</div>"

        # Top outgoing
        if top_outgoing:
            html += f"<div style='font-size: {DisplayScaling.font_size(14)}px; margin-left: 8px; margin-top: 4px;'>"  # ← changed
            html += "➡️ <b>Top Outgoing:</b><br>"
            for target, weight in top_outgoing:
                arrow = "→" if weight > 0 else "⊣"
                color = "#4CAF50" if weight > 0 else "#f44336"
                html += f"<span style='color: {color};'>{arrow} {target} {weight:.2f}</span><br>"
            html += "</div>"

        html += "</div>"
        return html
    
    def _get_utility_color(self, utility):
        """Get color for utility score"""
        if utility > 0.7:
            return "#4CAF50"  # Green
        elif utility > 0.4:
            return "#FFC107"  # Yellow
        elif utility > 0.2:
            return "#FF9800"  # Orange
        else:
            return "#F44336"  # Red
    
    def _get_activation_color(self, activation):
        """Get color for activation level"""
        deviation = abs(activation - 50)
        if deviation > 30:
            return "#F44336"  # Red
        elif deviation > 15:
            return "#FF9800"  # Orange
        else:
            return "#4CAF50"  # Green
    
    def _get_utility_indicator(self, utility):
        """Get emoji indicator for utility"""
        if utility > 0.7:
            return "⭐⭐⭐"
        elif utility > 0.4:
            return "⭐⭐"
        elif utility > 0.2:
            return "⭐"
        else:
            return "⚠️"

