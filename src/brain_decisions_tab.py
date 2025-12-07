# src/brain_decisions_tab.py

from PyQt5 import QtCore, QtGui, QtWidgets
from .brain_base_tab import BrainBaseTab
from .display_scaling import DisplayScaling
from .personality import Personality
import time
import hashlib

class DecisionsTab(BrainBaseTab):
    def __init__(self, parent=None, tamagotchi_logic=None, brain_widget=None, config=None, debug_mode=False):
        # FIX: Initialize with None, update later
        self.decision_engine = None
        self.last_decision_hash = None
        self.update_counter = 0  # For performance logging
        
        super().__init__(parent, tamagotchi_logic, brain_widget, config, debug_mode)
        self.initialize_ui()
        
    def set_tamagotchi_logic(self, tamagotchi_logic):
        """CRITICAL FIX: Update decision engine reference when logic is set"""
        super().set_tamagotchi_logic(tamagotchi_logic)
        if tamagotchi_logic and hasattr(tamagotchi_logic, 'squid') and hasattr(tamagotchi_logic.squid, 'decision_engine'):
            self.decision_engine = tamagotchi_logic.squid.decision_engine
            print(f"✅ DecisionsTab: Connected to DecisionEngine ({self.decision_engine is not None})")
        else:
            print("⚠️ DecisionsTab: No DecisionEngine available")

    def initialize_ui(self):
        """Modern, responsive dashboard layout"""
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # Header with gradient and live status
        self.header = self._create_header()
        self.layout.addWidget(self.header)
        
        # Main scrollable timeline
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea { border: none; background: #f5f7fa; }
            QScrollBar:vertical { width: 8px; background: transparent; }
            QScrollBar::handle:vertical { background: #bdc3c7; border-radius: 4px; }
        """)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        self.timeline_widget = QtWidgets.QWidget()
        self.timeline_layout = QtWidgets.QVBoxLayout(self.timeline_widget)
        self.timeline_layout.setSpacing(20)
        self.timeline_layout.setAlignment(QtCore.Qt.AlignTop)
        self.timeline_layout.setContentsMargins(15, 20, 15, 20)
        
        scroll.setWidget(self.timeline_widget)
        self.layout.addWidget(scroll)
        
        # Sticky winner card at bottom
        self.winner_card = self._create_winner_card()
        self.layout.addWidget(self.winner_card)
        
        # Initialize empty state
        self._render_empty_state()

    def _create_header(self):
        """Animated header with personality and connection status"""
        header = QtWidgets.QFrame()
        header.setObjectName("decisionHeader")
        header.setStyleSheet("""
            #decisionHeader {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #667eea, stop:1 #764ba2);
                padding: 20px;
                min-height: 80px;
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(header)
        
        # Title with animation
        title_container = QtWidgets.QWidget()
        title_layout = QtWidgets.QHBoxLayout(title_container)
        title_layout.setSpacing(10)
        
        self.brain_icon = QtWidgets.QLabel("🧠")
        self.brain_icon.setStyleSheet("font-size: 32px;")
        # Add subtle pulsing animation
        self.pulse_animation = QtCore.QPropertyAnimation(self.brain_icon, b"scale")
        self.pulse_animation.setLoopCount(-1)
        
        title = QtWidgets.QLabel("Neural Decision Pathway")
        title.setStyleSheet("font-size: 24px; font-weight: 800; color: white;")
        
        title_layout.addWidget(self.brain_icon)
        title_layout.addWidget(title)
        layout.addWidget(title_container)
        
        layout.addStretch()
        
        # Status indicators
        self.status_container = QtWidgets.QWidget()
        status_layout = QtWidgets.QVBoxLayout(self.status_container)
        status_layout.setSpacing(5)
        
        self.personality_badge = QtWidgets.QLabel("UNKNOWN")
        self.personality_badge.setStyleSheet("""
            background: rgba(255,255,255,0.2);
            color: white;
            padding: 6px 12px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 600;
        """)
        
        self.connection_status = QtWidgets.QLabel("● DISCONNECTED")
        self.connection_status.setStyleSheet("color: #ff6b6b; font-size: 11px; font-weight: bold;")
        
        status_layout.addWidget(self.personality_badge)
        status_layout.addWidget(self.connection_status)
        
        layout.addWidget(self.status_container)
        
        return header

    def _create_winner_card(self):
        """Professional winner card with confidence meter"""
        card = QtWidgets.QFrame()
        card.setObjectName("winnerCard")
        card.setStyleSheet("""
            #winnerCard {
                background: #ffffff;
                border: 2px solid #e3f2fd;
                border-radius: 12px;
                padding: 15px;
                min-height: 90px;
                margin: 0 15px 15px 15px;
            }
        """)
        
        layout = QtWidgets.QHBoxLayout(card)
        
        # Trophy icon with glow effect
        icon = QtWidgets.QLabel("🏆")
        icon.setStyleSheet("font-size: 40px;")
        layout.addWidget(icon)
        
        # Decision text
        decision_layout = QtWidgets.QVBoxLayout()
        
        self.winner_title = QtWidgets.QLabel("Final Action")
        self.winner_title.setStyleSheet("font-size: 14px; color: #666; font-weight: 600;")
        
        self.winner_label = QtWidgets.QLabel("Awaiting Decision...")
        self.winner_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #1976d2;")
        
        decision_layout.addWidget(self.winner_title)
        decision_layout.addWidget(self.winner_label)
        
        # Confidence bar
        self.confidence_container = QtWidgets.QWidget()
        confidence_layout = QtWidgets.QVBoxLayout(self.confidence_container)
        confidence_layout.setSpacing(3)
        
        confidence_header = QtWidgets.QHBoxLayout()
        confidence_label = QtWidgets.QLabel("Confidence:")
        confidence_label.setStyleSheet("font-size: 12px; color: #666;")
        
        self.confidence_value = QtWidgets.QLabel("--")
        self.confidence_value.setStyleSheet("font-size: 12px; font-weight: bold; color: #28a745;")
        
        confidence_header.addWidget(confidence_label)
        confidence_header.addWidget(self.confidence_value)
        confidence_header.addStretch()
        
        self.confidence_bar = QtWidgets.QProgressBar()
        self.confidence_bar.setRange(0, 100)
        self.confidence_bar.setTextVisible(False)
        self.confidence_bar.setStyleSheet("""
            QProgressBar {
                border: none;
                background: #e0e0e0;
                height: 8px;
                border-radius: 4px;
            }
            QProgressBar::chunk {
                border-radius: 4px;
            }
        """)
        
        confidence_layout.addLayout(confidence_header)
        confidence_layout.addWidget(self.confidence_bar)
        
        decision_layout.addWidget(self.confidence_container)
        layout.addLayout(decision_layout, 1)
        
        return card

    def _render_empty_state(self):
        """Show friendly empty state"""
        self._clear_timeline()
        
        empty = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(empty)
        layout.setAlignment(QtCore.Qt.AlignCenter)
        
        icon = QtWidgets.QLabel("🤔")
        icon.setStyleSheet("font-size: 64px; opacity: 0.5;")
        icon.setAlignment(QtCore.Qt.AlignCenter)
        
        text = QtWidgets.QLabel(
            "Awaiting the squid's next thought...\n\n"
            "Make sure the game is running and the squid is active."
        )
        text.setStyleSheet("color: #94a3b8; font-size: 16px; text-align: center;")
        text.setAlignment(QtCore.Qt.AlignCenter)
        text.setWordWrap(True)
        
        layout.addStretch()
        layout.addWidget(icon)
        layout.addWidget(text)
        layout.addStretch()
        
        self.timeline_layout.addWidget(empty)

    def _clear_timeline(self):
        """Clear timeline safely"""
        while self.timeline_layout.count():
            child = self.timeline_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

    def update_from_brain_state(self, state):
        """FIXED: Robust update with connection monitoring"""
        if not hasattr(self, 'decision_engine') or self.decision_engine is None:
            self.connection_status.setText("● DISCONNECTED")
            self.connection_status.setStyleSheet("color: #ff6b6b; font-size: 11px; font-weight: bold;")
            if self.update_counter % 60 == 0:  # Log every ~60 frames
                print("⚠️ DecisionsTab: DecisionEngine not connected")
            self.update_counter += 1
            return
        
        try:
            decision_data = self.decision_engine.get_decision_data()
            if decision_data and isinstance(decision_data, dict):
                # Check if data is new (prevent redundant rendering)
                data_hash = hashlib.md5(str(sorted(decision_data.items())).encode()).hexdigest()
                if data_hash != self.last_decision_hash:
                    self.last_decision_hash = data_hash
                    self._render_decision_timeline(decision_data)
                    self._update_winner_card(decision_data)
                    
                    # Update status
                    self.connection_status.setText("● LIVE")
                    self.connection_status.setStyleSheet("color: #28a745; font-size: 11px; font-weight: bold;")
                    
                    if self.debug_mode and self.update_counter % 30 == 0:
                        print(f"🧠 DecisionsTab: Rendered new decision data (counter: {self.update_counter})")
                
                self.update_counter += 1
            else:
                # Empty but connected
                self.connection_status.setText("● IDLE")
                self.connection_status.setStyleSheet("color: #ffc107; font-size: 11px; font-weight: bold;")
                
        except Exception as e:
            print(f"❌ DecisionsTab.update_from_brain_state error: {e}")
            self.connection_status.setText("● ERROR")
            self.connection_status.setStyleSheet("color: #dc3545; font-size: 11px; font-weight: bold;")

    def _render_decision_timeline(self, data):
        """Render the decision pipeline as interactive cards"""
        self._clear_timeline()
        
        steps = [
            (1, "Sensory Input", "📡", self._render_sensory_step, data.get('inputs', {})),
            (2, "Base Urges", "⚡", self._render_urges_step, data.get('base_weights', {})),
            (3, "Memory & Personality", "🧬", self._render_modifiers_step, data),
            (4, "Final Scoring", "🎯", self._render_scoring_step, data),
        ]
        
        for i, (num, title, icon, renderer, step_data) in enumerate(steps):
            card = self._create_timeline_card(num, title, icon, renderer, step_data)
            self.timeline_layout.addWidget(card)
            
            # Add connector line
            if i < len(steps) - 1:
                self.timeline_layout.addWidget(self._create_connector())

    def _create_timeline_card(self, num, title, icon, renderer, data):
        """Create modern card with expandable content"""
        card = QtWidgets.QFrame()
        card.setObjectName(f"stepCard{num}")
        card.setStyleSheet("""
            QFrame {
                background: #ffffff;
                border: 1px solid #e2e8f0;
                border-radius: 12px;
                padding: 0px;
            }
            QFrame:hover {
                border-color: #cbd5e0;
                background: #f8fafc;
            }
        """)
        
        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # Header (clickable to expand/collapse)
        header = QtWidgets.QWidget()
        header.setObjectName("cardHeader")
        header.setStyleSheet("""
            #cardHeader {
                background: transparent;
                padding: 15px 20px;
                border-radius: 12px 12px 0 0;
            }
            #cardHeader:hover {
                background: #f1f5f9;
            }
        """)
        header_layout = QtWidgets.QHBoxLayout(header)
        
        # Step number badge
        step_num = QtWidgets.QLabel(str(num))
        step_num.setStyleSheet("""
            background: #e3f2fd;
            color: #1976d2;
            font-size: 14px;
            font-weight: bold;
            border-radius: 15px;
            min-width: 30px;
            max-width: 30px;
            height: 30px;
            qproperty-alignment: AlignCenter;
        """)
        
        title_label = QtWidgets.QLabel(f"{icon} {title}")
        title_label.setStyleSheet("font-size: 17px; font-weight: 600; color: #1e293b;")
        
        header_layout.addWidget(step_num)
        header_layout.addWidget(title_label)
        header_layout.addStretch()
        
        # Expand indicator
        self.expand_indicators = getattr(self, 'expand_indicators', {})
        expand_label = QtWidgets.QLabel("▼")
        expand_label.setStyleSheet("color: #94a3b8; font-size: 12px;")
        self.expand_indicators[num] = expand_label
        header_layout.addWidget(expand_label)
        
        layout.addWidget(header)
        
        # Content area (collapsible)
        content = renderer(data)
        content.setObjectName(f"cardContent{num}")
        content.setMinimumHeight(0)
        content.setMaximumHeight(16777215)
        layout.addWidget(content)
        
        # Make header clickable for collapse/expand
        header.mousePressEvent = lambda e, n=num, c=content: self._toggle_card(n, c)
        
        return card

    def _toggle_card(self, num, content):
        """Toggle card expansion state"""
        current_height = content.maximumHeight()
        is_expanded = current_height > 0
        
        if is_expanded:
            content.setMaximumHeight(0)
            self.expand_indicators[num].setText("▶")
        else:
            content.setMaximumHeight(16777215)
            self.expand_indicators[num].setText("▼")

    def _create_connector(self):
        """Elegant connector line"""
        container = QtWidgets.QWidget()
        container.setFixedHeight(20)
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        
        line = QtWidgets.QFrame()
        line.setFrameShape(QtWidgets.QFrame.VLine)
        line.setStyleSheet("background: #e2e8f0; width: 2px; margin: 0 auto;")
        layout.addWidget(line)
        
        arrow = QtWidgets.QLabel("⬇")
        arrow.setStyleSheet("color: #cbd5e0; font-size: 14px; margin: -5px 0;")
        arrow.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(arrow)
        
        return container

    def _render_sensory_step(self, inputs):
        """Visual sensory input rendering"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(15)
        
        if not inputs:
            layout.addWidget(QtWidgets.QLabel("<i>No sensory data available</i>"))
            return widget
        
        # Stats bars
        stats_grid = QtWidgets.QGridLayout()
        stats = ['hunger', 'happiness', 'sleepiness', 'anxiety', 'curiosity', 'cleanliness']
        
        for i, stat in enumerate(stats):
            if stat in inputs:
                self._create_stat_bar(stats_grid, i, stat, inputs[stat])
        
        layout.addLayout(stats_grid)
        
        # Visible objects
        self._add_visible_objects(layout, inputs)
        
        # Status badges
        self._add_status_badges(layout, inputs)
        
        return widget

    def _create_stat_bar(self, grid, index, stat, value):
        """Create a modern stat bar"""
        bar_container = QtWidgets.QWidget()
        bar_layout = QtWidgets.QVBoxLayout(bar_container)
        bar_layout.setSpacing(3)
        
        label = QtWidgets.QLabel(stat.capitalize())
        label.setStyleSheet("font-size: 11px; color: #64748b; font-weight: 500;")
        
        bar = QtWidgets.QProgressBar()
        bar.setRange(0, 100)
        bar.setValue(int(value))
        bar.setFormat(f"%v%")
        
        # Color gradient based on value
        if value > 75:
            color = "#ef4444"  # Red (critical)
        elif value > 50:
            color = "#f59e0b"  # Orange (moderate)
        else:
            color = "#10b981"  # Green (good)
        
        bar.setStyleSheet(f"""
            QProgressBar {{
                border: none;
                background: #f1f5f9;
                height: 8px;
                border-radius: 4px;
            }}
            QProgressBar::chunk {{
                background: {color};
                border-radius: 4px;
            }}
        """)
        
        bar_layout.addWidget(label)
        bar_layout.addWidget(bar)
        grid.addWidget(bar_container, index // 3, index % 3)

    def _add_visible_objects(self, layout, inputs):
        """Add visible objects section"""
        visible = []
        if inputs.get("has_food_visible"): visible.append("🍖 Food")
        if inputs.get("has_rock_visible"): visible.append("🪨 Rock")
        if inputs.get("has_poop_visible"): visible.append("💩 Poop")
        if inputs.get("has_plant_visible"): visible.append("🌿 Plant")
        
        if visible:
            obj_label = QtWidgets.QLabel(f"<b>Visual Field:</b> {', '.join(visible)}")
            obj_label.setStyleSheet("font-size: 13px; color: #374151; padding-top: 10px;")
            layout.addWidget(obj_label)

    def _add_status_badges(self, layout, inputs):
        """Add status badges"""
        status_layout = QtWidgets.QHBoxLayout()
        status_layout.setSpacing(8)
        
        badges = [
            ("🪨 Carrying Rock", inputs.get("carrying_rock"), "#e0f2fe"),
            ("💩 Carrying Poop", inputs.get("carrying_poop"), "#fce7f3"),
            ("🤒 Sick", inputs.get("is_sick"), "#fee2e2"),
            ("💤 Sleeping", inputs.get("is_sleeping"), "#ecfdf5"),
        ]
        
        for text, active, color in badges:
            if active:
                badge = self._create_badge(text, color)
                status_layout.addWidget(badge)
        
        status_layout.addStretch()
        layout.addLayout(status_layout)

    def _render_urges_step(self, weights):
        """Render base urges as sorted bars"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(8)
        
        non_zero = {k: v for k, v in weights.items() if v > 0.01}
        
        if not non_zero:
            layout.addWidget(QtWidgets.QLabel("<i>No active urges - squid is content</i>"))
            return widget
        
        # Sort by weight
        sorted_weights = sorted(non_zero.items(), key=lambda x: x[1], reverse=True)
        
        for action, weight in sorted_weights:
            row = QtWidgets.QHBoxLayout()
            
            # Action name with icon
            icon = self._get_action_icon(action)
            name = QtWidgets.QLabel(f"{icon} {action.replace('_', ' ').title()}")
            name.setStyleSheet("font-size: 13px; min-width: 140px; font-weight: 500;")
            
            # Visual bar
            bar = QtWidgets.QProgressBar()
            bar.setRange(0, int(max(non_zero.values()) * 1.2))
            bar.setValue(int(weight))
            bar.setFormat(f"{weight:.2f}")
            bar.setStyleSheet("""
                QProgressBar {
                    border: none;
                    background: #e2e8f0;
                    height: 6px;
                    border-radius: 3px;
                    text-align: right;
                    padding-right: 5px;
                }
                QProgressBar::chunk {
                    background: #3b82f6;
                    border-radius: 3px;
                }
            """)
            
            row.addWidget(name)
            row.addWidget(bar, 1)
            layout.addLayout(row)
        
        return widget

    def _render_modifiers_step(self, data):
        """Render personality and memory influences"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(12)
        
        # Personality
        personality = data.get('personality', 'UNKNOWN')
        pers_label = QtWidgets.QLabel(f"<b>Personality:</b> {personality}")
        pers_label.setStyleSheet("font-size: 14px; color: #1e293b;")
        layout.addWidget(pers_label)
        
        # Memory influences
        memory_inf = data.get('memory_influences', {})
        if memory_inf:
            layout.addWidget(QtWidgets.QLabel("<b>Memory Effects:</b>"))
            for action, multiplier in memory_inf.items():
                if multiplier != 1.0:
                    effect = "✓ Boosted" if multiplier > 1.0 else "✗ Reduced"
                    color = "#10b981" if multiplier > 1.0 else "#ef4444"
                    label = QtWidgets.QLabel(f"  {effect} {action.replace('_', ' ').title()} (×{multiplier:.2f})")
                    label.setStyleSheet(f"color: {color}; font-size: 12px;")
                    layout.addWidget(label)
        
        # Personality modifiers
        pers_mod = data.get('personality_modifiers', {})
        if pers_mod:
            layout.addWidget(QtWidgets.QLabel("<b>Personality Modifiers:</b>"))
            for action, multiplier in pers_mod.items():
                if multiplier != 1.0:
                    effect = "↑" if multiplier > 1.0 else "↓"
                    label = QtWidgets.QLabel(f"  {effect} {action.replace('_', ' ').title()} (×{multiplier:.2f})")
                    label.setStyleSheet("font-size: 12px;")
                    layout.addWidget(label)
        
        return widget

    def _render_scoring_step(self, data):
        """Render final scoring comparison"""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(widget)
        layout.setSpacing(10)
        
        adj_weights = data.get('adjusted_weights', {})
        final = data.get('final_decision', '')
        
        if not adj_weights:
            layout.addWidget(QtWidgets.QLabel("<i>No scoring data available</i>"))
            return widget
        
        # Show top scores
        top_scores = sorted(adj_weights.items(), key=lambda x: x[1], reverse=True)[:5]
        
        for action, score in top_scores:
            row = QtWidgets.QHBoxLayout()
            
            # Winner highlight
            is_winner = action == final
            if is_winner:
                name = QtWidgets.QLabel(f"🏆 {action.replace('_', ' ').title()}")
                name.setStyleSheet("font-size: 14px; font-weight: bold; color: #059669;")
            else:
                name = QtWidgets.QLabel(action.replace('_', ' ').title())
                name.setStyleSheet("font-size: 13px;")
            
            # Score
            score_label = QtWidgets.QLabel(f"{score:.2f}")
            score_label.setStyleSheet("font-weight: bold;" if is_winner else "")
            
            row.addWidget(name)
            row.addStretch()
            row.addWidget(score_label)
            
            if is_winner:
                winner_badge = QtWidgets.QLabel("✓ CHOSEN")
                winner_badge.setStyleSheet("background: #d1fae5; color: #065f46; padding: 2px 8px; border-radius: 10px; font-size: 11px; font-weight: bold;")
                row.addWidget(winner_badge)
            
            layout.addLayout(row)
        
        return widget

    def _update_winner_card(self, data):
        """Update winner card with animation"""
        final_decision = data.get('final_decision', 'N/A')
        confidence = data.get('confidence', 0.0) * 100
        
        # Update personality
        personality = data.get('personality', 'UNKNOWN')
        self.personality_badge.setText(personality)
        
        # Animate decision change
        if self.winner_label.text() != final_decision.replace('_', ' ').title():
            # Fade out
            self.winner_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #e5e7eb;")
            QtCore.QTimer.singleShot(100, lambda: self._fade_in_winner(final_decision))
        
        # Update confidence
        self.confidence_value.setText(f"{confidence:.1f}%")
        self.confidence_bar.setValue(int(confidence))
        
        # Color code confidence bar
        if confidence > 50:
            self.confidence_bar.setStyleSheet("""
                QProgressBar { border: none; background: #e5e7eb; height: 8px; border-radius: 4px; }
                QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #10b981, stop:1 #34d399); border-radius: 4px; }
            """)
            self.confidence_value.setStyleSheet("font-size: 12px; font-weight: bold; color: #059669;")
        elif confidence > 20:
            self.confidence_bar.setStyleSheet("""
                QProgressBar { border: none; background: #e5e7eb; height: 8px; border-radius: 4px; }
                QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #f59e0b, stop:1 #fbbf24); border-radius: 4px; }
            """)
            self.confidence_value.setStyleSheet("font-size: 12px; font-weight: bold; color: #d97706;")
        else:
            self.confidence_bar.setStyleSheet("""
                QProgressBar { border: none; background: #e5e7eb; height: 8px; border-radius: 4px; }
                QProgressBar::chunk { background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #ef4444, stop:1 #f87171); border-radius: 4px; }
            """)
            self.confidence_value.setStyleSheet("font-size: 12px; font-weight: bold; color: #dc2626;")

    def _fade_in_winner(self, decision):
        """Fade in animation for winner"""
        self.winner_label.setText(decision.replace('_', ' ').title())
        self.winner_label.setStyleSheet("font-size: 22px; font-weight: bold; color: #1976d2;")

    def _create_badge(self, text, bg_color):
        """Create modern badge"""
        badge = QtWidgets.QLabel(text)
        badge.setStyleSheet(f"""
            background: {bg_color};
            color: #1f2937;
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        """)
        return badge

    def _get_action_icon(self, action):
        """Get appropriate icon for action"""
        icon_map = {
            'eating': '🍖',
            'exploring': '🔍',
            'playing': '🎾',
            'sleeping': '💤',
            'approaching_rock': '🪨',
            'throwing_rock': '🎯',
            'approaching_plant': '🌿',
            'approaching_poop': '💩',
            'throwing_poop': '😈',
            'organizing': '📦',
        }
        return icon_map.get(action, '⚡')