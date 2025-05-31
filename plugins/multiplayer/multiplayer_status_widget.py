from PyQt5 import QtCore, QtGui, QtWidgets
import time

class MultiplayerStatusWidget(QtWidgets.QWidget):
    def __init__(self, plugin_manager=None, parent=None): # MODIFIED: Added plugin_manager
        super().__init__(parent)
        self.plugin_manager = plugin_manager # MODIFIED: Store plugin_manager
        self.setObjectName("MultiplayerStatusWidget")
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
        
        # Keep track of peers and connection status
        self.connection_active = False
        self.node_id = "Unknown" # Initial node_id
        self.local_ip = "N/A"    # Initial local_ip
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
        
        title_label = QtWidgets.QLabel("🌐 Multiplayer")
        title_label.setStyleSheet("color: #FFFFFF; font-weight: bold; font-size: 14px;")
        title_label.setAlignment(QtCore.Qt.AlignCenter)
        frame_layout.addWidget(title_label)
        
        status_layout = QtWidgets.QHBoxLayout()
        self.status_icon = QtWidgets.QLabel("⚠️") 
        status_layout.addWidget(self.status_icon)
        
        self.status_label = QtWidgets.QLabel("Disconnected")
        self.status_label.setStyleSheet("color: #FF6666; font-weight: bold;")
        status_layout.addWidget(self.status_label)
        
        # Node ID and IP display label
        self.node_id_label = QtWidgets.QLabel(f"Node ID: {self.node_id} IP: {self.local_ip}") # MODIFIED: Shows both
        self.node_id_label.setStyleSheet("color: #DDDDDD; margin-left: 10px;")
        status_layout.addWidget(self.node_id_label)
        status_layout.addStretch()
        frame_layout.addLayout(status_layout)
        
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

        self.peers_label = QtWidgets.QLabel("Connected Peers: 0")
        self.peers_label.setStyleSheet("color: #DDDDDD; margin-top: 5px;")
        frame_layout.addWidget(self.peers_label)

        self.peers_list = QtWidgets.QListWidget()
        self.peers_list.setMaximumHeight(80)
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
        
        toggle_button = QtWidgets.QPushButton("▼")
        toggle_button.setMaximumWidth(30)
        toggle_button.clicked.connect(self.toggle_expanded)
        frame_layout.addWidget(toggle_button, alignment=QtCore.Qt.AlignRight)
        
        layout.addWidget(frame)
        
        self.is_expanded = True
        self.activity_log.setVisible(self.is_expanded)
        self.peers_label.setVisible(self.is_expanded)
        self.peers_list.setVisible(self.is_expanded)

    def add_activity(self, message):
        timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
        item = QtWidgets.QListWidgetItem(f"{timestamp}: {message}")
        self.activity_log.insertItem(0, item)
        if self.activity_log.count() > 50:
            self.activity_log.takeItem(self.activity_log.count() - 1)

    def toggle_expanded(self):
        self.is_expanded = not self.is_expanded
        self.activity_log.setVisible(self.is_expanded)
        self.peers_label.setVisible(self.is_expanded)
        self.peers_list.setVisible(self.is_expanded)
        
        sender = self.sender()
        if isinstance(sender, QtWidgets.QPushButton):
            sender.setText("▼" if self.is_expanded else "▲")
        
        if self.is_expanded:
            self.parentWidget().adjustSize()
            self.setMaximumHeight(10000)
        else:
            self.parentWidget().adjustSize()
            min_height = self.layout().itemAt(0).widget().layout().itemAt(0).widget().sizeHint().height()
            min_height += self.layout().itemAt(0).widget().layout().itemAt(1).layout().sizeHint().height()
            min_height += self.layout().itemAt(0).widget().layout().itemAt(4).widget().sizeHint().height()
            min_height += self.layout().itemAt(0).widget().layout().contentsMargins().top() + self.layout().itemAt(0).widget().layout().contentsMargins().bottom()
            min_height += self.layout().contentsMargins().top() + self.layout().contentsMargins().bottom()
            self.setMaximumHeight(min_height + 20)

    def update_connection_status(self, is_connected, node_id=None):
        self.connection_active = is_connected
        
        if node_id: # If a node_id is provided, update it
            self.node_id = node_id
        
        if is_connected:
            self.status_label.setText("Connected")
            self.status_label.setStyleSheet("color: #66FF66; font-weight: bold;")
            self.status_icon.setText("✔️")
        else:
            self.status_label.setText("Disconnected")
            self.status_label.setStyleSheet("color: #FF6666; font-weight: bold;")
            self.status_icon.setText("⚠️")
        
        # Update the node_id_label with current node_id and local_ip
        self.node_id_label.setText(f"Node ID: {self.node_id} IP: {self.local_ip}")


    def update_peers(self, peers_data):
        self.peers = []
        if not hasattr(self, 'peers_list'): return
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
            item_text = f"{node_id[-6:]} ({ip})"
            item = QtWidgets.QListWidgetItem(item_text)
            if status == "Active":
                item.setForeground(QtGui.QBrush(QtGui.QColor(100, 255, 100)))
            else:
                item.setForeground(QtGui.QBrush(QtGui.QColor(150, 150, 150)))
            self.peers_list.addItem(item)
        
        active_count = sum(1 for p in self.peers if p['status'] == "Active")
        if hasattr(self, 'peers_label'):
            self.peers_label.setText(f"Connected Peers: {active_count}")
    
    def update_display(self):
        if self.peers:
            current_time = time.time()
            update_needed = False
            for peer in self.peers:
                old_status = peer['status']
                if isinstance(peer.get('last_seen'), (int, float)):
                    peer['status'] = "Active" if current_time - peer['last_seen'] < 10 else "Inactive"
                else:
                    peer['status'] = "Unknown"
                if old_status != peer['status']:
                    update_needed = True
            if update_needed:
                self.refresh_peers_list()
    
    def refresh_peers_list(self):
        if not hasattr(self, 'peers_list') or not hasattr(self, 'peers_label'): return
        self.peers_list.clear()
        for peer in self.peers:
            item_text = f"{peer.get('node_id', 'N/A')[-6:]} ({peer.get('ip', 'N/A')})"
            item = QtWidgets.QListWidgetItem(item_text)
            if peer.get('status') == "Active":
                item.setForeground(QtGui.QBrush(QtGui.QColor(100, 255, 100)))
            else:
                item.setForeground(QtGui.QBrush(QtGui.QColor(150, 150, 150)))
            self.peers_list.addItem(item)
        active_count = sum(1 for p in self.peers if p.get('status') == "Active")
        self.peers_label.setText(f"Connected Peers: {active_count}")

    # --- ADDED/MODIFIED METHODS TO MATCH mp_plugin_logic.py EXPECTATIONS ---

    def update_status(self, status_text, is_enabled):
        """
        Called by mp_plugin_logic.py to update the general enabled/disabled status.
        It maps to the widget's more specific 'update_connection_status'.
        Note: This version does not receive node_id directly. Node ID is managed
        by calls to update_connection_status (potentially by mp_plugin_logic.py
        if it calls that) or set initially.
        """
        # Update connection status (visuals like "Connected"/"Disconnected" and icon)
        # It uses the currently stored self.node_id.
        self.update_connection_status(is_connected=is_enabled, node_id=self.node_id) 

        # Logging through plugin_manager if available
        if self.plugin_manager and hasattr(self.plugin_manager, 'logger'):
            self.plugin_manager.logger.debug(
                f"MultiplayerStatusWidget: 'update_status' called. Status Text='{status_text}', IsEnabled={is_enabled}"
            )
        else: # Fallback print for debugging if logger is not available
            print(f"DEBUG: MultiplayerStatusWidget: 'update_status' called. Status Text='{status_text}', IsEnabled={is_enabled}")

    def set_ip_address(self, ip_address_text):
        """
        Called by mp_plugin_logic.py to set the local IP address display.
        """
        self.local_ip = ip_address_text if ip_address_text else "N/A"
        
        # Update the display to show the new IP along with the current node_id
        self.node_id_label.setText(f"Node ID: {self.node_id} IP: {self.local_ip}")

        if self.plugin_manager and hasattr(self.plugin_manager, 'logger'):
            self.plugin_manager.logger.debug(
                f"MultiplayerStatusWidget: 'set_ip_address' called. IP='{self.local_ip}'"
            )
        else:
            print(f"DEBUG: MultiplayerStatusWidget: 'set_ip_address' called. IP='{self.local_ip}'")

    def update_icon(self, is_enabled):
        """
        Placeholder to prevent AttributeError if called.
        Actual icon update is handled by update_connection_status.
        """
        # The actual icon (self.status_icon) is updated in self.update_connection_status.
        # This method is here to satisfy any external calls that might have been based on earlier designs.
        pass
        # If direct control over the icon from this method signature is needed later,
        # you can add logic here, e.g.:
        # if is_enabled:
        #     self.status_icon.setText("✔️")
        # else:
        #     self.status_icon.setText("⚠️")