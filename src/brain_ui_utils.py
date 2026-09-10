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

# =============================================================================
# KEEPING A PANEL WHERE THE READER LEFT IT
# =============================================================================
# Every panel in the Brain Tool is rebuilt on a timer, and a rebuilt panel
# starts at the top. Read a long explanation in the Knowledge tab, or scroll
# back through the memories, and the next refresh threw you back to the first
# line - which made the longer panels effectively unreadable while the game was
# running.
#
# Two shapes of rebuild cause it, and both are handled here:
#
#   a text view rewritten wholesale   setHtml()/setPlainText() replace the
#                                     document, and a new document scrolls to
#                                     the top
#   a scroll area repopulated         the contents are deleted and rebuilt, so
#                                     the scroll area has nothing to be
#                                     scrolled through at the moment it is
#                                     asked to stay put
#
# The best fix for the first is not to rebuild at all: set_html() and
# set_plain_text() compare against what they last wrote and return early when
# nothing has changed, which is the common case on a timer-driven refresh. That
# also keeps any text the reader has SELECTED, which no amount of scroll
# restoration can bring back.

from contextlib import contextmanager

_LAST_SOURCE = "_dosidicus_last_source"


def _scrollbars(widget):
    """(vertical, horizontal) scrollbars, or (None, None) if it has none."""
    getters = (getattr(widget, 'verticalScrollBar', None),
               getattr(widget, 'horizontalScrollBar', None))
    if not callable(getters[0]):
        return None, None
    try:
        return getters[0](), getters[1]() if callable(getters[1]) else None
    except RuntimeError:          # underlying C++ widget already gone
        return None, None


_ACTIVE_RESTORE = "_dosidicus_scroll_restore"


def _apply_until_range_settles(vbar, apply_fn, timeout_ms=400):
    """Run `apply_fn` now, and again each time the scrollbar's range changes.

    Restoring a scroll position immediately after a rebuild does not work: the
    new contents have not been laid out, so the scrollbar's range is still the
    old one (or nothing at all) and setValue clamps against it. Nor is one
    deferred call enough - a QScrollArea needs the layout request to reach it
    AND to resize its contents, which is two turns of the event loop, not one.

    So rather than guessing at a delay, listen for the range actually changing
    and re-apply whenever it does, until it has stopped moving.

    Only one of these may be live per scrollbar. A second refresh arriving
    inside the timeout would otherwise leave the FIRST one still listening,
    and it would happily undo the second one's work using a position measured
    before either of them ran.
    """
    previous = getattr(vbar, _ACTIVE_RESTORE, None)
    if callable(previous):
        previous()

    def stop():
        if getattr(vbar, _ACTIVE_RESTORE, None) is stop:
            setattr(vbar, _ACTIVE_RESTORE, None)
        try:
            vbar.rangeChanged.disconnect(on_range)
        except (TypeError, RuntimeError):
            pass

    def on_range(_minimum, _maximum):
        try:
            apply_fn()
        except RuntimeError:
            stop()

    try:
        apply_fn()
        vbar.rangeChanged.connect(on_range)
        setattr(vbar, _ACTIVE_RESTORE, stop)
        QtCore.QTimer.singleShot(timeout_ms, stop)
    except RuntimeError:
        pass                      # the widget went away mid-refresh


@contextmanager
def preserve_scroll(widget, follow_tail=False):
    """Put `widget` back where it was scrolled to after the block rebuilds it.

    `follow_tail` is for logs: a reader sitting at the bottom is watching for
    new entries and wants to stay at the bottom, while a reader who has
    scrolled up is reading something and wants to stay there.
    """
    vbar, hbar = _scrollbars(widget)
    if vbar is None:
        yield
        return

    at_tail = follow_tail and vbar.value() >= vbar.maximum() - 2
    want_v = vbar.value()
    want_h = hbar.value() if hbar is not None else 0

    def restore():
        vbar.setValue(vbar.maximum() if at_tail else min(want_v, vbar.maximum()))
        if hbar is not None:
            hbar.setValue(min(want_h, hbar.maximum()))

    try:
        yield
    finally:
        _apply_until_range_settles(vbar, restore)


@contextmanager
def hold_position_on_prepend(scroll_area):
    """Keep the reader on the same content while a card is added ABOVE it.

    The learning log inserts each new pair at the top, which pushes everything
    below it down by the height of the new card. Restoring the old scroll VALUE
    is wrong here - the value is a distance from the top, and the top just
    moved - so a reader studying a card three down would find themselves
    looking at a different one every time the squid learned something.

    Instead, measure how much taller the content got and scroll down by exactly
    that. A reader already at the top stays at the top, where the new card is
    the thing they wanted to see.
    """
    vbar, _hbar = _scrollbars(scroll_area)
    if vbar is None:
        yield
        return

    before_value = vbar.value()
    before_max = vbar.maximum()

    def restore():
        if before_value <= 0:
            return                         # at the top: watch the new arrivals
        grew_by = vbar.maximum() - before_max
        if grew_by:
            vbar.setValue(min(before_value + grew_by, vbar.maximum()))

    try:
        yield
    finally:
        _apply_until_range_settles(vbar, restore)


def set_html(view, html, follow_tail=False):
    """setHtml() that leaves the reader where they were. True if it rewrote."""
    if getattr(view, _LAST_SOURCE, None) == html:
        return False
    setattr(view, _LAST_SOURCE, html)
    with preserve_scroll(view, follow_tail):
        view.setHtml(html)
    return True


def set_plain_text(view, text, follow_tail=False):
    """setPlainText() that leaves the reader where they were."""
    if getattr(view, _LAST_SOURCE, None) == text:
        return False
    setattr(view, _LAST_SOURCE, text)
    with preserve_scroll(view, follow_tail):
        view.setPlainText(text)
    return True
