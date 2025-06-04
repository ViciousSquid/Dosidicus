from PyQt5 import QtCore, QtGui, QtWidgets
import os

class PluginManagerDialog(QtWidgets.QDialog):
    def __init__(self, plugin_manager, parent=None):
        super().__init__(parent)
        self.plugin_manager = plugin_manager
        self.setWindowTitle("Plugin Manager")
        self.resize(600, 450) # Adjusted size slightly for better layout
        
        self.setup_ui()
        self.load_plugin_data() # Initial population
        
    def setup_ui(self):
        # Main layout
        layout = QtWidgets.QVBoxLayout(self)
        
        # Plugin list (renamed self.plugin_list_widget for clarity if you prefer)
        self.plugin_list_widget = QtWidgets.QListWidget() 
        self.plugin_list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.plugin_list_widget.currentItemChanged.connect(self.on_plugin_selected)
        layout.addWidget(self.plugin_list_widget, 2) # Give more space to list
        
        # Plugin details group
        details_group = QtWidgets.QGroupBox("Plugin Details")
        details_layout = QtWidgets.QFormLayout(details_group)
        
        self.plugin_name_label = QtWidgets.QLabel() # Renamed for clarity
        details_layout.addRow("Name:", self.plugin_name_label)
        
        self.plugin_version_label = QtWidgets.QLabel() # Renamed
        details_layout.addRow("Version:", self.plugin_version_label)
        
        self.plugin_author_label = QtWidgets.QLabel() # Renamed
        details_layout.addRow("Author:", self.plugin_author_label)
        
        self.plugin_description_label = QtWidgets.QLabel() # Renamed
        self.plugin_description_label.setWordWrap(True)
        self.plugin_description_label.setMinimumHeight(40) # Allow space for description
        details_layout.addRow("Description:", self.plugin_description_label)
        
        self.plugin_requires_label = QtWidgets.QLabel() # Renamed
        self.plugin_requires_label.setWordWrap(True)
        details_layout.addRow("Dependencies:", self.plugin_requires_label)
        
        self.plugin_status_label = QtWidgets.QLabel() # Renamed
        details_layout.addRow("Status:", self.plugin_status_label)
        
        layout.addWidget(details_group, 1) # Give less relative space to details
        
        # Actions group
        actions_group = QtWidgets.QGroupBox("Actions")
        actions_layout = QtWidgets.QHBoxLayout(actions_group)
        
        self.enable_button = QtWidgets.QPushButton("Enable")
        self.enable_button.clicked.connect(self.enable_selected_plugin)
        self.enable_button.setToolTip("Enable the selected plugin. This will also load and set it up if it's the first time.")
        actions_layout.addWidget(self.enable_button)
        
        self.disable_button = QtWidgets.QPushButton("Disable")
        self.disable_button.clicked.connect(self.disable_selected_plugin)
        self.disable_button.setToolTip("Disable the selected plugin.")
        actions_layout.addWidget(self.disable_button)
        
        self.refresh_button = QtWidgets.QPushButton("Refresh List")
        self.refresh_button.clicked.connect(self.load_plugin_data)
        self.refresh_button.setToolTip("Refresh the list of plugins and their status.")
        actions_layout.addWidget(self.refresh_button)
        
        layout.addWidget(actions_group)
        
        # Close button
        self.close_button = QtWidgets.QPushButton("Close")
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.close_button, 0, QtCore.Qt.AlignRight) # Align to right

    def load_plugin_data(self):
        """Load/refresh plugin data into the list, ensuring 'multiplayer' is first if present."""
        current_selected_key = None
        if self.plugin_list_widget.currentItem():
            current_metadata = self.plugin_list_widget.currentItem().data(QtCore.Qt.UserRole)
            if current_metadata:
                current_selected_key = current_metadata.get('name', '').lower()

        self.plugin_list_widget.clear()
        if not self.plugin_manager:
            self.clear_plugin_details()
            return

        # Use discovered_plugins as the source of truth for what *can* be managed
        discovered_plugins_meta = self.plugin_manager._discovered_plugins if self.plugin_manager._discovered_plugins else {}
        if not discovered_plugins_meta:
            self.plugin_list_widget.addItem("No plugins discovered.")
            self.clear_plugin_details()
            return

        all_plugin_data_values = list(discovered_plugins_meta.values())
        
        multiplayer_plugin_metadata = None
        other_plugins_metadata = []

        for p_data in all_plugin_data_values:
            if p_data.get('name', '').lower() == 'multiplayer': # 'name' from discovery is the lowercase key
                multiplayer_plugin_metadata = p_data
            else:
                other_plugins_metadata.append(p_data)
                
        other_plugins_metadata.sort(key=lambda p: p.get('original_name', p.get('name', ''))) # Sort by display name
        
        final_sorted_metadata_list = []
        if multiplayer_plugin_metadata:
            final_sorted_metadata_list.append(multiplayer_plugin_metadata)
        final_sorted_metadata_list.extend(other_plugins_metadata)

        item_to_reselect = None
        for plugin_metadata in final_sorted_metadata_list:
            display_name = plugin_metadata.get('original_name', plugin_metadata.get('name', 'Unknown Plugin'))
            plugin_key = plugin_metadata.get('name', '').lower()

            if not plugin_key: continue

            item = QtWidgets.QListWidgetItem(display_name)
            # Store the full discovered metadata with the item.
            # This metadata contains 'name' (lowercase key), 'original_name', 'version', etc.
            item.setData(QtCore.Qt.UserRole, plugin_metadata) 

            # Determine status for icon and tooltip
            is_loaded = plugin_key in self.plugin_manager.plugins
            is_enabled = plugin_key in self.plugin_manager.enabled_plugins
            
            status_icon_type = "discovered" # Default for not loaded
            if is_enabled:
                status_icon_type = "enabled"
            elif is_loaded: # Loaded but not enabled
                status_icon_type = "loaded"
            
            item.setIcon(self.get_status_icon(status_icon_type))
            self.plugin_list_widget.addItem(item)

            if plugin_key == current_selected_key:
                item_to_reselect = item
        
        if item_to_reselect:
            self.plugin_list_widget.setCurrentItem(item_to_reselect)
        elif self.plugin_list_widget.count() > 0:
            self.plugin_list_widget.setCurrentRow(0)
        else:
            self.clear_plugin_details() # Explicitly clear if list is empty
            
    def get_status_icon(self, status):
        pixmap = QtGui.QPixmap(16, 16)
        pixmap.fill(QtCore.Qt.transparent)
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        color = QtGui.QColor(150, 150, 150) # Default: Gray for discovered
        if status == "enabled":
            color = QtGui.QColor(0, 180, 0)  # Darker Green
        elif status == "loaded":
            color = QtGui.QColor(220, 165, 0)  # Orange/Yellow
            
        painter.setBrush(QtGui.QBrush(color))
        painter.setPen(QtGui.QPen(QtCore.Qt.black, 0.5)) # Thinner pen
        painter.drawEllipse(2, 2, 11, 11) # Slightly smaller ellipse
        painter.end()
        return QtGui.QIcon(pixmap)
        
    def on_plugin_selected(self, current_item, previous_item):
        if not current_item:
            self.clear_plugin_details()
            return
            
        plugin_metadata = current_item.data(QtCore.Qt.UserRole)
        if not plugin_metadata:
            self.clear_plugin_details()
            return

        plugin_display_name = current_item.text() 
        plugin_key = plugin_metadata.get('name', '').lower() # The reliable lowercase key from discovery metadata

        self.plugin_name_label.setText(f"<b>{plugin_display_name}</b>")
        self.plugin_version_label.setText(plugin_metadata.get('version', 'N/A'))
        self.plugin_author_label.setText(plugin_metadata.get('author', 'N/A'))
        self.plugin_description_label.setText(plugin_metadata.get('description', 'No description available.'))
        
        requires = plugin_metadata.get('requires', [])
        self.plugin_requires_label.setText(", ".join(requires) if requires else "None")
        
        # Determine status based on the plugin_key by checking PluginManager state
        is_loaded = plugin_key in self.plugin_manager.plugins 
        is_setup = is_loaded and self.plugin_manager.plugins[plugin_key].get('is_setup', False)
        is_enabled = plugin_key in self.plugin_manager.enabled_plugins
        
        status_text_parts = []
        status_style = "color: gray;" # Default for discovered

        if is_enabled:
            status_text_parts.append("Enabled")
            if is_setup:
                status_text_parts.append("Setup Complete")
            elif is_loaded: # Should ideally be setup if enabled
                status_text_parts.append("Loaded (Setup Incomplete!)") 
            status_style = "color: darkgreen; font-weight: bold;"
        elif is_loaded: # Loaded but not enabled
            status_text_parts.append("Loaded (Disabled)")
            if is_setup:
                status_text_parts.append("Setup Complete")
            else: 
                status_text_parts.append("Setup Pending")
            status_style = "color: orange; font-weight: bold;" # orange for loaded but not enabled
        else: # Discovered, not loaded
            status_text_parts.append("Discovered (Not Loaded)")
        
        self.plugin_status_label.setText(", ".join(status_text_parts))
        self.plugin_status_label.setStyleSheet(status_style)
        
        # --- MODIFIED BUTTON LOGIC ---
        # Enable button should be active if the plugin is NOT currently enabled.
        # PluginManager.enable_plugin (called by self.enable_selected_plugin)
        # will handle the full lifecycle: load, setup, and then call plugin's own enable.
        self.enable_button.setEnabled(not is_enabled) 
        self.disable_button.setEnabled(is_enabled)
        
    def clear_plugin_details(self):
        self.plugin_name_label.setText("N/A")
        self.plugin_version_label.setText("N/A")
        self.plugin_author_label.setText("N/A")
        self.plugin_description_label.setText("Select a plugin to see details.")
        self.plugin_requires_label.setText("N/A")
        self.plugin_status_label.setText("N/A")
        self.plugin_status_label.setStyleSheet("") # Reset style
        
        self.enable_button.setEnabled(False)
        self.disable_button.setEnabled(False)
        
    def enable_selected_plugin(self):
        current_item = self.plugin_list_widget.currentItem()
        if not current_item: return
            
        plugin_metadata = current_item.data(QtCore.Qt.UserRole)
        if not plugin_metadata: return

        plugin_key = plugin_metadata.get('name', '').lower()
        plugin_display_name = plugin_metadata.get('original_name', plugin_key)

        if not plugin_key:
            QtWidgets.QMessageBox.warning(self, "Plugin Action Error", "Invalid plugin data.")
            return

        # PluginManager.enable_plugin is now responsible for the full sequence:
        # 1. Load (call initialize()) if not already loaded (not in self.plugin_manager.plugins)
        # 2. Setup (call instance.setup()) if not already setup (checks 'is_setup' flag in plugin_data)
        # 3. Enable (call instance.enable())
        success = self.plugin_manager.enable_plugin(plugin_key) 
        
        if success:
            # Optionally show a less intrusive notification or just rely on list refresh
            # QtWidgets.QMessageBox.information(self, "Plugin Enabled", f"Plugin '{plugin_display_name}' enabled successfully.")
            pass # Success is visually indicated by list refresh
        else:
            QtWidgets.QMessageBox.warning(self, "Plugin Action Failed", f"Failed to enable plugin '{plugin_display_name}'. Check logs for details.")
        self.load_plugin_data() # Refresh list to show new status and update button states
    
    def disable_selected_plugin(self):
        current_item = self.plugin_list_widget.currentItem()
        if not current_item: return

        plugin_metadata = current_item.data(QtCore.Qt.UserRole)
        if not plugin_metadata: return

        plugin_key = plugin_metadata.get('name', '').lower()
        plugin_display_name = plugin_metadata.get('original_name', plugin_key)

        if not plugin_key:
            QtWidgets.QMessageBox.warning(self, "Plugin Action Error", "Invalid plugin data.")
            return

        success = self.plugin_manager.disable_plugin(plugin_key) # PM's disable calls plugin's disable
        
        if success:
            # QtWidgets.QMessageBox.information(self, "Plugin Disabled", f"Plugin '{plugin_display_name}' disabled successfully.")
            pass
        else:
            QtWidgets.QMessageBox.warning(self, "Plugin Action Failed", f"Failed to disable plugin '{plugin_display_name}'.")
        self.load_plugin_data() # Refresh list

