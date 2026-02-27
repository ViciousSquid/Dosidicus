from datetime import datetime
from PyQt5 import QtCore, QtGui, QtWidgets

class UiUtils:
    @staticmethod
    def create_styled_button(text, callback, color, size=(200, 50), font_size=10):
        """Create a button with consistent styling"""
        button = QtWidgets.QPushButton(text)
        button.clicked.connect(callback)
        button.setStyleSheet(f"""
            QPushButton {{
                background-color: {color}; 
                border: 1px solid black; 
                padding: 5px;
                font-size: {font_size}px;
                border-radius: 5px;
            }}
            QPushButton:hover {{
                background-color: {darken_color(color, 20)};
            }}
        """)
        button.setFixedSize(size[0], size[1])
        return button
    
    @staticmethod
    def format_memory_display(memory):
        """Format a memory dictionary for display with colored boxes based on valence"""
        if not UiUtils.is_displayable_memory(memory):
            return ""
        
        # Get the display text - prefer formatted_value, fall back to value
        display_text = memory.get('formatted_value', str(memory.get('value', '')))
        
        # Skip if the display text contains just a timestamp
        if 'timestamp' in display_text.lower() and len(display_text.split()) < 3:
            return ""
        
        timestamp = memory.get('timestamp', '')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
            except:
                timestamp = ""
        
        # Determine valence and color
        if memory.get('category') == 'mental_state' and memory.get('key') == 'startled':
            interaction_type = "Negative"
            background_color = "#FFD1DC"  # Pastel red
        elif isinstance(memory.get('raw_value'), dict):
            total_effect = sum(float(val) for val in memory['raw_value'].values() 
                            if isinstance(val, (int, float)))
            if total_effect > 0:
                interaction_type = "Positive"
                background_color = "#D1FFD1"  # Pastel green
            elif total_effect < 0:
                interaction_type = "Negative"
                background_color = "#FFD1DC"  # Pastel red
            else:
                interaction_type = "Neutral"
                background_color = "#FFFACD"  # Pastel yellow
        else:
            interaction_type = "Neutral"
            background_color = "#FFFACD"  # Pastel yellow
        
        # Create HTML formatted memory box
        formatted_memory = f"""
        <div style="
            background-color: {background_color}; 
            padding: 8px; 
            margin: 5px; 
            border-radius: 5px;
            border: 1px solid #ccc;
        ">
            <div style="font-weight: bold; margin-bottom: 5px;">{interaction_type}</div>
            <div>{display_text}</div>
            <div style="font-size: 0.8em; color: #555; margin-top: 5px;">{timestamp}</div>
        </div>
        """
        
        return formatted_memory
    
    @staticmethod
    def _is_displayable_memory(self, memory):
        """Check if a memory should be displayed in the UI"""
        if not isinstance(memory, dict):
            return False
        
        # Skip timestamp-only memories (they have numeric keys)
        if isinstance(memory.get('key'), str) and memory['key'].isdigit():
            return False
            
        # Skip memories that don't have a proper category or value
        if not memory.get('category') or not memory.get('value'):
            return False
            
        # Skip memories where the value is just a timestamp number
        if isinstance(memory.get('value'), (int, float)) and 'timestamp' in str(memory['value']).lower():
            return False
            
        # Must have either formatted_value or a displayable string value
        if 'formatted_value' not in memory and not isinstance(memory.get('value'), str):
            return False
            
        return True
    
    @staticmethod
    def create_memory_card(memory):
        """Create a styled HTML memory card"""
        # Determine card style
        bg_color, border_color = UiUtils.get_memory_colors(memory)
        
        # Format card HTML
        card_html = f"""
        <div style="
            background-color: {bg_color};
            border: 2px solid {border_color};
            border-radius: 10px;
            padding: 15px;
            margin: 10px;
            font-size: 10pt;
        ">
            <div style="font-weight: bold; color: #333;">{memory.get('category', 'unknown').capitalize()}</div>
            <div style="font-size: 12pt; margin-top: 8px;">{memory.get('formatted_value', '')[:60]}</div>
            <div style="font-size: 10pt; color: #666; margin-top: 8px;">
                {memory.get('timestamp', '').split(' ')[-1]}
            </div>
        </div>
        """
        
        return card_html

    @staticmethod
    def get_memory_colors(memory):
        """Determine colors based on memory content"""
        if 'positive' in memory.get('tags', []):
            return "#E8F5E9", "#C8E6C9"  # Green shades
        elif 'negative' in memory.get('tags', []):
            return "#FFEBEE", "#FFCDD2"   # Red shades
        elif 'novelty' in memory.get('tags', []):
            return "#FFFDE7", "#FFF9C4"   # Yellow shades
        return "#F5F5F5", "#EEEEEE"       # Default gray

    @staticmethod
    def create_info_box(title, content, icon_path=None, bg_color="#f8f9fa"):
        """Create a styled information box with optional icon"""
        box = QtWidgets.QGroupBox(title)
        box.setStyleSheet(f"""
            QGroupBox {{
                background-color: {bg_color};
                border-radius: 8px;
                border: 1px solid #dee2e6;
                margin-top: 15px;
                padding: 10px;
                font-weight: bold;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
                color: #495057;
            }}
        """)
        
        box_layout = QtWidgets.QVBoxLayout(box)
        
        # Add icon if provided
        if icon_path:
            icon_label = QtWidgets.QLabel()
            icon_label.setPixmap(QtGui.QPixmap(icon_path).scaled(24, 24, QtCore.Qt.KeepAspectRatio))
            box_layout.addWidget(icon_label, alignment=QtCore.Qt.AlignRight)
        
        # Add content
        content_label = QtWidgets.QLabel(content)
        content_label.setTextFormat(QtCore.Qt.RichText)
        content_label.setWordWrap(True)
        content_label.setStyleSheet("font-weight: normal; color: #343a40;")
        box_layout.addWidget(content_label)
        
        return box

# Utility functions
def darken_color(color, amount=20):
    """Darken a hex color by the specified amount"""
    # Remove # if present
    color = color.lstrip('#')
    
    # Convert to RGB
    r, g, b = tuple(int(color[i:i+2], 16) for i in (0, 2, 4))
    
    # Darken
    r = max(0, r - amount)
    g = max(0, g - amount)
    b = max(0, b - amount)
    
    # Convert back to hex
    return f"#{r:02x}{g:02x}{b:02x}"