"""The plugin's windows and menus: dashboard, status bar, settings, the
connection lines between tanks, and gifts left by visitors.
"""
import os
import time
import random
import math
from PyQt5 import QtCore, QtGui, QtWidgets
from . import mp_constants # Access constants like mp_constants.PLUGIN_NAME


class MultiplayerInterfaceMixin:
    """Part of MultiplayerPlugin (see mp_plugin_logic.py); not used on its own."""

    def handle_squid_interaction(self, local_squid, remote_node_id, remote_squid_data):
        """Handles interactions between the local squid and a detected remote squid."""
        if not self.logger: return
        if not local_squid or not remote_squid_data or not self.tamagotchi_logic: return
        local_pos = (local_squid.squid_x, local_squid.squid_y)
        remote_pos = (remote_squid_data.get('x',0.0), remote_squid_data.get('y',0.0))
        distance = math.hypot(local_pos[0] - remote_pos[0], local_pos[1] - remote_pos[1])
        interaction_distance_threshold = 80 # Example threshold
        if distance < interaction_distance_threshold:
            if hasattr(local_squid, 'memory_manager') and hasattr(local_squid.memory_manager, 'add_short_term_memory'):
                local_squid.memory_manager.add_short_term_memory(
                    category='social', event_type='squid_meeting',
                    description=f"Met squid {remote_node_id[-6:]} from another tank.",
                    importance=5
                )
            self.attempt_gift_exchange(local_squid, remote_node_id)

    def attempt_gift_exchange(self, local_squid, remote_node_id: str):
        """Allows squids to exchange a random decoration item if conditions are met."""
        if not self.logger: return False
        if random.random() > 0.15: return False # 15% chance
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return False
        ui = self.tamagotchi_logic.user_interface
        local_decorations = [
            item for item in ui.scene.items()
            if isinstance(item, QtWidgets.QGraphicsPixmapItem) and
               getattr(item, 'category', '') == 'decoration' and
               item.isVisible() and not getattr(item, 'is_foreign', False) and # Not already from remote
               not getattr(item, 'is_gift_from_remote', False) # Not a gift they received
        ]
        if not local_decorations: return False
        gift_to_send_away = random.choice(local_decorations)
        
        # Simulate receiving a gift (create a new decoration)
        received_gift_item = self.create_gift_decoration(remote_node_id)
        
        if received_gift_item: # If a gift was successfully created for the local scene
            # Make the local squid's chosen decoration disappear (sent away)
            gift_to_send_away.setVisible(False)
            # Optionally, remove it from the scene after a delay or permanently
            QtCore.QTimer.singleShot(15000, lambda item=gift_to_send_away: self._remove_gifted_item_from_scene(item))

            if hasattr(local_squid, 'memory_manager'):
                local_squid.memory_manager.add_short_term_memory(
                    'social', 'decoration_exchange',
                    f"Exchanged decorations with squid {remote_node_id[-6:]}!", importance=7
                )
            if hasattr(self.tamagotchi_logic, 'show_message'):
                self.tamagotchi_logic.show_message(f"🎁 Your squid exchanged gifts with {remote_node_id[-6:]}!")
            return True
        return False

    def _remove_gifted_item_from_scene(self, item_to_remove):
        """Safely removes an item from the scene if it's still present."""
        if not self.logger: return
        if item_to_remove and self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
            scene = self.tamagotchi_logic.user_interface.scene
            if item_to_remove in scene.items():
                scene.removeItem(item_to_remove)
                if self.debug_mode: self.logger.debug(f"Removed gifted item '{getattr(item_to_remove,'filename','N/A')}' from scene.")

    def create_stolen_rocks(self, local_squid, num_rocks: int, entry_position: tuple):
        """Creates rock items in the local scene, representing rocks 'stolen' by the local squid from a remote tank."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface') or num_rocks <= 0:
            return
        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        rock_image_files = []
        search_paths = [os.path.join("images", "decoration"), "images"] # Common paths for rocks
        for path in search_paths:
            if os.path.exists(path):
                for filename in os.listdir(path):
                    if 'rock' in filename.lower() and filename.lower().endswith(('.png', '.jpg')):
                        rock_image_files.append(os.path.join(path, filename))
        
        if not rock_image_files: # Fallback if no specific rocks found
            rock_image_files.append(os.path.join("images", "rock.png")) # Assume a default rock image

        entry_x, entry_y = entry_position
        for i in range(num_rocks):
            try:
                chosen_rock_file = random.choice(rock_image_files)
                # Scatter rocks around the entry point
                angle_offset = random.uniform(-math.pi / 4, math.pi / 4) 
                angle = (i * (2 * math.pi / num_rocks)) + angle_offset 
                dist = random.uniform(60, 100) # Distance from entry point
                rock_x = entry_x + dist * math.cos(angle)
                rock_y = entry_y + dist * math.sin(angle)

                rock_pixmap = QtGui.QPixmap(chosen_rock_file)
                if rock_pixmap.isNull(): continue # Skip if image fails to load

                rock_graphics_item = None
                if hasattr(ui, 'ResizablePixmapItem'): # Check if custom item class exists
                    rock_graphics_item = ui.ResizablePixmapItem(rock_pixmap, chosen_rock_file)
                else:
                    rock_graphics_item = QtWidgets.QGraphicsPixmapItem(rock_pixmap)
                    setattr(rock_graphics_item, 'filename', chosen_rock_file) # Store filename if not ResizablePixmapItem
                
                setattr(rock_graphics_item, 'category', 'rock')
                setattr(rock_graphics_item, 'can_be_picked_up', True)
                setattr(rock_graphics_item, 'is_stolen_from_remote', True)
                setattr(rock_graphics_item, 'is_foreign', True) # Mark as foreign for tinting
                rock_graphics_item.setPos(rock_x, rock_y)
                scene.addItem(rock_graphics_item)
                self.apply_foreign_object_tint(rock_graphics_item) # Apply a visual tint

                # Simple fade-in for stolen rocks (no complex animation for static testing)
                rock_graphics_item.setOpacity(0.2) # Start slightly transparent
                # Removed QPropertyAnimation for opacity for static testing
                rock_graphics_item.setOpacity(1.0) # Make fully visible immediately


            except Exception as e:
                if self.debug_mode: self.logger.error(f"Error creating stolen rock visuals: {e}", exc_info=True)
        
        if hasattr(local_squid, 'memory_manager'):
            local_squid.memory_manager.add_short_term_memory(
                'achievement', 'rock_heist',
                f"Brought back {num_rocks} rocks from an adventure!", importance=8
            )

    def apply_foreign_object_tint(self, q_graphics_item: QtWidgets.QGraphicsPixmapItem):
        """Applies a visual tint to indicate an object is from a remote instance."""
        if not self.logger: return
        if not isinstance(q_graphics_item, QtWidgets.QGraphicsPixmapItem): return
        
        existing_effect = q_graphics_item.graphicsEffect()
        if isinstance(existing_effect, QtWidgets.QGraphicsColorizeEffect):
            # Update existing effect if it's already the right type
            existing_effect.setColor(QtGui.QColor(255, 120, 120, 200)) # Tint color (e.g., reddish)
            existing_effect.setStrength(0.3) # Tint strength
        else:
            # Create and apply new effect
            colorize_effect = QtWidgets.QGraphicsColorizeEffect()
            colorize_effect.setColor(QtGui.QColor(255, 120, 120, 200)) 
            colorize_effect.setStrength(0.3)
            q_graphics_item.setGraphicsEffect(colorize_effect)
        setattr(q_graphics_item, 'is_foreign', True) # Ensure flag is set

    def show_network_dashboard(self):
        """Displays a dialog with detailed network status and peer information."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface') or not self.network_node:
            self.logger.warning("Cannot show network dashboard - UI or NetworkNode missing.")
            return

        parent_window = self.tamagotchi_logic.user_interface.window
        dashboard_dialog = QtWidgets.QDialog(parent_window)
        dashboard_dialog.setWindowTitle("Multiplayer Network Dashboard")
        dashboard_dialog.setMinimumSize(550, 450)

        main_layout = QtWidgets.QVBoxLayout(dashboard_dialog)

        # Connection Info Group
        conn_info_group = QtWidgets.QGroupBox("My Connection")
        conn_info_form = QtWidgets.QFormLayout(conn_info_group)
        node_id_label = QtWidgets.QLabel(self.network_node.node_id)
        ip_label = QtWidgets.QLabel(self.network_node.local_ip)
        status_val_label = QtWidgets.QLabel() # Will be updated
        conn_info_form.addRow("Node ID:", node_id_label)
        conn_info_form.addRow("Local IP:", ip_label)
        conn_info_form.addRow("Status:", status_val_label)
        main_layout.addWidget(conn_info_group)

        # Peers Group
        peers_group = QtWidgets.QGroupBox("Detected Peers")
        peers_layout = QtWidgets.QVBoxLayout(peers_group)
        peers_table_widget = QtWidgets.QTableWidget()
        peers_table_widget.setColumnCount(4)
        peers_table_widget.setHorizontalHeaderLabels(["Node ID", "IP Address", "Last Seen", "Status"])
        peers_table_widget.horizontalHeader().setStretchLastSection(True)
        peers_table_widget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        peers_table_widget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        peers_layout.addWidget(peers_table_widget)
        main_layout.addWidget(peers_group)
        
        # Network Stats Group (Conceptual)
        stats_group = QtWidgets.QGroupBox("Network Statistics (Conceptual)")
        stats_form = QtWidgets.QFormLayout(stats_group)
        # These read the real counters now. Both rows used to name attributes
        # NetworkNode has never had, so they showed "N/A" - and an instance
        # that was sending into a group it never listened to looked exactly
        # like a healthy one.
        sent_label = QtWidgets.QLabel("0")
        received_label = QtWidgets.QLabel("0")
        listening_label = QtWidgets.QLabel("unknown")
        stats_form.addRow("Messages Sent:", sent_label)
        stats_form.addRow("Messages Received:", received_label)
        stats_form.addRow("Listener:", listening_label)
        main_layout.addWidget(stats_group)


        def refresh_dashboard_data():
            # Update connection status
            is_connected = self.network_node.is_connected
            status_val_label.setText("Connected" if is_connected else "Disconnected")
            status_val_label.setStyleSheet("color: green; font-weight: bold;" if is_connected else "color: red; font-weight: bold;")

            # Traffic, so "am I actually hearing anything" is answerable at a
            # glance. Received sitting at 0 while Sent climbs means this
            # instance is talking and not listening.
            node = self.network_node
            sent_label.setText(str(getattr(node, 'messages_sent', 0)))
            received_label.setText(str(getattr(node, 'messages_received', 0)))
            if node is not None and node.is_listening():
                listening_label.setText("running")
                listening_label.setStyleSheet("color: green;")
            else:
                listening_label.setText("NOT RUNNING - no peer can be seen")
                listening_label.setStyleSheet("color: red; font-weight: bold;")

            # Update peers table
            peers_table_widget.setRowCount(0) # Clear table
            if self.network_node: # Check if network_node still exists
                for row, (node_id, (ip, last_seen, _)) in enumerate(self.network_node.known_nodes.items()):
                    peers_table_widget.insertRow(row)
                    peers_table_widget.setItem(row, 0, QtWidgets.QTableWidgetItem(node_id))
                    peers_table_widget.setItem(row, 1, QtWidgets.QTableWidgetItem(ip))
                    time_delta_secs = time.time() - last_seen
                    time_ago_str = f"{int(time_delta_secs)}s ago"
                    peers_table_widget.setItem(row, 2, QtWidgets.QTableWidgetItem(time_ago_str))
                    
                    peer_status_str = "Active" if time_delta_secs < 20 else "Inactive" # Example threshold
                    status_cell_item = QtWidgets.QTableWidgetItem(peer_status_str)
                    status_cell_item.setForeground(QtGui.QBrush(QtGui.QColor("green" if peer_status_str == "Active" else "gray")))
                    peers_table_widget.setItem(row, 3, status_cell_item)
            peers_table_widget.resizeColumnsToContents()
        
        refresh_dashboard_data() # Initial population

        # Buttons
        button_box = QtWidgets.QDialogButtonBox()
        refresh_btn = button_box.addButton("Refresh", QtWidgets.QDialogButtonBox.ActionRole)
        close_btn = button_box.addButton(QtWidgets.QDialogButtonBox.Close)
        refresh_btn.clicked.connect(refresh_dashboard_data)
        close_btn.clicked.connect(dashboard_dialog.accept)
        main_layout.addWidget(button_box)

        dashboard_dialog.exec_()

    def initialize_status_ui(self):
        """Initializes UI components for displaying multiplayer status."""
        if not self.logger: return
        try:
            if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'):
                self.logger.warning("Status UI cannot be initialized - user_interface not found.")
                return

            ui = self.tamagotchi_logic.user_interface
            try:
                from plugins.multiplayer.multiplayer_status_widget import MultiplayerStatusWidget
                if not hasattr(ui, '_mp_status_widget_instance_'): # Create if not exists
                    ui._mp_status_widget_instance_ = MultiplayerStatusWidget(ui.window)
                    # Position the widget (example: top-right corner)
                    ui._mp_status_widget_instance_.move(
                        ui.window.width() - ui._mp_status_widget_instance_.width() - 15, 15
                    )
                    ui._mp_status_widget_instance_.hide() # Initially hidden
                
                self.status_widget = ui._mp_status_widget_instance_
                if self.network_node and hasattr(self.status_widget, 'set_network_node_reference'):
                    self.status_widget.set_network_node_reference(self.network_node)
                self.logger.info("Dedicated status widget initialized.")

            except ImportError:
                self.logger.info("MultiplayerStatusWidget not found. Will attempt fallback status bar integration.")
                self.initialize_status_bar() # Fallback
            except Exception as e_msw:
                self.logger.error(f"Error initializing MultiplayerStatusWidget: {e_msw}. Using fallback.", exc_info=True)
                self.initialize_status_bar() # Fallback

        except Exception as e:
            self.logger.error(f"Could not initialize status UI: {e}", exc_info=True)

    def initialize_status_bar(self): # Added stub, assuming it was missing
        """Fallback to initialize status bar component if dedicated widget fails."""
        if not self.logger: return
        self.logger.info("Attempting to initialize fallback status bar component.")
        # Implementation for status_bar initialization would go here
        # For now, just log that it's a fallback
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface') and \
           hasattr(self.tamagotchi_logic.user_interface, 'statusBar'): # Example access
            self.status_bar = self.tamagotchi_logic.user_interface.statusBar()
            # Example: Add a permanent widget or label to the status bar
            # if self.status_bar and not hasattr(self, '_mp_status_label_basic'):
            #     self._mp_status_label_basic = QtWidgets.QLabel("MP: Disconnected")
            #     self.status_bar.addPermanentWidget(self._mp_status_label_basic)
            self.logger.info("Fallback status bar component obtained.")
        else:
            self.logger.warning("Fallback status bar component could not be obtained.")

    def register_menu_actions(self, main_ui_window: QtWidgets.QMainWindow, target_menu: QtWidgets.QMenu):
        """Registers menu actions related to the multiplayer plugin."""
        if not self.logger: return

        about_action = QtWidgets.QAction(f"About {mp_constants.PLUGIN_NAME}...", main_ui_window)
        about_action.triggered.connect(self.show_about_dialog)
        target_menu.addAction(about_action)

        config_action = QtWidgets.QAction("Network Settings...", main_ui_window)
        config_action.triggered.connect(self.show_config_dialog)
        target_menu.addAction(config_action)

        dashboard_action = QtWidgets.QAction("Network Dashboard...", main_ui_window)
        dashboard_action.triggered.connect(self.show_network_dashboard)
        target_menu.addAction(dashboard_action)

        friends_action = QtWidgets.QAction("Friends (internet play)...", main_ui_window)
        friends_action.triggered.connect(self.show_friends_dialog)
        target_menu.addAction(friends_action)
        
        target_menu.addSeparator()

        refresh_connections_action = QtWidgets.QAction("Refresh Connections", main_ui_window)
        refresh_connections_action.triggered.connect(self.refresh_connections)
        target_menu.addAction(refresh_connections_action)

        # Toggle for connection lines
        self.mp_menu_toggle_connection_lines_action = QtWidgets.QAction("Show Connection Lines", main_ui_window)
        self.mp_menu_toggle_connection_lines_action.setCheckable(True)
        self.mp_menu_toggle_connection_lines_action.setChecked(self.SHOW_CONNECTION_LINES)
        self.mp_menu_toggle_connection_lines_action.triggered.connect(self.toggle_connection_lines)
        target_menu.addAction(self.mp_menu_toggle_connection_lines_action)
        
        if self.debug_mode: # Debug specific actions
            target_menu.addSeparator()
            debug_autopilot_action = QtWidgets.QAction("Debug Autopilot Status", main_ui_window)
            debug_autopilot_action.triggered.connect(self.debug_autopilot_status)
            target_menu.addAction(debug_autopilot_action)

    def update_menu_states(self):
        """Updates the state of checkable menu items."""
        if hasattr(self, 'mp_menu_toggle_connection_lines_action'):
            self.mp_menu_toggle_connection_lines_action.setChecked(self.SHOW_CONNECTION_LINES)

    def show_about_dialog(self):
        """Displays an 'About' dialog."""
        if not self.logger: return
        parent_window = None
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
            parent_window = self.tamagotchi_logic.user_interface.window
        
        node_id_str = getattr(self.network_node, 'node_id', "N/A") if self.network_node else "N/A"
        ip_str = getattr(self.network_node, 'local_ip', "N/A") if self.network_node else "N/A"
        status_str = "Connected" if self.network_node and self.network_node.is_connected else "Disconnected"

        about_text_content = (
            f"<h3>{mp_constants.PLUGIN_NAME}</h3>"
            f"<p><b>Version:</b> {mp_constants.PLUGIN_VERSION}<br>"
            f"<b>Author:</b> {mp_constants.PLUGIN_AUTHOR}</p>"
            f"<p>{mp_constants.PLUGIN_DESCRIPTION}</p><hr>"
            f"<p><b>Node ID:</b> {node_id_str}<br>"
            f"<b>Local IP:</b> {ip_str}<br>"
            f"<b>Status:</b> {status_str}</p>"
        )
        QtWidgets.QMessageBox.about(parent_window, f"About {mp_constants.PLUGIN_NAME}", about_text_content)

    def show_config_dialog(self):
        """Displays the configuration dialog for multiplayer settings."""
        if not self.logger: return
        try:
            from .multiplayer_config_dialog import MultiplayerConfigDialog
        except ImportError:
            self.logger.error("MultiplayerConfigDialog class/file not found.")
            parent_win = self.tamagotchi_logic.user_interface.window if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface') else None
            QtWidgets.QMessageBox.critical(parent_win, "Configuration Error", "The multiplayer settings dialog could not be loaded.")
            return

        parent_window = None
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
            parent_window = self.tamagotchi_logic.user_interface.window

        current_settings = {
            'multicast_group': self.MULTICAST_GROUP, 'port': self.MULTICAST_PORT,
            'sync_interval': self.SYNC_INTERVAL, 'remote_opacity': self.REMOTE_SQUID_OPACITY,
            'show_labels': self.SHOW_REMOTE_LABELS, 'show_connections': self.SHOW_CONNECTION_LINES,
            'debug_mode': self.debug_mode,
            'auto_reconnect': self.network_node.auto_reconnect if self.network_node else True,
            'use_compression': self.network_node.use_compression if self.network_node else True
        }
        
        if not self.config_dialog or not self.config_dialog.isVisible(): # Create new or reuse
            self.config_dialog = MultiplayerConfigDialog(
                plugin_instance=self, parent=parent_window, initial_settings=current_settings
            )
        else:
            self.config_dialog.load_settings(current_settings) # Update existing dialog with current settings
        
        self.config_dialog.exec_() # Show as modal dialog

    def toggle_connection_lines(self, checked_state: bool):
        """Toggles the visibility of connection lines."""
        if not self.logger: return
        self.SHOW_CONNECTION_LINES = checked_state
        
        # This will be handled by entity_manager's update_settings or fallback update_connection_lines
        if getattr(self, 'entity_manager', None):
            self.entity_manager.update_settings(show_connections=self.SHOW_CONNECTION_LINES)
        else: # Fallback if no entity manager
            if hasattr(self.tamagotchi_logic, 'user_interface') and self.tamagotchi_logic.user_interface:
                scene = self.tamagotchi_logic.user_interface.scene
                for line_item in self.connection_lines.values():
                    if line_item in scene.items(): # Check if item is still in scene
                        line_item.setVisible(self.SHOW_CONNECTION_LINES)
                if not self.SHOW_CONNECTION_LINES: # If hiding, remove them
                    for node_id_key in list(self.connection_lines.keys()):
                        line_to_remove = self.connection_lines.pop(node_id_key)
                        if line_to_remove in scene.items():
                            scene.removeItem(line_to_remove)
            self.update_connection_lines() # Trigger an update to draw/remove lines

        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(f"Connection lines to remote squids {'shown' if checked_state else 'hidden'}.")

    def refresh_connections(self):
        """Manually triggers a network presence announcement."""
        if not self.logger: return
        if not self.network_node:
            msg = "Multiplayer: Network component not initialized. Cannot refresh."
            if hasattr(self.tamagotchi_logic, 'show_message'): self.tamagotchi_logic.show_message(msg)
            else: self.logger.warning(msg)
            return

        if not self.network_node.is_connected:
            if self.debug_mode: self.logger.debug("Attempting to reconnect before refresh...")
            self.network_node.try_reconnect() # Attempt reconnect if not connected

        message_to_show = ""
        if self.network_node.is_connected:
            self.network_node.send_message(
                'heartbeat',
                {'node_id': self.network_node.node_id, 'status': 'active_refresh_request'}
            )
            message_to_show = "Multiplayer: Sent network heartbeat. Checking for peers..."
        else:
            message_to_show = "Multiplayer: Network disconnected. Could not send heartbeat."

        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(message_to_show)
        elif self.debug_mode or not self.network_node.is_connected: # Log if no UI message or on error
            self.logger.info(message_to_show)

        # Update UI status
        current_peers_count = len(self.network_node.known_nodes if self.network_node else {})
        if self.status_widget:
            self.status_widget.update_peers(self.network_node.known_nodes if self.network_node else {})
            self.status_widget.add_activity(f"Connections refreshed. {current_peers_count} peers currently detected.")
        elif self.status_bar: # Fallback to basic status bar
            if hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(current_peers_count)
            if hasattr(self.status_bar, 'showMessage'): self.status_bar.showMessage(f"Refreshed. {current_peers_count} peers.", 3000)

    def update_connection_lines(self):
        """(Fallback) Updates visual lines connecting local squid to remote squids if entity_manager is None."""
        if not self.logger: return
        if self.entity_manager: return # entity_manager handles its own connection lines

        if not self.SHOW_CONNECTION_LINES or not self.tamagotchi_logic or \
           not self.tamagotchi_logic.squid or not self.tamagotchi_logic.user_interface or \
           not self.tamagotchi_logic.squid.squid_item: # Ensure all parts exist
            # Clear existing lines if not showing or prerequisites missing
            if hasattr(self.tamagotchi_logic, 'user_interface') and self.tamagotchi_logic.user_interface:
                scene = self.tamagotchi_logic.user_interface.scene
                for node_id_key in list(self.connection_lines.keys()):
                    line_to_remove = self.connection_lines.pop(node_id_key)
                    if line_to_remove in scene.items(): scene.removeItem(line_to_remove)
            return

        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        local_squid_visual = self.tamagotchi_logic.squid.squid_item
        local_rect = local_squid_visual.boundingRect()
        local_center_pos = local_squid_visual.pos() + local_rect.center() # Center of local squid

        active_remote_node_ids = set()
        for node_id, remote_squid_info in self.remote_squids.items(): # Iterate this plugin's remote_squids
            remote_visual = remote_squid_info.get('visual')
            if not remote_visual or not remote_visual.isVisible() or remote_visual not in scene.items():
                continue # Skip if no visual or not in scene
            
            active_remote_node_ids.add(node_id)
            remote_rect = remote_visual.boundingRect()
            remote_center_pos = remote_visual.pos() + remote_rect.center() # Center of remote squid

            line_color_data = remote_squid_info.get('data', {}).get('color', (100, 100, 255)) # Use squid's color
            try:
                pen_color = QtGui.QColor(*line_color_data, 120) # Add alpha
            except TypeError:
                pen_color = QtGui.QColor(100,100,255,120) # Default color

            pen = QtGui.QPen(pen_color)
            pen.setWidth(2)
            pen.setStyle(QtCore.Qt.DashLine) # Dashed line style

            if node_id in self.connection_lines: # Update existing line
                line = self.connection_lines[node_id]
                if line not in scene.items(): scene.addItem(line) # Re-add if removed somehow
                line.setLine(local_center_pos.x(), local_center_pos.y(), remote_center_pos.x(), remote_center_pos.y())
                line.setPen(pen)
                line.setVisible(True)
            else: # Create new line
                line = QtWidgets.QGraphicsLineItem(
                    local_center_pos.x(), local_center_pos.y(), remote_center_pos.x(), remote_center_pos.y()
                )
                line.setPen(pen)
                line.setZValue(-10) # Draw behind other items
                scene.addItem(line)
                self.connection_lines[node_id] = line
        
        # Remove lines for squids that are no longer active/present
        for node_id_key in list(self.connection_lines.keys()):
            if node_id_key not in active_remote_node_ids:
                line_to_remove = self.connection_lines.pop(node_id_key)
                if line_to_remove in scene.items():
                    scene.removeItem(line_to_remove)

    def create_gift_decoration(self, from_remote_node_id: str) -> QtWidgets.QGraphicsPixmapItem | None:
        """Creates a new decoration item representing a received gift."""
        if not self.logger: return None
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return None
        
        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        
        available_decoration_images = []
        decoration_image_dirs = [os.path.join("images", "decoration"), "images"] # Search paths
        for img_dir in decoration_image_dirs:
            if os.path.exists(img_dir):
                for filename in os.listdir(img_dir):
                    if filename.lower().endswith(('.png', '.jpg', '.gif')) and \
                       any(kw in filename.lower() for kw in ['decor', 'plant', 'toy', 'shell', 'coral', 'starfish', 'gem']): # Keywords for decorations
                        available_decoration_images.append(os.path.join(img_dir, filename))
        
        if not available_decoration_images: # Fallback if no specific decorations found
            default_gift_img = os.path.join("images", "plant.png") # Example default
            if not os.path.exists(default_gift_img):
                if self.debug_mode: self.logger.warning("Default gift image 'plant.png' not found. Cannot create gift.")
                return None
            available_decoration_images.append(default_gift_img)

        chosen_gift_image_path = random.choice(available_decoration_images)
        
        try:
            gift_pixmap = QtGui.QPixmap(chosen_gift_image_path)
            if gift_pixmap.isNull():
                if self.debug_mode: self.logger.error(f"Failed to load gift image '{chosen_gift_image_path}'.")
                return None

            gift_item = None
            if hasattr(ui, 'ResizablePixmapItem'): # Use custom item if available
                gift_item = ui.ResizablePixmapItem(gift_pixmap, chosen_gift_image_path)
            else: # Use standard QGraphicsPixmapItem
                gift_item = QtWidgets.QGraphicsPixmapItem(gift_pixmap)
                setattr(gift_item, 'filename', chosen_gift_image_path) # Store filename

            setattr(gift_item, 'category', 'decoration')
            setattr(gift_item, 'is_gift_from_remote', True) # Mark as a received gift
            setattr(gift_item, 'received_from_node', from_remote_node_id) # Store sender
            gift_item.setToolTip(f"A surprise gift from tank {from_remote_node_id[-6:]}!")

            # Position the gift randomly but within bounds
            item_width = gift_pixmap.width() * gift_item.scale() # Account for scale
            item_height = gift_pixmap.height() * gift_item.scale()
            max_placement_x = ui.window_width - item_width - 30 # 30px margin
            max_placement_y = ui.window_height - item_height - 30
            gift_pos_x = random.uniform(30, max(30, max_placement_x))
            gift_pos_y = random.uniform(30, max(30, max_placement_y))
            gift_item.setPos(gift_pos_x, gift_pos_y)
            
            self.apply_foreign_object_tint(gift_item) # Apply tint to show it's from remote
            scene.addItem(gift_item)
            
            # Static display for gift, no complex animation
            gift_item.setOpacity(0.0) # Start transparent
            # MODIFIED: For static testing, make it immediately visible
            gift_item.setOpacity(1.0)


            # Optional: Add a temporary "🎁 Gift!" text label above it
            gift_indicator_label = scene.addText("🎁 Gift!")
            label_font = QtGui.QFont("Fio UI", 10, QtGui.QFont.Bold)
            gift_indicator_label.setFont(label_font)
            gift_indicator_label.setDefaultTextColor(QtGui.QColor(255, 100, 100)) # Bright color
            label_x = gift_pos_x + (item_width / 2) - (gift_indicator_label.boundingRect().width() / 2)
            label_y = gift_pos_y - gift_indicator_label.boundingRect().height() - 5 # Above gift
            gift_indicator_label.setPos(label_x, label_y)
            gift_indicator_label.setZValue(gift_item.zValue() + 1) # Ensure label is on top
            # Make label disappear after a few seconds
            QtCore.QTimer.singleShot(4000, lambda item=gift_indicator_label: item.scene().removeItem(item) if item.scene() else None)

            return gift_item
        except Exception as e_gift:
            if self.debug_mode: self.logger.error(f"Error creating gift decoration: {e_gift}", exc_info=True)
            return None