# Example usage (for testing this dialog standalone, not part of main app flow):
if __name__ == '__main__':
    app = QtWidgets.QApplication(sys.argv)

    # Mock PluginManager for testing the dialog
    class MockPluginManager:
        def __init__(self):
            self._discovered_plugins = {
                'plugin_a': {'name': 'plugin_a', 'original_name': 'Plugin A', 'version': '1.0', 'author': 'Dev A', 'description': 'Description for A', 'requires': ['plugin_b']},
                'multiplayer': {'name': 'multiplayer', 'original_name': 'Multiplayer', 'version': '0.9', 'author': 'Dev MP', 'description': 'Multiplayer functionality plugin.'},
                'plugin_b': {'name': 'plugin_b', 'original_name': 'Plugin B', 'version': '2.1', 'author': 'Dev B', 'description': 'Description for B, a utility plugin.'},
                'plugin_c': {'name': 'plugin_c', 'original_name': 'Plugin C (Core)', 'version': '1.5', 'author': 'Dev C', 'description': 'Core C functionality.'},
            }
            self.plugins = { # Mock some as "loaded"
                 'plugin_b': {'instance': object(), 'is_setup': True, 'original_name': 'Plugin B', 'name': 'plugin_b'}
            }
            self.enabled_plugins = {'plugin_b'} # Mock 'plugin_b' as also enabled

        def get_enabled_plugins(self): # This method on PM returns list of original_names
            return [self.plugins[key].get('original_name', key) for key in self.enabled_plugins if key in self.plugins]

        def enable_plugin(self, key):
            print(f"Dialog trying to enable: {key}")
            if key not in self._discovered_plugins: return False
            # Simulate loading if not loaded
            if key not in self.plugins:
                self.plugins[key] = self._discovered_plugins[key].copy()
                self.plugins[key]['instance'] = object() # Mock instance
                self.plugins[key]['is_setup'] = False
                print(f"PM: Loaded {key}")
            # Simulate setup if not setup
            if not self.plugins[key].get('is_setup'):
                 self.plugins[key]['is_setup'] = True
                 print(f"PM: Setup {key}")
            self.enabled_plugins.add(key)
            print(f"PM: Enabled {key}")
            return True

        def disable_plugin(self, key):
            print(f"Dialog trying to disable: {key}")
            if key in self.enabled_plugins:
                self.enabled_plugins.remove(key)
                print(f"PM: Disabled {key}")
                return True
            return False

    mock_pm = MockPluginManager()
    dialog = PluginManagerDialog(mock_pm)
    dialog.show()
    sys.exit(app.exec_())