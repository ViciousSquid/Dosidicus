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
        
        # Add minimize/expand button
        toggle_button = QtWidgets.QPushButton("▲")
        toggle_button.setMaximumWidth(30)
        toggle_button.clicked.connect(self.toggle_expanded)
        frame_layout.addWidget(toggle_button, alignment=QtCore.Qt.AlignRight)
        
        # Add to main layout
        layout.addWidget(frame)
        
        # Initialize as expanded
        self.is_expanded = True

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
        
        # Adjust button text
        sender = self.sender()
        if isinstance(sender, QtWidgets.QPushButton):
            sender.setText("▲" if not self.is_expanded else "▼")
        
        # Resize the widget
        if self.is_expanded:
            self.setMaximumHeight(1000)  # Effectively no max height
        else:
            self.setMaximumHeight(100)  # Just enough for status and ID
    
    def update_connection_status(self, is_connected, node_id=None):
        """Update the connection status display"""
        self.connection_active = is_connected
        
        if node_id:
            self.node_id = node_id
        
        if is_connected:
            self.status_label.setText("Multiplayer: Connected")
            self.status_label.setStyleSheet("color: #66FF66; font-weight: bold;")
            self.node_id_label.setText(f"Node ID: {self.node_id}")
        else:
            self.status_label.setText("Multiplayer: Disconnected")
            self.status_label.setStyleSheet("color: #FF6666; font-weight: bold;")
            self.node_id_label.setText("Node ID: -")
    
    def update_peers(self, peers_data):
        """Update the list of connected peers"""
        self.peers = []
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
            item = QtWidgets.QListWidgetItem(f"{node_id[-6:]} ({ip})")
            
            # Style based on status
            if status == "Active":
                item.setForeground(QtGui.QBrush(QtGui.QColor(100, 255, 100)))
            else:
                item.setForeground(QtGui.QBrush(QtGui.QColor(150, 150, 150)))
            
            self.peers_list.addItem(item)
        
        # Update peers count
        active_count = sum(1 for p in self.peers if p['status'] == "Active")
        self.peers_label.setText(f"Connected Peers: {active_count}")
    
    def update_display(self):
        """Update the display with current information"""
        # Refresh active/inactive status based on timers
        if self.peers:
            current_time = time.time()
            update_needed = False
            
            for peer in self.peers:
                old_status = peer['status']
                peer['status'] = "Active" if current_time - peer['last_seen'] < 10 else "Inactive"
                
                if old_status != peer['status']:
                    update_needed = True
            
            if update_needed:
                self.refresh_peers_list()
    
    def refresh_peers_list(self):
        """Refresh the peers list widget without changing the underlying data"""
        self.peers_list.clear()
        
        for peer in self.peers:
            item = QtWidgets.QListWidgetItem(f"{peer['node_id'][-6:]} ({peer['ip']})")
            
            # Style based on status
            if peer['status'] == "Active":
                item.setForeground(QtGui.QBrush(QtGui.QColor(100, 255, 100)))
            else:
                item.setForeground(QtGui.QBrush(QtGui.QColor(150, 150, 150)))
            
            self.peers_list.addItem(item)
        
        # Update peers count
        active_count = sum(1 for p in self.peers if p['status'] == "Active")
        self.peers_label.setText(f"Connected Peers: {active_count}")