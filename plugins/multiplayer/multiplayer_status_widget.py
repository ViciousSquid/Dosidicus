from PyQt5 import QtCore, QtGui, QtWidgets
import time

class MultiplayerStatusWidget(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("MultiplayerStatusWidget")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        # Keep track of peers and connection status
        self.connection_active = False
        self.node_id = "Unknown"
        self.peers = []
        self.last_activity = {}
        
        # Setup UI
        self.setup_ui()
        
        # Update timer
        self.update_timer = QtCore.QTimer(self)
        self.update_timer.timeout.connect(self.update_display)
        self.update_timer.start(1000)  # Update every second
    
    def setup_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        
        # Create a frame with semi-transparent background
        frame = QtWidgets.QFrame(self)
        frame.setStyleSheet("""
            QFrame {
                background-color: rgba(0, 0, 0, 170);
                border-radius: 12px;
                color: white;
                border: 1px solid rgba(255, 255, 255, 100);
            }
        """)
        frame_layout = QtWidgets.QVBoxLayout(frame)
        
        # Title with improved styling
        title_label = QtWidgets.QLabel("🌐 Multiplayer")
        title_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 14px;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        frame_layout.addWidget(title_label)
        
        # Status header with icon
        status_layout = QtWidgets.QHBoxLayout()
        status_icon = QtWidgets.QLabel("⚠️")  # Default to warning icon
        self.status_icon = status_icon
        status_layout.addWidget(status_icon)
        
        self.status_label = QtWidgets.QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #FF6666; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        # Node ID display
        self.node_id_label = QtWidgets.QLabel("Node ID: Unknown")
        self.node_id_label.setStyleSheet("color: #DDDDDD; margin-left: 10px;") # Style as needed
        status_layout.addWidget(self.node_id_label)
        status_layout.addStretch()
        frame_layout.addLayout(status_layout)
        
        # Add activity log
        self.activity_log = QtWidgets.QListWidget()
        self.activity_log.setMaximumHeight(120)
        self.activity_log.setStyleSheet("""
            QListWidget {
                background-color: rgba(0, 0, 0, 100);
                border: 1px solid #444444;
                border-radius: 5px;
                color: white;
            }
            QListWidget::item {
                padding: 2px;
            }
        """)
        frame_layout.addWidget(self.activity_log)

        # Peers display
        self.peers_label = QtWidgets.QLabel("Connected Peers: 0")
        self.peers_label.setStyleSheet("color: #DDDDDD; margin-top: 5px;")
        frame_layout.addWidget(self.peers_label)

        self.peers_list = QtWidgets.QListWidget()
        self.peers_list.setMaximumHeight(80) # Adjust as needed
        self.peers_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(0, 0, 0, 80);
                border: 1px solid #333333;
                border-radius: 5px;
                color: white;
            }
            QListWidget::item {
                padding: 2px;
            }
        """)
        frame_layout.addWidget(self.peers_list)
        
        # Add minimize/expand button
        toggle_button = QtWidgets.QPushButton("▼") # Initial state is expanded
        toggle_button.setMaximumWidth(30)
        toggle_button.clicked.connect(self.toggle_expanded)
        frame_layout.addWidget(toggle_button, alignment=QtCore.Qt.AlignRight)
        
        # Add to main layout
        layout.addWidget(frame)
        
        # Initialize as expanded
        self.is_expanded = True
        # Set initial visibility for expandable elements
        self.activity_log.setVisible(self.is_expanded)
        self.peers_label.setVisible(self.is_expanded)
        self.peers_list.setVisible(self.is_expanded)


    def add_activity(self, message):
        """Add an entry to the activity log"""
        timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
        item = QtWidgets.QListWidgetItem(f"{timestamp}: {message}")
        
        # Add to beginning for most recent at top
        self.activity_log.insertItem(0, item)
        
        # Limit size of log
        if self.activity_log.count() > 50:
            self.activity_log.takeItem(self.activity_log.count() - 1)

    def toggle_expanded(self):
        """Toggle between minimized and expanded view"""
        self.is_expanded = not self.is_expanded
        
        # Show/hide elements based on state
        self.activity_log.setVisible(self.is_expanded)
        self.peers_label.setVisible(self.is_expanded)
        self.peers_list.setVisible(self.is_expanded)
        
        # Adjust button text
        sender = self.sender()
        if isinstance(sender, QtWidgets.QPushButton):
            sender.setText("▼" if self.is_expanded else "▲")
        
        # Resize the widget (optional, as setVisible might be enough if layouts handle it)
        # If you rely on setMaximumHeight, ensure it accounts for all content.
        # For simplicity, setVisible is preferred if the layout adjusts well.
        if self.is_expanded:
            self.parentWidget().adjustSize() # Or self.adjustSize() if appropriate
            self.setMaximumHeight(10000) # Effectively no max height
        else:
            self.parentWidget().adjustSize() # Or self.adjustSize()
            # Calculate a sensible minimum height or set a fixed one
            # This might need to be dynamic based on title, status_layout
            min_height = self.layout().itemAt(0).widget().layout().itemAt(0).widget().sizeHint().height() # Title
            min_height += self.layout().itemAt(0).widget().layout().itemAt(1).layout().sizeHint().height() # Status layout
            min_height += self.layout().itemAt(0).widget().layout().itemAt(4).widget().sizeHint().height() # Button
            min_height += self.layout().itemAt(0).widget().layout().contentsMargins().top() + self.layout().itemAt(0).widget().layout().contentsMargins().bottom()
            min_height += self.layout().contentsMargins().top() + self.layout().contentsMargins().bottom()
            self.setMaximumHeight(min_height + 20) # Add some padding


    def update_connection_status(self, is_connected, node_id=None):
        """Update the connection status display"""
        self.connection_active = is_connected
        
        if node_id:
            self.node_id = node_id
        
        if is_connected:
            self.status_label.setText("Connected") # Made shorter
            self.status_label.setStyleSheet("color: #66FF66; font-weight: bold;")
            self.status_icon.setText("✔️") # Check icon for connected
            self.node_id_label.setText(f"Node ID: {self.node_id}")
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: #FF6666; font-weight: bold;")
            self.status_icon.setText("⚠️") # Warning icon
            self.node_id_label.setText("Node ID: -")
    
    def update_peers(self, peers_data):
        """Update the list of connected peers"""
        self.peers = []
        if not hasattr(self, 'peers_list'): return # Guard if UI not fully up
        
        self.peers_list.clear()
        
        current_time = time.time()
        
        for node_id, (ip, last_seen, _) in peers_data.items():
            status = "Active" if current_time - last_seen < 10 else "Inactive"
            self.peers.append({
                'node_id': node_id,
                'ip': ip,
                'last_seen': last_seen,
                'status': status
            })
            
            # Add to the list widget
            item_text = f"{node_id[-6:]} ({ip})" # Display last 6 chars of node_id and IP
            item = QtWidgets.QListWidgetItem(item_text)
            
            # Style based on status
            if status == "Active":
                item.setForeground(QtGui.QBrush(QtGui.QColor(100, 255, 100)))
            else:
                item.setForeground(QtGui.QBrush(QtGui.QColor(150, 150, 150)))
            
            self.peers_list.addItem(item)
        
        # Update peers count
        active_count = sum(1 for p in self.peers if p['status'] == "Active")
        if hasattr(self, 'peers_label'):
            self.peers_label.setText(f"Connected Peers: {active_count}")
    
    def update_display(self):
        """Update the display with current information"""
        # Refresh active/inactive status based on timers
        if self.peers:
            current_time = time.time()
            update_needed = False
            
            for peer in self.peers:
                old_status = peer['status']
                # Use a more robust check for last_seen, e.g., if it's a float
                if isinstance(peer.get('last_seen'), (int, float)):
                    peer['status'] = "Active" if current_time - peer['last_seen'] < 10 else "Inactive"
                else:
                    peer['status'] = "Unknown" # Or handle as appropriate

                if old_status != peer['status']:
                    update_needed = True
            
            if update_needed:
                self.refresh_peers_list()
    
    def refresh_peers_list(self):
        """Refresh the peers list widget without changing the underlying data"""
        if not hasattr(self, 'peers_list') or not hasattr(self, 'peers_label'): return # Guard
        
        self.peers_list.clear()
        
        for peer in self.peers:
            item_text = f"{peer.get('node_id', 'N/A')[-6:]} ({peer.get('ip', 'N/A')})"
            item = QtWidgets.QListWidgetItem(item_text)
            
            # Style based on status
            if peer.get('status') == "Active":
                item.setForeground(QtGui.QBrush(QtGui.QColor(100, 255, 100)))
            else:
                item.setForeground(QtGui.QBrush(QtGui.QColor(150, 150, 150)))
            
            self.peers_list.addItem(item)
        
        # Update peers count
        active_count = sum(1 for p in self.peers if p.get('status') == "Active")
        self.peers_label.setText(f"Connected Peers: {active_count}")