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
                background-color: rgba(0, 0, 0, 150);
                border-radius: 10px;
                color: white;
            }
        """)
        frame_layout = QtWidgets.QVBoxLayout(frame)
        
        # Status header
        self.status_label = QtWidgets.QLabel("Multiplayer: Disconnected")
        self.status_label.setStyleSheet("color: #FF6666; font-weight: bold;")
        frame_layout.addWidget(self.status_label)
        
        # Node ID
        self.node_id_label = QtWidgets.QLabel("Node ID: -")
        self.node_id_label.setStyleSheet("color: #CCCCCC;")
        frame_layout.addWidget(self.node_id_label)
        
        # Peers count
        self.peers_label = QtWidgets.QLabel("Connected Peers: 0")
        self.peers_label.setStyleSheet("color: #CCCCCC;")
        frame_layout.addWidget(self.peers_label)
        
        # Active peers list
        self.peers_list = QtWidgets.QListWidget()
        self.peers_list.setMaximumHeight(100)
        self.peers_list.setStyleSheet("""
            QListWidget {
                background-color: rgba(0, 0, 0, 100);
                border: 1px solid #444444;
                border-radius: 5px;
                color: white;
            }
            QListWidget::item {
                padding: 2px;
            }
            QListWidget::item:selected {
                background-color: rgba(0, 100, 200, 100);
            }
        """)
        frame_layout.addWidget(self.peers_list)
        
        # Add the frame to the main layout
        layout.addWidget(frame)
        
        # Set size
        self.setMinimumWidth(200)
        self.setMaximumWidth(300)
    
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