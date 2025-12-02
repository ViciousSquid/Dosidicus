from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .brain_ui_utils import UiUtils
from datetime import datetime


class MemoryTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
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
        
        # Add tabs
        self.memory_subtabs.addTab(self.stm_tab, "🧠 Short-Term")
        self.memory_subtabs.addTab(self.ltm_tab, "📚 Long-Term")
        self.memory_subtabs.addTab(self.overview_tab, "📊 Overview")
        
        # Configure STM tab
        self.stm_scroll = QtWidgets.QScrollArea()
        self.stm_scroll.setWidgetResizable(True)
        self.stm_content = QtWidgets.QWidget()
        self.stm_content_layout = QtWidgets.QVBoxLayout(self.stm_content)
        self.stm_scroll.setWidget(self.stm_content)
        self.stm_layout.addWidget(self.stm_scroll)
        
        # Configure LTM tab
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
        
        # Add test button
        #self.test_memory_button = QtWidgets.QPushButton("Add Test Memory")
        #self.test_memory_button.clicked.connect(self.add_test_memory)
        #self.overview_layout.addWidget(self.test_memory_button)
        
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
        #print("Updating memory display...")
        try:
            # Get short-term and long-term memories
            if hasattr(self.tamagotchi_logic, 'squid') and hasattr(self.tamagotchi_logic.squid, 'memory_manager'):
                # Get memories
                stm = self.tamagotchi_logic.squid.memory_manager.get_all_short_term_memories()
                ltm = self.tamagotchi_logic.squid.memory_manager.get_all_long_term_memories()
                
                #print(f"Raw short-term memories: {len(stm)}")
                #print(f"Raw long-term memories: {len(ltm)}")
                
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
                
                #print(f"Filtered short-term memories: {len(stm_deduped)}")
                #print(f"Filtered long-term memories: {len(ltm_deduped)}")
                
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
                
                #print("Memory display update completed")
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
        # Basic type check
        if not isinstance(memory, dict):
            return False

        # Ensure it has at least a category
        if 'category' not in memory:
            return False

        # Filter out memories with None or empty values
        if 'value' not in memory or memory.get('value') is None or memory.get('value') == "":
            return False

        # Filter out internal behavior status changes
        if memory.get('category') == 'behavior':
            value = str(memory.get('value', '')).lower()
            formatted_value = str(memory.get('formatted_value', '')).lower()

            # Filter status transition messages
            if 'returned to' in value or 'returned to' in formatted_value:
                return False

            if 'status changed' in value or 'status changed' in formatted_value:
                return False

            if 'after fleeing' in value or 'after fleeing' in formatted_value:
                return False

            # Also filter status-only messages
            if len(value.split()) <= 3 and any(s in value for s in ['status', 'roaming', 'fleeing']):
                return False

        # Filter out interactions with raw JSON or None items
        if memory.get('category') == 'interaction':
            value = str(memory.get('value', ''))
            if '{' in value and '}' in value and 'None' in value:
                return False

        # Filter out memories with timestamp values or keys
        key = memory.get('key', '')
        if isinstance(key, str) and key.replace('.', '', 1).isdigit():
            return False  # Skip timestamp-like keys

        # Always show food and decoration memories (with timestamp filtering)
        if memory.get('category') in ['food', 'decorations', 'interaction']:
            # But filter out timestamp-named items
            formatted_value = memory.get('formatted_value', '')
            if 'interaction with' in formatted_value.lower():
                # Extract the filename part
                parts = formatted_value.split('with')
                if len(parts) > 1:
                    filename = parts[1].strip().split(':')[0].strip()
                    # Check if filename looks like a timestamp (mostly digits with maybe a dot)
                    if any(c.isdigit() for c in filename) and '.' in filename:
                        return False
            return True

        # Get formatted value or raw value
        formatted_value = memory.get('formatted_value', '')
        value = str(memory.get('value', ''))

        # Filter out timestamp-containing values
        if 'timestamp' in formatted_value.lower() or 'timestamp' in value.lower():
            return False

        # If it has a formatted_value, it's likely displayable
        if formatted_value:
            return True

        # If it has a value field with content, it's likely displayable
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
    
    def _create_memory_widget(self, memory, target_layout):
        """Create a memory card widget and add it to the target layout"""
        from .display_scaling import DisplayScaling

        # Create a frame with styled background
        memory_widget = QtWidgets.QFrame()
        memory_widget.setFrameStyle(QtWidgets.QFrame.Box | QtWidgets.QFrame.Raised)
        memory_widget.setLineWidth(DisplayScaling.scale(2))

        # Set color based on memory valence
        bg_color = self._get_memory_color(memory)
        memory_widget.setStyleSheet(f"background-color: {bg_color};")

        # Set scaled size constraints
        memory_widget.setMinimumHeight(DisplayScaling.scale(220))
        memory_widget.setMinimumWidth(DisplayScaling.scale(300))
        memory_widget.setMaximumHeight(DisplayScaling.scale(220))

        # Create layout
        card_layout = QtWidgets.QVBoxLayout(memory_widget)

        # Category header - removed "Category:" prefix
        header = QtWidgets.QLabel(f"{memory.get('category', 'unknown').capitalize()}")
        font = header.font()
        font.setBold(True)
        font.setPointSize(DisplayScaling.font_size(12))
        header.setFont(font)
        card_layout.addWidget(header)

        # Content
        content = memory.get('formatted_value', str(memory.get('value', '')))
        content_label = QtWidgets.QLabel(content)
        content_label.setWordWrap(True)
        content_font = content_label.font()
        content_font.setPointSize(DisplayScaling.font_size(10))
        content_label.setFont(content_font)
        card_layout.addWidget(content_label)

        # Timestamp at bottom
        timestamp = memory.get('timestamp', '')
        if isinstance(timestamp, str):
            try:
                from datetime import datetime
                timestamp = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
            except Exception as e:
                timestamp = str(memory.get('timestamp', ''))

        time_label = QtWidgets.QLabel(f"Time: {timestamp}")
        time_font = time_label.font()
        time_font.setPointSize(DisplayScaling.font_size(8))
        time_label.setFont(time_font)
        card_layout.addWidget(time_label, alignment=QtCore.Qt.AlignRight)

        # Importance indicator (if available)
        if 'importance' in memory:
            importance = memory.get('importance', 1)
            if importance >= 5:
                importance_label = QtWidgets.QLabel("⭐ Important")
                importance_label.setStyleSheet(f"color: #FF5733; font-weight: bold; font-size: {DisplayScaling.font_sze(8)}px;")
                card_layout.addWidget(importance_label, alignment=QtCore.Qt.AlignRight)

        # Add to layout
        target_layout.addWidget(memory_widget)

        # Add click handler to increase importance and potentially transfer to long-term
        memory_widget.mousePressEvent = lambda event, mem=memory: self._on_memory_card_clicked(mem)

        return memory_widget
    
    def _get_memory_color(self, memory):
        """Determine the background color for a memory based on its valence"""
        # Check for "positive:" or "negative:" prefix in the formatted value
        formatted_value = memory.get('formatted_value', '').lower()
        if formatted_value.startswith('positive:'):
            return "#D1FFD1"  # Pastel green for positive
        if formatted_value.startswith('negative:'):
            return "#FFD1DC"  # Pastel red for negative
            
        # Check for negative memories (startled events)
        if memory.get('category') == 'mental_state' and memory.get('key') == 'startled':
            return "#FFD1DC"  # Pastel red for negative

        # ADDED: Check for plant calming effect memory
        if memory.get('key') == 'plant_calming_effect':
            return "#E0FFD1" # Pastel green for positive
        
        # Check for memories with numerical effects
        if isinstance(memory.get('raw_value'), dict):
            # Calculate total effect
            total_effect = sum(float(val) for val in memory['raw_value'].values() 
                            if isinstance(val, (int, float)))
            
            if total_effect > 0:
                return "#D1FFD1"  # Pastel green for positive
            elif total_effect < 0:
                return "#FFD1DC"  # Pastel red for negative
        
        # Default for neutral memories
        return "#FFFACD"  # Pastel yellow

    
    def _create_memory_tooltip(self, memory):
        """Create detailed tooltip for a memory card"""
        tooltip = "<html><body style='white-space:pre'>"
        tooltip += f"<b>Category:</b> {memory.get('category', 'unknown')}\n"
        tooltip += f"<b>Key:</b> {memory.get('key', 'unknown')}\n"
        
        timestamp = memory.get('timestamp', '')
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp).strftime("%H:%M:%S")
            except:
                timestamp = ""
        
        tooltip += f"<b>Time:</b> {timestamp}\n"
        
        if 'importance' in memory:
            tooltip += f"<b>Importance:</b> {memory.get('importance')}\n"
        
        if 'access_count' in memory:
            tooltip += f"<b>Access count:</b> {memory.get('access_count')}\n"
        
        # Add full content
        full_content = memory.get('formatted_value', str(memory.get('value', '')))
        tooltip += f"\n<b>Full Content:</b>\n{full_content}\n"
        
        # Add effects if present
        if isinstance(memory.get('raw_value'), dict):
            tooltip += "\n<b>Effects:</b>\n"
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
            # Increment importance by 1
            memory_manager.update_memory_importance(category, key, 1)
        
        # Check if memory meets transfer criteria
        if self._should_transfer_to_long_term(memory):
            # Transfer memory to long-term
            memory_manager.transfer_to_long_term_memory(category, key)
            print(f"Memory transferred to long-term: {category}, {key}")
            
            # Update displays
            self.update_memory_display()