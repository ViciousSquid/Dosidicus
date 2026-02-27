from PyQt5 import QtCore, QtGui, QtWidgets
import os

class PluginManagerDialog(QtWidgets.QDialog):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.setWindowTitle("Plugin Manager")
        self.resize(800, 500)
        
        self.setup_ui()
        self.load_plugin_data()
        
    def setup_ui(self):
        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # Header label
        header = QtWidgets.QLabel("🧩 Plugin Manager")
        header.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(header)
        
        # Splitter for resizable sections
        splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        
        # Plugin list container
        list_container = QtWidgets.QWidget()
        list_layout = QtWidgets.QVBoxLayout(list_container)
        list_layout.setContentsMargins(0, 0, 0, 0)
        
        list_label = QtWidgets.QLabel("Available Plugins")
        list_layout.addWidget(list_label)
        
        self.plugin_list = QtWidgets.QListWidget()
        self.plugin_list.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.plugin_list.currentItemChanged.connect(self.on_plugin_selected)
        self.plugin_list.setIconSize(QtCore.QSize(16, 16))
        list_layout.addWidget(self.plugin_list)
        
        splitter.addWidget(list_container)
        
        # Right panel
        right_panel = QtWidgets.QWidget()
        right_layout = QtWidgets.QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        
        # Plugin details group
        details_group = QtWidgets.QGroupBox("Plugin Details")
        details_layout = QtWidgets.QFormLayout(details_group)
        details_layout.setSpacing(10)
        details_layout.setLabelAlignment(QtCore.Qt.AlignRight)
        details_layout.setFieldGrowthPolicy(QtWidgets.QFormLayout.AllNonFixedFieldsGrow)
        
        self.plugin_name = QtWidgets.QLabel()
        details_layout.addRow("Name:", self.plugin_name)
        
        self.plugin_version = QtWidgets.QLabel()
        details_layout.addRow("Version:", self.plugin_version)
        
        self.plugin_author = QtWidgets.QLabel()
        details_layout.addRow("Author:", self.plugin_author)
        
        self.plugin_description = QtWidgets.QLabel()
        self.plugin_description.setWordWrap(True)
        self.plugin_description.setMinimumHeight(60)
        details_layout.addRow("Description:", self.plugin_description)
        
        self.plugin_requires = QtWidgets.QLabel()
        details_layout.addRow("Dependencies:", self.plugin_requires)
        
        self.plugin_status = QtWidgets.QLabel()
        details_layout.addRow("Status:", self.plugin_status)
        
        right_layout.addWidget(details_group)
        
        # Actions group
        actions_group = QtWidgets.QGroupBox("Actions")
        actions_layout = QtWidgets.QHBoxLayout(actions_group)
        actions_layout.setSpacing(10)
        
        self.enable_button = QtWidgets.QPushButton("Enable")
        self.enable_button.clicked.connect(self.enable_selected_plugin)
        actions_layout.addWidget(self.enable_button)
        
        self.disable_button = QtWidgets.QPushButton("Disable")
        self.disable_button.clicked.connect(self.disable_selected_plugin)
        actions_layout.addWidget(self.disable_button)
        
        self.refresh_button = QtWidgets.QPushButton("Refresh List")
        self.refresh_button.clicked.connect(self.load_plugin_data)
        actions_layout.addWidget(self.refresh_button)
        
        right_layout.addWidget(actions_group)
        right_layout.addStretch()
        
        splitter.addWidget(right_panel)
        splitter.setSizes([300, 400])
        layout.addWidget(splitter)
        
        # Close button
        button_container = QtWidgets.QWidget()
        button_layout = QtWidgets.QHBoxLayout(button_container)
        button_layout.setContentsMargins(0, 0, 0, 0)
        
        button_layout.addStretch()
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(button_container)
        
    def load_plugin_data(self):
        """Load plugin data into the list"""
        self.plugin_list.clear()
        
        # Get all plugin states
        loaded_plugins = {name.lower(): True for name in self.plugin_manager.get_loaded_plugins()}
        enabled_plugins = {name.lower(): True for name in self.plugin_manager.get_enabled_plugins()}
        
        # First, add loaded plugins
        for plugin_name in self.plugin_manager.get_loaded_plugins():
            plugin_data = self.plugin_manager.plugins.get(plugin_name.lower(), {})
            original_name = plugin_data.get('original_name', plugin_name)
            
            item = QtWidgets.QListWidgetItem(original_name)
            item.setData(QtCore.Qt.UserRole, plugin_data)
            
            if plugin_name.lower() in enabled_plugins:
                item.setIcon(self.get_status_icon("enabled"))
            else:
                item.setIcon(self.get_status_icon("loaded"))
                
            self.plugin_list.addItem(item)
        
        # Then add discovered plugins that aren't loaded
        if hasattr(self.plugin_manager, '_discovered_plugins'):
            for plugin_key, plugin_data in self.plugin_manager._discovered_plugins.items():
                if plugin_key not in loaded_plugins:
                    original_name = plugin_data.get('original_name', plugin_key)
                    item = QtWidgets.QListWidgetItem(original_name)
                    item.setData(QtCore.Qt.UserRole, plugin_data)
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
        """Handle plugin selection change with fixed enable logic"""
        if not current:
            self.clear_plugin_details()
            return
            
        plugin_data = current.data(QtCore.Qt.UserRole)
        plugin_key = plugin_data.get('name', current.text()).lower()
        original_name = plugin_data.get('original_name', current.text())
        
        # Update details
        self.plugin_name.setText(original_name)
        self.plugin_version.setText(plugin_data.get('version', 'Unknown'))
        self.plugin_author.setText(plugin_data.get('author', 'Unknown'))
        self.plugin_description.setText(plugin_data.get('description', 'No description available'))
        
        # Dependencies
        requires = plugin_data.get('requires', [])
        self.plugin_requires.setText(", ".join(requires) if requires else "None")
        
        # Status and button logic
        is_loaded = plugin_key in {name.lower() for name in self.plugin_manager.get_loaded_plugins()}
        is_enabled = plugin_key in {name.lower() for name in self.plugin_manager.get_enabled_plugins()}
        
        # NEW: Check if plugin can be enabled (loaded OR discovered)
        can_enable = not is_enabled and (is_loaded or plugin_key in self.plugin_manager._discovered_plugins)
        
        if is_enabled:
            self.plugin_status.setText("✓ ENABLED")
        elif is_loaded:
            self.plugin_status.setText("Loaded (Not Enabled)")
        else:
            self.plugin_status.setText("Discovered (Not Loaded)")
        
        # FIX: Enable button for discovered-but-not-loaded plugins
        self.enable_button.setEnabled(bool(can_enable))
        self.disable_button.setEnabled(bool(is_enabled))
        
    def clear_plugin_details(self):
        """Clear all plugin details"""
        self.plugin_name.clear()
        self.plugin_version.clear()
        self.plugin_author.clear()
        self.plugin_description.clear()
        self.plugin_requires.clear()
        self.plugin_status.clear()
        
        self.enable_button.setEnabled(False)
        self.disable_button.setEnabled(False)
        
    def enable_selected_plugin(self):
        """Enable the selected plugin with automatic loading"""
        current_item = self.plugin_list.currentItem()
        if not current_item:
            return
            
        plugin_data = current_item.data(QtCore.Qt.UserRole)
        plugin_key = plugin_data.get('name', current_item.text()).lower()
        
        try:
            # If plugin isn't loaded yet, load it first
            if plugin_key not in self.plugin_manager.plugins:
                self.plugin_manager.logger.info(f"Plugin '{plugin_key}' not loaded. Loading now...")
                if not self.plugin_manager.load_plugin(plugin_key):
                    QtWidgets.QMessageBox.warning(
                        self, 
                        "Error", 
                        f"Failed to load plugin '{plugin_key}'. Check logs for details."
                    )
                    return
            
            # Now enable it
            success = self.plugin_manager.enable_plugin(plugin_key)
            
            if success:
                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    f"Plugin '{plugin_data.get('original_name', plugin_key)}' enabled successfully"
                )
                self.load_plugin_data()
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to enable plugin '{plugin_key}'"
                )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, 
                "Error", 
                f"Error enabling plugin: {str(e)}"
            )
    
    def disable_selected_plugin(self):
        """Disable the selected plugin"""
        current_item = self.plugin_list.currentItem()
        if not current_item:
            return
            
        plugin_name = current_item.text()
        
        try:
            success = self.plugin_manager.disable_plugin(plugin_name)
            
            if success:
                # Call custom disable method if available
                if plugin_name.lower() in self.plugin_manager.plugins:
                    plugin_instance = self.plugin_manager.plugins[plugin_name.lower()].get('instance')
                    if plugin_instance and hasattr(plugin_instance, 'disable'):
                        try:
                            plugin_instance.disable()
                        except Exception as e:
                            print(f"Error in plugin disable method: {e}")
                
                QtWidgets.QMessageBox.information(
                    self,
                    "Success",
                    f"Plugin '{plugin_name}' disabled successfully"
                )
                self.load_plugin_data()
            else:
                QtWidgets.QMessageBox.warning(
                    self,
                    "Error",
                    f"Failed to disable plugin '{plugin_name}'"
                )
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, 
                "Error", 
                f"Error disabling plugin: {str(e)}"
            )