"""The Brain Tool's memory views: memory cards, their statistics, decay, and
the associations summary.
"""
import time
from datetime import datetime
from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_ui_utils import set_html


class MemoryViewsMixin:
    """Part of SquidBrainWindow (see brain_tool.py); not used on its own."""

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
        
        set_html(self.overview_stats, stats_html)

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
        set_html(self.memory_stats_text, stats_html)

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
