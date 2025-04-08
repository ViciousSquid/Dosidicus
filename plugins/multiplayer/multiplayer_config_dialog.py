from PyQt5 import QtCore, QtGui, QtWidgets
import time

class MultiplayerConfigDialog(QtWidgets.QDialog):
    def __init__(self, plugin, parent=None, multicast_group=None, port=None, sync_interval=None, remote_opacity=None, show_labels=None, show_connections=None):
        super().__init__(parent)
        self.plugin = plugin
        
        # Store settings
        self.MULTICAST_GROUP = multicast_group
        self.MULTICAST_PORT = port
        self.SYNC_INTERVAL = sync_interval
        self.REMOTE_SQUID_OPACITY = remote_opacity
        self.SHOW_REMOTE_LABELS = show_labels
        self.SHOW_CONNECTION_LINES = show_connections

        # Initialize UI
        self.setup_ui()

    def setup_ui(self):
        """Set up the UI components with larger fonts and better scaling"""
        layout = QtWidgets.QVBoxLayout(self)
        
        # Set a base font size for better readability
        base_font = QtGui.QFont()
        base_font.setPointSize(10)  # Increase default font size
        
        # Apply the font to the dialog
        self.setFont(base_font)
        
        # Network settings group
        network_group = QtWidgets.QGroupBox("Network Settings")
        network_group.setFont(base_font)  # Apply font to group box title
        network_layout = QtWidgets.QFormLayout(network_group)
        
        # Multicast group address (larger font)
        self.multicast_address = QtWidgets.QLineEdit(self.MULTICAST_GROUP)
        self.multicast_address.setFont(base_font)  # Apply font to text input
        network_layout.addRow("Multicast Group:", self.multicast_address)
        
        # Port (larger font)
        self.port = QtWidgets.QSpinBox()
        self.port.setFont(base_font)
        self.port.setRange(1024, 65535)
        self.port.setValue(self.MULTICAST_PORT)
        network_layout.addRow("Port:", self.port)
        
        # Sync interval (larger font)
        self.sync_interval = QtWidgets.QDoubleSpinBox()
        self.sync_interval.setFont(base_font)
        self.sync_interval.setRange(0.1, 5.0)
        self.sync_interval.setSingleStep(0.1)
        self.sync_interval.setValue(self.SYNC_INTERVAL)
        network_layout.addRow("Sync Interval (s):", self.sync_interval)
        
        layout.addWidget(network_group)
        
        # Node info group (larger font)
        node_group = QtWidgets.QGroupBox("Local Node Information")
        node_group.setFont(base_font)
        node_layout = QtWidgets.QFormLayout(node_group)
        
        # Node ID (read-only, larger font)
        self.node_id = QtWidgets.QLineEdit()
        self.node_id.setFont(base_font)
        self.node_id.setReadOnly(True)
        if hasattr(self.plugin, 'network_node') and self.plugin.network_node:
            self.node_id.setText(self.plugin.network_node.node_id)
        node_layout.addRow("Node ID:", self.node_id)
        
        # Local IP (read-only, larger font)
        self.local_ip = QtWidgets.QLineEdit()
        self.local_ip.setFont(base_font)
        self.local_ip.setReadOnly(True)
        if hasattr(self.plugin, 'network_node') and self.plugin.network_node:
            self.local_ip.setText(self.plugin.network_node.local_ip)
        node_layout.addRow("Local IP:", self.local_ip)
        
        layout.addWidget(node_group)
        
        # Visual settings group (larger font)
        visual_group = QtWidgets.QGroupBox("Visual Settings")
        visual_group.setFont(base_font)
        visual_layout = QtWidgets.QFormLayout(visual_group)
        
        # Remote squid opacity (larger font)
        self.remote_opacity = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.remote_opacity.setFont(base_font)
        self.remote_opacity.setRange(10, 100)
        self.remote_opacity.setValue(int(self.REMOTE_SQUID_OPACITY * 100))
        self.remote_opacity.setTickPosition(QtWidgets.QSlider.TicksBelow)
        self.remote_opacity.setTickInterval(10)
        visual_layout.addRow("Remote Squid Opacity:", self.remote_opacity)
        
        # Show remote labels (larger font)
        self.show_labels = QtWidgets.QCheckBox()
        self.show_labels.setFont(base_font)
        self.show_labels.setChecked(self.SHOW_REMOTE_LABELS)
        visual_layout.addRow("Show Remote Labels:", self.show_labels)
        
        # Show connection lines (larger font)
        self.show_connections = QtWidgets.QCheckBox()
        self.show_connections.setFont(base_font)
        self.show_connections.setChecked(self.SHOW_CONNECTION_LINES)
        visual_layout.addRow("Show Connection Lines:", self.show_connections)
        
        layout.addWidget(visual_group)
        
        # Connected peers list (larger font)
        peers_group = QtWidgets.QGroupBox("Connected Peers")
        peers_group.setFont(base_font)
        peers_layout = QtWidgets.QVBoxLayout(peers_group)
        
        self.peers_list = QtWidgets.QListWidget()
        self.peers_list.setFont(base_font)  # Apply font to list items
        self.update_peers_list()
        peers_layout.addWidget(self.peers_list)
        
        refresh_button = QtWidgets.QPushButton("Refresh")
        refresh_button.setFont(base_font)  # Larger button text
        refresh_button.clicked.connect(self.update_peers_list)
        peers_layout.addWidget(refresh_button)
        
        layout.addWidget(peers_group)
        
        # Buttons (larger font)
        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Save | 
            QtWidgets.QDialogButtonBox.Cancel
        )
        button_box.setFont(base_font)  # Larger button text
        button_box.accepted.connect(self.save_settings)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)
    
    def update_peers_list(self):
        """Update the list of connected peers"""
        self.peers_list.clear()
        
        if (hasattr(self.plugin, 'network_node') and 
            self.plugin.network_node and 
            hasattr(self.plugin.network_node, 'known_nodes')):
            
            for node_id, (ip, last_seen, squid_data) in self.plugin.network_node.known_nodes.items():
                status = "Active" if time.time() - last_seen < 10 else "Inactive"
                item = QtWidgets.QListWidgetItem(f"{node_id} ({ip}) - {status}")
                
                # Set color based on status
                if status == "Active":
                    item.setForeground(QtGui.QBrush(QtGui.QColor(0, 128, 0)))
                else:
                    item.setForeground(QtGui.QBrush(QtGui.QColor(128, 128, 128)))
                
                self.peers_list.addItem(item)
                
        if self.peers_list.count() == 0:
            self.peers_list.addItem("No peers connected")
    
    def save_settings(self):
        """Save settings back to the plugin"""
        try:
            # Validate multicast address
            import socket
            socket.inet_aton(self.multicast_address.text())
            
            # Save settings that can be changed without restart
            self.plugin.REMOTE_SQUID_OPACITY = self.remote_opacity.value() / 100.0
            self.plugin.SHOW_REMOTE_LABELS = self.show_labels.isChecked()
            self.plugin.SHOW_CONNECTION_LINES = self.show_connections.isChecked()
            
            # Update remote squid visuals with new opacity
            if hasattr(self.plugin, 'remote_squids'):
                for squid_data in self.plugin.remote_squids.values():
                    if 'visual' in squid_data and squid_data['visual']:
                        squid_data['visual'].setOpacity(self.plugin.REMOTE_SQUID_OPACITY)
            
            # Settings that require restart
            restart_needed = False
            if (self.plugin.MULTICAST_GROUP != self.multicast_address.text() or
                self.plugin.MULTICAST_PORT != self.port.value() or
                abs(self.plugin.SYNC_INTERVAL - self.sync_interval.value()) > 0.01):
                
                self.plugin.MULTICAST_GROUP = self.multicast_address.text()
                self.plugin.MULTICAST_PORT = self.port.value()
                self.plugin.SYNC_INTERVAL = self.sync_interval.value()
                restart_needed = True
            
            # Show message about restart if needed
            if restart_needed:
                QtWidgets.QMessageBox.information(
                    self,
                    "Restart Required",
                    "Some settings changes require restarting the application to take effect."
                )
            
            self.accept()
            
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self,
                "Invalid Settings",
                f"Error in settings: {str(e)}"
            )