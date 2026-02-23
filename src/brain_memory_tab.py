from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .brain_ui_utils import UiUtils
from .localisation import Localisation  # Import Localisation
from datetime import datetime


class MemoryTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        # Initialize localisation
        self.loc = Localisation.instance()
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.initialize_ui()
        
    def initialize_ui(self):
        """Initialize the memory tab with sub-tabs and card-based display"""
        # Print debug info
        print(f"MemoryTab initialize_ui: tamagotchi_logic is {self.tamagotchi_logic is not None}")
        
        # Create sub-tabs for different memory types
        self.memory_subtabs = QtWidgets.QTabWidget()
        self.memory_subtabs.setFont(QtGui.QFont("Arial", 12))
        
        # Short-term memory tab
        self.stm_tab = QtWidgets.QWidget()
        self.stm_layout = QtWidgets.QVBoxLayout(self.stm_tab)
        
        # Long-term memory tab
        self.ltm_tab = QtWidgets.QWidget()
        self.ltm_layout = QtWidgets.QVBoxLayout(self.ltm_tab)
        
        # Overview tab
        self.overview_tab = QtWidgets.QWidget()
        self.overview_layout = QtWidgets.QVBoxLayout(self.overview_tab)
        
        # Add tabs with LOCALIZED names
        # We keep the emojis but translate the text
        self.memory_subtabs.addTab(self.stm_tab, f"🧠 {self.loc.get('short_term_memory')}")
        self.memory_subtabs.addTab(self.ltm_tab, f"📚 {self.loc.get('long_term_memory')}")
        self.memory_subtabs.addTab(self.overview_tab, f"📊 {self.loc.get('overview')}")
        
        # Configure STM tab
        self.stm_scroll = QtWidgets.QScrollArea()
        self.stm_scroll.setWidgetResizable(True)
        self.stm_content = QtWidgets.QWidget()
        self.stm_content_layout = QtWidgets.QVBoxLayout(self.stm_content)
        self.stm_scroll.setWidget(self.stm_content)
        self.stm_layout.addWidget(self.stm_scroll)
        
        # Configure LTM tab
        self.ltm_header_label = QtWidgets.QLabel("it happened often...")
        ltm_header_font = self.ltm_header_label.font()
        ltm_header_font.setItalic(True)
        ltm_header_font.setPointSize(11)
        self.ltm_header_label.setFont(ltm_header_font)
        self.ltm_header_label.setAlignment(QtCore.Qt.AlignLeft)
        self.ltm_header_label.setContentsMargins(6, 4, 0, 2)
        self.ltm_layout.addWidget(self.ltm_header_label)

        self.ltm_scroll = QtWidgets.QScrollArea()
        self.ltm_scroll.setWidgetResizable(True)
        self.ltm_content = QtWidgets.QWidget()
        self.ltm_content_layout = QtWidgets.QVBoxLayout(self.ltm_content)
        self.ltm_scroll.setWidget(self.ltm_content)
        self.ltm_layout.addWidget(self.ltm_scroll)
        
        # Configure Overview tab
        self.overview_stats = QtWidgets.QTextEdit()
        self.overview_stats.setReadOnly(True)
        self.overview_layout.addWidget(self.overview_stats)
        
        # Add memory subtabs to main memory tab layout, set to expand and fill
        self.layout.addWidget(self.memory_subtabs)
        self.layout.setStretchFactor(self.memory_subtabs, 1)
        
        # Initialize memory display
        self.update_memory_display()
        
    def update_from_brain_state(self, state):
        """Update memory tab based on brain state changes"""
        # Only update when state changes and tamagotchi_logic exists
        if self.tamagotchi_logic is None:
            print("Warning: tamagotchi_logic is None in update_from_brain_state - memory tab will not update")
            return
            
        self.update_memory_display()

    def set_tamagotchi_logic(self, tamagotchi_logic):
        """Update the tamagotchi_logic reference and refresh memory display"""
        super().set_tamagotchi_logic(tamagotchi_logic)
        print(f"MemoryTab.set_tamagotchi_logic: {tamagotchi_logic is not None}")
        
        # Print debug info to verify squid and memory_manager
        if tamagotchi_logic and hasattr(tamagotchi_logic, 'squid'):
            print(f"squid reference exists: {tamagotchi_logic.squid is not None}")
            if tamagotchi_logic.squid and hasattr(tamagotchi_logic.squid, 'memory_manager'):
                print(f"memory_manager exists")
            else:
                print(f"memory_manager doesn't exist")
        else:
            print(f"squid reference doesn't exist")
        
        # Refresh the memory display if we have a valid reference chain
        if (tamagotchi_logic and 
            hasattr(tamagotchi_logic, 'squid') and 
            tamagotchi_logic.squid and 
            hasattr(tamagotchi_logic.squid, 'memory_manager')):
            self.update_memory_display()
    
    def update_memory_display(self):
        """Update all memory displays"""
        try:
            # Get short-term and long-term memories
            if hasattr(self.tamagotchi_logic, 'squid') and hasattr(self.tamagotchi_logic.squid, 'memory_manager'):
                # Get memories
                stm = self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories()
                ltm = self.tamagotchi_logic.squid.memory_manager.get_all_long_term_memories()
                
                # Filter displayable memories
                stm_filtered = [m for m in stm if self._is_displayable_memory(m)]
                ltm_filtered = [m for m in ltm if self._is_displayable_memory(m)]
                
                # De-duplicate memories based on category and key
                stm_deduped = []
                seen_keys = set()
                for m in stm_filtered:
                    key = (m.get('category', ''), m.get('key', ''))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        stm_deduped.append(m)
                
                ltm_deduped = []
                seen_keys = set()
                for m in ltm_filtered:
                    key = (m.get('category', ''), m.get('key', ''))
                    if key not in seen_keys:
                        seen_keys.add(key)
                        ltm_deduped.append(m)
                
                # Save scroll positions before rebuilding
                stm_scroll_pos = self.stm_scroll.verticalScrollBar().value()
                ltm_scroll_pos = self.ltm_scroll.verticalScrollBar().value()

                # Clear existing content
                self._clear_layout(self.stm_content_layout)
                self._clear_layout(self.ltm_content_layout)
                
                # Add memory cards
                for memory in stm_deduped:
                    self._create_memory_widget(memory, self.stm_content_layout)
                    
                for memory in ltm_deduped:
                    self._create_memory_widget(memory, self.ltm_content_layout)
                
                # Update overview
                self._update_overview_stats(stm_deduped, ltm_deduped)
                
                # Force UI update
                self.stm_content.update()
                self.ltm_content.update()
                
                # Make sure the scroll areas show their content
                self.stm_scroll.setWidget(self.stm_content)
                self.ltm_scroll.setWidget(self.ltm_content)

                # Restore scroll positions
                self.stm_scroll.verticalScrollBar().setValue(stm_scroll_pos)
                self.ltm_scroll.verticalScrollBar().setValue(ltm_scroll_pos)
                
        except Exception as e:
            print(f"Error updating memory tab: {e}")
            import traceback
            traceback.print_exc()

    def _clear_layout(self, layout):
        """Clear all widgets from the given layout"""
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

    def _is_displayable_memory(self, memory):
        """Check if a memory should be displayed in the UI"""
        if not isinstance(memory, dict):
            return False
        if 'category' not in memory:
            return False
        if 'value' not in memory or memory.get('value') is None or memory.get('value') == "":
            return False

        cat = memory.get('category', '').lower()
        key = memory.get('key', '')

        # Always-show categories (no further filtering needed)
        _ALWAYS_SHOW = {
            'play', 'food', 'favourite_plant',
            'mental_state', 'behaviour', 'behavior',
            'environment', 'social', 'observation',
            'travel', 'emotion', 'achievement', 'cleanliness',
        }
        if cat in _ALWAYS_SHOW:
            return True

        # interaction: skip raw dicts with None
        if cat == 'interaction':
            value = str(memory.get('value', ''))
            if '{' in value and '}' in value and 'None' in value:
                return False
            return True

        # decorations: skip timestamp-keyed entries
        if cat == 'decorations':
            if isinstance(key, str) and key.replace('.', '', 1).isdigit():
                return False
            formatted_value = memory.get('formatted_value', '')
            if 'interaction with' in formatted_value.lower():
                parts = formatted_value.split('with')
                if len(parts) > 1:
                    fname = parts[1].strip().split(':')[0].strip()
                    if any(c.isdigit() for c in fname) and '.' in fname:
                        return False
            return True

        # Filter out internal behavior status messages
        if cat == 'behavior':
            value = str(memory.get('value', '')).lower()
            if any(s in value for s in ('returned to', 'status changed', 'after fleeing')):
                return False
            if len(value.split()) <= 3 and any(s in value for s in ('status', 'roaming', 'fleeing')):
                return False

        # Skip timestamp-like keys
        if isinstance(key, str) and key.replace('.', '', 1).isdigit():
            return False

        # Skip timestamp-containing values
        formatted_value = memory.get('formatted_value', '')
        value = str(memory.get('value', ''))
        if 'timestamp' in formatted_value.lower() or 'timestamp' in value.lower():
            return False

        if formatted_value:
            return True
        if value and not value.replace('.', '', 1).isdigit():
            return True

        return False


    def add_test_memory(self):
        """Add a test memory to verify display mechanism"""
        print("Adding test memory...")
        if hasattr(self.tamagotchi_logic, 'squid') and hasattr(self.tamagotchi_logic.squid, 'memory_manager'):
            print("Found memory manager, creating test memory...")
            
            # Create a test memory
            formatted_value = "Test memory: Happiness +10, Satisfaction +15"
            self.tamagotchi_logic.squid.memory_manager.add_short_term_memory(
                'food', 'test_food', formatted_value, importance=10)
            
            # Verify memory was added
            all_memories = self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories()
            print(f"Current memory count: {len(all_memories)}")
            
            # Update the display
            self.update_memory_display()
            print("Test memory added and display updated")
        else:
            print("ERROR: Could not find squid.memory_manager")
    
    # ------------------------------------------------------------------ #
    #  Thumbnail helper                                                    #
    # ------------------------------------------------------------------ #
    def _make_thumbnail(self, image_path, size, angle_deg=0):
        """
        Load *image_path*, scale to *size*×*size* (keeping aspect ratio),
        then rotate by *angle_deg* degrees (small random tilt).
        Returns a QLabel ready to drop into a layout, or None if the
        image can't be loaded.
        """
        import os as _os
        if not image_path or not _os.path.exists(image_path):
            return None

        src = QtGui.QPixmap(image_path)
        if src.isNull():
            return None

        scaled = src.scaled(size, size,
                            QtCore.Qt.KeepAspectRatio,
                            QtCore.Qt.SmoothTransformation)

        if angle_deg != 0:
            # Rotate onto a transparent canvas large enough to avoid clipping
            pad = int(size * 0.45)
            canvas = QtGui.QPixmap(size + pad * 2, size + pad * 2)
            canvas.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(canvas)
            painter.setRenderHint(QtGui.QPainter.SmoothPixmapTransform)
            cx = canvas.width() / 2
            cy = canvas.height() / 2
            painter.translate(cx, cy)
            painter.rotate(angle_deg)
            painter.translate(-scaled.width() / 2, -scaled.height() / 2)
            painter.drawPixmap(0, 0, scaled)
            painter.end()
            scaled = canvas

        label = QtWidgets.QLabel()
        label.setPixmap(scaled)
        label.setFixedSize(scaled.size())
        label.setAlignment(QtCore.Qt.AlignCenter)
        return label

    # ------------------------------------------------------------------ #
    #  Effect-pills helper                                                 #
    # ------------------------------------------------------------------ #
    def _make_effect_pills(self, effects, scale_fn, font_size_fn):
        """Return a QWidget containing coloured stat pills, or None."""
        if not effects:
            return None
        _EMOJI = {
            'happiness': '😊', 'satisfaction': '✨',
            'anxiety': '😰', 'hunger': '🍖', 'energy': '⚡',
            'cleanliness': '🚿', 'curiosity': '🔍',
        }
        pills_widget = QtWidgets.QWidget()
        pills_layout = QtWidgets.QHBoxLayout(pills_widget)
        pills_layout.setContentsMargins(0, 0, 0, 0)
        pills_layout.setSpacing(scale_fn(4))
        for stat, delta in effects.items():
            try:
                delta = float(delta)
            except (TypeError, ValueError):
                continue
            sign = '+' if delta >= 0 else ''
            emoji = _EMOJI.get(stat, '')
            pill = QtWidgets.QLabel(f"{emoji} {stat.capitalize()} {sign}{int(delta)}")
            color = '#D1FFD1' if delta > 0 else '#FFD1DC' if delta < 0 else '#FFFACD'
            pill.setStyleSheet(
                f"background:{color}; border-radius:{scale_fn(8)}px;"
                f" padding:2px {scale_fn(6)}px;"
                f" font-size:{font_size_fn(11)}px;"
            )
            pills_layout.addWidget(pill)
        pills_layout.addStretch()
        return pills_widget

    # ------------------------------------------------------------------ #
    #  Card metadata resolver                                              #
    # ------------------------------------------------------------------ #
    def _card_meta(self, memory):
        """
        Return (header_str, thumb_path_or_None, content_str, effects_dict_or_None)
        for every memory category the squid can produce.
        """
        import os as _os
        cat   = memory.get('category', '').lower()
        key   = memory.get('key', '')
        value = memory.get('value', '')

        # ---- play -------------------------------------------------------
        if cat == 'play' and isinstance(value, dict):
            activity    = value.get('activity', '')
            description = value.get('description', activity.replace('_', ' ').capitalize())
            effects     = value.get('effects', {})
            item_file   = value.get('item', '')   # filename stored at throw time
            _TITLES = {
                'rock_throwing':   'Rock Throwing',
                'urchin_throwing': 'Urchin Throwing',
                'poop_throwing':   'Poop Throwing',
            }
            _DEFAULT_THUMBS = {
                'rock_throwing':   'images/decoration/rock01.png',
                'urchin_throwing': 'images/decoration/rock03.png',
                'poop_throwing':   'images/poop1.png',
            }
            # Prefer the actual item filename if it exists on disk
            thumb = (item_file if item_file and _os.path.exists(item_file)
                     else _DEFAULT_THUMBS.get(activity))
            return (_TITLES.get(activity, 'Play'),
                    thumb,
                    description,
                    effects)

        # ---- food -------------------------------------------------------
        if cat == 'food':
            thumb = f'images/{key}.png'
            return ('Eating', thumb, str(value), None)

        # ---- favourite_plant (long-term) --------------------------------
        if cat == 'favourite_plant':
            plant_name = _os.path.splitext(_os.path.basename(key))[0]
            lines = [plant_name]
            if isinstance(value, dict):
                if value.get('reason'):
                    lines.append(value['reason'])
                if value.get('anxiety_reduction'):
                    lines.append('Reduces anxiety')
            return ('Favourite Plant', key, '\n'.join(lines), None)

        # ---- interaction ------------------------------------------------
        if cat == 'interaction':
            if key == 'plant_contact' and isinstance(value, dict):
                plant_path = value.get('plant_key', '')
                plant_name = _os.path.splitext(_os.path.basename(plant_path))[0]
                return ('Plant Contact', plant_path,
                        f'Touched {plant_name} – feeling calmer', None)
            if 'rock' in key:
                item_path = value.get('item', '') if isinstance(value, dict) else ''
                return ('Picked Up Rock', item_path or 'images/decoration/rock01.png',
                        'Picked up a rock', None)
            if 'poop' in key:
                item_path = value.get('item', '') if isinstance(value, dict) else ''
                return ('Picked Up Poop', item_path or 'images/poop1.png',
                        'Picked up some poop…', None)
            return ('Interaction', None, str(value), None)

        # ---- mental_state -----------------------------------------------
        if cat == 'mental_state':
            if key == 'startled':
                return ('Startled!', 'images/startled.png', str(value), None)
            return ('Mental State', None, str(value), None)

        # ---- behaviour / behavior ---------------------------------------
        if cat in ('behaviour', 'behavior'):
            if key == 'ink_cloud':
                return ('Ink Cloud!', 'images/inkcloud.png', str(value), None)
            if key == 'startle_response':
                return ('Startle Response', 'images/startled.png', str(value), None)
            if key == 'calm_after_startle':
                return ('Calmed Down', None, str(value), None)
            return ('Behaviour', None, str(value), None)

        # ---- environment ------------------------------------------------
        if cat == 'environment':
            if key == 'plant_calming_effect':
                return ('Plant Calming', 'images/plant.png', str(value), None)
            if key == 'window_enlarged':
                return ('More Space!', None, str(value), None)
            if key == 'window_reduced':
                return ('Less Space', None, str(value), None)
            return ('Environment', None, str(value), None)

        # ---- decorations ------------------------------------------------
        if cat == 'decorations':
            thumb = key if (_os.path.exists(key) if key else False) else None
            name  = _os.path.splitext(_os.path.basename(key))[0] if key else 'decoration'
            if isinstance(value, dict):
                content = ', '.join(
                    f"{k.capitalize()} {'+' if v >= 0 else ''}{v:.0f}"
                    for k, v in value.items() if isinstance(v, (int, float))
                ) or str(value)
            else:
                content = str(value)
            return (name.replace('_', ' ').capitalize(), thumb, content, None)

        # ---- social -----------------------------------------------------
        if cat == 'social':
            _SOCIAL = {
                'squid_meeting':        'Met Another Squid',
                'squid_detection':      'Spotted a Squid',
                'squid_lost':           'Lost Sight of Squid',
                'decoration_exchange':  'Decoration Exchange',
                'targeted':             'Targeted by Rock',
            }
            return (_SOCIAL.get(key, 'Social'), None, str(value), None)

        # ---- observation ------------------------------------------------
        if cat == 'observation':
            if 'rock' in key:
                return ('Saw Rock Thrown', 'images/decoration/rock01.png',
                        str(value), None)
            return ('Observation', None, str(value), None)

        # ---- travel -----------------------------------------------------
        if cat == 'travel':
            _TRAVEL = {
                'ate_on_trip':        'Ate on Trip',
                'played_on_trip':     'Played on Trip',
                'completed_journey':  'Journey Complete',
            }
            return (_TRAVEL.get(key, 'Travel'), None, str(value), None)

        # ---- cleanliness ------------------------------------------------
        if cat == 'cleanliness':
            return ('Washed Clean', 'images/icons/clean.png', str(value), None)

        # ---- emotion ----------------------------------------------------
        if cat == 'emotion':
            _EMO = {
                'happy_return':     'Happy Return',
                'calm_return':      'Calm Return',
                'intense_curiosity': 'Intense Curiosity',
                'fear':             'Fear',
            }
            _EMO_THUMBS = {
                'intense_curiosity': 'images/curious.png',
                'fear':              'images/startled.png',
            }
            return (_EMO.get(key, 'Emotion'),
                    _EMO_THUMBS.get(key),
                    str(value), None)

        # ---- achievement ------------------------------------------------
        if cat == 'achievement':
            return (key.replace('_', ' ').capitalize(), None, str(value), None)

        # ---- fallback ---------------------------------------------------
        content = memory.get('formatted_value', str(value))
        return (cat.capitalize(), None, content, None)

    # ------------------------------------------------------------------ #
    #  Card builder                                                        #
    # ------------------------------------------------------------------ #
    def _create_memory_widget(self, memory, target_layout):
        """Create a memory card widget and add it to the target layout"""
        import random as _random
        from .display_scaling import DisplayScaling

        THUMB_SIZE  = DisplayScaling.scale(64)   # bigger thumbnails
        MAX_ANGLE   = 12                          # ± degrees of random tilt

        memory_widget = QtWidgets.QFrame()
        memory_widget.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Raised)
        memory_widget.setLineWidth(DisplayScaling.scale(2))

        bg_color = self._get_memory_color(memory)
        memory_widget.setStyleSheet(f"background-color: {bg_color};")
        memory_widget.setMinimumHeight(DisplayScaling.scale(200))
        memory_widget.setMinimumWidth(DisplayScaling.scale(300))
        memory_widget.setMaximumHeight(DisplayScaling.scale(250))

        card_layout = QtWidgets.QVBoxLayout(memory_widget)
        card_layout.setSpacing(DisplayScaling.scale(4))

        cat_key = memory.get('category', 'unknown').lower()

        # --- resolve metadata -------------------------------------------
        header_text, thumb_path, content_text, effects = self._card_meta(memory)

        # --- header label -----------------------------------------------
        header = QtWidgets.QLabel(header_text)
        hfont = header.font()
        hfont.setBold(True)
        hfont.setPointSize(DisplayScaling.font_size(12))
        header.setFont(hfont)
        card_layout.addWidget(header)

        # --- thumbnail + content row ------------------------------------
        row_widget = QtWidgets.QWidget()
        row_layout = QtWidgets.QHBoxLayout(row_widget)
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(DisplayScaling.scale(8))

        angle = _random.uniform(-MAX_ANGLE, MAX_ANGLE)
        thumb_label = self._make_thumbnail(thumb_path, THUMB_SIZE, angle)
        if thumb_label:
            row_layout.addWidget(thumb_label, alignment=QtCore.Qt.AlignVCenter)

        content_label = QtWidgets.QLabel(content_text)
        content_label.setWordWrap(True)
        cfont = content_label.font()
        cfont.setPointSize(DisplayScaling.font_size(10))
        content_label.setFont(cfont)
        row_layout.addWidget(content_label, stretch=1)
        card_layout.addWidget(row_widget)

        # --- effect pills -----------------------------------------------
        pills = self._make_effect_pills(effects, DisplayScaling.scale,
                                        DisplayScaling.font_size)
        if pills:
            card_layout.addWidget(pills)

        # --- timestamp --------------------------------------------------
        timestamp = memory.get('timestamp', '')
        if isinstance(timestamp, (int, float)) and timestamp > 0:
            from datetime import datetime
            timestamp = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")
        elif isinstance(timestamp, str):
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
            except Exception:
                pass

        time_label = QtWidgets.QLabel(f"{self.loc.get('time_label')} {timestamp}")
        tfont = time_label.font()
        tfont.setPointSize(DisplayScaling.font_size(8))
        time_label.setFont(tfont)
        card_layout.addWidget(time_label, alignment=QtCore.Qt.AlignRight)

        # --- importance star --------------------------------------------
        if memory.get('importance', 0) >= 5:
            imp_label = QtWidgets.QLabel(f"⭐ {self.loc.get('important_label')}")
            imp_label.setStyleSheet(
                f"color:#FF5733; font-weight:bold;"
                f" font-size:{DisplayScaling.font_size(8)}px;"
            )
            card_layout.addWidget(imp_label, alignment=QtCore.Qt.AlignRight)

        # --- wire up ----------------------------------------------------
        target_layout.addWidget(memory_widget)
        memory_widget.setToolTip(self._create_memory_tooltip(memory))
        memory_widget.mousePressEvent = (
            lambda event, mem=memory: self._on_memory_card_clicked(mem)
        )

        # Plant hover tint
        if cat_key == 'favourite_plant':
            plant_key = memory.get('key', '')
            memory_widget.enterEvent = (
                lambda event, k=plant_key: self._tint_scene_plant(k)
            )
            memory_widget.leaveEvent = (
                lambda event, k=plant_key: self._untint_scene_plant(k)
            )

        return memory_widget
    
    def _tint_scene_plant(self, filename):
        """Apply a green tint to the matching plant decoration in the live scene."""
        item = self._find_scene_decoration(filename)
        if item is None:
            return
        try:
            original = item.original_pixmap or item.pixmap()
            if original.isNull():
                return
            tinted = QtGui.QPixmap(original.size())
            tinted.fill(QtCore.Qt.transparent)
            painter = QtGui.QPainter(tinted)
            painter.drawPixmap(0, 0, original)
            painter.setCompositionMode(QtGui.QPainter.CompositionMode_SourceAtop)
            painter.fillRect(tinted.rect(), QtGui.QColor(0, 200, 80, 120))  # semi-transparent green
            painter.end()
            item.setPixmap(tinted)
        except Exception as e:
            print(f"[MemoryTab] Could not tint plant: {e}")

    def _untint_scene_plant(self, filename):
        """Restore the plant decoration in the live scene to its original pixmap."""
        item = self._find_scene_decoration(filename)
        if item is None:
            return
        try:
            original = item.original_pixmap
            if original and not original.isNull():
                item.setPixmap(original)
        except Exception as e:
            print(f"[MemoryTab] Could not restore plant: {e}")

    def _find_scene_decoration(self, filename):
        """Return the ResizablePixmapItem in the scene whose filename matches."""
        try:
            scene = self.tamagotchi_logic.user_interface.scene
            for item in scene.items():
                if hasattr(item, 'filename') and item.filename == filename:
                    return item
        except Exception:
            pass
        return None

    def _get_memory_color(self, memory):
        """Determine the background color for a memory based on its valence"""
        cat = memory.get('category', '').lower()
        key = memory.get('key', '')
        val = memory.get('value', '')

        # Explicit prefix overrides
        formatted_value = memory.get('formatted_value', str(val)).lower()
        if formatted_value.startswith('positive:'):
            return "#D1FFD1"
        if formatted_value.startswith('negative:'):
            return "#FFD1DC"

        # Play activities
        if cat == 'play' and isinstance(val, dict):
            return "#D1FFD1" if val.get('is_positive', True) else "#FFD1DC"

        # Food is always positive
        if cat == 'food':
            return "#D1FFD1"

        # Favourite plant / plant calming
        if cat == 'favourite_plant':
            return "#C8F7C5"
        if key == 'plant_calming_effect':
            return "#E0FFD1"

        # Plant contact = positive
        if cat == 'interaction' and key == 'plant_contact':
            return "#E0FFD1"

        # Startled / scary events
        if cat == 'mental_state' and key == 'startled':
            return "#FFD1DC"
        if cat in ('behaviour', 'behavior') and key in ('ink_cloud', 'startle_response'):
            return "#FFD1DC"
        if cat in ('behaviour', 'behavior') and key == 'calm_after_startle':
            return "#D1FFD1"

        # Environment
        if cat == 'environment':
            if key == 'window_enlarged':
                return "#D1FFD1"
            if key == 'window_reduced':
                return "#FFD1DC"

        # Social
        if cat == 'social':
            if key == 'targeted':
                return "#FFD1DC"
            return "#E8F4FD"  # pale blue

        # Cleanliness always positive
        if cat == 'cleanliness':
            return "#B8D4F0"  # mid-tone cornflower blue — distinct from curiosity #E8F4FD

        # Emotion sub-types
        if cat == 'emotion':
            if key == 'fear':
                return "#FFD1DC"
            if key == 'intense_curiosity':
                return "#E8F4FD"  # pale blue
            if 'happy' in key:
                return "#D1FFD1"
            return "#FFFACD"
        if cat == 'achievement':
            return "#FFF3CD"  # gold-ish

        # Numeric dict values – sum to decide
        if isinstance(val, dict):
            total = sum(float(v) for v in val.values() if isinstance(v, (int, float)))
            if total > 0:
                return "#D1FFD1"
            if total < 0:
                return "#FFD1DC"

        return "#FFFACD"  # default pastel yellow

    
    def _create_memory_tooltip(self, memory):
        """Create detailed tooltip for a memory card with LOCALIZED labels"""
        tooltip = "<html><body style='white-space:pre'>"
        tooltip += f"<b>{self.loc.get('category_label')}</b> {memory.get('category', self.loc.get('unknown'))}\n"
        tooltip += f"<b>{self.loc.get('key_label')}</b> {memory.get('key', self.loc.get('unknown'))}\n"
        
        timestamp = memory.get('timestamp', '')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
            except:
                timestamp = ""
        
        tooltip += f"<b>{self.loc.get('time_label')}</b> {timestamp}\n"
        
        if 'importance' in memory:
            # Reusing 'important_label' but as a header, or 'Importance' if added to loc
            tooltip += f"<b>Importance:</b> {memory.get('importance')}\n"
        
        if 'access_count' in memory:
            tooltip += f"<b>{self.loc.get('access_count')}</b> {memory.get('access_count')}\n"
        
        # Add full content
        full_content = memory.get('formatted_value', str(memory.get('value', '')))
        tooltip += f"\n<b>{self.loc.get('full_content')}</b>\n{full_content}\n"
        
        # Add effects if present
        if isinstance(memory.get('raw_value'), dict):
            tooltip += f"\n<b>{self.loc.get('effects_label')}</b>\n"
            for key, value in memory['raw_value'].items():
                if isinstance(value, (int, float)):
                    tooltip += f"  {key}: {value:+.2f}\n"
        
        tooltip += "</body></html>"
        return tooltip
    
    def _update_overview_stats(self, stm, ltm):
        """Update the overview tab with statistics"""
        # Import datetime correctly at the top of your function
        from datetime import datetime
        
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
        
        # Memory counts - Localized Labels
        stats_html += f"""
        <div class="stat-box">
            <div class="stat-title">📈 {self.loc.get('memory_stats')}</div>
            <table>
                <tr><td>{self.loc.get('short_term_memory')}:</td><td style="padding-left: 20px;">{len(stm)}</td></tr>
                <tr><td>{self.loc.get('long_term_memory')}:</td><td style="padding-left: 20px;">{len(ltm)}</td></tr>
            </table>
        </div>
        """
        
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
            <div class="stat-title">🗂️ {self.loc.get('categories')}</div>
            <table>{category_html}</table>
        </div>
        """
        
        # Fix: Convert timestamp to string format for consistent comparison
        def get_timestamp_key(memory):
            timestamp = memory.get('timestamp', '')
            if isinstance(timestamp, datetime):  # Corrected: Use datetime instead of datetime.datetime
                return timestamp.isoformat()  # Convert datetime to string
            return str(timestamp)  # Ensure string format
        
        # Use the new key function for sorting
        recent_memories = sorted(stm, key=get_timestamp_key, reverse=True)[:5]
        
        self.overview_stats.setHtml(stats_html)

    def _update_memory_importance(self, memory):
        """Increase importance of displayed memory and check for transfer"""
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'squid'):
            return

        # Get memory manager
        memory_manager = self.tamagotchi_logic.squid.memory_manager

        # Only process short-term memories
        all_stm = memory_manager.get_all_short_term_memories()
        matching_memories = [m for m in all_stm if
                            m.get('category') == memory.get('category') and
                            m.get('key') == memory.get('key')]

        if not matching_memories:
            return

        # Increase memory access count and importance
        category = memory.get('category', '')
        key = memory.get('key', '')

        if hasattr(memory_manager, 'update_memory_importance'):
            try:
                # Increment importance by 1
                memory_manager.update_memory_importance(category, key, 1)
            except Exception as e:
                print(f"Error updating memory importance: {e}")

        # Check if memory meets transfer criteria
        if self._should_transfer_to_long_term(memory):
            try:
                # Transfer memory to long-term
                memory_manager.transfer_to_long_term_memory(category, key)
                print(f"Memory transferred to long-term: {category}, {key}")
            except Exception as e:
                print(f"Error transferring memory to long-term: {e}")

            # Update displays
            self.update_memory_display()

    def _should_transfer_to_long_term(self, memory):
        """Check if a memory should be transferred to long-term"""
        # Criteria for transfer:
        
        # 1. Extremely high importance (>= 8) - require higher importance
        if memory.get('importance', 0) >= 8:
            return True
        
        # 2. Repeated access - memory has been accessed frequently (>= 4 times)
        if memory.get('access_count', 0) >= 4:
            return True
        
        # 3. Combination of moderately important and repeated access
        if memory.get('importance', 0) >= 5 and memory.get('access_count', 0) >= 3:
            return True
        
        # 4. Special categories that should be remembered long-term
        if memory.get('category') == 'health' and memory.get('importance', 0) >= 6:
            return True
        
        # Most play activities should not automatically go to long-term
        # unless they're truly significant or repeated
        if memory.get('category') == 'play':
            # Only really exceptional play events go to long-term
            return memory.get('importance', 0) >= 9
        
        return False
    
    def _on_memory_card_clicked(self, memory):
        """Handle memory card clicks - update importance and check for transfer"""
        print(f"Memory card clicked: {memory.get('category')}")
        self._update_memory_importance(memory)
