from PyQt5 import QtCore, QtGui, QtWidgets

class StatusBarComponent:
    def __init__(self, main_window):
        self.main_window = main_window
        
        # Create the status bar if it doesn't exist
        if not main_window.statusBar():
            self.status_bar = QtWidgets.QStatusBar(main_window)
            main_window.setStatusBar(self.status_bar)
        else:
            self.status_bar = main_window.statusBar()
        
        # Create status indicators
        self.create_indicators()
        
        # Message queue for rotating messages
        self.message_queue = []
        self.message_timer = QtCore.QTimer()
        self.message_timer.timeout.connect(self.rotate_messages)
        self.message_timer.start(5000)  # Rotate messages every 5 seconds
    
    def create_indicators(self):
        """Create permanent status indicators"""
        # Plugins indicator
        self.plugins_label = QtWidgets.QLabel("Plugins: None")
        self.plugins_label.setStyleSheet("padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.plugins_label)
        
        # Network status indicator
        self.network_label = QtWidgets.QLabel("Network: Disconnected")
        self.network_label.setStyleSheet("padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.network_label)
        
        # Peers indicator
        self.peers_label = QtWidgets.QLabel("Peers: 0")
        self.peers_label.setStyleSheet("padding: 0 10px;")
        self.status_bar.addPermanentWidget(self.peers_label)
    
    def update_plugins_status(self, plugin_manager):
        """Update the plugins status indicator"""
        if not plugin_manager:
            self.plugins_label.setText("Plugins: None")
            return
        
        enabled_plugins = plugin_manager.get_enabled_plugins()
        if not enabled_plugins:
            self.plugins_label.setText("Plugins: None")
            self.plugins_label.setStyleSheet("padding: 0 10px; color: gray;")
        else:
            plugin_count = len(enabled_plugins)
            self.plugins_label.setText(f"Plugins: {plugin_count} active")
            self.plugins_label.setStyleSheet("padding: 0 10px; color: green;")
            
            # Create tooltip with plugin names
            tooltip = "Active plugins:\n" + "\n".join(f"• {p}" for p in enabled_plugins)
            self.plugins_label.setToolTip(tooltip)
    
    def update_network_status(self, connected, node_id=None):
        """Update the network status indicator"""
        if connected:
            self.network_label.setText(f"Network: Connected")
            self.network_label.setStyleSheet("padding: 0 10px; color: green;")
            if node_id:
                self.network_label.setToolTip(f"Connected as {node_id}")
        else:
            self.network_label.setText("Network: Disconnected")
            self.network_label.setStyleSheet("padding: 0 10px; color: gray;")
            self.network_label.setToolTip("Network functionality is disconnected")
    
    def update_peers_count(self, count):
        """Update the peers count indicator"""
        self.peers_label.setText(f"Peers: {count}")
        if count > 0:
            self.peers_label.setStyleSheet("padding: 0 10px; color: green;")
        else:
            self.peers_label.setStyleSheet("padding: 0 10px; color: gray;")
    
    def add_message(self, message, duration=5000):
        """Add a temporary message to the status bar"""
        self.status_bar.showMessage(message, duration)
    
    def add_to_message_queue(self, message):
        """Add a message to the rotation queue"""
        if message not in self.message_queue:
            self.message_queue.append(message)
    
    def rotate_messages(self):
        """Rotate through queued messages"""
        if not self.message_queue:
            return
            
        # Show the next message
        message = self.message_queue.pop(0)
        self.status_bar.showMessage(message, 4500)  # Show for slightly less than rotation time
        
        # Add the message back to the end of the queue
        self.message_queue.append(message)