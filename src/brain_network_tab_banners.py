from PyQt5 import QtWidgets, QtCore, QtGui

class BindingOverlay(QtWidgets.QWidget):
    """
    Overlay banners that attach to the NetworkTab's functional stats area.
    Displays loaded bindings and collapses to a 15px strip on click.
    """
    
    def __init__(self, network_tab, target_widget):
        super().__init__(network_tab)
        self.network_tab = network_tab
        self.target_widget = target_widget
        self.is_expanded = True
        self.bindings = []
        
        # Auto-collapse state tracking - only auto-collapse the first time
        self._first_auto_collapse_done = False
        self._auto_collapse_timer = QtCore.QTimer(self)
        self._auto_collapse_timer.setSingleShot(True)
        self._auto_collapse_timer.timeout.connect(self._perform_auto_collapse)
        
        # CRITICAL FIX: Enable CSS background painting
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        
        # UI Setup
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        self.hide() 
        
        # Layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Content Container
        self.content_widget = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        self.content_layout.setSpacing(2)
        
        # Header
        self.header_label = QtWidgets.QLabel("🔗 Bindings Loaded:")
        self.header_label.setStyleSheet("font-weight: bold; font-size: 10pt; color: #1b5e20;")
        self.content_layout.addWidget(self.header_label)
        
        # Scroll area
        self.scroll_area = QtWidgets.QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setStyleSheet("""
            QScrollArea { background: transparent; border: none; }
            QScrollBar:vertical { width: 10px; }
        """)
        # Allow scrolling if list exceeds banner height
        self.scroll_area.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        
        self.scroll_widget = QtWidgets.QWidget()
        self.scroll_widget.setStyleSheet("background: transparent;")
        self.scroll_layout = QtWidgets.QVBoxLayout(self.scroll_widget)
        self.scroll_layout.setContentsMargins(2, 0, 0, 0)
        self.scroll_layout.setSpacing(4)
        
        self.scroll_area.setWidget(self.scroll_widget)
        self.content_layout.addWidget(self.scroll_area)
        
        self.main_layout.addWidget(self.content_widget)
        
        # Visual Style - Sage Green (#a4d4a3)
        self.setStyleSheet("""
            BindingOverlay {
                background-color: #a4d4a3;
                border: 1px solid #689f38;
                border-radius: 5px;
            }
            QLabel {
                color: #1b5e20;  /* Dark green text for contrast */
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 9pt;
            }
        """)

        # Shadow effect
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        if self.network_tab:
            self.network_tab.installEventFilter(self)

    def _perform_auto_collapse(self):
        """Perform the auto-collapse if banner is still expanded after first show"""
        if self.is_expanded:
            self.animate_toggle()

    def update_bindings(self, bindings_list):
        """Populate the overlay with a list of binding widgets."""
        if not bindings_list:
            self.hide()
            return

        # Force target visibility
        if self.target_widget and not self.target_widget.isVisible():
            self.target_widget.setVisible(True)

        # Clear old items
        while self.scroll_layout.count():
            item = self.scroll_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        # Add new items
        for binding in bindings_list:
            # Create a container widget for the row
            row_widget = QtWidgets.QWidget()
            row_layout = QtWidgets.QHBoxLayout(row_widget)
            row_layout.setContentsMargins(0, 0, 0, 0)
            row_layout.setSpacing(5)
            
            if isinstance(binding, dict):
                n_name = binding.get('neuron_name', binding.get('neuron', '?'))
                raw_action = binding.get('output_hook', binding.get('action', binding.get('action_name', '?')))
                
                # Clean action name
                if isinstance(raw_action, str) and raw_action.startswith('neuron_output_'):
                    action = raw_action.replace('neuron_output_', '')
                else:
                    action = raw_action
                
                # Logic Details
                threshold = float(binding.get('threshold', 0))
                mode = binding.get('trigger_mode', 'rising')
                params = binding.get('hook_params', {})
                
                # Map mode to symbol
                mode_symbols = {
                    'rising': '↑',    # Crossing up
                    'falling': '↓',   # Crossing down
                    'above': '>',     # While above
                    'below': '<',     # While below
                    'change': 'Δ'     # On change
                }
                symbol = mode_symbols.get(mode, '>')

                # 1. Text Label (Neuron > Threshold -> Action)
                text_lbl = QtWidgets.QLabel(f"{n_name} <b>{symbol} {threshold:g}</b> ➡ {action}")
                text_lbl.setTextFormat(QtCore.Qt.RichText)
                row_layout.addWidget(text_lbl)

                # 2. Parameter Visualization
                if params and all(k in params for k in ('red', 'green', 'blue')):
                    # It's a color binding - Show 15x15 box
                    try:
                        r = int(params['red'])
                        g = int(params['green'])
                        b = int(params['blue'])
                        
                        color_box = QtWidgets.QFrame()
                        color_box.setFixedSize(15, 15)
                        # Dark border for visibility on green background
                        color_box.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: 1px solid #1b5e20; border-radius: 2px;")
                        row_layout.addWidget(color_box)
                    except ValueError:
                        pass # Invalid color data, skip box
                elif params:
                    # Non-color params, show generic text
                    import json
                    p_text = json.dumps(params).replace('"', '').replace('{', '').replace('}', '')
                    if p_text:
                        p_lbl = QtWidgets.QLabel(f"[{p_text}]")
                        p_lbl.setStyleSheet("font-size: 8pt; color: #2e7d32;")
                        row_layout.addWidget(p_lbl)
            else:
                lbl = QtWidgets.QLabel(str(binding))
                row_layout.addWidget(lbl)
            
            row_layout.addStretch() # Align contents to left
            self.scroll_layout.addWidget(row_widget)
            
        self.scroll_layout.addStretch()
        self.bindings = bindings_list
        
        self.show()
        self.raise_()
        
        # Align slightly after show to ensure correct geometry
        QtCore.QTimer.singleShot(10, self.align_to_target)
        
        # Auto-collapse after 6 seconds on first show only
        if not self._first_auto_collapse_done:
            self._first_auto_collapse_done = True
            self._auto_collapse_timer.start(6000)  # 6 seconds
        
        # Ensure banner is expanded when new bindings are loaded
        if not self.is_expanded:
            self.animate_toggle()

    def align_to_target(self):
        """Aligns the overlay to the target widget."""
        if not self.target_widget or not self.target_widget.isVisible():
            return

        # Get the target widget's geometry in its immediate parent's coordinates
        target_geo = self.target_widget.geometry()
        
        # CRITICAL FIX: Map coordinates from target's parent (functional_stats_area) 
        # to network_tab's coordinate system
        parent = self.target_widget.parent()
        if parent:
            # Map top-left and bottom-right corners to network_tab coordinates
            top_left = parent.mapTo(self.network_tab, target_geo.topLeft())
            bottom_right = parent.mapTo(self.network_tab, target_geo.bottomRight())
            target_geo = QtCore.QRect(top_left, bottom_right)
        
        # Apply the correctly-mapped geometry
        if self.is_expanded:
            self.setGeometry(target_geo)
        else:
            # Collapsed state - show as a narrow strip
            self.setGeometry(
                target_geo.x(), 
                target_geo.y(), 
                15, 
                target_geo.height()
        )

    def eventFilter(self, source, event):
        if source == self.network_tab and event.type() == QtCore.QEvent.Resize:
            self.align_to_target()
        return super().eventFilter(source, event)

    def mousePressEvent(self, event):
        """Cancel auto-collapse timer if user manually toggles"""
        self._auto_collapse_timer.stop()
        self.animate_toggle()
        super().mousePressEvent(event)

    def animate_toggle(self):
        if not self.target_widget:
            return

        # CRITICAL FIX: Get correctly mapped geometry (same as align_to_target)
        target_geo = self.target_widget.geometry()
        parent = self.target_widget.parent()
        if parent:
            top_left = parent.mapTo(self.network_tab, target_geo.topLeft())
            bottom_right = parent.mapTo(self.network_tab, target_geo.bottomRight())
            target_geo = QtCore.QRect(top_left, bottom_right)

        start_rect = self.geometry()
        
        if self.is_expanded:
            # Collapse to narrow strip
            end_rect = QtCore.QRect(target_geo.x(), target_geo.y(), 15, target_geo.height())
            self.content_widget.hide()
        else:
            # Expand to full size
            end_rect = target_geo
            QtCore.QTimer.singleShot(50, self.content_widget.show)

        self.anim = QtCore.QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(300)
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(end_rect)
        self.anim.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
        self.anim.start()

        self.is_expanded = not self.is_expanded
        self.update()

    def paintEvent(self, event):
        """Draw grip dots when collapsed."""
        super().paintEvent(event)
        if not self.is_expanded:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(QtCore.Qt.NoPen)
            # Dark green dots to match the text/theme
            painter.setBrush(QtGui.QColor(27, 94, 32, 180)) 
            
            cx = self.width() / 2
            cy = self.height() / 2
            for offset in [-10, 0, 10]:
                painter.drawEllipse(QtCore.QPointF(cx, cy + offset), 2.0, 2.0)


