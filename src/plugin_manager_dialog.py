from PyQt5 import QtCore, QtGui, QtWidgets
import os

class PluginManagerDialog(QtWidgets.QDialog):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.setWindowTitle("Plugin Manager")
        self.resize(600, 400)
        
        self.setup_ui()
        self.load_plugin_data()
        
    def setup_ui(self):
        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Plugin list
        self.plugin_list = QtWidgets.QListWidget()
        self.plugin_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.plugin_list.currentItemChanged.connect(self.on_plugin_selected)
        layout.addWidget(self.plugin_list, 2)
        
        # Plugin details group
        details_group = QtWidgets.QGroupBox("Plugin Details")
        details_layout = QtWidgets.QFormLayout(details_group)
        
        self.plugin_name = QtWidgets.QLabel()
        details_layout.addRow("Name:", self.plugin_name)
        
        self.plugin_version = QtWidgets.QLabel()
        details_layout.addRow("Version:", self.plugin_version)
        
        self.plugin_author = QtWidgets.QLabel()
        details_layout.addRow("Author:", self.plugin_author)
        
        self.plugin_description = QtWidgets.QLabel()
        self.plugin_description.setWordWrap(True)
        details_layout.addRow("Description:", self.plugin_description)
        
        self.plugin_requires = QtWidgets.QLabel()
        details_layout.addRow("Dependencies:", self.plugin_requires)
        
        self.plugin_status = QtWidgets.QLabel()
        details_layout.addRow("Status:", self.plugin_status)
        
        layout.addWidget(details_group, 1)
        
        # Actions group
        actions_group = QtWidgets.QGroupBox("Actions")
        actions_layout = QtWidgets.QHBoxLayout(actions_group)
        
        self.enable_button = QtWidgets.QPushButton("Enable")
        self.enable_button.clicked.connect(self.enable_selected_plugin)
        actions_layout.addWidget(self.enable_button)
        
        self.disable_button = QtWidgets.QPushButton("Disable")
        self.disable_button.clicked.connect(self.disable_selected_plugin)
        actions_layout.addWidget(self.disable_button)
        
        self.refresh_button = QtWidgets.QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.load_plugin_data)
        actions_layout.addWidget(self.refresh_button)
        
        layout.addWidget(actions_group)
        
        # Close button
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button)
        
    def load_plugin_data(self):
        """Load plugin data into the list"""
        self.plugin_list.clear()
        
        # Load plugins from plugin_manager
        loaded_plugins = {}
        enabled_plugins = self.plugin_manager.get_enabled_plugins()
        
        # First, add loaded plugins
        for plugin_name in self.plugin_manager.get_loaded_plugins():
            plugin_data = self.plugin_manager.plugins.get(plugin_name, {})
            
            item = QtWidgets.QListWidgetItem(plugin_name)
            item.setData(QtCore.Qt.UserRole, plugin_data)
            
            # Set icon based on status
            if plugin_name in enabled_plugins:
                # Green dot for enabled
                item.setIcon(self.get_status_icon("enabled"))
            else:
                # Yellow dot for loaded but not enabled
                item.setIcon(self.get_status_icon("loaded"))
                
            self.plugin_list.addItem(item)
            loaded_plugins[plugin_name] = True
        
        # Then add discovered plugins that aren't loaded
        if hasattr(self.plugin_manager, '_discovered_plugins'):
            for plugin_name, plugin_data in self.plugin_manager._discovered_plugins.items():
                if plugin_name not in loaded_plugins:
                    item = QtWidgets.QListWidgetItem(plugin_name)
                    item.setData(QtCore.Qt.UserRole, plugin_data)
                    
                    # Gray dot for discovered but not loaded
                    item.setIcon(self.get_status_icon("discovered"))
                    self.plugin_list.addItem(item)
        
        # Select the first plugin if available
        if self.plugin_list.count() > 0:
            self.plugin_list.setCurrentRow(0)
        else:
            self.clear_plugin_details()
            
    def get_status_icon(self, status):
        """Create a colored dot icon for the plugin status"""
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtCore.Qt.transparent)
        
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        if status == "enabled":
            color = QtGui.QColor(0, 200, 0)  # Green
        elif status == "loaded":
            color = QtGui.QColor(200, 200, 0)  # Yellow
        else:
            color = QtGui.QColor(150, 150, 150)  # Gray
            
        painter.setBrush(QtGui.QBrush(color))
        painter.setPen(QtGui.QPen(QtCore.Qt.black, 1))
        painter.drawEllipse(2, 2, 12, 12)
        painter.end()
        
        return QtGui.QIcon(pixmap)
        
    def on_plugin_selected(self, current, previous):
        """Handle plugin selection change"""
        if not current:
            self.clear_plugin_details()
            return
            
        # Get plugin data
        plugin_data = current.data(QtCore.Qt.UserRole)
        plugin_name = current.text()
        
        # Update details
        self.plugin_name.setText(plugin_data.get('name', plugin_name))
        self.plugin_version.setText(plugin_data.get('version', 'Unknown'))
        self.plugin_author.setText(plugin_data.get('author', 'Unknown'))
        self.plugin_description.setText(plugin_data.get('description', 'No description available'))
        
        # Dependencies
        requires = plugin_data.get('requires', [])
        if requires:
            self.plugin_requires.setText(", ".join(requires))
        else:
            self.plugin_requires.setText("None")
        
        # Status
        is_loaded = plugin_name in self.plugin_manager.get_loaded_plugins()
        is_enabled = plugin_name in self.plugin_manager.get_enabled_plugins()
        
        if is_enabled:
            self.plugin_status.setText("Enabled")
            self.plugin_status.setStyleSheet("color: green; font-weight: bold;")
        elif is_loaded:
            self.plugin_status.setText("Loaded (Not Enabled)")
            self.plugin_status.setStyleSheet("color: orange; font-weight: bold;")
        else:
            self.plugin_status.setText("Discovered (Not Loaded)")
            self.plugin_status.setStyleSheet("color: gray;")
        
        # Enable/disable buttons based on status
        self.enable_button.setEnabled(is_loaded and not is_enabled)
        self.disable_button.setEnabled(is_enabled)
        
    def clear_plugin_details(self):
        """Clear all plugin details"""
        self.plugin_name.clear()
        self.plugin_version.clear()
        self.plugin_author.clear()
        self.plugin_description.clear()
        self.plugin_requires.clear()
        self.plugin_status.clear()
        self.plugin_status.setStyleSheet("")
        
        self.enable_button.setEnabled(False)
        self.disable_button.setEnabled(False)
        
    def enable_selected_plugin(self):
        """Enable the selected plugin"""
        current_item = self.plugin_list.currentItem()
        if not current_item:
            return
            
        plugin_name = current_item.text()
        
        # Try to enable the plugin
        success = False
        
        # First check if plugin has a custom enable method
        if plugin_name in self.plugin_manager.plugins:
            plugin_instance = self.plugin_manager.plugins[plugin_name].get('instance')
            if plugin_instance and hasattr(plugin_instance, 'enable'):
                try:
                    success = plugin_instance.enable()
                    if success:
                        self.plugin_manager.enable_plugin(plugin_name)
                except Exception as e:
                    QtWidgets.QMessageBox.warning(
                        self, 
                        "Error", 
                        f"Error enabling plugin {plugin_name}: {str(e)}"
                    )
                    return
            else:
                success = self.plugin_manager.enable_plugin(plugin_name)
        
        if success:
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"Plugin {plugin_name} enabled successfully"
            )
            self.load_plugin_data()
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                f"Failed to enable plugin {plugin_name}"
            )
    
    def disable_selected_plugin(self):
        """Disable the selected plugin"""
        current_item = self.plugin_list.currentItem()
        if not current_item:
            return
            
        plugin_name = current_item.text()
        
        # Try to disable the plugin
        success = self.plugin_manager.disable_plugin(plugin_name)
        
        if success:
            # Call custom disable method if available
            if plugin_name in self.plugin_manager.plugins:
                plugin_instance = self.plugin_manager.plugins[plugin_name].get('instance')
                if plugin_instance and hasattr(plugin_instance, 'disable'):
                    try:
                        plugin_instance.disable()
                    except Exception as e:
                        print(f"Error in plugin disable method: {e}")
            
            QtWidgets.QMessageBox.information(
                self,
                "Success",
                f"Plugin {plugin_name} disabled successfully"
            )
            self.load_plugin_data()
        else:
            QtWidgets.QMessageBox.warning(
                self,
                "Error",
                f"Failed to disable plugin {plugin_name}"
            )