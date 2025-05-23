import sys
import csv
import os
import time
import json
import random
import numpy as np
from datetime import datetime
from PyQt5.QtWidgets import QSplitter
from PyQt5.QtGui import QPixmap, QFont
from PyQt5 import QtCore, QtGui, QtWidgets

# Dependencies
from .brain_widget import BrainWidget
from .brain_dialogs import StimulateDialog, RecentThoughtsDialog, LogWindow, DiagnosticReportDialog
from .brain_utils import ConsoleOutput
from .personality import Personality
from .learning import LearningConfig
from .brain_network_tab import NetworkTab
from .brain_about_tab import AboutTab
from .brain_learning_tab import NeuralNetworkVisualizerTab
from .brain_memory_tab import MemoryTab
from .brain_decisions_tab import DecisionsTab
from .brain_personality_tab import PersonalityTab

class SquidBrainWindow(QtWidgets.QMainWindow):
    def __init__(self, tamagotchi_logic, debug_mode=False, config=None):
        super().__init__()

        # Initialize font size FIRST
        from .display_scaling import DisplayScaling

        self.base_font_size = DisplayScaling.font_size(8)
        self.debug_mode = debug_mode
        self.config = config if config else LearningConfig()
        self.tamagotchi_logic = tamagotchi_logic
        self.initialized = False
        self.is_paused = False

        self.setWindowTitle("Brain Tool")

        # Get screen resolution
        screen = QtWidgets.QApplication.primaryScreen()
        screen_size = screen.size()

        # Resolution-specific sizing
        if screen_size.width() <= 1920 and screen_size.height() <= 1080:
            # For 1080p, use narrower width (65% of screen width)
            width = int(screen_size.width() * 0.65)
            height = int(screen_size.height() * 0.75)
        else:
            # Use standard scaling for higher resolutions
            width = DisplayScaling.scale(1280)
            height = DisplayScaling.scale(800)

        self.resize(width, height)

        # Position window properly
        screen = QtWidgets.QDesktopWidget().screenNumber(QtWidgets.QDesktopWidget().cursor().pos())
        screen_geometry = QtWidgets.QDesktopWidget().screenGeometry(screen)
        self.move(screen_geometry.right() - width, screen_geometry.top())

        # Continue with the rest of initialization...
        # Setup the central widget and main layout
        self.central_widget = QtWidgets.QWidget()
        self.setCentralWidget(self.central_widget)

        self.layout = QtWidgets.QVBoxLayout()
        self.central_widget.setLayout(self.layout)

        # Create the brain widget first
        self.brain_widget = BrainWidget(self.config, self.debug_mode, tamagotchi_logic=tamagotchi_logic)

        # Initialize tab widget
        self.init_tabs()

        # Set up timers
        self.init_timers()

        # Initialize memory update timer if needed
        if hasattr(self, 'memory_tab'):
            self.memory_update_timer = QtCore.QTimer(self)
            self.memory_update_timer.timeout.connect(self.update_memory_tab)
            self.memory_update_timer.start(2000)  # Update every 2 secs


    def set_tamagotchi_logic(self, tamagotchi_logic):
        """Set the tamagotchi_logic reference and update all tabs"""
        print(f"SquidBrainWindow.set_tamagotchi_logic: {tamagotchi_logic is not None}")
        self.tamagotchi_logic = tamagotchi_logic
        
        # Update brain widget
        if hasattr(self, 'brain_widget'):
            self.brain_widget.tamagotchi_logic = tamagotchi_logic
        
        # Update all tabs
        for tab_attr in ['memory_tab', 'network_tab', 'learning_tab', 'decisions_tab', 'about_tab']:
            if hasattr(self, tab_attr):
                tab = getattr(self, tab_attr)
                if hasattr(tab, 'set_tamagotchi_logic'):
                    tab.set_tamagotchi_logic(tamagotchi_logic)

    def set_debug_mode(self, enabled):
        """Properly set debug mode for brain window and all tabs"""
        self.debug_mode = enabled
        
        # Update brain widget's debug mode
        if hasattr(self, 'brain_widget'):
            self.brain_widget.debug_mode = enabled
        
        # Update all tabs
        for tab_name in ['network_tab', 'nn_viz_tab', 'memory_tab', 'decisions_tab', 'about_tab']:
            if hasattr(self, tab_name):
                tab = getattr(self, tab_name)
                if hasattr(tab, 'debug_mode'):
                    tab.debug_mode = enabled
        
        print(f"Brain window debug mode set to: {enabled}")


    def on_hebbian_countdown_finished(self):
        """Called when the Hebbian learning countdown reaches zero"""
        pass

    def set_pause_state(self, is_paused):
        """Set pause state for the brain window"""
        # Only manage internal state but don't apply visual overlay
        self.is_paused = is_paused
        
        # Set brain widget pause state
        if hasattr(self, 'brain_widget'):
            self.brain_widget.is_paused = is_paused
        
        # Manage timers based on pause state
        if is_paused:
            if hasattr(self, 'hebbian_timer'):
                self.hebbian_timer.stop()
        else:
            if hasattr(self, 'hebbian_timer'):
                self.hebbian_timer.start(self.config.hebbian['learning_interval'])

    def init_inspector(self):
        self.inspector_action = QtWidgets.QAction("Neuron Inspector", self)
        self.inspector_action.triggered.connect(self.show_inspector)
        self.debug_menu.addAction(self.inspector_action)

    def show_inspector(self):
        if not hasattr(self, '_inspector') or not self._inspector:
            self._inspector = NeuronInspector(self.brain_widget)
        self._inspector.show()
        self._inspector.raise_()

    def debug_print(self, message):
        if self.debug_mode:
            print(f"DEBUG: {message}")

    def toggle_debug_mode(self, enabled):
        self.debug_mode = enabled
        self.debug_print(f"Debug mode {'enabled' if enabled else 'disabled'}")
        # Update stimulate button state
        if hasattr(self, 'stimulate_button'):
            self.stimulate_button.setEnabled(enabled)

    def get_brain_state(self):
        weights = {}
        for k, v in self.brain_widget.weights.items():
            if isinstance(k, tuple):
                key = f"{k[0]}_{k[1]}"
            else:
                key = str(k)
            weights[key] = v

        return {
            'weights': weights,
            'neuron_positions': {str(k): v for k, v in self.brain_widget.neuron_positions.items()}
        }

    def set_brain_state(self, state):
        if 'weights' in state:
            weights = {}
            for k, v in state['weights'].items():
                if '_' in k:
                    key = tuple(k.split('_'))
                else:
                    key = k
                weights[key] = v
            self.brain_widget.weights = weights

        if 'neuron_positions' in state:
            self.brain_widget.neuron_positions = {k: v for k, v in state['neuron_positions'].items()}

        self.brain_widget.update()  # Trigger a redraw of the brain widget

    def init_timers(self):
        # Hebbian learning timer
        self.hebbian_timer = QtCore.QTimer()
        self.hebbian_timer.timeout.connect(self.brain_widget.perform_hebbian_learning)
        self.hebbian_timer.start(self.config.hebbian.get('learning_interval', 30000))
        
        # Hebbian countdown
        self.hebbian_countdown_seconds = int(self.config.hebbian.get('learning_interval', 30000) / 1000)

        # Add countdown timer
        self.countdown_timer = QtCore.QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_timer.start(1000)  # Update every second

        # Associations timer
        self.update_timer = QtCore.QTimer()
        self.update_timer.timeout.connect(self.update_associations)
        self.update_timer.start(10000)  # Update every 10 seconds
        self.last_update_time = time.time()
        self.update_threshold = 5  # Minimum seconds between updates

    def init_tabs(self):
        # Create tab widget
        self.tabs = QtWidgets.QTabWidget()
        self.layout.addWidget(self.tabs)

        # Set base font for all tab content
        base_font = QtGui.QFont()
        base_font.setPointSize(self.base_font_size)
        self.tabs.setFont(base_font)

        # Create and add existing tabs
        self.network_tab = NetworkTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.network_tab, "Network")
        
        # Add our Neural Network Visualizer tab as the Learning tab
        self.nn_viz_tab = NeuralNetworkVisualizerTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.nn_viz_tab, "Learning")
        
        self.memory_tab = MemoryTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.memory_tab, "Memory")
        
        self.decisions_tab = DecisionsTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.decisions_tab, "Decisions")
        
        self.personality_tab = PersonalityTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.personality_tab, "Personality")
        
        self.about_tab = AboutTab(self, self.tamagotchi_logic, self.brain_widget, self.config, self.debug_mode)
        self.tabs.addTab(self.about_tab, "About")
        
        # Make sure all tabs have correct tamagotchi_logic reference
        for tab_name in ['memory_tab', 'network_tab', 'nn_viz_tab', 'decisions_tab', 'personality_tab', 'about_tab']:
            if hasattr(self, tab_name):
                tab = getattr(self, tab_name)
                if hasattr(tab, 'set_tamagotchi_logic') and self.tamagotchi_logic:
                    tab.set_tamagotchi_logic(self.tamagotchi_logic)
                    print(f"Set tamagotchi_logic for {tab_name}")
        
        # Pre-load the learning tab to make it responsive on first click
        if hasattr(self, 'nn_viz_tab'):
            if hasattr(self.nn_viz_tab, 'pre_load_data'):
                QtCore.QTimer.singleShot(500, self.nn_viz_tab.pre_load_data)


    def update_randomness_factors(self, randomness):
        """Update the randomness factors table"""
        self.random_factors_table.setRowCount(len(randomness))
        
        for i, (action, factor) in enumerate(randomness.items()):
            # Action name
            action_item = QtWidgets.QTableWidgetItem(action)
            self.random_factors_table.setItem(i, 0, action_item)
            
            # Random factor
            value_item = QtWidgets.QTableWidgetItem(f"{factor:.2f}")
            color = QtGui.QColor("darkgreen") if factor > 1.0 else QtGui.QColor("darkred")
            value_item.setForeground(color)
            self.random_factors_table.setItem(i, 1, value_item)


    def create_thought_node(self, text):
        node = QtWidgets.QGraphicsRectItem(0, 0, 250, 150)  # Increase node size
        node.setBrush(QtGui.QBrush(QtGui.QColor(240, 248, 255)))

        # Use QTextDocument for better text handling
        text_document = QtGui.QTextDocument()
        text_document.setPlainText(text)
        text_document.setTextWidth(230)  # Set text width to fit within the node

        # Create a QGraphicsTextItem with an empty string
        text_item = QtWidgets.QGraphicsTextItem()
        text_item.setDocument(text_document)
        text_item.setPos(10, 10)

        group = QtWidgets.QGraphicsItemGroup()
        group.addToGroup(node)
        group.addToGroup(text_item)
        return group

    def draw_connection(self, start, end, label):
        line = QtWidgets.QGraphicsLineItem(start[0]+200, start[1]+50, end[0], end[1]+50)
        line.setPen(QtGui.QPen(QtCore.Qt.darkGray, 2, QtCore.Qt.DashLine))
        self.decision_scene.addItem(line)

        arrow = QtWidgets.QGraphicsPolygonItem(
            QtGui.QPolygonF([QtCore.QPointF(0, -5), QtCore.QPointF(10, 0), QtCore.QPointF(0, 5)]))
        arrow.setPos(end[0], end[1]+50)
        arrow.setRotation(180 if start[0] > end[0] else 0)
        self.decision_scene.addItem(arrow)

        label_item = QtWidgets.QGraphicsTextItem(label)
        label_item.setPos((start[0]+end[0])/2, (start[1]+end[1])/2)
        self.decision_scene.addItem(label_item)

    
    def _get_memory_colors(self, memory):
        """Determine colors based on memory content"""
        if 'positive' in memory.get('tags', []):
            return "#E8F5E9", "#C8E6C9"  # Green shades
        elif 'negative' in memory.get('tags', []):
            return "#FFEBEE", "#FFCDD2"   # Red shades
        elif 'novelty' in memory.get('tags', []):
            return "#FFFDE7", "#FFF9C4"   # Yellow shades
        return "#F5F5F5", "#EEEEEE"       # Default gray

    def update_memory_tab(self):
        """Update memory tab if it exists"""
        if hasattr(self, 'memory_tab'):
            # Forward to the tab's update method
            self.memory_tab.update_memory_display()

    def _update_overview_stats(self, stm, ltm):
        """Update the overview tab with statistics"""
        stats_html = """
        <style>
            .stat-box { 
                background: #f8f9fa; 
                border-radius: 10px; 
                padding: 15px; 
                margin: 10px;
            }
            .stat-title { 
                font-size: 10pt; 
                color: #2c3e50; 
                margin-bottom: 10px;
            }
        </style>
        """
        
        # Memory counts
        stats_html += """
        <div class="stat-box">
            <div class="stat-title">📈 Memory Statistics</div>
            <table>
                <tr><td>Short-Term Memories:</td><td style="padding-left: 20px;">{stm_count}</td></tr>
                <tr><td>Long-Term Memories:</td><td style="padding-left: 20px;">{ltm_count}</td></tr>
            </table>
        </div>
        """.format(stm_count=len(stm), ltm_count=len(ltm))
        
        # Category breakdown
        categories = {}
        for m in stm + ltm:
            cat = m.get('category', 'unknown')
            categories[cat] = categories.get(cat, 0) + 1
        
        category_html = "\n".join(
            f"<tr><td>{k}:</td><td style='padding-left: 20px;'>{v}</td></tr>"
            for k, v in sorted(categories.items())
        )
        
        stats_html += f"""
        <div class="stat-box">
            <div class="stat-title">🗂️ Categories</div>
            <table>{category_html}</table>
        </div>
        """
        
        self.overview_stats.setHtml(stats_html)

    def _clear_layout(self, layout):
        """Clear all widgets from the given layout"""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def set_pause_state(self, paused=None):
        """Set or toggle the pause state"""
        if paused is not None:
            self.is_paused = paused
        else:
            self.is_paused = not self.is_paused
        
        # Update brain widget pause state if it exists
        if hasattr(self, 'brain_widget') and self.brain_widget:
            self.brain_widget.is_paused = self.is_paused
        
        # Update UI
        self.update_paused_overlay()
        
        # Update status label if it exists
        if hasattr(self, 'status_label'):
            self.status_label.setText("Paused" if self.is_paused else "Running")

    def _create_memory_card(self, memory):
        """Create a styled HTML memory card with tooltip"""
        category = memory.get('category', 'unknown')
        value = memory.get('formatted_value', str(memory.get('value', '')))
        timestamp = memory.get('timestamp', '')
        effects = memory.get('effects', {})
        
        # Determine card color based on memory type
        bg_color, border_color = self._get_memory_colors(memory)
        
        # Create concise display text
        card_html = f"""
        <div style="
            background-color: {bg_color};
            border: 2px solid {border_color};
            border-radius: 10px;
            padding: 15px;
            margin: 10px;
            font-size: 10pt;
        ">
            <div style="font-weight: bold; color: #333;">{category.capitalize()}</div>
            <div style="font-size: 12pt; margin-top: 8px;">{value[:60]}</div>
            <div style="font-size: 10pt; color: #666; margin-top: 8px;">
                {timestamp.split(' ')[-1]}
            </div>
        </div>
        """
        
        # Create tooltip with extended info
        tooltip = f"""
        <b>Full Content:</b> {value}<br>
        <b>Effects:</b> {', '.join(f'{k}: {v}' for k,v in effects.items())}<br>
        <b>Last Accessed:</b> {timestamp}
        """
        
        # Create widget with HTML and tooltip
        card = QtWidgets.QTextEdit()
        card.setHtml(card_html)
        card.setReadOnly(True)
        card.setToolTip(tooltip)
        card.setFixedHeight(120)
        card.setStyleSheet("border: none;")
        
        return card
    
    def _get_card_style(self, memory):
        """Get CSS style for a memory card based on its valence and importance"""
        # Determine card background color based on memory valence
        if memory.get('category') == 'mental_state' and memory.get('key') == 'startled':
            background_color = "#FFD1DC"  # Pastel red for negative
        elif isinstance(memory.get('raw_value'), dict):
            total_effect = sum(float(val) for val in memory['raw_value'].values() 
                            if isinstance(val, (int, float)))
            if total_effect > 0:
                background_color = "#D1FFD1"  # Pastel green for positive
            elif total_effect < 0:
                background_color = "#FFD1DC"  # Pastel red for negative
            else:
                background_color = "#FFFACD"  # Pastel yellow for neutral
        else:
            background_color = "#FFFACD"  # Pastel yellow for neutral
        
        # Determine border based on importance (only for short-term)
        importance = memory.get('importance', 1)
        if importance >= 7:
            border = "2px solid #FF5733"  # Important memory
        elif importance >= 4:
            border = "1px solid #666"     # Medium importance
        else:
            border = "1px solid #ccc"     # Low importance
        
        return f"""
            background-color: {background_color};
            border: {border};
            border-radius: 8px;
            padding: 8px;
            margin: 4px;
        """
    
    def _format_memory_content(self, memory):
        """Format memory content for display in a card"""
        # Get the display text - prefer formatted_value, fall back to value
        display_text = memory.get('formatted_value', str(memory.get('value', '')))
        
        # Skip if the display text contains just a timestamp
        if 'timestamp' in display_text.lower() and len(display_text.split()) < 3:
            return "<i>Empty memory</i>"
        
        # Make text more concise and readable
        # Remove any HTML tags already in the text to avoid nesting issues
        import re
        display_text = re.sub(r'<[^>]*>', '', display_text)
        
        # Format based on category
        category = memory.get('category', '')
        
        if category == 'decorations':
            # Extract the important parts of decoration interactions
            if 'interaction with' in display_text.lower():
                parts = display_text.split(':')
                if len(parts) >= 2:
                    item = parts[0].strip()
                    effects = parts[1].strip()
                    return f"<b>{item}</b><br>{effects}"
        
        # Default formatting with bold beginning
        words = display_text.split()
        if len(words) > 3:
            bold_part = ' '.join(words[:3])
            rest = ' '.join(words[3:])
            return f"<b>{bold_part}</b> {rest}"
        
        return display_text
    
    def _create_memory_tooltip(self, memory):
        """Create detailed tooltip for a memory card"""
        tooltip = "<html><body style='white-space:pre'>"
        tooltip += f"<b>Category:</b> {memory.get('category', 'unknown')}\n"
        tooltip += f"<b>Key:</b> {memory.get('key', 'unknown')}\n"
        
        timestamp = memory.get('timestamp', '')
        if isinstance(timestamp, str):
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
            except:
                timestamp = ""
        
        tooltip += f"<b>Time:</b> {timestamp}\n"
        
        if 'importance' in memory:
            tooltip += f"<b>Importance:</b> {memory.get('importance')}\n"
        
        if 'access_count' in memory:
            tooltip += f"<b>Access count:</b> {memory.get('access_count')}\n"
        
        if isinstance(memory.get('raw_value'), dict):
            tooltip += "\n<b>Effects:</b>\n"
            for key, value in memory['raw_value'].items():
                if isinstance(value, (int, float)):
                    tooltip += f"  {key}: {value:+.2f}\n"
        
        tooltip += "</body></html>"
        return tooltip
    
    def _get_stm(self):
        """Get short-term memories from squid's memory manager"""
        if hasattr(self.tamagotchi_logic, 'squid') and hasattr(self.tamagotchi_logic.squid, 'memory_manager'):
            return self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories()
        return []
        
    def _get_ltm(self):
        """Get long-term memories from squid's memory manager"""
        if hasattr(self.tamagotchi_logic, 'squid') and hasattr(self.tamagotchi_logic.squid, 'memory_manager'):
            return self.tamagotchi_logic.squid.memory_manager.get_all_long_term_memories()
        return []
    
    def _is_displayable(self, memory):
        """Check if a memory should be displayed in the UI"""
        if not isinstance(memory, dict):
            return False
        
        # Skip timestamp-like memories (with numeric keys or timestamp values)
        if isinstance(memory.get('key'), str):
            # Filter out numeric keys (timestamps)
            if memory['key'].replace('.', '', 1).isdigit():
                return False
        
        # Check the value - filter out memories with timestamp values
        value = memory.get('value', '')
        if isinstance(value, str) and 'timestamp' in value.lower():
            return False
            
        # For memories with formatted_value
        formatted_value = memory.get('formatted_value', '')
        if isinstance(formatted_value, str):
            # If it contains timestamp numbers as part of the interaction
            if 'Interaction with' in formatted_value and any(c.isdigit() for c in formatted_value.split('with')[1]):
                return False
        
        # Check for timestamp-like value in the memory
        if 'Interaction with' in str(formatted_value) and '.' in str(formatted_value):
            timestamp_part = str(formatted_value).split('with')[1].strip()
            # If it looks like a float timestamp (e.g., 1744308365.4552662)
            if '.' in timestamp_part and any(part.replace('.', '', 1).isdigit() for part in timestamp_part.split()):
                return False
        
        # Skip memories that don't have a proper category or value
        if not memory.get('category') or not memory.get('value'):
            return False
            
        # Must have either formatted_value or a displayable string value
        if 'formatted_value' not in memory and not isinstance(memory.get('value'), str):
            return False
            
        return True
    
    def _update_memory_stats(self, short_term_memories, long_term_memories):
        """Update memory statistics in the overview tab"""
        stats_html = "<h2>Memory System Statistics</h2>"
        
        # Basic stats
        stats_html += f"<p><b>Short-term memories:</b> {len(short_term_memories)}</p>"
        stats_html += f"<p><b>Long-term memories:</b> {len(long_term_memories)}</p>"
        
        # Category breakdown
        stats_html += "<h3>Memory Categories</h3>"
        
        # Count memories by category
        all_memories = short_term_memories + long_term_memories
        categories = {}
        
        for mem in all_memories:
            category = mem.get('category', 'unknown')
            categories[category] = categories.get(category, 0) + 1
        
        # Create category table
        if categories:
            stats_html += "<table border='1' cellpadding='4' style='border-collapse: collapse;'>"
            stats_html += "<tr><th>Category</th><th>Count</th></tr>"
            
            for category, count in sorted(categories.items(), key=lambda x: x[1], reverse=True):
                stats_html += f"<tr><td>{category}</td><td>{count}</td></tr>"
            
            stats_html += "</table>"
        
        # Memory importance breakdown (short-term only)
        if short_term_memories:
            stats_html += "<h3>Memory Importance (Short-term)</h3>"
            
            importance_levels = {
                "High (7-10)": 0,
                "Medium (4-6)": 0,
                "Low (1-3)": 0
            }
            
            for mem in short_term_memories:
                imp = mem.get('importance', 1)
                if imp >= 7:
                    importance_levels["High (7-10)"] += 1
                elif imp >= 4:
                    importance_levels["Medium (4-6)"] += 1
                else:
                    importance_levels["Low (1-3)"] += 1
            
            stats_html += "<table border='1' cellpadding='4' style='border-collapse: collapse;'>"
            stats_html += "<tr><th>Importance Level</th><th>Count</th></tr>"
            
            for level, count in importance_levels.items():
                stats_html += f"<tr><td>{level}</td><td>{count}</td></tr>"
            
            stats_html += "</table>"
        
        # Update stats display
        self.memory_stats_text.setHtml(stats_html)


    def add_thought(self, thought):
        """Bridge method to forward thoughts to the decisions tab"""
        if hasattr(self, 'decisions_tab') and self.decisions_tab:
            # If we have a decisions tab, forward to its thought log
            if hasattr(self.decisions_tab, 'thought_log_text'):
                self.decisions_tab.thought_log_text.append(thought)
                # Auto-scroll to bottom
                scrollbar = self.decisions_tab.thought_log_text.verticalScrollBar()
                scrollbar.setValue(scrollbar.maximum())
            elif hasattr(self.decisions_tab, 'add_thought'):
                # Alternative: if the tab has its own add_thought method
                self.decisions_tab.add_thought(thought)
        else:
            # Fallback: print to console if no UI element available
            print(f"Thought: {thought}")

    def clear_thoughts(self):
        self.thoughts_text.clear()

    def init_decisions_tab(self):
        font = QtGui.QFont()
        font.setPointSize(self.base_font_size)
        # Add a label for decision history
        decision_history_label = QtWidgets.QLabel("Decision History:")
        self.decisions_tab_layout.addWidget(decision_history_label)

        # Add a text area to display decision history
        self.decision_history_text = QtWidgets.QTextEdit()
        self.decision_history_text.setReadOnly(True)
        self.decisions_tab_layout.addWidget(self.decision_history_text)

        # Add a label for decision inputs
        decision_inputs_label = QtWidgets.QLabel("Decision Inputs:")
        self.decisions_tab_layout.addWidget(decision_inputs_label)

        # Add a text area to display decision inputs
        self.decision_inputs_text = QtWidgets.QTextEdit()
        self.decision_inputs_text.setReadOnly(True)
        self.decisions_tab_layout.addWidget(self.decision_inputs_text)

    def update_decisions_tab(self, decision, decision_inputs):
        # Append the decision to the decision history
        self.decision_history_text.append(f"Decision: {decision}")

        # Display the decision inputs
        self.decision_inputs_text.clear()
        for key, value in decision_inputs.items():
            self.decision_inputs_text.append(f"{key}: {value}")

    def init_associations_tab(self):
        font = QtGui.QFont()
        font.setPointSize(self.base_font_size)
        # Add a checkbox to toggle explanation
        self.show_explanation_checkbox = QtWidgets.QCheckBox("Show Explanation")
        self.show_explanation_checkbox.stateChanged.connect(self.toggle_explanation)
        self.associations_tab_layout.addWidget(self.show_explanation_checkbox)

        # Add explanation text (hidden by default)
        self.explanation_text = QtWidgets.QTextEdit()
        self.explanation_text.setReadOnly(True)
        self.explanation_text.setHidden(True)
        self.explanation_text.setPlainText(
            "This tab shows the learned associations between different neural states of the squid. "
            "These associations are formed through the Hebbian learning process, where 'neurons that fire together, wire together'. "
            "The strength of an association is determined by how often these states occur together or influence each other. "
            "Positive associations mean that as one state increases, the other tends to increase as well. "
            "Negative associations (indicated by 'reduced') mean that as one state increases, the other tends to decrease. "
            "These associations help us understand how the squid's experiences shape its behavior and decision-making processes."
        )
        self.associations_tab_layout.addWidget(self.explanation_text)

        # Add a label for the associations
        label = QtWidgets.QLabel("Learned associations:")
        self.associations_tab_layout.addWidget(label)

        # Add a text area to display associations
        self.associations_text = QtWidgets.QTextEdit()
        self.associations_text.setReadOnly(True)
        self.associations_tab_layout.addWidget(self.associations_text)

        # Add export button
        self.export_associations_button = QtWidgets.QPushButton("Export Associations")
        self.export_associations_button.clicked.connect(self.export_associations)
        self.associations_tab_layout.addWidget(self.export_associations_button, alignment=QtCore.Qt.AlignRight)

    def toggle_explanation(self, state):
        self.explanation_text.setVisible(state == QtCore.Qt.Checked)

    def update_associations(self):
        """Update association data if we have the learning tab"""
        if hasattr(self, 'learning_tab'):
            # Forward to the tab's update method
            current_time = time.time()
            if current_time - self.last_update_time > self.update_threshold:
                self.last_update_time = current_time
                self.learning_tab.update_from_brain_state(self.brain_widget.state)

    def generate_association_summary(self, neuron1, neuron2, weight):
        strength = "strongly" if abs(weight) > 0.8 else "moderately"
        if weight > 0:
            relation = "associated with"
        else:
            relation = "associated with reduced"

        # Correct grammar for specific neurons
        neuron1_text = self.get_neuron_display_name(neuron1)
        neuron2_text = self.get_neuron_display_name(neuron2)

        summaries = {
            "hunger-satisfaction": f"{neuron1_text} is {strength} associated with satisfaction (probably from eating)",
            "satisfaction-hunger": f"Feeling satisfied is {strength} associated with reduced hunger",
            "cleanliness-anxiety": f"{neuron1_text} is {strength} {relation} anxiety",
            "anxiety-cleanliness": f"Feeling anxious is {strength} associated with reduced cleanliness",
            "curiosity-happiness": f"{neuron1_text} is {strength} associated with happiness",
            "happiness-curiosity": f"Being happy is {strength} associated with increased curiosity",
            "hunger-anxiety": f"{neuron1_text} is {strength} associated with increased anxiety",
            "sleepiness-satisfaction": f"{neuron1_text} is {strength} {relation} satisfaction",
            "happiness-cleanliness": f"Being happy is {strength} associated with cleanliness",
        }

        key = f"{neuron1}-{neuron2}"
        if key in summaries:
            return summaries[key]
        else:
            return f"{neuron1_text} is {strength} {relation} {neuron2_text}"

    def get_neuron_display_name(self, neuron):
        display_names = {
            "cleanliness": "Being clean",
            "sleepiness": "Being sleepy",
            "happiness": "Being happy",
            "hunger": "Being hungry",
            "satisfaction": "Satisfaction",
            "anxiety": "Being anxious",
            "curiosity": "Curiosity",
            "direction": "Direction"
        }
        return display_names.get(neuron, f"{neuron}")



    def update_countdown(self):
        """Update the Hebbian learning countdown display"""
        # Calculate time until next learning cycle
        if hasattr(self.brain_widget, 'last_hebbian_time'):
            elapsed = time.time() - self.brain_widget.last_hebbian_time
            interval_sec = self.config.hebbian.get('learning_interval', 30000) / 1000
            remaining = max(0, interval_sec - elapsed)
            self.brain_widget.hebbian_countdown_seconds = int(remaining)
        else:
            self.brain_widget.hebbian_countdown_seconds = 0

        # If we have the neural network visualizer tab initialized, update its countdown
        if hasattr(self, 'nn_viz_tab') and hasattr(self.nn_viz_tab, 'countdown_label'):
            # Update the formatted display
            if hasattr(self.brain_widget, 'is_paused') and self.brain_widget.is_paused:
                self.nn_viz_tab.countdown_label.setText("PAUSED")
            else:
                self.nn_viz_tab.countdown_label.setText(f"{self.brain_widget.hebbian_countdown_seconds} seconds")
            
            # If countdown reached zero and not paused, trigger learning
            if (self.brain_widget.hebbian_countdown_seconds == 0 and 
                hasattr(self.brain_widget, 'is_paused') and 
                not self.brain_widget.is_paused):
                self.brain_widget.perform_hebbian_learning()

    def check_memory_decay(self):
        """Check for short-term memory decay and transfer important memories to long-term"""
        if not hasattr(self.tamagotchi_logic, 'squid') or not self.tamagotchi_logic.squid:
            return
            
        # Run periodic memory management on the squid's memory manager
        if hasattr(self.tamagotchi_logic.squid, 'memory_manager'):
            memory_manager = self.tamagotchi_logic.squid.memory_manager
            
            # Get all short-term memories to check for decay
            short_term_memories = memory_manager.get_all_short_term_memories()
            
            # Process memories that are about to decay (older than 100 seconds)
            current_time = datetime.now()
            for memory in short_term_memories:
                if 'timestamp' in memory:
                    timestamp = memory['timestamp']
                    if isinstance(timestamp, str):
                        timestamp = datetime.fromisoformat(timestamp)
                    
                    time_diff = current_time - timestamp
                    
                    # If memory is influential or important, make sure it's transferred to long-term
                    is_influential = False
                    
                    # Check if it's an important or influential memory
                    if 'importance' in memory and memory['importance'] >= 7:
                        is_influential = True
                        
                    # Check if it's about to decay but is important
                    if time_diff.total_seconds() > 100:  # About to decay (120s is default)
                        category = memory.get('category', '')
                        key = memory.get('key', '')
                        
                        if is_influential:
                            # Log the memory transfer
                            self.activity_log.append(f"""
                            <div style="background-color: #fff3cd; padding: 8px; margin: 5px; border-radius: 5px; border-left: 4px solid #ffc107;">
                                <span style="font-weight: bold;">Important Memory Transfer</span><br>
                                <span>Category: {category}</span><br>
                                <span>Key: {key}</span><br>
                                <span>Age: {int(time_diff.total_seconds())} seconds</span><br>
                                <span>Importance: {memory.get('importance', 'unknown')}</span>
                            </div>
                            """)
                            
                            # Transfer to long-term memory
                            memory_manager.transfer_to_long_term_memory(category, key)

    def clear_learning_data(self):
        self.weight_changes_text.clear()
        self.learning_data_table.setRowCount(0)
        self.learning_data = []
        print("Learning data cleared.")

    def update_learning_interval(self, seconds):
        """Update the learning interval when spinbox value changes"""
        # Convert seconds to milliseconds (QTimer uses ms)
        interval_ms = seconds * 1000
        
        # Update config
        if hasattr(self.config, 'hebbian'):
            self.config.hebbian['learning_interval'] = interval_ms
        else:
            self.config.hebbian = {'learning_interval': interval_ms}
        
        # Restart timer with new interval
        if hasattr(self, 'hebbian_timer'):
            self.hebbian_timer.setInterval(interval_ms)
            self.last_hebbian_time = time.time()  # Reset countdown
        
        if self.debug_mode:
            print(f"Learning interval updated to {seconds} seconds ({interval_ms} ms)")

    

    def deduce_weight_change_reason(self, pair, value1, value2, prev_weight, new_weight, weight_change):
        neuron1, neuron2 = pair
        threshold_high = 70
        threshold_low = 30

        reasons = []

        # Analyze neuron activity levels
        if value1 > threshold_high and value2 > threshold_high:
            reasons.append(f"Both {neuron1.upper()} and {neuron2.upper()} were highly active")
        elif value1 < threshold_low and value2 < threshold_low:
            reasons.append(f"Both {neuron1.upper()} and {neuron2.upper()} had low activity")
        elif value1 > threshold_high:
            reasons.append(f"{neuron1.upper()} was highly active")
        elif value2 > threshold_high:
            reasons.append(f"{neuron2.upper()} was highly active")

        # Analyze weight change
        if abs(weight_change) > 0.1:
            if weight_change > 0:
                reasons.append("Strong positive reinforcement")
            else:
                reasons.append("Strong negative reinforcement")
        elif abs(weight_change) > 0.01:
            if weight_change > 0:
                reasons.append("Moderate positive reinforcement")
            else:
                reasons.append("Moderate negative reinforcement")
        else:
            reasons.append("Weak reinforcement")

        # Analyze the relationship between neurons
        if "hunger" in pair and "satisfaction" in pair:
            reasons.append("Potential hunger-satisfaction relationship")
        elif "cleanliness" in pair and "happiness" in pair:
            reasons.append("Potential cleanliness-happiness relationship")

        # Analyze the current weight
        if abs(new_weight) > 0.8:
            reasons.append("Strong connection formed")
        elif abs(new_weight) < 0.2:
            reasons.append("Weak connection")

        # Analyze learning progress
        if abs(prev_weight) < 0.1 and abs(new_weight) > 0.1:
            reasons.append("New significant connection emerging")
        elif abs(prev_weight) > 0.8 and abs(new_weight) < 0.8:
            reasons.append("Previously strong connection weakening")

        # Combine reasons
        if len(reasons) > 1:
            return " | ".join(reasons)
        elif len(reasons) == 1:
            return reasons[0]
        else:
            return "Complex interaction with no clear single reason"


    def get_neuron_value(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        elif isinstance(value, bool):
            return 100.0 if value else 0.0
        elif isinstance(value, str):
            # For string values (like 'direction'), return a default value
            return 75.0
        else:
            return 0.0

    def update_learning_data_table(self):
        self.learning_data_table.setRowCount(len(self.learning_data))
        for row, data in enumerate(self.learning_data):
            for col, value in enumerate(data):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col == 3:  # Weight change column
                    item.setData(QtCore.Qt.DisplayRole, f"{value:.4f}")
                if col == 4:  # Direction column
                    if value == "increase ⬆️":
                        item.setForeground(QtGui.QColor("green"))
                    elif value == "⬇️ decrease":
                        item.setForeground(QtGui.QColor("red"))
                self.learning_data_table.setItem(row, col, item)
        self.learning_data_table.scrollToBottom()

    def export_learning_data(self):
        # Save the weight changes text to a file
        with open("learningdata_reasons.txt", 'w') as file:
            file.write(self.weight_changes_text.toPlainText())

        # Save the learning data table to a CSV file
        with open("learningdata_weights.csv", 'w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Timestamp", "Neuron 1", "Neuron 2", "Weight Change", "Direction"])
            for row in range(self.learning_data_table.rowCount()):
                row_data = []
                for col in range(self.learning_data_table.columnCount()):
                    item = self.learning_data_table.item(row, col)
                    row_data.append(item.text() if item else "")
                writer.writerow(row_data)

        QtWidgets.QMessageBox.information(self, "Export Successful", "Learning data exported to 'weight_changes.txt' and 'learning_data.csv'")

    def export_learning_tab_contents(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Learning Tab Contents", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w') as file:
                file.write("Learning Data Table:\n")
                for row in range(self.learning_data_table.rowCount()):
                    row_data = []
                    for col in range(self.learning_data_table.columnCount()):
                        item = self.learning_data_table.item(row, col)
                        row_data.append(item.text() if item else "")
                    file.write("\t".join(row_data) + "\n")

                file.write("\nWeight Changes Text:\n")
                file.write(self.weight_changes_text.toPlainText())

            QtWidgets.QMessageBox.information(self, "Export Successful", f"Learning tab contents exported to {file_name}")

    def export_associations(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export Associations", "", "Text Files (*.txt)")
        if file_name:
            with open(file_name, 'w') as file:
                file.write(self.associations_text.toPlainText())
            QtWidgets.QMessageBox.information(self, "Export Successful", f"Associations exported to {file_name}")

    def update_personality_effects(self, personality, weights, adjusted_weights):
        """Update the personality modifier display in the thinking tab"""
        # Convert enum to string if needed
        personality_str = getattr(personality, 'value', str(personality))
        
        self.personality_label.setText(f"Personality: {personality_str.capitalize()}")
        
        # Generate effect text based on weight differences
        effects_text = []
        for action, weight in weights.items():
            adjusted = adjusted_weights.get(action, weight)
            if abs(adjusted - weight) > 0.01:  # If there's a significant difference
                direction = "increases" if adjusted > weight else "decreases"
                effect = f"{action}: {direction} by {abs(adjusted - weight):.2f}"
                effects_text.append(effect)
        
        if effects_text:
            self.personality_effects.setPlainText("\n".join(effects_text))
        else:
            self.personality_effects.setPlainText("No significant personality effects")

    def update_personality_display(self, personality):
        # Convert enum to string if needed
        personality_str = getattr(personality, 'value', str(personality))
        
        # Set personality type label
        self.personality_type_label.setText(f"Squid Personality: {personality_str.capitalize()}")
        
        # Set personality modifier label
        self.personality_modifier_label.setText(f"Personality Modifier: {self.get_personality_modifier(personality)}")
        
        # Set description text
        self.personality_description.setPlainText(self.get_personality_description(personality))
        
        # Set modifiers text
        self.modifiers_text.setPlainText(self.get_personality_modifiers(personality))
        
        # Set care tips text
        self.care_tips.setPlainText(self.get_care_tips(personality))

    def get_personality_description(self, personality):
        descriptions = {
            Personality.TIMID: "Your squid is Timid. It tends to be more easily startled and anxious, especially in new situations. It may prefer quiet, calm environments and might be less likely to explore on its own. However, it can form strong bonds when it feels safe and secure.",
            Personality.ADVENTUROUS: "Your squid is Adventurous. It loves to explore and try new things. It's often the first to investigate new objects or areas in its environment. This squid thrives on novelty and might get bored more easily in unchanging surroundings.",
            Personality.LAZY: "Your squid is Lazy. It prefers a relaxed lifestyle and may be less active than other squids. It might need extra encouragement to engage in activities but can be quite content just lounging around. This squid is great at conserving energy!",
            Personality.ENERGETIC: "Your squid is Energetic. It's always on the move, full of life and vigor. This squid needs plenty of stimulation and activities to keep it happy. It might get restless if not given enough opportunity to burn off its excess energy.",
            Personality.INTROVERT: "Your squid is an Introvert. It enjoys solitude and might prefer quieter, less crowded spaces. While it can interact with others, it may need time alone to 'recharge'. This squid might be more observant and thoughtful in its actions.",
            Personality.GREEDY: "Your squid is Greedy. It has a strong focus on food and resources. This squid might be more motivated by treats and rewards than others. While it can be more demanding, it also tends to be resourceful and good at finding hidden treats!",
            Personality.STUBBORN: "Your squid is Stubborn. It has a strong will and definite preferences. This squid might be more resistant to change and could take longer to adapt to new routines. However, its determination can also make it persistent in solving problems."
        }
        return descriptions.get(personality, "Unknown personality type")

    def get_personality_modifier(self, personality):
        modifiers = {
            Personality.TIMID: "Higher chance of becoming anxious",
            Personality.ADVENTUROUS: "Increased curiosity and exploration",
            Personality.LAZY: "Slower movement and energy consumption",
            Personality.ENERGETIC: "Faster movement and higher activity levels",
            Personality.INTROVERT: "Prefers solitude and quiet environments",
            Personality.GREEDY: "More focused on food and resources",
            Personality.STUBBORN: "Only eats favorite food (sushi), may refuse to sleep"
        }
        return modifiers.get(personality, "No specific modifier")

    def get_care_tips(self, personality):
        tips = {
            Personality.TIMID: "- Place plants in the environment to reduce anxiety\n- Keep the environment clean and calm\n- Approach slowly and avoid sudden movements",
            Personality.ADVENTUROUS: "- Regularly introduce new objects or decorations\n- Provide diverse food options\n- Encourage exploration with strategic food placement",
            Personality.LAZY: "- Place food closer to the squid's resting spots\n- Clean the environment more frequently\n- Use enticing food to encourage movement",
            Personality.ENERGETIC: "- Provide a large, open space for movement\n- Offer frequent feeding opportunities\n- Introduce interactive elements or games",
            Personality.INTROVERT: "- Create quiet, secluded areas with decorations\n- Avoid overcrowding the environment\n- Respect the squid's need for alone time",
            Personality.GREEDY: "- Offer a variety of food types, including sushi\n- Use food as a reward for desired behaviors\n- Be cautious not to overfeed",
            Personality.STUBBORN: "- Always have sushi available as it's their favorite food\n- Be patient when introducing changes\n- Use positive reinforcement for desired behaviors"
        }
        return tips.get(personality, "No specific care tips available for this personality.")

    def get_personality_modifiers(self, personality):
        modifiers = {
            Personality.TIMID: "- Anxiety increases 50% faster\n- Curiosity increases 50% slower\n- Anxiety decreases by 50% when near plants",
            Personality.ADVENTUROUS: "- Curiosity increases 50% faster",
            Personality.LAZY: "- Moves slower\n- Energy consumption is lower",
            Personality.ENERGETIC: "- Moves faster\n- Energy consumption is higher",
            Personality.INTROVERT: "- Prefers quieter, less crowded spaces\n- May need more time alone to 'recharge'",
            Personality.GREEDY: "- Gets 50% more anxious when hungry\n- Satisfaction increases more when eating",
            Personality.STUBBORN: "- Only eats favorite food (sushi)\n- May refuse to sleep even when tired"
        }
        return modifiers.get(personality, "No specific modifiers available for this personality.")

    def init_personality_tab(self):
        # Common style for all text elements
        base_font_size = 11
        text_style = f"font-size: {base_font_size}px;"
        header_style = f"font-size: {base_font_size + 4}px; font-weight: bold;"

        # Personality type display
        self.personality_tab_layout.addWidget(QtWidgets.QFrame(frameShape=QtWidgets.QFrame.HLine))
        self.personality_type_label = QtWidgets.QLabel("Squid Personality: ")
        self.personality_type_label.setStyleSheet(header_style)
        self.personality_tab_layout.addWidget(self.personality_type_label)

        # Personality modifier display
        self.personality_modifier_label = QtWidgets.QLabel("Personality Modifier: ")
        self.personality_modifier_label.setStyleSheet(text_style)
        self.personality_tab_layout.addWidget(self.personality_modifier_label)

        # Separator
        self.personality_tab_layout.addWidget(QtWidgets.QFrame(frameShape=QtWidgets.QFrame.HLine))

        # Personality description
        description_label = QtWidgets.QLabel("Description:")
        description_label.setStyleSheet(header_style)
        self.personality_tab_layout.addWidget(description_label)

        self.personality_description = QtWidgets.QTextEdit()
        self.personality_description.setReadOnly(True)
        self.personality_description.setStyleSheet(text_style)
        self.personality_tab_layout.addWidget(self.personality_description)

        # Personality modifiers
        self.modifiers_label = QtWidgets.QLabel("Personality Modifiers:")
        self.modifiers_label.setStyleSheet(header_style)
        self.personality_tab_layout.addWidget(self.modifiers_label)

        self.modifiers_text = QtWidgets.QTextEdit()
        self.modifiers_text.setReadOnly(True)
        self.modifiers_text.setStyleSheet(text_style)
        self.personality_tab_layout.addWidget(self.modifiers_text)

        # Care tips
        self.care_tips_label = QtWidgets.QLabel("Care Tips:")
        self.care_tips_label.setStyleSheet(header_style)
        self.personality_tab_layout.addWidget(self.care_tips_label)

        self.care_tips = QtWidgets.QTextEdit()
        self.care_tips.setReadOnly(True)
        self.care_tips.setStyleSheet(text_style)
        self.personality_tab_layout.addWidget(self.care_tips)

        # Note about personality generation
        note_label = QtWidgets.QLabel("Note: Personality is randomly generated at the start of a new game")
        note_label.setStyleSheet(text_style + "font-style: italic;")
        self.personality_tab_layout.addWidget(note_label)

    def update_brain(self, state):
        """Main update method to distribute state changes to all tabs"""
        if not self.initialized:
            self.initialized = True
            return  # Skip first update
        
        # Update the brain widget first
        self.brain_widget.update_state(state)
        
        # Explicitly update personality tab when personality is available
        if hasattr(self, 'personality_tab') and 'personality' in state:
            self.personality_tab.update_from_brain_state(state)
        
        # Forward updates to each tab that has an update method
        tabs_to_update = ['network_tab', 'learning_tab', 'memory_tab', 'decisions_tab', 'personality_tab', 'about_tab', 'nn_viz_tab']
        for tab_name in tabs_to_update:
            if hasattr(self, tab_name):
                tab = getattr(self, tab_name)
                if hasattr(tab, 'update_from_brain_state'):
                    tab.update_from_brain_state(state)


    def train_hebbian(self):
        self.brain_widget.train_hebbian()
        #self.update_data_table(self.brain_widget.state)
        self.update_training_data_table()

        # Switch to the Console tab
        self.tabs.setCurrentWidget(self.console_tab)

        # Print training results to the console
        print("Hebbian training completed.")
        print("Updated association strengths:")
        for i, neuron1 in enumerate(self.brain_widget.neuron_positions.keys()):
            for j, neuron2 in enumerate(self.brain_widget.neuron_positions.keys()):
                if i < j:
                    strength = self.brain_widget.get_association_strength(neuron1, neuron2)
                    print(f"{neuron1} - {neuron2}: {strength:.2f}")

    def init_training_data_tab(self):
        self.show_overview_checkbox = QtWidgets.QCheckBox("Show Training Process Overview")
        self.show_overview_checkbox.stateChanged.connect(self.toggle_overview)
        self.training_data_tab_layout.addWidget(self.show_overview_checkbox)

        self.overview_label = QtWidgets.QLabel(
            "Training Process Overview:\n\n"
            "1. Data Capture: When 'Capture training data' is checked, the current state of all neurons is recorded each time the brain is stimulated.\n\n"
            "2. Hebbian Learning: The 'Train Hebbian' button applies the Hebbian learning rule to the captured data.\n\n"
            "3. Association Strength: The learning process strengthens connections between neurons that are frequently active together.\n\n"
            "4. Weight Updates: After training, the weights between neurons are updated based on their co-activation patterns.\n\n"
            "5. Adaptive Behavior: Over time, this process allows the brain to adapt its behavior based on input patterns."
        )
        self.overview_label.setWordWrap(True)
        self.overview_label.hide()  # Hide by default
        self.training_data_tab_layout.addWidget(self.overview_label)

        self.training_data_table = QtWidgets.QTableWidget()
        self.training_data_tab_layout.addWidget(self.training_data_table)

        self.training_data_table.setColumnCount(len(self.brain_widget.neuron_positions))
        self.training_data_table.setHorizontalHeaderLabels(list(self.brain_widget.neuron_positions.keys()))

        self.training_data_timer = QtCore.QTimer()
        self.training_data_timer.timeout.connect(self.update_training_data_table)
        self.training_data_timer.start(1000)  # Update every second

        self.checkbox_capture_training_data = QtWidgets.QCheckBox("Capture training data")
        self.checkbox_capture_training_data.stateChanged.connect(self.toggle_capture_training_data)
        self.training_data_tab_layout.addWidget(self.checkbox_capture_training_data)

        self.train_button = self.create_button("Train Hebbian", self.train_hebbian, "#ADD8E6")
        self.train_button.setEnabled(False)  # Initially grey out the train button
        self.training_data_tab_layout.addWidget(self.train_button)

    def toggle_overview(self, state):
        if state == QtCore.Qt.Checked:
            self.overview_label.show()
        else:
            self.overview_label.hide()

    def toggle_capture_training_data(self, state):
        self.brain_widget.toggle_capture_training_data(state)
        if state == QtCore.Qt.Checked:
            os.makedirs('training_data', exist_ok=True)

    def update_training_data_table(self):
        self.training_data_table.setRowCount(len(self.brain_widget.training_data))
        for row, sample in enumerate(self.brain_widget.training_data):
            for col, value in enumerate(sample):
                self.training_data_table.setItem(row, col, QtWidgets.QTableWidgetItem(str(value)))

        if len(self.brain_widget.training_data) > 0:
            self.train_button.setEnabled(True)

        # Save raw data to file
        if self.checkbox_capture_training_data.isChecked():
            with open(os.path.join('training_data', 'raw_data.json'), 'w') as f:
                json.dump(self.brain_widget.training_data, f)

    def save_brain_state(self):
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Save Brain State", "", "JSON Files (*.json)")
        if file_name:
            with open(file_name, 'w') as f:
                json.dump(self.brain_widget.state, f)

    def load_brain_state(self):
        file_name, _ = QtWidgets.QFileDialog.getOpenFileName(self, "Load Brain State", "", "JSON Files (*.json)")
        if file_name:
            with open(file_name, 'r') as f:
                state = json.load(f)
            self.brain_widget.update_state(state)

    def init_console(self):
        self.console_output = QtWidgets.QTextEdit()
        self.console_output.setReadOnly(True)
        self.console_tab_layout.addWidget(self.console_output)
        self.console = ConsoleOutput(self.console_output)

    def create_button(self, text, callback, color):
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        button.setStyleSheet(f"background-color: {color}; border: 1px solid black; padding: 5px;")
        button.setFixedSize(200, 50)
        return button

    def stimulate_brain(self):
        dialog = StimulateDialog(self)
        if dialog.exec_() == QtWidgets.QDialog.Accepted:
            stimulation_values = dialog.get_stimulation_values()
            if stimulation_values is not None:
                self.brain_widget.update_state(stimulation_values)
                if self.tamagotchi_logic:
                    self.tamagotchi_logic.update_from_brain(stimulation_values)
                else:
                    print("Warning: tamagotchi_logic is not set. Brain stimulation will not affect the squid.")


    def update_neural_visualization(self, inputs):
        """Update the neural network visualization with current input values"""
        if not hasattr(self, 'neuron_items') or not self.neuron_items:
            self.setup_neural_visualization()
            return
        
        # Update neuron colors based on activation values
        for neuron, value in inputs.items():
            if neuron in self.neuron_items:
                # Only update numerical values
                if isinstance(value, (int, float)):
                    # Update stored value
                    self.neuron_items[neuron]["value"] = value
                    
                    # Calculate color based on value (0-100)
                    intensity = int(value * 2.55)  # Scale 0-100 to 0-255
                    
                    if neuron in ["hunger", "sleepiness", "anxiety"]:
                        # Red-based for "negative" neurons (more red = higher activation)
                        color = QtGui.QColor(255, 255 - intensity, 255 - intensity)
                    else:
                        # Blue/green-based for "positive" neurons (more color = higher activation)
                        color = QtGui.QColor(100, intensity, 255)
                    
                    # Update neuron ellipse color
                    self.neuron_items[neuron]["shape"].setBrush(QtGui.QBrush(color))
                    
                    # Make neurons pulse slightly based on value
                    scale = 1.0 + (value / 200)  # 1.0 to 1.5
                    rect = self.neuron_items[neuron]["shape"].rect()
                    center_x = rect.x() + rect.width()/2
                    center_y = rect.y() + rect.height()/2
                    new_width = 40 * scale
                    new_height = 40 * scale
                    self.neuron_items[neuron]["shape"].setRect(
                        center_x - new_width/2,
                        center_y - new_height/2,
                        new_width,
                        new_height
                    )
        
        # Update connection line widths and colors based on neuron activations
        for connection, items in self.connection_items.items():
            source, target = connection
            source_value = self.neuron_items.get(source, {}).get("value", 50)
            target_value = self.neuron_items.get(target, {}).get("value", 50)
            
            # Calculate connection strength based on both neuron activations
            # Higher when both neurons are highly activated
            connection_strength = (source_value * target_value) / 10000  # Scale to 0-1
            
            # Update line width and color
            pen_width = 1 + 3 * connection_strength
            
            # Get current brain connection weight if available
            weight = items.get("weight", 0)
            
            # Color based on weight (green for positive, red for negative)
            if weight > 0:
                pen_color = QtGui.QColor(0, 150, 0, 50 + int(200 * connection_strength))
            else:
                pen_color = QtGui.QColor(150, 0, 0, 50 + int(200 * connection_strength))
            
            items["line"].setPen(QtGui.QPen(pen_color, pen_width))
            
            # Update the weight display
            items["text"].setPlainText(f"{weight:.1f}")


    def update_brain_weights(self, weights_data):
        """Update the brain connection weights based on current neural network weights"""
        if not hasattr(self, 'connection_items'):
            return
            
        # Update connection weights
        for (src, dst), weight in weights_data.items():
            # Look for the connection in either direction
            connection = (src, dst)
            if connection in self.connection_items:
                self.connection_items[connection]["weight"] = weight
            else:
                # Try the reverse connection
                connection = (dst, src)
                if connection in self.connection_items:
                    self.connection_items[connection]["weight"] = weight
                    

    def animate_decision_process(self, decision_data):
        """Animate the decision-making process with visual effects"""
        if not hasattr(self, 'processing_animation'):
            return
            
        # Get the decision information
        decision = decision_data.get('final_decision', 'unknown')
        processing_time = decision_data.get('processing_time', 1000)
        
        # Display processing text
        self.processing_text.setText(f"Processing decision ({processing_time}ms)...")
        
        # Start the animation with a brief delay to show processing
        QtCore.QTimer.singleShot(300, lambda: self.highlight_decision_in_ui(decision))


    def highlight_decision_in_ui(self, decision):
        """Highlight the chosen decision in the UI"""
        # Update decision output with animation effect
        self.decision_output.setText(decision.capitalize())
        
        # Flash the decision with a highlight animation
        original_style = self.decision_output.styleSheet()
        self.decision_output.setStyleSheet("font-size: 18px; font-weight: bold; color: white; background-color: green; padding: 5px; border-radius: 5px;")
        
        # Reset after brief highlight
        QtCore.QTimer.singleShot(500, lambda: self.decision_output.setStyleSheet(original_style))
        
        # Update processing text
        self.processing_text.setText(f"Decision made: {decision.capitalize()}")

    def update_learning_status(self, is_active):
        """Update the learning status indicator"""
        if is_active:
            self.learning_status.setText("Learning Status: Active")
            self.learning_status.setStyleSheet("""
                font-size: 14px;
                padding: 5px;
                background-color: #d4edda;
                border-radius: 4px;
                border: 1px solid #c3e6cb;
                color: #155724;
                font-weight: bold;
            """)
        else:
            self.learning_status.setText("Learning Status: Inactive")
            self.learning_status.setStyleSheet("""
                font-size: 14px;
                padding: 5px;
                background-color: #f8f9fa;
                border-radius: 4px;
                border: 1px solid #e9ecef;
                color: #495057;
            """)

    def update_learning_interval(self, seconds):
        """Update the learning interval when spinbox value changes"""
        # Convert seconds to milliseconds (QTimer uses ms)
        interval_ms = seconds * 1000
        
        # Update config
        if hasattr(self.config, 'hebbian'):
            self.config.hebbian['learning_interval'] = interval_ms
        else:
            self.config.hebbian = {'learning_interval': interval_ms}
        
        # Restart timer with new interval
        if hasattr(self, 'hebbian_timer'):
            self.hebbian_timer.setInterval(interval_ms)
            self.brain_widget.last_hebbian_time = time.time()  # Reset countdown
        
        # Log the change
        self.activity_log.append(f"""
        <div style="background-color: #e8f4f8; padding: 8px; margin: 5px; border-radius: 5px;">
            <span style="font-weight: bold;">Learning interval updated</span><br>
            New interval: {seconds} seconds ({interval_ms} ms)
        </div>
        """)
        
        # Force update of countdown
        self.update_countdown()

    def trigger_learning_cycle(self):
        """Force an immediate Hebbian learning cycle"""
        if hasattr(self.brain_widget, 'perform_hebbian_learning'):
            # Record the current state for before/after comparison
            old_weights = {k: v for k, v in self.brain_widget.weights.items()}
            
            # Perform the learning
            self.brain_widget.perform_hebbian_learning()
            
            # Find changed weights
            changes = []
            for k, v in self.brain_widget.weights.items():
                if k in old_weights and abs(v - old_weights[k]) > 0.001:
                    changes.append((k, old_weights[k], v))
            
            # Log the forced learning event
            log_html = f"""
            <div style="background-color: #d4edda; padding: 10px; margin: 8px; border-radius: 5px; border-left: 4px solid #28a745;">
                <span style="font-weight: bold; font-size: 14px;">Manual learning cycle triggered</span><br>
                <span style="color: #555;">Time: {time.strftime('%H:%M:%S')}</span><br>
                <span>Changes detected: {len(changes)}</span>
            """
            
            if changes:
                log_html += "<ul style='margin-top: 5px;'>"
                for (source, target), old_val, new_val in changes[:5]:  # Show top 5 changes
                    direction = "+" if new_val > old_val else ""
                    log_html += f"""
                    <li>
                        <span style="font-weight: bold;">{source} → {target}</span>: 
                        <span style="color: #777;">{old_val:.3f}</span> → 
                        <span style="color: {'green' if new_val > old_val else 'red'}; font-weight: bold;">
                            {new_val:.3f} ({direction}{new_val - old_val:.3f})
                        </span>
                    </li>
                    """
                if len(changes) > 5:
                    log_html += f"<li>...and {len(changes) - 5} more changes</li>"
                log_html += "</ul>"
            else:
                log_html += "<br><span style='font-style: italic;'>No significant weight changes detected</span>"
                
            log_html += "</div>"
            self.activity_log.append(log_html)
            
            # Update the connection table and heatmap
            self.update_connection_table()
            self.update_heatmap()
            self.update_learning_statistics()

    def update_connection_table(self):
        """Update the connection table with current weights"""
        self.connections_view.setRowCount(0)  # Clear existing rows
        
        # Get all weights
        weights = self.brain_widget.weights
        if not weights:
            return
        
        # Get blacklisted neurons to exclude
        excluded_neurons = getattr(self.brain_widget, 'excluded_neurons', ['is_sick', 'is_eating', 'is_sleeping', 'pursuing_food', 'direction'])
        
        # Apply current filter
        filter_text = self.connection_search.text().lower()
        filter_type = self.connection_filter.currentText()
        
        # Add rows to table
        row = 0
        for (source, target), weight in sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True):
            # Skip connections involving blacklisted neurons
            if source in excluded_neurons or target in excluded_neurons:
                continue
                
            # Apply filters
            if filter_type == "Strong Positive" and weight <= 0.5:
                continue
            elif filter_type == "Strong Negative" and weight >= -0.5:
                continue
            elif filter_type == "Weak Connections" and abs(weight) > 0.3:
                continue
            elif filter_type == "New Connections":
                # Check if either neuron is new
                if (source not in self.brain_widget.neurogenesis_data.get('new_neurons', []) and
                    target not in self.brain_widget.neurogenesis_data.get('new_neurons', [])):
                    continue
            
            # Apply text search
            if filter_text and not (filter_text in source.lower() or filter_text in target.lower()):
                continue
                
            # Add the row
            self.connections_view.insertRow(row)
            
            # Source neuron
            source_item = QtWidgets.QTableWidgetItem(source)
            if source in self.brain_widget.neurogenesis_data.get('new_neurons', []):
                source_item.setBackground(QtGui.QColor(255, 255, 200))  # Light yellow for new neurons
            source_item.setFont(QtGui.QFont("Arial", 14))  # Bigger font size
            self.connections_view.setItem(row, 0, source_item)
            
            # Target neuron
            target_item = QtWidgets.QTableWidgetItem(target)
            if target in self.brain_widget.neurogenesis_data.get('new_neurons', []):
                target_item.setBackground(QtGui.QColor(255, 255, 200))
            target_item.setFont(QtGui.QFont("Arial", 14))  # Bigger font size
            self.connections_view.setItem(row, 1, target_item)
            
            # Weight value
            weight_item = QtWidgets.QTableWidgetItem(f"{weight:.3f}")
            if weight > 0.5:
                weight_item.setForeground(QtGui.QColor(0, 150, 0))  # Green for strong positive
            elif weight > 0:
                weight_item.setForeground(QtGui.QColor(0, 100, 0))  # Dark green for mild positive
            elif weight > -0.5:
                weight_item.setForeground(QtGui.QColor(150, 0, 0))  # Dark red for mild negative
            else:
                weight_item.setForeground(QtGui.QColor(200, 0, 0))  # Bright red for strong negative
            weight_item.setFont(QtGui.QFont("Arial", 14))  # Bigger font size
            self.connections_view.setItem(row, 2, weight_item)
            
            # Trend indicator with emoji arrows
            trend_item = QtWidgets.QTableWidgetItem("—")
            if hasattr(self, '_prev_weights') and (source, target) in self._prev_weights:
                prev = self._prev_weights.get((source, target), 0)
                if weight > prev + 0.01:
                    trend_item = QtWidgets.QTableWidgetItem("⬆️")  # Up emoji arrow
                elif weight < prev - 0.01:
                    trend_item = QtWidgets.QTableWidgetItem("⬇️")  # Down emoji arrow
            trend_item.setFont(QtGui.QFont("Arial", 14))  # Bigger font size
            self.connections_view.setItem(row, 3, trend_item)
            
            row += 1
        
        # Store current weights for future trend comparison
        if not hasattr(self, '_prev_weights'):
            self._prev_weights = {}
        self._prev_weights = weights.copy()

    def filter_connections(self):
        """Apply the current filters to the connection table"""
        self.update_connection_table()

    def show_connection_details(self):
        """Show details for the selected connection"""
        selected_items = self.connections_view.selectedItems()
        if not selected_items:
            self.connection_details.clear()
            return
        
        # Get the row (assumes single row selection)
        row = selected_items[0].row()
        
        # Get values from the row
        source = self.connections_view.item(row, 0).text()
        target = self.connections_view.item(row, 1).text()
        weight = float(self.connections_view.item(row, 2).text())
        
        # Generate detailed HTML content
        details_html = f"""
        <div style="font-family: Arial, sans-serif;">
            <h3 style="margin: 5px 0; color: #2c3e50;">Connection Details</h3>
            
            <table style="width: 100%; border-collapse: collapse; margin-top: 10px;">
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 5px; font-weight: bold;">Source Neuron:</td>
                    <td style="padding: 5px;">{source}</td>
                </tr>
                <tr>
                    <td style="padding: 5px; font-weight: bold;">Target Neuron:</td>
                    <td style="padding: 5px;">{target}</td>
                </tr>
                <tr style="background-color: #f8f9fa;">
                    <td style="padding: 5px; font-weight: bold;">Connection Weight:</td>
                    <td style="padding: 5px; font-weight: bold; color: {'green' if weight > 0 else 'red'};">
                        {weight:.4f}
                    </td>
                </tr>
                <tr>
                    <td style="padding: 5px; font-weight: bold;">Connection Strength:</td>
                    <td style="padding: 5px;">
        """
        
        # Add strength description
        if abs(weight) > 0.8:
            details_html += "<span style='color: #2980b9; font-weight: bold;'>Very Strong</span>"
        elif abs(weight) > 0.5:
            details_html += "<span style='color: #3498db; font-weight: bold;'>Strong</span>"
        elif abs(weight) > 0.3:
            details_html += "<span style='color: #7f8c8d;'>Moderate</span>"
        elif abs(weight) > 0.1:
            details_html += "<span style='color: #95a5a6;'>Weak</span>"
        else:
            details_html += "<span style='color: #bdc3c7;'>Very Weak</span>"
            
        details_html += """
                    </td>
                </tr>
            </table>
            
            <div style="margin-top: 15px; font-weight: bold;">Interpretation:</div>
        """
        
        # Add interpretation based on the connection
        if weight > 0:
            details_html += f"""
            <p style="margin: 5px 0;">This is a <span style="color: green;">positive connection</span>. When <b>{source}</b> is active, it will tend to increase the activity of <b>{target}</b>.</p>
            """
        else:
            details_html += f"""
            <p style="margin: 5px 0;">This is an <span style="color: red;">inhibitory connection</span>. When <b>{source}</b> is active, it will tend to decrease the activity of <b>{target}</b>.</p>
            """
        
        # Check if either neuron is from neurogenesis
        if source in self.brain_widget.neurogenesis_data.get('new_neurons', []) or target in self.brain_widget.neurogenesis_data.get('new_neurons', []):
            details_html += """
            <div style="margin-top: 10px; background-color: #fff9c4; padding: 8px; border-radius: 4px;">
                <b>Note:</b> This connection involves a neuron created through neurogenesis!
            </div>
            """
        
        details_html += "</div>"
        
        # Update the details widget
        self.connection_details.setHtml(details_html)

    def apply_neurogenesis_settings(self):
        """Apply changes to neurogenesis settings"""
        # Validate and update the neurogenesis configuration
        if not hasattr(self.config, 'neurogenesis'):
            self.config.neurogenesis = {}
        
        # Get current values from UI
        self.config.neurogenesis['novelty_threshold'] = self.novelty_threshold.value()
        self.config.neurogenesis['stress_threshold'] = self.stress_threshold.value()
        self.config.neurogenesis['reward_threshold'] = self.reward_threshold.value()
        self.config.neurogenesis['cooldown'] = self.cooldown_spinbox.value()
        
        # Log the changes
        self.activity_log.append(f"""
        <div style="background-color: #d4edda; padding: 10px; margin: 8px; border-radius: 5px; border-left: 4px solid #4285f4;">
            <span style="font-weight: bold; font-size: 14px;">Neurogenesis Settings Updated</span><br>
            <span style="color: #555;">Time: {time.strftime('%H:%M:%S')}</span><br>
            <ul style="margin-top: 5px;">
                <li>Novelty Threshold: {self.config.neurogenesis['novelty_threshold']}</li>
                <li>Stress Threshold: {self.config.neurogenesis['stress_threshold']}</li>
                <li>Reward Threshold: {self.config.neurogenesis['reward_threshold']}</li>
                <li>Cooldown Period: {self.config.neurogenesis['cooldown']} seconds</li>
            </ul>
        </div>
        """)
        
        # Update the status display
        self.update_neurogenesis_status()
        
        # Show confirmation message
        QtWidgets.QMessageBox.information(
            self, "Settings Applied", 
            "Neurogenesis settings have been updated successfully."
        )

    def trigger_neurogenesis(self):
        """Trigger neurogenesis by boosting natural trigger values"""
        try:
            if not hasattr(self, 'squid_brain_window') or not self.squid_brain_window:
                self.show_message("Brain window not initialized")
                print("Error: Brain window not initialized")
                return
                
            brain = self.squid_brain_window.brain_widget
            print("Brain widget found")
            
            # Get current neuron count to verify success
            old_neurons = set(brain.neuron_positions.keys())
            print(f"Current neurons: {len(old_neurons)}")
            
            # Get thresholds to ensure we exceed them
            novelty_threshold = brain.neurogenesis_config.get('novelty_threshold', 3) 
            stress_threshold = brain.neurogenesis_config.get('stress_threshold', 0.7)
            reward_threshold = brain.neurogenesis_config.get('reward_threshold', 0.6)
            
            print(f"Neurogenesis thresholds - Novelty: {novelty_threshold}, Stress: {stress_threshold}, Reward: {reward_threshold}")
            
            # Reset cooldown to allow neurogenesis to happen
            if hasattr(brain, 'neurogenesis_data'):
                # Store original for restoration
                original_time = brain.neurogenesis_data.get('last_neuron_time', 0)
                brain.neurogenesis_data['last_neuron_time'] = 0
                print("Neurogenesis cooldown temporarily reset")
            
            # Create state with all triggers boosted significantly above thresholds
            state = {
                # Boost all three pathways to ensure at least one succeeds
                'novelty_exposure': novelty_threshold * 2,  # Double the threshold
                'sustained_stress': stress_threshold * 2,
                'recent_rewards': reward_threshold * 2,
                
                # Add current state values for context
                'hunger': getattr(self.tamagotchi_logic.squid, 'hunger', 50),
                'happiness': getattr(self.tamagotchi_logic.squid, 'happiness', 50),
                'personality': getattr(self.tamagotchi_logic.squid, 'personality', None)
            }
            
            print(f"Submitting state with trigger values: {state}")
            
            # Update state which will trigger natural neurogenesis
            brain.update_state(state)
            
            # Verify if neurogenesis occurred
            new_neurons = set(brain.neuron_positions.keys()) - old_neurons
            
            if new_neurons:
                # Get details of the new neuron(s)
                for new_neuron in new_neurons:
                    # Check if connections were created
                    connections = [k for k in brain.weights.keys() if new_neuron in k]
                    
                    # Generate message with details
                    message = f"Created neuron: {new_neuron} with {len(connections)} connections"
                    self.show_message(message)
                    print(message)
                    print(f"Connections: {connections[:5]}...")
                    
                    # Highlight the new neuron
                    if hasattr(brain, 'neurogenesis_highlight'):
                        brain.neurogenesis_highlight = {
                            'neuron': new_neuron,
                            'start_time': time.time(),
                            'duration': 10.0  # 10 seconds highlight
                        }
                        brain.update()  # Force redraw
                    
                    # Force an immediate hebbian learning cycle to integrate the neuron
                    if hasattr(brain, 'perform_hebbian_learning'):
                        print("Triggering hebbian learning cycle to integrate new neuron")
                        brain.perform_hebbian_learning()
            else:
                self.show_message("No new neurons created - check console for details")
                print("WARNING: Neurogenesis was triggered but no new neurons were created")
                print(f"State submitted: {state}")
                print(f"Neurogenesis config: {brain.neurogenesis_config}")
            
            # Restore original cooldown time
            if hasattr(brain, 'neurogenesis_data') and 'original_time' in locals():
                brain.neurogenesis_data['last_neuron_time'] = original_time
                print("Neurogenesis cooldown restored")
                
        except Exception as e:
            self.show_message(f"Neurogenesis Error: {str(e)}")
            import traceback
            traceback.print_exc()

    def update_heatmap(self):
        """Update the connection weight heatmap visualization"""
        if not hasattr(self, 'heatmap_scene') or not hasattr(self, 'brain_widget'):
            return

        self.heatmap_scene.clear()
        
        try:
            # Get neuron data from brain widget
            neurons = list(self.brain_widget.neuron_positions.keys())
            excluded = getattr(self.brain_widget, 'excluded_neurons', [])
            weights = getattr(self.brain_widget, 'weights', {})
            
            # Filter out excluded neurons
            neurons = [n for n in neurons if n not in excluded]
            if not neurons:
                self.heatmap_scene.addText("No neurons available", QtGui.QFont(), QtCore.QPointF(50, 50))
                return

            # Heatmap parameters
            cell_size = 30
            padding = 50
            max_weight = max(abs(w) for w in weights.values()) if weights else 1.0
            max_weight = max(max_weight, 0.01)  # Prevent division by zero

            # Create heatmap grid
            for i, src in enumerate(neurons):
                for j, dst in enumerate(neurons):
                    if src == dst:
                        continue
                        
                    # Get weight value (check both direction permutations)
                    weight = weights.get((src, dst), weights.get((dst, src), 0))
                    
                    # Calculate color intensity
                    intensity = min(abs(weight) / max_weight, 1.0)
                    if weight > 0:
                        color = QtGui.QColor(0, 0, int(255 * intensity))  # Blue for positive
                    else:
                        color = QtGui.QColor(int(255 * intensity), 0, 0)  # Red for negative
                        
                    # Draw cell
                    rect = QtCore.QRectF(
                        padding + j * cell_size,
                        padding + i * cell_size,
                        cell_size - 1,  # -1 for grid lines
                        cell_size - 1
                    )
                    self.heatmap_scene.addRect(rect, QtGui.QPen(QtCore.Qt.black, 0.5), 
                                            QtGui.QBrush(color))

            # Add labels
            font = QtGui.QFont()
            font.setPointSize(8)
            for idx, neuron in enumerate(neurons):
                # Column labels (top)
                text = self.heatmap_scene.addText(neuron, font)
                text.setPos(padding + idx * cell_size + cell_size/2 - text.boundingRect().width()/2, 
                        padding - 25)
                
                # Row labels (left)
                text = self.heatmap_scene.addText(neuron, font)
                text.setPos(padding - text.boundingRect().width() - 5, 
                        padding + idx * cell_size + cell_size/2 - text.boundingRect().height()/2)

            # Add legend
            self._draw_heatmap_legend(padding, len(neurons) * cell_size + padding + 20)

        except Exception as e:
            print(f"Heatmap error: {str(e)}")
            error_text = self.heatmap_scene.addText("Heatmap unavailable")
            error_text.setPos(50, 50)

    def _draw_heatmap_legend(self, x, y):
        """Add color legend to heatmap"""
        legend_width = 200
        gradient = QtGui.QLinearGradient(0, 0, legend_width, 0)
        gradient.setColorAt(0, QtGui.QColor(255, 0, 0))  # Red
        gradient.setColorAt(0.5, QtGui.QColor(0, 0, 0))   # Black
        gradient.setColorAt(1, QtGui.QColor(0, 0, 255))  # Blue
        
        legend = QtWidgets.QGraphicsRectItem(x, y, legend_width, 20)
        legend.setBrush(QtGui.QBrush(gradient))
        self.heatmap_scene.addItem(legend)
        
        # Add labels - create text items first, then set their positions
        text_min = self.heatmap_scene.addText("-1.0")
        text_min.setPos(x, y + 20)
        
        text_zero = self.heatmap_scene.addText("0")
        text_zero.setPos(x + legend_width//2 - 10, y + 20)
        
        text_max = self.heatmap_scene.addText("+1.0")
        text_max.setPos(x + legend_width - 30, y + 20)

    def get_center_position(self):
        """Calculate center position for new debug neurons"""
        x = sum(p[0] for p in self.neuron_positions.values()) // len(self.neuron_positions)
        y = sum(p[1] for p in self.neuron_positions.values()) // len(self.neuron_positions)
        return (x + random.randint(-50, 50), y + random.randint(-50, 50))
    
    def update_paused_overlay(self):
        """Update the paused state"""
        # Maintain pause state but don't show visual overlay
        if hasattr(self, 'paused_overlay_label'):
            self.paused_overlay_label.setVisible(False)  # Always keep it invisible
            self.paused_overlay_label.deleteLater()
            delattr(self, 'paused_overlay_label')
    
    def update_learning_statistics(self):
        """Update the statistics tab with comprehensive learning metrics"""
        # Get blacklisted neurons
        excluded_neurons = getattr(self.brain_widget, 'excluded_neurons', ['is_sick', 'is_eating', 'is_sleeping', 'pursuing_food', 'direction'])
        
        # Clear the stats layout
        while self.stats_box_layout.count():
            item = self.stats_box_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        
        # Add styled stats
        def add_stat_box(title, content, bg_color="#f8f9fa", icon=None):
            box = QtWidgets.QGroupBox()
            box.setStyleSheet(f"""
                QGroupBox {{
                    background-color: {bg_color};
                    border-radius: 8px;
                    border: 1px solid #dee2e6;
                    margin-top: 15px;
                    padding: 10px;
                }}
                QGroupBox::title {{
                    subcontrol-origin: margin;
                    left: 10px;
                    padding: 0 5px;
                    color: #495057;
                }}
            """)
            
            box_layout = QtWidgets.QVBoxLayout(box)
            
            # Add title with icon if provided
            title_layout = QtWidgets.QHBoxLayout()
            
            if icon:
                icon_label = QtWidgets.QLabel()
                icon_label.setPixmap(QtGui.QPixmap(icon).scaled(24, 24, QtCore.Qt.KeepAspectRatio))
                title_layout.addWidget(icon_label)
            
            title_label = QtWidgets.QLabel(title)
            title_label.setStyleSheet("font-weight: bold; font-size: 14px; color: #212529;")
            title_layout.addWidget(title_label)
            title_layout.addStretch()
            
            box_layout.addLayout(title_layout)
            
            # Add content
            content_widget = QtWidgets.QLabel(content)
            content_widget.setTextFormat(QtCore.Qt.RichText)
            content_widget.setWordWrap(True)
            content_widget.setStyleSheet("font-size: 13px; color: #343a40; margin: 5px;")
            box_layout.addWidget(content_widget)
            
            self.stats_box_layout.addWidget(box)
        
        # 1. Connection Statistics
        # Filter weights to exclude connections involving blacklisted neurons
        filtered_weights = {(src, dst): weight for (src, dst), weight in self.brain_widget.weights.items() 
                        if src not in excluded_neurons and dst not in excluded_neurons}
        
        positive_weights = sum(1 for w in filtered_weights.values() if w > 0)
        negative_weights = sum(1 for w in filtered_weights.values() if w < 0)
        avg_weight = sum(abs(w) for w in filtered_weights.values()) / max(1, len(filtered_weights))
        
        connection_stats = f"""
        <table style='width:100%; margin-top:5px;'>
            <tr>
                <td style='padding:3px;'><b>Total Connections:</b></td>
                <td style='padding:3px;'>{len(filtered_weights)}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Positive Connections:</b></td>
                <td style='padding:3px;'>{positive_weights} ({positive_weights/max(1,len(filtered_weights))*100:.1f}%)</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Negative Connections:</b></td>
                <td style='padding:3px;'>{negative_weights} ({negative_weights/max(1,len(filtered_weights))*100:.1f}%)</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Average Weight Strength:</b></td>
                <td style='padding:3px;'>{avg_weight:.3f}</td>
            </tr>
        </table>
        """
        add_stat_box("Connection Statistics", connection_stats, "#e3f2fd")
        
        # 2. Neuron Statistics
        all_neurons = self.brain_widget.neuron_positions.keys()
        neurons = [n for n in all_neurons if n not in excluded_neurons]
        original_neurons = [n for n in neurons if n in getattr(self.brain_widget, 'original_neuron_positions', {})]
        new_neurons = [n for n in neurons if n in self.brain_widget.neurogenesis_data.get('new_neurons', [])]
        
        neuron_stats = f"""
        <table style='width:100%; margin-top:5px;'>
            <tr>
                <td style='padding:3px;'><b>Learning-Eligible Neurons:</b></td>
                <td style='padding:3px;'>{len(neurons)}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Original Core Neurons:</b></td>
                <td style='padding:3px;'>{len(original_neurons)}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Neurons from Neurogenesis:</b></td>
                <td style='padding:3px;'>{len(new_neurons)}</td>
            </tr>
            <tr>
                <td style='padding:3px;'><b>Excluded System Neurons:</b></td>
                <td style='padding:3px;'>{len(excluded_neurons)}</td>
            </tr>
        </table>
        """
        add_stat_box("Neuron Statistics", neuron_stats, "#e8f5e9")
        
        # 3. Learning Parameters
        if hasattr(self.config, 'hebbian'):
            learning_rate = self.config.hebbian.get('base_learning_rate', 0.1)
            threshold = self.config.hebbian.get('threshold', 0.7)
            decay = self.config.hebbian.get('weight_decay', 0.01)
            
            learning_params = f"""
            <table style='width:100%; margin-top:5px;'>
                <tr>
                    <td style='padding:3px;'><b>Learning Rate:</b></td>
                    <td style='padding:3px;'>{learning_rate}</td>
                </tr>
                <tr>
                    <td style='padding:3px;'><b>Activation Threshold:</b></td>
                    <td style='padding:3px;'>{threshold}</td>
                </tr>
                <tr>
                    <td style='padding:3px;'><b>Weight Decay:</b></td>
                    <td style='padding:3px;'>{decay}</td>
                </tr>
                <tr>
                    <td style='padding:3px;'><b>Learning Interval:</b></td>
                    <td style='padding:3px;'>{self.config.hebbian.get('learning_interval', 30000)/1000} seconds</td>
                </tr>
            </table>
            """
            add_stat_box("Learning Parameters", learning_params, "#fff3e0")
        
        # 4. Strong Influence Neurons
        # Find neurons with strongest outgoing connections
        neuron_influence = {}
        for neuron in neurons:
            outgoing_sum = 0
            outgoing_count = 0
            for (src, dst), weight in filtered_weights.items():
                if src == neuron:
                    outgoing_sum += abs(weight)
                    outgoing_count += 1
            
            if outgoing_count > 0:
                neuron_influence[neuron] = outgoing_sum / outgoing_count
        
        top_influence = sorted(neuron_influence.items(), key=lambda x: x[1], reverse=True)[:5]
        
        influence_stats = "<table style='width:100%; margin-top:5px;'>"
        for neuron, influence in top_influence:
            influence_stats += f"""
            <tr>
                <td style='padding:3px;'><b>{neuron}</b></td>
                <td style='padding:3px;'>{influence:.3f}</td>
            </tr>
            """
        influence_stats += "</table>"
        
        add_stat_box("Top Influential Neurons", influence_stats, "#f3e5f5")
        
        # 5. Recently Created Neurons
        if self.brain_widget.neurogenesis_data.get('new_neurons'):
            new_neurons = [n for n in self.brain_widget.neurogenesis_data.get('new_neurons', []) 
                        if n not in excluded_neurons]
            last_time = self.brain_widget.neurogenesis_data.get('last_neuron_time', 0)
            time_ago = time.time() - last_time
            
            neurogenesis_stats = f"""
            <p>Most recent neuron created <b>{int(time_ago/60)} minutes</b> ago.</p>
            <p>Recent neurons (newest first):</p>
            <ul>
            """
            
            for neuron in reversed(new_neurons[-5:]):
                neurogenesis_stats += f"<li>{neuron}</li>"
            
            neurogenesis_stats += "</ul>"
            
            add_stat_box("Neurogenesis", neurogenesis_stats, "#ffebee")
        
        # Add a stretch to push all boxes to the top
        self.stats_box_layout.addStretch()

    def zoom_heatmap(self, value):
        """Zoom the heatmap view based on slider value"""
        scale = value / 100.0
        
        # Get current transform
        transform = QtGui.QTransform()
        transform.scale(scale, scale)
        
        # Apply new transform
        self.heatmap_view.setTransform(transform)

    

    def export_learning_data(self):
        """Export learning data with all available information"""
        file_name, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Learning Data", "", "HTML Files (*.html);;CSV Files (*.csv);;Text Files (*.txt)")
        
        if not file_name:
            return
            
        try:
            if file_name.endswith('.html'):
                self.export_learning_data_html(file_name)
            elif file_name.endswith('.csv'):
                self.export_learning_data_csv(file_name)
            else:
                self.export_learning_data_text(file_name)
                
            # Show success message
            QtWidgets.QMessageBox.information(
                self, "Export Successful", f"Learning data exported to {file_name}")
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Export Error", f"Error exporting data: {str(e)}")

    def export_learning_data_html(self, file_name):
        """Export learning data as rich HTML report"""
        with open(file_name, 'w') as f:
            # Start HTML document
            f.write("""<!DOCTYPE html>
            <html>
            <head>
                <title>Squid Brain Learning Data</title>
                <style>
                    body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 1200px; margin: 0 auto; padding: 20px; }
                    h1, h2, h3 { color: #2c3e50; }
                    table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }
                    th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
                    th { background-color: #f2f2f2; }
                    tr:hover { background-color: #f5f5f5; }
                    .positive { color: green; }
                    .negative { color: red; }
                    .stats-box { background-color: #f8f9fa; border-radius: 8px; padding: 15px; margin: 15px 0; }
                    .stats-title { font-weight: bold; font-size: 18px; margin-bottom: 10px; }
                    .heatmap { overflow-x: auto; }
                </style>
            </head>
            <body>
                <h1>Squid Brain Learning Data</h1>
                <p>Export time: """ + time.strftime("%Y-%m-%d %H:%M:%S") + """</p>
            """)
            
            # Learning parameters
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Learning Parameters</div>
                    <table>
                        <tr>
                            <th>Parameter</th>
                            <th>Value</th>
                        </tr>
            """)
            
            if hasattr(self.config, 'hebbian'):
                for param, value in self.config.hebbian.items():
                    if param == 'learning_interval':
                        value = f"{value/1000} seconds"
                    f.write(f"<tr><td>{param}</td><td>{value}</td></tr>")
            
            f.write("""
                    </table>
                </div>
            """)
            
            # Neuron information
            neurons = sorted(self.brain_widget.neuron_positions.keys())
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Neurons</div>
                    <p>Total neurons: """ + str(len(neurons)) + """</p>
                    <table>
                        <tr>
                            <th>Neuron</th>
                            <th>Position</th>
                            <th>Type</th>
                            <th>Current Value</th>
                        </tr>
            """)
            
            for neuron in neurons:
                neuron_type = "Original" if neuron in getattr(self.brain_widget, 'original_neuron_positions', {}) else "New"
                value = self.brain_widget.state.get(neuron, 0)
                position = self.brain_widget.neuron_positions.get(neuron, (0, 0))
                
                f.write(f"""
                    <tr>
                        <td>{neuron}</td>
                        <td>({position[0]:.1f}, {position[1]:.1f})</td>
                        <td>{neuron_type}</td>
                        <td>{value:.1f}</td>
                    </tr>
                """)
            
            f.write("""
                    </table>
                </div>
            """)
            
            # Connection weights
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Connection Weights</div>
                    <p>Total connections: """ + str(len(self.brain_widget.weights)) + """</p>
                    <table>
                        <tr>
                            <th>Source</th>
                            <th>Target</th>
                            <th>Weight</th>
                        </tr>
            """)
            
            for (source, target), weight in sorted(self.brain_widget.weights.items(), key=lambda x: abs(x[1]), reverse=True):
                weight_class = "positive" if weight > 0 else "negative"
                f.write(f"""
                    <tr>
                        <td>{source}</td>
                        <td>{target}</td>
                        <td class="{weight_class}">{weight:.3f}</td>
                    </tr>
                """)
            
            f.write("""
                    </table>
                </div>
            """)
            
            # Simple text-based heatmap
            f.write("""
                <div class="stats-box">
                    <div class="stats-title">Weight Heatmap (Text Representation)</div>
                    <p>This is a simplified text representation of the weight matrix.</p>
                    <div class="heatmap">
                        <table>
                            <tr>
                                <th>Source / Target</th>
            """)
            
            # Column headers
            for neuron in neurons:
                f.write(f"<th>{neuron}</th>")
            
            f.write("</tr>")
            
            # Rows with data
            for src in neurons:
                f.write(f"<tr><th>{src}</th>")
                
                for dst in neurons:
                    if src == dst:
                        f.write("<td style='background-color: #f0f0f0;'>—</td>")
                    else:
                        weight = self.brain_widget.weights.get((src, dst), 
                                self.brain_widget.weights.get((dst, src), 0))
                        
                        # Style based on weight
                        if weight > 0:
                            intensity = min(255, int(weight * 255))
                            bg_color = f"rgba(0, {intensity}, 0, 0.2)"
                            text_color = "green"
                        else:
                            intensity = min(255, int(abs(weight) * 255))
                            bg_color = f"rgba({intensity}, 0, 0, 0.2)"
                            text_color = "red"
                        
                        f.write(f"<td style='background-color: {bg_color}; color: {text_color};'>{weight:.2f}</td>")
                
                f.write("</tr>")
            
            f.write("""
                        </table>
                    </div>
                </div>
            """)
            
            # End HTML document
            f.write("""
            </body>
            </html>
            """)

    def export_learning_data_csv(self, file_name):
        """Export learning data as CSV"""
        with open(file_name, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Write neurons section
            writer.writerow(["NEURONS"])
            writer.writerow(["Neuron", "Position X", "Position Y", "Type", "Current Value"])
            
            for neuron in sorted(self.brain_widget.neuron_positions.keys()):
                neuron_type = "Original" if neuron in getattr(self.brain_widget, 'original_neuron_positions', {}) else "New"
                value = self.brain_widget.state.get(neuron, 0)
                position = self.brain_widget.neuron_positions.get(neuron, (0, 0))
                
                writer.writerow([neuron, position[0], position[1], neuron_type, value])
            
            # Blank row
            writer.writerow([])
            
            # Write connections section
            writer.writerow(["CONNECTIONS"])
            writer.writerow(["Source", "Target", "Weight"])
            
            for (source, target), weight in sorted(self.brain_widget.weights.items(), key=lambda x: abs(x[1]), reverse=True):
                writer.writerow([source, target, weight])
            
            # Blank row
            writer.writerow([])
            
            # Write learning parameters
            writer.writerow(["LEARNING PARAMETERS"])
            if hasattr(self.config, 'hebbian'):
                for param, value in self.config.hebbian.items():
                    writer.writerow([param, value])

    def export_learning_data_text(self, file_name):
        """Export learning data as plain text"""
        with open(file_name, 'w') as f:
            f.write("SQUID BRAIN LEARNING DATA\n")
            f.write("=========================\n")
            f.write(f"Export time: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Learning parameters
            f.write("LEARNING PARAMETERS\n")
            f.write("-----------------\n")
            if hasattr(self.config, 'hebbian'):
                for param, value in self.config.hebbian.items():
                    if param == 'learning_interval':
                        value = f"{value/1000} seconds"
                    f.write(f"{param}: {value}\n")
            
            f.write("\n")
            
            # Neuron information
            neurons = sorted(self.brain_widget.neuron_positions.keys())
            f.write(f"NEURONS ({len(neurons)} total)\n")
            f.write("-----------------\n")
            
            for neuron in neurons:
                neuron_type = "Original" if neuron in getattr(self.brain_widget, 'original_neuron_positions', {}) else "New"
                value = self.brain_widget.state.get(neuron, 0)
                position = self.brain_widget.neuron_positions.get(neuron, (0, 0))
                
                f.write(f"{neuron}: Position ({position[0]:.1f}, {position[1]:.1f}), Type: {neuron_type}, Value: {value:.1f}\n")
            
            f.write("\n")
            
            # Connection weights
            f.write(f"CONNECTION WEIGHTS ({len(self.brain_widget.weights)} total)\n")
            f.write("-----------------\n")
            
            for (source, target), weight in sorted(self.brain_widget.weights.items(), key=lambda x: abs(x[1]), reverse=True):
                f.write(f"{source} → {target}: {weight:.3f}\n")

    def clear_learning_log(self):
        """Clear the activity log"""
        reply = QtWidgets.QMessageBox.question(
            self, "Clear Log", 
            "Are you sure you want to clear the learning activity log?",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        
        if reply == QtWidgets.QMessageBox.Yes:
            self.activity_log.clear()

class NeuronInspector(QtWidgets.QDialog):
    def __init__(self, brain_window, parent=None):
        super().__init__(parent)
        self.brain_window = brain_window
        self.setWindowTitle("Neuron Inspector")
        self.setFixedSize(400, 400)
        
        layout = QtWidgets.QVBoxLayout()
        self.setLayout(layout)
        
        # Neuron selector
        self.neuron_combo = QtWidgets.QComboBox()
        layout.addWidget(self.neuron_combo)
        
        # Info display
        self.info_text = QtWidgets.QTextEdit()
        self.info_text.setReadOnly(True)
        layout.addWidget(self.info_text)
        
        # Connection list
        self.connections_list = QtWidgets.QListWidget()
        layout.addWidget(self.connections_list)
        
        # Refresh button
        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self.update_info)
        layout.addWidget(self.refresh_btn)
        
        # Connect to brain widget's neuronClicked signal
        if hasattr(brain_window.brain_widget, 'neuronClicked'):
            brain_window.brain_widget.neuronClicked.connect(self.inspect_neuron)
        
        self.update_neuron_list()

    def update_neuron_list(self):
        if hasattr(self.brain_window, 'brain_widget'):
            brain = self.brain_window.brain_widget
            self.neuron_combo.clear()
            self.neuron_combo.addItems(sorted(brain.neuron_positions.keys()))
            self.neuron_combo.currentIndexChanged.connect(self.update_info)
            self.update_info()

    def inspect_neuron(self, neuron_name):
        """Update the inspector with data for the clicked neuron"""
        # Find the index of the neuron in the combo box
        index = self.neuron_combo.findText(neuron_name)
        if index >= 0:
            self.neuron_combo.setCurrentIndex(index)
        self.update_info()

    def update_info(self):
        """Update all display elements for current neuron"""
        if not hasattr(self.brain_window, 'brain_widget'):
            return
            
        brain = self.brain_window.brain_widget
        neuron = self.neuron_combo.currentText()
        
        if not neuron or neuron not in brain.neuron_positions:
            return
            
        # Get neuron details
        pos = brain.neuron_positions[neuron]
        state = brain.state.get(neuron, 0)
        
        # Determine neuron type
        neuron_type = "Original" if neuron in getattr(brain, 'original_neuron_positions', {}) else "New"
        
        # Update info text
        info_html = f"""
        <h2>{neuron}</h2>
        <p><strong>Position:</strong> ({pos[0]:.1f}, {pos[1]:.1f})</p>
        <p><strong>Current Value:</strong> {state:.1f}</p>
        <p><strong>Type:</strong> {neuron_type}</p>
        """
        self.info_text.setHtml(info_html)
        
        # Update connections list
        self.connections_list.clear()
        
        # Find and display connections
        for (src, dst), weight in brain.weights.items():
            if src == neuron or dst == neuron:
                connection_neuron = dst if src == neuron else src
                direction = "→" if src == neuron else "←"
                item_text = f"{src} {direction} {dst}: {weight:.3f}"
                
                # Color code based on weight
                item = QtWidgets.QListWidgetItem(item_text)
                if weight > 0:
                    item.setForeground(QtGui.QColor(0, 150, 0))  # Green for positive
                else:
                    item.setForeground(QtGui.QColor(200, 0, 0))  # Red for negative
                
                self.connections_list.addItem(item)