class PlaceholderBanner(QtWidgets.QWidget):
    """
    A placeholder banner with a pastel yellow background.
    Can be used for warnings, system notifications, or future features.
    """
    
    def __init__(self, network_tab, target_widget):
        super().__init__(network_tab)
        self.network_tab = network_tab
        self.target_widget = target_widget
        self.is_expanded = True
        
        self.setAttribute(QtCore.Qt.WA_StyledBackground, True)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, False)
        
        # Layout
        self.main_layout = QtWidgets.QVBoxLayout(self)
        self.main_layout.setContentsMargins(5, 5, 5, 5)
        
        # Content
        self.content_widget = QtWidgets.QWidget()
        self.content_layout = QtWidgets.QVBoxLayout(self.content_widget)
        self.content_layout.setContentsMargins(0, 0, 0, 0)
        
        self.label = QtWidgets.QLabel("⚠️ System Notification")
        self.label.setWordWrap(True)
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.content_layout.addWidget(self.label)
        
        self.main_layout.addWidget(self.content_widget)
        
        # Style - Pastel Yellow (#fff9c4)
        self.setStyleSheet("""
            PlaceholderBanner {
                background-color: #fff9c4;
                border: 1px solid #fbc02d;
                border-radius: 5px;
            }
            QLabel {
                color: #f57f17;
                font-weight: bold;
                font-size: 10pt;
            }
        """)

        # Shadow
        shadow = QtWidgets.QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(10)
        shadow.setColor(QtGui.QColor(0, 0, 0, 80))
        shadow.setOffset(0, 2)
        self.setGraphicsEffect(shadow)

        if self.network_tab:
            self.network_tab.installEventFilter(self)

    def set_message(self, text):
        self.label.setText(text)
        self.show()
        self.raise_()
        QtCore.QTimer.singleShot(10, self.align_to_target)

    def align_to_target(self):
        if not self.target_widget or not self.target_widget.isVisible():
            return
        
        # Note: If using multiple banners, you may need to offset Y here
        target_geo = self.target_widget.geometry()
        
        if self.is_expanded:
            self.setGeometry(target_geo)
        else:
            self.setGeometry(target_geo.x(), target_geo.y(), 15, target_geo.height())

    def eventFilter(self, source, event):
        if source == self.network_tab and event.type() == QtCore.QEvent.Resize:
            self.align_to_target()
        return super().eventFilter(source, event)

    def mousePressEvent(self, event):
        self.animate_toggle()
        super().mousePressEvent(event)

    def animate_toggle(self):
        if not self.target_widget: return
        
        target_geo = self.target_widget.geometry()
        start_rect = self.geometry()
        
        if self.is_expanded:
            end_rect = QtCore.QRect(target_geo.x(), target_geo.y(), 15, target_geo.height())
            self.content_widget.hide()
        else:
            end_rect = target_geo
            QtCore.QTimer.singleShot(50, self.content_widget.show)

        self.anim = QtCore.QPropertyAnimation(self, b"geometry")
        self.anim.setDuration(300)
        self.anim.setStartValue(start_rect)
        self.anim.setEndValue(end_rect)
        self.anim.setEasingCurve(QtCore.QEasingCurve.InOutQuad)
        self.anim.start()

        self.is_expanded = not self.is_expanded
        self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if not self.is_expanded:
            painter = QtGui.QPainter(self)
            painter.setRenderHint(QtGui.QPainter.Antialiasing)
            painter.setPen(QtCore.Qt.NoPen)
            painter.setBrush(QtGui.QColor(245, 127, 23, 180)) # Dark orange dots
            
            cx = self.width() / 2
            cy = self.height() / 2
            for offset in [-10, 0, 10]:

                painter.drawEllipse(QtCore.QPointF(cx, cy + offset), 2.0, 2.0)