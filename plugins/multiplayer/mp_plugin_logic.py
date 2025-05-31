# File: mp_plugin_logic.py

import os
# import sys # sys.path is handled in main.py
import inspect # For _find_tamagotchi_logic
import json
import uuid
import time
# import socket # Network operations are in NetworkNode
import threading
import queue # For plugin's own internal queuing if different from NetworkNode's
import random
import traceback # For logging exceptions
import math
from typing import Dict, List, Any, Tuple
from PyQt5 import QtCore, QtGui, QtWidgets

# --- Local Imports ---
import logging # Added for logger
from . import mp_constants # Access constants like mp_constants.PLUGIN_NAME
from .mp_network_node import NetworkNode

# TamagotchiLogic is imported in main.py and should be in sys.path
# If type hinting is needed here and main.py's import might not be seen by linters:
try:
    from src.tamagotchi_logic import TamagotchiLogic
except ImportError:
    TamagotchiLogic = None


class MultiplayerPlugin:
    def __init__(self):
        # --- Initialize logger attribute ---
        self.logger = None 

        # --- Locks for thread safety ---
        self.network_lock = threading.RLock()
        self.remote_squids_lock = threading.RLock()
        self.remote_objects_lock = threading.RLock()

        # --- Core Components ---
        self.network_node: NetworkNode | None = None
        self.plugin_manager = None # Set by plugin system or during setup
        self.tamagotchi_logic: TamagotchiLogic | None = None # Set during setup

        # --- Timers and Threads ---
        self.sync_thread: threading.Thread | None = None
        self.message_process_timer: QtCore.QTimer | None = None
        self.controller_update_timer: QtCore.QTimer | None = None
        self.controller_creation_timer: QtCore.QTimer | None = None
        self.cleanup_timer_basic: QtCore.QTimer | None = None
        self.connection_timer_basic: QtCore.QTimer | None = None

        # --- State and Data ---
        self.remote_squids: Dict[str, Dict[str, Any]] = {}
        self.remote_objects: Dict[str, Dict[str, Any]] = {}
        self.remote_squid_controllers: Dict[str, Any] = {}
        self.pending_controller_creations: List[Dict[str, Any]] = []
        self.connection_lines: Dict[str, QtWidgets.QGraphicsLineItem] = {}
        self.last_message_times: Dict[str, float] = {}

        # --- Configuration ---
        self.MULTICAST_GROUP = mp_constants.MULTICAST_GROUP
        self.MULTICAST_PORT = mp_constants.MULTICAST_PORT
        self.SYNC_INTERVAL = mp_constants.SYNC_INTERVAL
        self.REMOTE_SQUID_OPACITY = mp_constants.REMOTE_SQUID_OPACITY
        self.SHOW_REMOTE_LABELS = mp_constants.SHOW_REMOTE_LABELS
        self.SHOW_CONNECTION_LINES = mp_constants.SHOW_CONNECTION_LINES

        # --- UI Elements ---
        self.config_dialog: QtWidgets.QDialog | None = None
        self.status_widget: Any | None = None
        self.status_bar: Any | None = None

        # --- Flags ---
        self.is_setup = False
        self.debug_mode = False
        self.last_controller_update = time.time() # Initialize here

    def debug_autopilot_status(self):
        """Debug the status of all autopilot controllers for remote squids."""
        if not self.logger: # Safeguard
            print("Multiplayer ERRA: Logger not initialized in debug_autopilot_status")
            return

        if not hasattr(self, 'remote_squid_controllers') or not self.remote_squid_controllers:
            self.logger.debug("No remote squid controllers are currently active.")
            return

        self.logger.debug(f"\n=== AUTOPILOT DEBUG ({len(self.remote_squid_controllers)} controllers) ===")
        for node_id, controller in self.remote_squid_controllers.items():
            squid_name = node_id[-6:]
            self.logger.debug(f"Squid {squid_name}:")
            self.logger.debug(f"  State: {getattr(controller, 'state', 'N/A')}")
            squid_data = getattr(controller, 'squid_data', {})
            pos_x = squid_data.get('x', 0.0)
            pos_y = squid_data.get('y', 0.0)
            self.logger.debug(f"  Position: ({pos_x:.1f}, {pos_y:.1f})")
            self.logger.debug(f"  Direction: {squid_data.get('direction', 'N/A')}")
            self.logger.debug(f"  Home Dir: {getattr(controller, 'home_direction', 'N/A')}")
            time_away = getattr(controller, 'time_away', 0.0)
            max_time = getattr(controller, 'max_time_away', 0.0)
            self.logger.debug(f"  Time Away: {time_away:.1f}s / {max_time:.1f}s")
            food_count = getattr(controller, 'food_eaten_count', 0)
            rock_count = getattr(controller, 'rock_interaction_count', 0)
            self.logger.debug(f"  Activities: {food_count} food, {rock_count} rocks")
            target_obj = getattr(controller, 'target_object', None)
            self.logger.debug(f"  Target: {'Yes (' + type(target_obj).__name__ + ')' if target_obj else 'No'}")
        self.logger.debug("=====================================\n")

    def enable(self):
        """Enables the multiplayer plugin, performing setup if necessary."""
        # Safeguard for logger initialization (as previously discussed)
        if self.logger is None:
            emergency_logger = logging.getLogger(f"{mp_constants.PLUGIN_NAME}_EnableEmergency")
            if not emergency_logger.hasHandlers():
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
                handler.setFormatter(formatter)
                emergency_logger.addHandler(handler)
                emergency_logger.setLevel(logging.WARNING)
            self.logger = emergency_logger
            self.logger.warning("Logger was not initialized prior to enable() method. Using emergency logger.")

        self.logger.info(f"Attempting to enable {mp_constants.PLUGIN_NAME}...")
        try:
            is_currently_setup = getattr(self, 'is_setup', False)

            if not is_currently_setup:
                self.logger.info(f"{mp_constants.PLUGIN_NAME} is not yet set up. Proceeding with setup.")

                # --- BEGIN MODIFICATION ---
                # self.plugin_manager should have been set by main.py's initialize function.
                if self.plugin_manager is None:
                    # This is now a more critical error, as it indicates a failure in the
                    # earlier plugin loading/initialization step in plugins/multiplayer/main.py.
                    self.logger.critical("CRITICAL: self.plugin_manager attribute not set on plugin instance prior to enable/setup. Initialization in plugins/multiplayer/main.py might have failed or was skipped.")
                    return False # Cannot proceed without plugin_manager
                # --- END MODIFICATION ---

                # Obtain the tamagotchi_logic_instance required by the setup method.
                tamagotchi_logic_ref = getattr(self, 'tamagotchi_logic', None)

                if tamagotchi_logic_ref is None:
                    tamagotchi_logic_ref = getattr(self.plugin_manager, 'tamagotchi_logic', None)
                
                if tamagotchi_logic_ref is None:
                    self.logger.info("TamagotchiLogic not found directly on plugin_manager, attempting deep search via plugin_manager attributes...")
                    tamagotchi_logic_ref = self._find_tamagotchi_logic(self.plugin_manager)

                if tamagotchi_logic_ref is None:
                    self.logger.error("TamagotchiLogic instance could not be found even after search. Setup cannot proceed.")
                    return False
                
                # Call setup. self.plugin_manager is now expected to be valid.
                # setup() will also assign self.tamagotchi_logic = tamagotchi_logic_ref
                # and initialize self.logger properly.
                if not self.setup(self.plugin_manager, tamagotchi_logic_ref):
                    self.logger.error("Setup method returned False during enable sequence.")
                    return False
            else:
                self.logger.info(f"{mp_constants.PLUGIN_NAME} is already marked as set up. Re-enabling components.")

            # --- Post-setup actions (continue with the rest of the original enable method) ---
            if hasattr(self, 'network_node') and self.network_node and not self.network_node.is_connected:
                self.logger.info("Network node not connected, attempting to initialize socket...")
                self.network_node.initialize_socket()

            if not (hasattr(self, 'sync_thread') and self.sync_thread and self.sync_thread.is_alive()):
                if hasattr(self, 'start_sync_timer'):
                    self.start_sync_timer() # This method should log its own status
                else:
                    self.logger.warning("start_sync_timer method not found.")

            if hasattr(self, 'status_widget') and self.status_widget:
                self.status_widget.show()
                is_connected_now = hasattr(self, 'network_node') and self.network_node and self.network_node.is_connected
                node_id_now = self.network_node.node_id if hasattr(self, 'network_node') and self.network_node else "N/A"
                if hasattr(self.status_widget, 'update_connection_status'): # Check method existence
                    self.status_widget.update_connection_status(is_connected_now, node_id_now)
                if hasattr(self, 'network_node') and self.network_node and hasattr(self.network_node, 'known_nodes') and \
                   hasattr(self.status_widget, 'update_peers'): # Check method existence
                    self.status_widget.update_peers(self.network_node.known_nodes)

            self.logger.info(f"{mp_constants.PLUGIN_NAME} enabled successfully.")
            return True
        except Exception as e:
            # Ensure logger is available before trying to use it, especially in top-level exception handlers
            if self.logger:
                self.logger.error(f"Unhandled error enabling {mp_constants.PLUGIN_NAME}: {e}", exc_info=True)
            else: # Fallback if self.logger itself is None here (shouldn't happen with safeguard)
                print(f"CRITICAL UNLOGGED ERROR in enable for {mp_constants.PLUGIN_NAME}: {e}")
                traceback.print_exc()
            return False

    def disable(self):
        """Disables the multiplayer plugin and cleans up resources."""
        if not self.logger: # Should be set by now
             print("Multiplayer ERRA: Logger not set in disable()") # Fallback to print if logger is broken
             return
        self.logger.info(f"Disabling {mp_constants.PLUGIN_NAME}...")
        if self.network_node and self.network_node.is_connected:
            self.network_node.send_message(
                'player_leave',
                {'node_id': self.network_node.node_id, 'reason': 'plugin_disabled'}
            )

        self.cleanup()

        if self.status_widget: self.status_widget.hide()
        if self.status_bar:
            if hasattr(self.status_bar, 'update_network_status'): self.status_bar.update_network_status(False)
            if hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(0)

        self.logger.info(f"{mp_constants.PLUGIN_NAME} disabled.")

    def setup(self, plugin_manager_instance, tamagotchi_logic_instance):
        """
        Sets up the multiplayer plugin. Called when the plugin is first loaded or enabled.
        Args:
            plugin_manager_instance: A reference to the main plugin manager.
            tamagotchi_logic_instance: A reference to the core tamagotchi logic.
        """
        self.plugin_manager = plugin_manager_instance

        # --- BEGIN LOGGER INITIALIZATION ---
        if hasattr(self.plugin_manager, 'logger') and self.plugin_manager.logger is not None:
            self.logger = self.plugin_manager.logger
        else:
            logger_name = f"{mp_constants.PLUGIN_NAME}_Plugin"
            self.logger = logging.getLogger(logger_name)
            if not self.logger.hasHandlers():
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - [%(levelname)s] - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
            # Initial level, might be changed by debug_mode later
            self.logger.setLevel(logging.INFO) 
            self.logger.warning(
                "PluginManager did not provide a valid logger. Using fallback logger."
            )
        
        self.logger.info(f"Initializing setup for {mp_constants.PLUGIN_NAME}...")
        # --- END LOGGER INITIALIZATION ---

        self.tamagotchi_logic = tamagotchi_logic_instance

        if not TamagotchiLogic:
            self.logger.critical("TamagotchiLogic module was not loaded (import failed). Cannot complete setup.")
            return False

        if self.tamagotchi_logic is None:
            self.logger.warning("TamagotchiLogic instance was not directly passed or was None. Attempting to find it via PluginManager.")
            if hasattr(self.plugin_manager, 'core_game_logic'):
                self.tamagotchi_logic = self.plugin_manager.core_game_logic
            elif hasattr(self.plugin_manager, 'tamagotchi_logic'):
                self.tamagotchi_logic = self.plugin_manager.tamagotchi_logic
            else:
                self.tamagotchi_logic = self._find_tamagotchi_logic(self.plugin_manager)

        if not self.tamagotchi_logic:
            self.logger.critical("TamagotchiLogic instance not found. Plugin functionality will be severely limited.")
        else:
            self.debug_mode = getattr(self.tamagotchi_logic, 'debug_mode', False)
            if self.logger and hasattr(self.logger, 'setLevel'):
                 self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
            self.logger.info(f"TamagotchiLogic instance found. Debug mode: {self.debug_mode}")

        node_id_val = f"squid_{uuid.uuid4().hex[:6]}"
        self.network_node = NetworkNode(node_id_val, logger=self.logger)
        self.network_node.debug_mode = self.debug_mode
        
        if self.tamagotchi_logic:
            setattr(self.tamagotchi_logic, 'multiplayer_network_node', self.network_node)

        if not self.message_process_timer:
            self.message_process_timer = QtCore.QTimer()
            self.message_process_timer.timeout.connect(self._process_network_node_queue)
            self.message_process_timer.start(50)

        if not self.controller_update_timer:
            self.controller_update_timer = QtCore.QTimer()
            self.controller_update_timer.timeout.connect(self.update_remote_controllers)
            self.controller_update_timer.start(50)

        if not self.controller_creation_timer:
             self._setup_controller_creation_timer()

        self._register_hooks()

        self.remote_squids.clear()
        self.remote_objects.clear()
        self.connection_lines.clear()
        self.remote_squid_controllers.clear()
        self.last_controller_update = time.time()

        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
            try:
                from plugins.multiplayer.remote_entity_manager import RemoteEntityManager
                self.entity_manager = RemoteEntityManager(
                    self.tamagotchi_logic.user_interface.scene,
                    self.tamagotchi_logic.user_interface.window_width,
                    self.tamagotchi_logic.user_interface.window_height,
                    self.debug_mode,
                    logger=self.logger
                )
                self.logger.info("Using dedicated RemoteEntityManager.")
            except ImportError:
                self.logger.info("RemoteEntityManager not found. Using basic timers for cleanup/lines.")
                self.entity_manager = None
                self.initialize_remote_representation()
        else:
            self.logger.warning("User interface or TamagotchiLogic not available for RemoteEntityManager setup.")
            self.entity_manager = None
            self.initialize_remote_representation()

        self.initialize_status_ui()

        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'show_message') and self.network_node:
            self.tamagotchi_logic.show_message(f"Multiplayer active! Node ID: {self.network_node.node_id}")

        node_ip = self.network_node.local_ip if self.network_node else "N/A"
        node_port = self.MULTICAST_PORT
        self.logger.info(f"Setup complete. Node: {node_id_val} on IP: {node_ip}. Listening for multicast on port: {node_port}")
        self.is_setup = True
        return True

    def _process_network_node_queue(self, **kwargs):
        """Called by a QTimer to process messages from the NetworkNode's incoming_queue."""
        if not self.logger: return
        if self.network_node and self.plugin_manager:
            try:
                self.network_node.process_messages(self.plugin_manager)
            except Exception as e:
                if self.debug_mode:
                    self.logger.error(f"Error in _process_network_node_queue: {e}", exc_info=True)

    def setup_minimal_network(self):
        """(Helper) Creates a basic network interface if one is required but not found."""
        if not self.logger: return
        self.logger.info("Setting up minimal network interface...")
        class MinimalNetworkInterface:
            def create_socket(self, socket_type='udp'):
                import socket
                return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.plugin_manager:
            self.plugin_manager.plugins['network_interface'] = {
                'instance': MinimalNetworkInterface(), 'name': 'Minimal Network Interface', 'version': '0.1'
            }
            self.logger.info("Minimal network interface registered.")

    def update_remote_squid_image(self, remote_squid_display_data: Dict, direction: str):
        """Updates the visual image of a remote squid based on its direction."""
        if not self.logger: return False
        visual_item = remote_squid_display_data.get('visual')
        if not visual_item or not isinstance(visual_item, QtWidgets.QGraphicsPixmapItem):
            return False
        try:
            base_image_path = "images"
            squid_image_file = f"{direction.lower()}1.png"
            full_image_path = os.path.join(base_image_path, squid_image_file)
            squid_pixmap = QtGui.QPixmap(full_image_path)
            if squid_pixmap.isNull():
                fallback_path = os.path.join(base_image_path, "right1.png")
                squid_pixmap = QtGui.QPixmap(fallback_path)
                if squid_pixmap.isNull() and self.debug_mode:
                    self.logger.warning(f"Could not load squid image '{full_image_path}' or fallback.")
                    return False
            visual_item.setPixmap(squid_pixmap)
            return True
        except Exception as e:
            if self.debug_mode:
                self.logger.error(f"Error updating remote squid image for direction '{direction}': {e}", exc_info=True)
            return False

    def handle_squid_interaction(self, local_squid, remote_node_id, remote_squid_data):
        """Handles interactions between the local squid and a detected remote squid."""
        if not self.logger: return
        if not local_squid or not remote_squid_data or not self.tamagotchi_logic: return
        local_pos = (local_squid.squid_x, local_squid.squid_y)
        remote_pos = (remote_squid_data.get('x',0.0), remote_squid_data.get('y',0.0))
        distance = math.hypot(local_pos[0] - remote_pos[0], local_pos[1] - remote_pos[1])
        interaction_distance_threshold = 80
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
        if random.random() > 0.15: return False
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return False
        ui = self.tamagotchi_logic.user_interface
        local_decorations = [
            item for item in ui.scene.items()
            if isinstance(item, QtWidgets.QGraphicsPixmapItem) and
               getattr(item, 'category', '') == 'decoration' and
               item.isVisible() and not getattr(item, 'is_foreign', False) and
               not getattr(item, 'is_gift_from_remote', False)
        ]
        if not local_decorations: return False
        gift_to_send_away = random.choice(local_decorations)
        received_gift_item = self.create_gift_decoration(remote_node_id)
        if received_gift_item:
            gift_to_send_away.setVisible(False)
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
        search_paths = [os.path.join("images", "decoration"), "images"]
        for path in search_paths:
            if os.path.exists(path):
                for filename in os.listdir(path):
                    if 'rock' in filename.lower() and filename.lower().endswith(('.png', '.jpg')):
                        rock_image_files.append(os.path.join(path, filename))
        if not rock_image_files:
            rock_image_files.append(os.path.join("images", "rock.png"))
        entry_x, entry_y = entry_position
        for i in range(num_rocks):
            try:
                chosen_rock_file = random.choice(rock_image_files)
                angle_offset = random.uniform(-math.pi / 4, math.pi / 4)
                angle = (i * (2 * math.pi / num_rocks)) + angle_offset
                dist = random.uniform(60, 100)
                rock_x = entry_x + dist * math.cos(angle)
                rock_y = entry_y + dist * math.sin(angle)
                rock_pixmap = QtGui.QPixmap(chosen_rock_file)
                if rock_pixmap.isNull(): continue
                rock_graphics_item = None
                if hasattr(ui, 'ResizablePixmapItem'):
                    rock_graphics_item = ui.ResizablePixmapItem(rock_pixmap, chosen_rock_file)
                else:
                    rock_graphics_item = QtWidgets.QGraphicsPixmapItem(rock_pixmap)
                    setattr(rock_graphics_item, 'filename', chosen_rock_file)
                setattr(rock_graphics_item, 'category', 'rock')
                setattr(rock_graphics_item, 'can_be_picked_up', True)
                setattr(rock_graphics_item, 'is_stolen_from_remote', True)
                setattr(rock_graphics_item, 'is_foreign', True)
                rock_graphics_item.setPos(rock_x, rock_y)
                scene.addItem(rock_graphics_item)
                self.apply_foreign_object_tint(rock_graphics_item)
                opacity_anim = QtCore.QPropertyAnimation(rock_graphics_item, b"opacity")
                opacity_anim.setDuration(1200)
                opacity_anim.setStartValue(0.2)
                opacity_anim.setEndValue(1.0)
                opacity_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
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
            existing_effect.setColor(QtGui.QColor(255, 120, 120, 200))
            existing_effect.setStrength(0.3)
        else:
            colorize_effect = QtWidgets.QGraphicsColorizeEffect()
            colorize_effect.setColor(QtGui.QColor(255, 120, 120, 200))
            colorize_effect.setStrength(0.3)
            q_graphics_item.setGraphicsEffect(colorize_effect)
        setattr(q_graphics_item, 'is_foreign', True)

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
        conn_info_group = QtWidgets.QGroupBox("My Connection")
        conn_info_form = QtWidgets.QFormLayout(conn_info_group)
        node_id_label = QtWidgets.QLabel(self.network_node.node_id)
        ip_label = QtWidgets.QLabel(self.network_node.local_ip)
        status_val_label = QtWidgets.QLabel()
        conn_info_form.addRow("Node ID:", node_id_label)
        conn_info_form.addRow("Local IP:", ip_label)
        conn_info_form.addRow("Status:", status_val_label)
        main_layout.addWidget(conn_info_group)
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
        stats_group = QtWidgets.QGroupBox("Network Statistics (Conceptual)")
        stats_form = QtWidgets.QFormLayout(stats_group)
        stats_form.addRow("Messages Sent (Total):", QtWidgets.QLabel(str(getattr(self.network_node, 'total_sent_count', 'N/A'))))
        stats_form.addRow("Messages Received (Total):", QtWidgets.QLabel(str(getattr(self.network_node, 'total_received_count', 'N/A'))))
        main_layout.addWidget(stats_group)
        def refresh_dashboard_data():
            is_connected = self.network_node.is_connected
            status_val_label.setText("Connected" if is_connected else "Disconnected")
            status_val_label.setStyleSheet("color: green; font-weight: bold;" if is_connected else "color: red; font-weight: bold;")
            peers_table_widget.setRowCount(0)
            if self.network_node:
                for row, (node_id, (ip, last_seen, _)) in enumerate(self.network_node.known_nodes.items()):
                    peers_table_widget.insertRow(row)
                    peers_table_widget.setItem(row, 0, QtWidgets.QTableWidgetItem(node_id))
                    peers_table_widget.setItem(row, 1, QtWidgets.QTableWidgetItem(ip))
                    time_delta_secs = time.time() - last_seen
                    time_ago_str = f"{int(time_delta_secs)}s ago"
                    peers_table_widget.setItem(row, 2, QtWidgets.QTableWidgetItem(time_ago_str))
                    peer_status_str = "Active" if time_delta_secs < 20 else "Inactive"
                    status_cell_item = QtWidgets.QTableWidgetItem(peer_status_str)
                    status_cell_item.setForeground(QtGui.QBrush(QtGui.QColor("green" if peer_status_str == "Active" else "gray")))
                    peers_table_widget.setItem(row, 3, status_cell_item)
            peers_table_widget.resizeColumnsToContents()
        refresh_dashboard_data()
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
                if not hasattr(ui, '_mp_status_widget_instance_'):
                    ui._mp_status_widget_instance_ = MultiplayerStatusWidget(ui.window)
                    ui._mp_status_widget_instance_.move(
                        ui.window.width() - ui._mp_status_widget_instance_.width() - 15, 15
                    )
                    ui._mp_status_widget_instance_.hide()
                self.status_widget = ui._mp_status_widget_instance_
                if self.network_node and hasattr(self.status_widget, 'set_network_node_reference'):
                    self.status_widget.set_network_node_reference(self.network_node)
                self.logger.info("Dedicated status widget initialized.")
            except ImportError:
                self.logger.info("MultiplayerStatusWidget not found. Will attempt fallback status bar integration.")
                self.initialize_status_bar()
            except Exception as e_msw:
                self.logger.error(f"Error initializing MultiplayerStatusWidget: {e_msw}. Using fallback.", exc_info=True)
                self.initialize_status_bar()
        except Exception as e:
            self.logger.error(f"Could not initialize status UI: {e}", exc_info=True)
    
    def initialize_status_bar(self): # Added stub, assuming it was missing
        """Fallback to initialize status bar component if dedicated widget fails."""
        if not self.logger: return
        self.logger.info("Attempting to initialize fallback status bar component.")
        # Implementation for status_bar initialization would go here
        # For now, just log that it's a fallback
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic.user_interface, 'statusBar'): # Example access
            self.status_bar = self.tamagotchi_logic.user_interface.statusBar()
            self.logger.info("Fallback status bar component obtained.")
        else:
            self.logger.warning("Fallback status bar component could not be obtained.")


    def _find_tamagotchi_logic(self, search_object, depth=0, visited_ids=None):
        """Recursively searches for an attribute named 'tamagotchi_logic'."""
        if not self.logger: return None # Should not happen if called after setup
        if visited_ids is None: visited_ids = set()
        if id(search_object) in visited_ids or depth > 6:
            return None
        visited_ids.add(id(search_object))
        if TamagotchiLogic and isinstance(search_object, TamagotchiLogic):
            return search_object
        if hasattr(search_object, 'tamagotchi_logic'):
            tl_attr = getattr(search_object, 'tamagotchi_logic')
            if TamagotchiLogic and isinstance(tl_attr, TamagotchiLogic):
                return tl_attr
        try:
            for attr_name in dir(search_object):
                if attr_name.startswith('_'): continue
                try:
                    attr_value = getattr(search_object, attr_name)
                    if attr_value is None or isinstance(attr_value, (int, str, bool, float, list, dict, set, tuple, bytes)):
                        continue
                    if inspect.ismodule(attr_value) or inspect.isbuiltin(attr_value) or inspect.isroutine(attr_value):
                        continue
                    if isinstance(attr_value, (QtWidgets.QWidget, QtCore.QObject)):
                         if depth > 2 and attr_name in ['parent', 'parentWidget', 'parentItem']:
                            continue
                    found_logic = self._find_tamagotchi_logic(attr_value, depth + 1, visited_ids)
                    if found_logic: return found_logic
                except (AttributeError, RecursionError, TypeError, ReferenceError):
                    continue
        except (RecursionError, TypeError, ReferenceError):
            pass
        return None

    def _animate_remote_squid_entry(self, squid_graphics_item, status_text_item, entry_direction_str):
        """Animates the visual entry of a remote squid."""
        if not self.logger: return
        if not squid_graphics_item: return
        squid_opacity_effect = QtWidgets.QGraphicsOpacityEffect(squid_graphics_item)
        squid_graphics_item.setGraphicsEffect(squid_opacity_effect)
        squid_fade_in_anim = QtCore.QPropertyAnimation(squid_opacity_effect, b"opacity")
        squid_fade_in_anim.setDuration(1200)
        squid_fade_in_anim.setStartValue(0.1)
        squid_fade_in_anim.setEndValue(self.REMOTE_SQUID_OPACITY)
        squid_fade_in_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        entry_animation_group = QtCore.QParallelAnimationGroup()
        entry_animation_group.addAnimation(squid_fade_in_anim)
        if status_text_item:
            text_opacity_effect = QtWidgets.QGraphicsOpacityEffect(status_text_item)
            status_text_item.setGraphicsEffect(text_opacity_effect)
            text_fade_in_anim = QtCore.QPropertyAnimation(text_opacity_effect, b"opacity")
            text_fade_in_anim.setDuration(1200)
            text_fade_in_anim.setStartValue(0.1)
            text_fade_in_anim.setEndValue(1.0)
            text_fade_in_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
            entry_animation_group.addAnimation(text_fade_in_anim)
        entry_animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def get_opposite_direction(self, direction_str: str) -> str:
        """Returns the opposite of a given cardinal direction string."""
        opposites = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}
        return opposites.get(direction_str.lower(), 'right')

    def create_entry_effect(self, center_x: float, center_y: float, direction_str: str = ""):
        """Creates a visual effect at the point where a remote squid enters the scene."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene
        ripple_item = QtWidgets.QGraphicsEllipseItem(center_x - 5, center_y - 5, 10, 10)
        ripple_item.setPen(QtGui.QPen(QtGui.QColor(135, 206, 250, 180), 2))
        ripple_item.setBrush(QtGui.QBrush(QtGui.QColor(135, 206, 250, 100)))
        ripple_item.setZValue(95)
        scene.addItem(ripple_item)
        ripple_opacity_effect = QtWidgets.QGraphicsOpacityEffect(ripple_item)
        ripple_item.setGraphicsEffect(ripple_opacity_effect)
        ripple_anim_group = QtCore.QParallelAnimationGroup()
        size_animation = QtCore.QPropertyAnimation(ripple_item, b"rect")
        size_animation.setDuration(1000)
        size_animation.setStartValue(QtCore.QRectF(center_x - 5, center_y - 5, 10, 10))
        size_animation.setEndValue(QtCore.QRectF(center_x - 60, center_y - 60, 120, 120))
        size_animation.setEasingCurve(QtCore.QEasingCurve.OutExpo)
        opacity_animation = QtCore.QPropertyAnimation(ripple_opacity_effect, b"opacity")
        opacity_animation.setDuration(1000)
        opacity_animation.setStartValue(0.8)
        opacity_animation.setEndValue(0.0)
        opacity_animation.setEasingCurve(QtCore.QEasingCurve.OutExpo)
        ripple_anim_group.addAnimation(size_animation)
        ripple_anim_group.addAnimation(opacity_animation)
        ripple_anim_group.finished.connect(lambda: scene.removeItem(ripple_item) if ripple_item in scene.items() else None)
        ripple_anim_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        arrival_text_str = "✨ New Visitor! ✨"
        arrival_text_item = scene.addText(arrival_text_str)
        arrival_font = QtGui.QFont("Arial", 12, QtGui.QFont.Bold)
        arrival_text_item.setFont(arrival_font)
        text_metrics = QtGui.QFontMetrics(arrival_font)
        text_rect = text_metrics.boundingRect(arrival_text_str)
        arrival_text_item.setDefaultTextColor(QtGui.QColor(255, 215, 0))
        arrival_text_item.setPos(center_x - text_rect.width() / 2, center_y - 80)
        arrival_text_item.setZValue(100)
        text_opacity_effect = QtWidgets.QGraphicsOpacityEffect(arrival_text_item)
        arrival_text_item.setGraphicsEffect(text_opacity_effect)
        text_fade_anim = QtCore.QPropertyAnimation(text_opacity_effect, b"opacity")
        text_fade_anim.setDuration(3500)
        text_fade_anim.setStartValue(0.0)
        text_fade_anim.setKeyValueAt(0.2, 1.0)
        text_fade_anim.setKeyValueAt(0.8, 1.0)
        text_fade_anim.setEndValue(0.0)
        text_fade_anim.finished.connect(lambda: scene.removeItem(arrival_text_item) if arrival_text_item in scene.items() else None)
        text_fade_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def _setup_controller_immediately(self, node_id: str, squid_initial_data: Dict):
        """Creates and initializes a RemoteSquidController."""
        if not self.logger: return
        try:
            from plugins.multiplayer.squid_multiplayer_autopilot import RemoteSquidController
        except ImportError:
            if self.debug_mode: self.logger.error("RemoteSquidController module not found. Remote squids will not be autonomous.")
            return
        if node_id in self.remote_squid_controllers:
            if self.debug_mode: self.logger.debug(f"Controller for squid {node_id[-6:]} already exists. Updating its data.")
            self.remote_squid_controllers[node_id].squid_data.update(squid_initial_data)
            return
        if self.debug_mode: self.logger.info(f"Creating autopilot controller for remote squid {node_id[-6:]}.")
        try:
            controller_instance = RemoteSquidController(
                squid_data=squid_initial_data,
                scene=self.tamagotchi_logic.user_interface.scene,
                plugin_instance=self,
                debug_mode=self.debug_mode
            )
            self.remote_squid_controllers[node_id] = controller_instance
            if self.debug_mode: self.logger.info(f"Controller for {node_id[-6:]} created. Initial state: {getattr(controller_instance, 'state', 'N/A')}")
        except Exception as e_create:
            self.logger.error(f"Failed to create RemoteSquidController for {node_id[-6:]}: {e_create}", exc_info=True)
            return
        if self.controller_update_timer and not self.controller_update_timer.isActive():
            self.controller_update_timer.start()
            if self.debug_mode: self.logger.debug("Restarted controller update timer.")



    def handle_squid_exit_message(self, node: Any, message: Dict, addr: tuple) -> bool: # Added return type hint
        # DEBUG_STEP_1: Log entry into this handler
        # Ensure self.logger exists or use a fallback print
        current_node_id_for_log = self.network_node.node_id if self.network_node else "UnknownNode(self)"
        # Using print for this very first debug line to ensure it appears even if logger is not fully set up
        print(f"DEBUG_STEP_1: Node {current_node_id_for_log} - handle_squid_exit_message CALLED. Message type: {message.get('type')}. Raw Full message: {message}")

        if not self.is_plugin_enabled() or not self.network_node or not hasattr(self, 'entity_manager') or not self.entity_manager:
            if self.logger: self.logger.warning("Multiplayer plugin not fully active or entity_manager missing, ignoring squid_exit.")
            else: print("Multiplayer plugin not fully active or entity_manager missing, ignoring squid_exit.")
            return False

        try:
            if self.logger: self.logger.info(f"My Node ID {current_node_id_for_log} - Received squid_exit message: {message} from {addr}")

            exit_payload_outer = message.get('payload', {})
            exit_payload_inner = exit_payload_outer.get('payload', None) 
            
            if not exit_payload_inner or not isinstance(exit_payload_inner, dict):
                if self.logger: self.logger.warning(f"squid_exit message missing correctly nested 'payload' dictionary. Outer payload: {exit_payload_outer}")
                return False

            source_node_id = exit_payload_inner.get('node_id')
            if not source_node_id:
                if self.logger: self.logger.warning(f"squid_exit inner payload missing 'node_id'. Inner payload: {exit_payload_inner}")
                return False

            if source_node_id == current_node_id_for_log:
                if self.logger: self.logger.debug(f"Ignoring own squid_exit broadcast for {source_node_id}.")
                return False 

            if self.logger: self.logger.info(f"Processing squid_exit from REMOTE node {source_node_id} for potential entry.")
            if self.logger: self.logger.debug(f"Exit payload from remote ({source_node_id}): {json.dumps(exit_payload_inner, default=str, indent=2)}")

            # Call entity_manager.update_remote_squid
            # It now returns the visual item on new creation success, True on update success, or False/None on failure.
            remote_squid_return_value = self.entity_manager.update_remote_squid(
                source_node_id,
                exit_payload_inner, 
                is_new_arrival=True 
            )
            
            # Detailed logging of the return value
            is_valid_graphics_item = isinstance(remote_squid_return_value, QtWidgets.QGraphicsPixmapItem)
            if self.logger: self.logger.info(f"Called entity_manager.update_remote_squid for {source_node_id}. TYPE of result: {type(remote_squid_return_value)}. Result is QGraphicsPixmapItem: {is_valid_graphics_item}. Raw Return Value: {remote_squid_return_value}")

            if remote_squid_return_value and is_valid_graphics_item: # Successfully created a new visual item
                if self.logger: self.logger.info(f"Remote squid {source_node_id} visual item IS VALID. Proceeding with autopilot setup.")
                
                remote_squid_instance_data = self.entity_manager.get_remote_squid_instance_by_id(source_node_id)
                
                if remote_squid_instance_data and remote_squid_instance_data.get('visual') == remote_squid_return_value:
                    if not remote_squid_instance_data.get('autopilot'): # Check if autopilot already exists
                        if self.logger: self.logger.info(f"Creating new autopilot for remote squid {source_node_id}")
                        try:
                            # Ensure SquidMultiplayerAutopilot is imported in mp_plugin_logic.py
                            from .squid_multiplayer_autopilot import SquidMultiplayerAutopilot # Assuming relative import
                            
                            autopilot = SquidMultiplayerAutopilot(
                                node_id=source_node_id,
                                tamagotchi_logic=self.tamagotchi_logic,
                                initial_state_data=exit_payload_inner, 
                                remote_entity_manager=self.entity_manager 
                            )
                            remote_squid_instance_data['autopilot'] = autopilot # Store it
                            
                            entry_details = self.entity_manager.get_last_calculated_entry_details(source_node_id)
                            if entry_details:
                                entry_pos_x, entry_pos_y = entry_details['entry_pos']
                                entry_side = entry_details['entry_direction']
                                if self.logger: self.logger.info(f"Autopilot for {source_node_id} using entry details: {entry_details}")

                                target_x, target_y = entry_pos_x, entry_pos_y
                                squid_w = float(exit_payload_inner.get('squid_width', 50))
                                squid_h = float(exit_payload_inner.get('squid_height', 50))
                                inward_buffer = squid_w * 1.5 

                                if entry_side == 'left': target_x += inward_buffer
                                elif entry_side == 'right': target_x -= inward_buffer
                                elif entry_side == 'top': target_y += inward_buffer 
                                elif entry_side == 'bottom': target_y -= inward_buffer
                                
                                if self.logger: self.logger.info(f"Autopilot for {source_node_id} initial movement target set to: ({target_x:.2f}, {target_y:.2f})")
                                autopilot.set_movement_target(target_x, target_y, None)
                            else:
                                if self.logger: self.logger.warning(f"Could not get entry details for {source_node_id} to set initial autopilot target.")
                        except ImportError:
                            if self.logger: self.logger.error("Failed to import SquidMultiplayerAutopilot. Autopilot not created.")
                        except Exception as auto_e:
                             if self.logger: self.logger.error(f"Error creating or setting up autopilot for {source_node_id}: {auto_e}", exc_info=True)
                    else:
                        if self.logger: self.logger.info(f"Autopilot already exists or remote_squid_instance_data is None for {source_node_id}.")
                else:
                    if self.logger: self.logger.warning(f"Remote squid instance data not found or visual mismatch for {source_node_id} after update_remote_squid call.")
            else: # update_remote_squid returned False or None
                if self.logger: self.logger.warning(f"Failed to get a valid visual item for remote squid {source_node_id} from entity_manager. Autopilot not set. Return value was: {remote_squid_return_value}")
            
            return True

        except Exception as e:
            if self.logger: self.logger.error(f"Critical error in handle_squid_exit_message for node {source_node_id if 'source_node_id' in locals() else 'UnknownSource'}: {e}", exc_info=True)
            return False

    def _setup_controller_creation_timer(self):
        """(Fallback) Sets up a QTimer to process pending controller creations."""
        if not self.logger: return
        if self.controller_creation_timer and self.controller_creation_timer.isActive():
            return
        if not self.controller_creation_timer:
            self.controller_creation_timer = QtCore.QTimer()
            self.controller_creation_timer.timeout.connect(self._process_pending_controller_creations)
        self.controller_creation_timer.start(300)
        if self.debug_mode: self.logger.debug("Fallback controller creation timer started.")

    def _process_pending_controller_creations(self):
        """(Fallback) Processes remote squids waiting for controllers."""
        if not self.logger: return
        if not hasattr(self, 'pending_controller_creations') or not self.pending_controller_creations:
            return
        items_to_process = list(self.pending_controller_creations)
        self.pending_controller_creations.clear()
        for creation_task in items_to_process:
            node_id = creation_task.get('node_id')
            squid_data = creation_task.get('squid_data')
            if not node_id or not squid_data: continue
            if node_id not in self.remote_squid_controllers:
                if self.debug_mode: self.logger.debug(f"Fallback: Creating controller for squid {node_id[-6:]}.")
                self._setup_controller_immediately(node_id, squid_data)
            elif self.debug_mode:
                self.logger.debug(f"Fallback: Controller for {node_id[-6:]} already exists, skipping duplicate creation.")

    def update_remote_controllers(self):
        """Called by a QTimer to update RemoteSquidController instances."""
        if not self.logger: return
        if not hasattr(self, 'remote_squid_controllers') or not self.remote_squid_controllers:
            return
        current_time = time.time()
        delta_time = current_time - self.last_controller_update
        if delta_time <= 0.001: return
        self.last_controller_update = current_time
        for node_id, controller in list(self.remote_squid_controllers.items()):
            try:
                controller.update(delta_time)
                updated_squid_data = controller.squid_data
                if node_id in self.remote_squids:
                    remote_squid_display = self.remote_squids[node_id]
                    visual = remote_squid_display.get('visual')
                    status_text = remote_squid_display.get('status_text')
                    if visual:
                        visual.setPos(updated_squid_data['x'], updated_squid_data['y'])
                        self.update_remote_squid_image(remote_squid_display, updated_squid_data['direction'])
                    if status_text:
                        current_status_on_display = status_text.toPlainText()
                        new_status_from_controller = updated_squid_data.get('status', 'exploring')
                        if current_status_on_display.upper() != new_status_from_controller.upper() or \
                           new_status_from_controller.upper() in ["ARRIVING", "ENTERING", "RETURNING..."]:
                            status_text.setPlainText(new_status_from_controller)
                        status_text.setPos(updated_squid_data['x'], updated_squid_data['y'] - 35)
                    if updated_squid_data.get('view_cone_visible', False):
                        self.update_remote_view_cone(node_id, updated_squid_data)
                    elif remote_squid_display.get('view_cone'):
                         if self.tamagotchi_logic and hasattr(self.tamagotchi_logic.user_interface, 'scene'):
                            cone = remote_squid_display['view_cone']
                            if cone in self.tamagotchi_logic.user_interface.scene.items():
                                self.tamagotchi_logic.user_interface.scene.removeItem(cone)
                            remote_squid_display['view_cone'] = None
                else:
                    if self.debug_mode: self.logger.warning(f"Visual for remote squid {node_id[-6:]} missing. Removing its controller.")
                    del self.remote_squid_controllers[node_id]
            except Exception as e:
                self.logger.error(f"Updating controller for {node_id[-6:]} failed: {e}", exc_info=True)

    def calculate_entry_position(self, entry_side_direction: str) -> tuple:
        """Calculates X,Y coordinates for a squid entering this local screen."""
        if not self.logger: return (100,100)
        if not self.tamagotchi_logic or not self.tamagotchi_logic.user_interface:
            return (100, 100)
        window_w = self.tamagotchi_logic.user_interface.window_width
        window_h = self.tamagotchi_logic.user_interface.window_height
        margin = 70
        if entry_side_direction == 'left':   return (margin, window_h / 2)
        elif entry_side_direction == 'right':return (window_w - margin, window_h / 2)
        elif entry_side_direction == 'up':   return (window_w / 2, margin)
        elif entry_side_direction == 'down': return (window_w / 2, window_h - margin)
        return (window_w / 2, window_h / 2)

    def apply_remote_experiences(self, local_squid, activity_summary: Dict):
        """Applies summarized experiences from a remote journey to the local squid."""
        if not self.logger: return
        if not local_squid or not activity_summary: return
        food_eaten = activity_summary.get('food_eaten', 0)
        rocks_interacted = activity_summary.get('rock_interactions', 0)
        rocks_brought_back = activity_summary.get('rocks_stolen', 0)
        time_away_seconds = activity_summary.get('time_away', 0)
        time_str = f"{int(time_away_seconds/60)}m {int(time_away_seconds%60)}s"
        journey_desc = f"Returned from a {time_str} journey to another tank. "
        if hasattr(local_squid, 'memory_manager'):
            mm = local_squid.memory_manager
            if food_eaten > 0:
                journey_desc += f"Ate {food_eaten} snacks there. "
                local_squid.hunger = max(0, local_squid.hunger - 10 * food_eaten)
                mm.add_short_term_memory('travel', 'ate_on_trip', f"Found {food_eaten} yummy treats on my trip!", 5)
            if rocks_interacted > 0:
                journey_desc += f"Played with {rocks_interacted} interesting rocks. "
                local_squid.happiness = min(100, local_squid.happiness + 3 * rocks_interacted)
                mm.add_short_term_memory('travel', 'played_on_trip', f"Played with {rocks_interacted} cool rocks elsewhere!", 4)
            mm.add_short_term_memory('travel', 'completed_journey', journey_desc, importance=7)
            if food_eaten > 1 or rocks_interacted > 3 or rocks_brought_back > 0:
                mm.add_short_term_memory('emotion', 'happy_return', "It's great to be back home after an exciting adventure!", 6)
            else:
                mm.add_short_term_memory('emotion', 'calm_return', "Returned home. It was a quiet trip.", 3)
        if hasattr(local_squid, 'curiosity'):
            local_squid.curiosity = max(0, local_squid.curiosity - 25)

    def create_exit_effect(self, center_x: float, center_y: float, direction_str: str = ""):
        """Creates a visual effect when a local squid exits the screen."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene
        ripple_item = QtWidgets.QGraphicsEllipseItem(center_x - 40, center_y - 40, 80, 80)
        ripple_item.setPen(QtGui.QPen(QtGui.QColor(255, 100, 100, 150), 2))
        ripple_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 100, 100, 80)))
        ripple_item.setZValue(90)
        scene.addItem(ripple_item)
        ripple_opacity_effect = QtWidgets.QGraphicsOpacityEffect(ripple_item)
        ripple_item.setGraphicsEffect(ripple_opacity_effect)
        exit_anim_group = QtCore.QParallelAnimationGroup()
        size_animation = QtCore.QPropertyAnimation(ripple_item, b"rect")
        size_animation.setDuration(800)
        size_animation.setStartValue(QtCore.QRectF(center_x - 40, center_y - 40, 80, 80))
        size_animation.setEndValue(QtCore.QRectF(center_x - 5, center_y - 5, 10, 10))
        size_animation.setEasingCurve(QtCore.QEasingCurve.InExpo)
        opacity_animation = QtCore.QPropertyAnimation(ripple_opacity_effect, b"opacity")
        opacity_animation.setDuration(800)
        opacity_animation.setStartValue(0.7)
        opacity_animation.setEndValue(0.0)
        opacity_animation.setEasingCurve(QtCore.QEasingCurve.InExpo)
        exit_anim_group.addAnimation(size_animation)
        exit_anim_group.addAnimation(opacity_animation)
        exit_anim_group.finished.connect(lambda: scene.removeItem(ripple_item) if ripple_item in scene.items() else None)
        exit_anim_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        travel_text_str = "🚀 Off to explore! 🚀"
        travel_text_item = scene.addText(travel_text_str)
        travel_font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
        travel_text_item.setFont(travel_font)
        text_metrics = QtGui.QFontMetrics(travel_font)
        text_rect = text_metrics.boundingRect(travel_text_str)
        travel_text_item.setDefaultTextColor(QtGui.QColor(173, 216, 230))
        travel_text_item.setPos(center_x - text_rect.width() / 2, center_y + 30)
        travel_text_item.setZValue(100)
        text_opacity_effect_exit = QtWidgets.QGraphicsOpacityEffect(travel_text_item)
        travel_text_item.setGraphicsEffect(text_opacity_effect_exit)
        text_fade_anim_exit = QtCore.QPropertyAnimation(text_opacity_effect_exit, b"opacity")
        text_fade_anim_exit.setDuration(2500)
        text_fade_anim_exit.setStartValue(1.0)
        text_fade_anim_exit.setEndValue(0.0)
        text_fade_anim_exit.finished.connect(lambda: scene.removeItem(travel_text_item) if travel_text_item in scene.items() else None)
        text_fade_anim_exit.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def handle_squid_return(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles a 'squid_return' message for the player's own squid."""
        if not self.logger: return
        try:
            return_payload = message.get('payload', {})
            returning_node_id = return_payload.get('node_id')
            if not self.network_node or returning_node_id != self.network_node.node_id:
                if self.debug_mode:
                    expected_id = self.network_node.node_id if self.network_node else "N/A"
                    self.logger.debug(f"Squid_return message ignored. Expected node '{expected_id}', got '{returning_node_id}'.")
                return
            local_squid = self.tamagotchi_logic.squid
            if not local_squid or not local_squid.squid_item:
                if self.debug_mode: self.logger.debug("Local squid or its visual item not found for return.")
                return
            activity_summary = return_payload.get('activity_summary', {})
            entry_side = return_payload.get('return_direction', 'left')
            entry_coords = self.calculate_entry_position(entry_side)
            local_squid.squid_x, local_squid.squid_y = entry_coords[0], entry_coords[1]
            local_squid.squid_item.setPos(local_squid.squid_x, local_squid.squid_y)
            local_squid.squid_item.setVisible(True)
            squid_opacity_effect = QtWidgets.QGraphicsOpacityEffect(local_squid.squid_item)
            local_squid.squid_item.setGraphicsEffect(squid_opacity_effect)
            fade_in_animation = QtCore.QPropertyAnimation(squid_opacity_effect, b"opacity")
            fade_in_animation.setDuration(1500)
            fade_in_animation.setStartValue(0.0)
            fade_in_animation.setEndValue(1.0)
            fade_in_animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
            self.apply_remote_experiences(local_squid, activity_summary)
            num_stolen_rocks = activity_summary.get('rocks_stolen', 0)
            if num_stolen_rocks > 0:
                self.create_stolen_rocks(local_squid, num_stolen_rocks, entry_coords)
                if hasattr(self.tamagotchi_logic, 'show_message'):
                    self.tamagotchi_logic.show_message(f"🎉 Your squid returned with {num_stolen_rocks} souvenir rocks!")
            else:
                if hasattr(self.tamagotchi_logic, 'show_message'):
                    journey_time_sec = activity_summary.get('time_away', 0)
                    time_str = f"{int(journey_time_sec/60)}m {int(journey_time_sec%60)}s"
                    self.tamagotchi_logic.show_message(f"🦑 Welcome back! Your squid explored for {time_str}.")
            local_squid.can_move = True
            if hasattr(local_squid, 'is_transitioning'): local_squid.is_transitioning = False
            local_squid.status = "just returned home"
            if self.debug_mode: self.logger.debug(f"Local squid '{local_squid.name if hasattr(local_squid,'name') else ''}' returned to position {entry_coords} from {entry_side}.")
        except Exception as e:
            self.logger.error(f"Handling local squid's return failed: {e}", exc_info=True)

    def _create_arrival_animation(self, graphics_item: QtWidgets.QGraphicsPixmapItem):
        """Creates a simple fade-in animation for newly arrived remote items."""
        if not self.logger: return
        if not graphics_item: return
        try:
            opacity_effect = QtWidgets.QGraphicsOpacityEffect(graphics_item)
            graphics_item.setGraphicsEffect(opacity_effect)
            fade_in_anim = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
            fade_in_anim.setDuration(1000)
            fade_in_anim.setStartValue(0.2)
            target_opacity = self.REMOTE_SQUID_OPACITY
            if hasattr(graphics_item, 'is_remote_clone') and getattr(graphics_item, 'is_remote_clone'):
                target_opacity *= 0.75
            fade_in_anim.setEndValue(target_opacity)
            fade_in_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)
            fade_in_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        except Exception as e:
            if self.debug_mode: self.logger.warning(f"Simple arrival animation error: {e}")
            if graphics_item: graphics_item.setOpacity(self.REMOTE_SQUID_OPACITY)

    def _reset_remote_squid_style(self, node_id_or_item):
        """Resets the visual style of a remote squid."""
        if not self.logger: return
        node_id = None
        squid_display_data = None
        if isinstance(node_id_or_item, str):
            node_id = node_id_or_item
            squid_display_data = self.remote_squids.get(node_id)
        elif isinstance(node_id_or_item, QtWidgets.QGraphicsPixmapItem):
            for nid, s_data in self.remote_squids.items():
                if s_data.get('visual') == node_id_or_item:
                    node_id = nid
                    squid_display_data = s_data
                    break
        if not squid_display_data: return
        visual_item = squid_display_data.get('visual')
        status_text_item = squid_display_data.get('status_text')
        id_text_item = squid_display_data.get('id_text')
        if visual_item:
            visual_item.setZValue(5)
            visual_item.setOpacity(self.REMOTE_SQUID_OPACITY)
            if visual_item.graphicsEffect() and isinstance(visual_item.graphicsEffect(), QtWidgets.QGraphicsDropShadowEffect):
                visual_item.setGraphicsEffect(None)
        if status_text_item:
            current_status_from_data = squid_display_data.get('data', {}).get('status', 'visiting')
            status_text_item.setPlainText(current_status_from_data)
            status_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200, 220))
            status_text_item.setFont(QtGui.QFont("Arial", 9))
            status_text_item.setZValue(6)
        if id_text_item:
            id_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200, 180))
            id_text_item.setFont(QtGui.QFont("Arial", 8))
            id_text_item.setZValue(6)

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
        target_menu.addSeparator()
        refresh_connections_action = QtWidgets.QAction("Refresh Connections", main_ui_window)
        refresh_connections_action.triggered.connect(self.refresh_connections)
        target_menu.addAction(refresh_connections_action)
        self.mp_menu_toggle_connection_lines_action = QtWidgets.QAction("Show Connection Lines", main_ui_window)
        self.mp_menu_toggle_connection_lines_action.setCheckable(True)
        self.mp_menu_toggle_connection_lines_action.setChecked(self.SHOW_CONNECTION_LINES)
        self.mp_menu_toggle_connection_lines_action.triggered.connect(self.toggle_connection_lines)
        target_menu.addAction(self.mp_menu_toggle_connection_lines_action)
        if self.debug_mode:
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
        node_id_str = getattr(self.network_node, 'node_id', "N/A")
        ip_str = getattr(self.network_node, 'local_ip', "N/A")
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
        if not self.config_dialog or not self.config_dialog.isVisible():
            self.config_dialog = MultiplayerConfigDialog(
                plugin_instance=self, parent=parent_window, initial_settings=current_settings
            )
        else:
            self.config_dialog.load_settings(current_settings)
        self.config_dialog.exec_()

    def toggle_connection_lines(self, checked_state: bool):
        """Toggles the visibility of connection lines."""
        if not self.logger: return
        self.SHOW_CONNECTION_LINES = checked_state
        if hasattr(self.tamagotchi_logic, 'user_interface') and self.tamagotchi_logic.user_interface:
            scene = self.tamagotchi_logic.user_interface.scene
            for line_item in self.connection_lines.values():
                if line_item in scene.items():
                    line_item.setVisible(self.SHOW_CONNECTION_LINES)
            if not self.SHOW_CONNECTION_LINES:
                for node_id_key in list(self.connection_lines.keys()):
                    line_to_remove = self.connection_lines.pop(node_id_key)
                    if line_to_remove in scene.items():
                        scene.removeItem(line_to_remove)
        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(f"Connection lines to remote squids {'shown' if checked_state else 'hidden'}.")

    def refresh_connections(self):
        """Manually triggers a network presence announcement."""
        if not self.logger: return
        if not self.network_node:
            if hasattr(self.tamagotchi_logic, 'show_message'):
                self.tamagotchi_logic.show_message("Multiplayer: Network component not initialized. Cannot refresh.")
            else:
                self.logger.warning("Network component not initialized. Cannot refresh connections.")
            return
        if not self.network_node.is_connected:
            if self.debug_mode: self.logger.debug("Attempting to reconnect before refresh...")
            self.network_node.try_reconnect()
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
        elif self.debug_mode or not self.network_node.is_connected: # Log if no UI message or error
            self.logger.info(message_to_show)

        current_peers_count = len(self.network_node.known_nodes if self.network_node else {})
        if self.status_widget:
            self.status_widget.update_peers(self.network_node.known_nodes if self.network_node else {})
            self.status_widget.add_activity(f"Connections refreshed. {current_peers_count} peers currently detected.")
        elif self.status_bar:
            if hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(current_peers_count)
            if hasattr(self.status_bar, 'add_message'): self.status_bar.add_message(f"Refreshed. {current_peers_count} peers.")

    def initialize_remote_representation(self):
        """(Fallback) Initializes basic timers for managing remote entity visuals."""
        if not self.logger: return
        if not self.cleanup_timer_basic:
            self.cleanup_timer_basic = QtCore.QTimer()
            self.cleanup_timer_basic.timeout.connect(self.cleanup_stale_nodes)
            self.cleanup_timer_basic.start(7500)
        if not self.connection_timer_basic:
            self.connection_timer_basic = QtCore.QTimer()
            self.connection_timer_basic.timeout.connect(self.update_connection_lines)
            self.connection_timer_basic.start(1200)

    def cleanup_stale_nodes(self):
        """(Fallback) Removes visuals of remote nodes that haven't sent updates."""
        if not self.logger: return
        if not self.network_node: return
        current_time = time.time()
        stale_threshold_seconds = 45.0
        nodes_to_remove_ids = []
        for node_id, (_, last_seen_time, _) in list(self.network_node.known_nodes.items()):
            if current_time - last_seen_time > stale_threshold_seconds:
                nodes_to_remove_ids.append(node_id)
        for node_id_to_remove in nodes_to_remove_ids:
            if self.debug_mode: self.logger.debug(f"Basic Cleanup: Node {node_id_to_remove[-6:]} timed out. Removing.")
            if node_id_to_remove in self.network_node.known_nodes:
                del self.network_node.known_nodes[node_id_to_remove]
            self.remove_remote_squid(node_id_to_remove)
            if node_id_to_remove in self.remote_squid_controllers:
                del self.remote_squid_controllers[node_id_to_remove]
        if self.network_node:
            peers_now = self.network_node.known_nodes if self.network_node else {}
            if self.status_widget: self.status_widget.update_peers(peers_now)
            elif self.status_bar and hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(len(peers_now))

    def update_connection_lines(self):
        """(Fallback) Updates visual lines connecting local squid to remote squids."""
        if not self.logger: return
        if not self.SHOW_CONNECTION_LINES or not self.tamagotchi_logic or \
           not self.tamagotchi_logic.squid or not self.tamagotchi_logic.user_interface or \
           not self.tamagotchi_logic.squid.squid_item:
            return
        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        local_squid_visual = self.tamagotchi_logic.squid.squid_item
        local_rect = local_squid_visual.boundingRect()
        local_center_pos = local_squid_visual.pos() + local_rect.center()
        active_remote_node_ids = set()
        for node_id, remote_squid_info in self.remote_squids.items():
            remote_visual = remote_squid_info.get('visual')
            if not remote_visual or not remote_visual.isVisible() or remote_visual not in scene.items():
                continue
            active_remote_node_ids.add(node_id)
            remote_rect = remote_visual.boundingRect()
            remote_center_pos = remote_visual.pos() + remote_rect.center()
            line_color_data = remote_squid_info.get('data', {}).get('color', (100, 100, 255))
            pen = QtGui.QPen(QtGui.QColor(*line_color_data, 120))
            pen.setWidth(2)
            pen.setStyle(QtCore.Qt.DashLine)
            if node_id in self.connection_lines:
                line = self.connection_lines[node_id]
                if line not in scene.items():
                    scene.addItem(line)
                line.setLine(local_center_pos.x(), local_center_pos.y(), remote_center_pos.x(), remote_center_pos.y())
                line.setPen(pen)
                line.setVisible(True)
            else:
                line = QtWidgets.QGraphicsLineItem(
                    local_center_pos.x(), local_center_pos.y(), remote_center_pos.x(), remote_center_pos.y()
                )
                line.setPen(pen)
                line.setZValue(-10)
                scene.addItem(line)
                self.connection_lines[node_id] = line
        for node_id_key in list(self.connection_lines.keys()):
            if node_id_key not in active_remote_node_ids:
                line_to_remove = self.connection_lines.pop(node_id_key)
                if line_to_remove in scene.items():
                    scene.removeItem(line_to_remove)

    def _register_hooks(self):
        """Registers handlers for network message types with the plugin manager."""
        if not self.logger: return
        if not self.plugin_manager:
            self.logger.error("Cannot register hooks, plugin_manager is not set.")
            return

        hook_handlers = {
            # The hook name generated by NetworkNode is "on_network_squid_exit"
            # The subscribe_to_hook call should match this.
            "on_network_squid_exit": self.handle_squid_exit_message,
            "on_network_squid_move": self.handle_squid_move,
            "on_network_object_sync": self.handle_object_sync,
            "on_network_rock_throw": self.handle_rock_throw,
            "on_network_heartbeat": self.handle_heartbeat,
            "on_network_state_update": self.handle_state_update,
            # Add new 'squid_return' handler
            "on_network_squid_return": self.handle_squid_return 
        }

        for hook_name_to_register, handler_method_to_call in hook_handlers.items():
            # The hook_name_to_register here (e.g., "on_network_squid_exit")
            # is the actual string the PluginManager will use to store the subscription.
            # NetworkNode's process_messages will generate a hook_name (e.g., "on_network_squid_exit")
            # and call plugin_manager.trigger_hook(generated_hook_name, ...)
            # These two must match exactly.

            # =============== ADD THIS LINE EXACTLY AS SHOWN BELOW ===============
            if hook_name_to_register == "on_network_squid_exit": # Only print for the one we are debugging
                print(f"DEBUG_STEP_2B: MultiplayerPluginLogic {self.network_node.node_id if self.network_node else 'Unknown'} is subscribing '{handler_method_to_call.__name__}' to hook: '{hook_name_to_register}'")
            # =====================================================================

            self.plugin_manager.register_hook(hook_name_to_register) # Ensures hook exists
            self.plugin_manager.subscribe_to_hook(
                hook_name_to_register, 
                mp_constants.PLUGIN_NAME, # Using the constant for plugin name
                handler_method_to_call
            )

        # This existing hook subscription is for the game's main update loop, not direct network messages.
        # It's used to periodically call _process_network_node_queue via a QTimer in the plugin.
        # The QTimer approach is fine, but this specific pre_update hook registration
        # for _process_network_node_queue might be redundant if the QTimer is the primary mechanism.
        # For now, assuming it's intentional or a secondary way to process.
        # If you rely *solely* on the QTimer in setup() to call _process_network_node_queue,
        # then this "pre_update" hook subscription for it might not be necessary.
        self.plugin_manager.register_hook("pre_update") 
        self.plugin_manager.subscribe_to_hook("pre_update", mp_constants.PLUGIN_NAME, self._process_network_node_queue)

        if self.debug_mode: self.logger.debug("Network message hooks and pre_update hook registered.")

    def pre_update(self, *args, **kwargs):
        """Called by game's main update loop if subscribed to 'pre_update' hook."""
        pass # Current design uses QTimer for _process_network_node_queue.

    def start_sync_timer(self):
        """Starts a daemon thread for periodic game state synchronization."""
        if not self.logger: return
        if self.sync_thread and self.sync_thread.is_alive():
            if self.debug_mode: self.logger.debug("Sync thread already running.")
            return
        def game_state_sync_loop():
            while True:
                if not self.is_setup:
                    if self.debug_mode: self.logger.debug("SyncLoop: Plugin not setup or disabled, loop exiting.")
                    break
                try:
                    if self.network_node and self.network_node.is_connected and \
                       self.tamagotchi_logic and self.tamagotchi_logic.squid:
                        is_local_squid_moving = getattr(self.tamagotchi_logic.squid, 'is_moving', False)
                        sync_delay_seconds = 0.3 if is_local_squid_moving else self.SYNC_INTERVAL
                        num_peers = len(getattr(self.network_node, 'known_nodes', {}))
                        if num_peers > 8: sync_delay_seconds *= 1.5
                        elif num_peers > 15: sync_delay_seconds *= 2.0
                        sync_delay_seconds = max(0.2, min(sync_delay_seconds, 3.0))
                        self.sync_game_state()
                        time.sleep(sync_delay_seconds)
                    else:
                        time.sleep(2.5)
                except ReferenceError:
                    if self.debug_mode: self.logger.debug("SyncLoop: ReferenceError (likely app shutting down), loop exiting.")
                    break
                except Exception as e_sync:
                    if self.debug_mode: self.logger.error(f"Error in game_state_sync_loop: {e_sync}", exc_info=True)
                    time.sleep(3.0)
        self.sync_thread = threading.Thread(target=game_state_sync_loop, daemon=True)
        self.sync_thread.start()
        if self.debug_mode: self.logger.info("Game state synchronization thread started.")

    def sync_game_state(self):
        """Collects and sends current local game state."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'squid') or \
           not self.network_node or not self.network_node.is_connected:
            # self.logger.debug("sync_game_state prerequisites not met.") # Too verbose for frequent call
            return
        try:
            squid_current_state = self._get_squid_state()
            objects_current_state = self._get_objects_state()
            sync_payload = {
                'squid': squid_current_state,
                'objects': objects_current_state,
                'node_info': {'id': self.network_node.node_id, 'ip': self.network_node.local_ip}
            }
            self.network_node.send_message('object_sync', sync_payload)
            # if self.debug_mode: self.logger.debug(f"Sent 'object_sync' with {len(objects_current_state)} objects.")
            time_now = time.time()
            if time_now - self.last_message_times.get('heartbeat_sent', 0) > 8.0:
                heartbeat_payload = {
                    'node_id': self.network_node.node_id, 'status': 'active',
                    'squid_pos': (squid_current_state['x'], squid_current_state['y'])
                }
                self.network_node.send_message('heartbeat', heartbeat_payload)
                self.last_message_times['heartbeat_sent'] = time_now
                # if self.debug_mode: self.logger.debug("Heartbeat sent.")
        except Exception as e:
            self.logger.error(f"ERROR during sync_game_state: {e}", exc_info=True)

    def _get_squid_state(self) -> Dict:
        """Compiles and returns a dictionary of the local squid's current state."""
        if not self.logger: return {}
        if not self.tamagotchi_logic or not self.tamagotchi_logic.squid or not self.network_node:
            return {}
        squid = self.tamagotchi_logic.squid
        view_direction_rad = self.get_actual_view_direction(squid)
        return {
            'x': squid.squid_x, 'y': squid.squid_y, 'direction': squid.squid_direction,
            'looking_direction': view_direction_rad,
            'view_cone_angle': getattr(squid, 'view_cone_angle_rad', math.radians(60)),
            'hunger': squid.hunger, 'happiness': squid.happiness,
            'status': getattr(squid, 'status', "idle"),
            'carrying_rock': getattr(squid, 'carrying_rock', False),
            'is_sleeping': getattr(squid, 'is_sleeping', False),
            'color': self.get_squid_color(),
            'node_id': self.network_node.node_id,
            'view_cone_visible': getattr(squid, 'view_cone_visible', False)
        }

    def get_actual_view_direction(self, squid_instance) -> float:
        """Determines the squid's current viewing direction in radians."""
        if hasattr(squid_instance, 'current_view_angle_radians'):
            return squid_instance.current_view_angle_radians
        direction_to_radians_map = {
            'right': 0.0, 'left': math.pi, 'up': 1.5 * math.pi, 'down': 0.5 * math.pi
        }
        return direction_to_radians_map.get(getattr(squid_instance, 'squid_direction', 'right'), 0.0)

    def get_squid_color(self) -> tuple:
        """Generates a persistent color (R,G,B) for the local squid."""
        if not hasattr(self, '_local_squid_color_cache'):
            node_id_str = "default_node"
            if self.network_node and self.network_node.node_id:
                node_id_str = self.network_node.node_id
            hash_value = 0
            for char_code in node_id_str.encode('utf-8'):
                hash_value = (hash_value * 37 + char_code) & 0xFFFFFF
            r = (hash_value >> 16) & 0xFF
            g = (hash_value >> 8) & 0xFF
            b = hash_value & 0xFF
            r = max(80, min(r, 220))
            g = max(80, min(g, 220))
            b = max(80, min(b, 220))
            self._local_squid_color_cache = (r, g, b)
        return self._local_squid_color_cache

    def _get_objects_state(self) -> List[Dict]:
        """Collects and returns a list of syncable game object states."""
        if not self.logger: return []
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'):
            return []
        ui = self.tamagotchi_logic.user_interface
        syncable_objects_list = []
        try:
            for item in ui.scene.items():
                if not isinstance(item, QtWidgets.QGraphicsPixmapItem) or not hasattr(item, 'filename'):
                    continue
                if not item.isVisible():
                    continue
                if getattr(item, 'is_remote_clone', False):
                    continue
                object_type_str = self._determine_object_type(item)
                valid_types_to_sync = ['rock', 'food', 'poop', 'decoration']
                if object_type_str not in valid_types_to_sync:
                    continue
                item_pos = item.pos()
                obj_id = f"{os.path.basename(item.filename)}_{int(item_pos.x())}_{int(item_pos.y())}"
                object_data = {
                    'id': obj_id, 'type': object_type_str, 'x': item_pos.x(), 'y': item_pos.y(),
                    'filename': item.filename,
                    'scale': item.scale() if hasattr(item, 'scale') else 1.0,
                    'zValue': item.zValue(),
                    'is_being_carried': getattr(item, 'is_being_carried', False)
                }
                syncable_objects_list.append(object_data)
        except RuntimeError:
             if self.debug_mode: self.logger.warning("Runtime error while iterating scene items for sync. Skipping this cycle.")
             return []
        except Exception as e:
            if self.debug_mode: self.logger.error(f"Getting object states for sync failed: {e}", exc_info=True)
        return syncable_objects_list

    def _determine_object_type(self, scene_item: QtWidgets.QGraphicsItem) -> str:
        """Determines a string type for a scene item."""
        if hasattr(scene_item, 'category') and isinstance(getattr(scene_item, 'category'), str):
            return getattr(scene_item, 'category')
        if hasattr(scene_item, 'object_type') and isinstance(getattr(scene_item, 'object_type'), str):
            return getattr(scene_item, 'object_type')
        if isinstance(scene_item, QtWidgets.QGraphicsPixmapItem) and hasattr(scene_item, 'filename'):
            filename_lower = getattr(scene_item, 'filename', '').lower()
            if not filename_lower: return 'unknown_pixmap'
            if 'rock' in filename_lower: return 'rock'
            if any(food_kw in filename_lower for food_kw in ['food', 'sushi', 'apple', 'cheese', 'berry']): return 'food'
            if 'poop' in filename_lower: return 'poop'
            if os.path.join("images", "decoration") in filename_lower.replace("\\", "/") or \
               any(kw in filename_lower for kw in ['decor', 'plant', 'toy', 'shell', 'coral', 'starfish', 'gem']):
                return 'decoration'
        return 'generic_item'

    def handle_object_sync(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles incoming 'object_sync' messages from remote peers."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        try:
            sync_payload = message.get('payload', {})
            remote_squid_state = sync_payload.get('squid', {})
            remote_objects_list = sync_payload.get('objects', [])
            source_node_info = sync_payload.get('node_info', {})
            sender_node_id = source_node_info.get('id') or remote_squid_state.get('node_id')
            if not sender_node_id:
                if self.debug_mode: self.logger.warning("Received object_sync with no identifiable sender node_id.")
                return
            if self.network_node and sender_node_id == self.network_node.node_id: return
            if remote_squid_state:
                self.update_remote_squid(sender_node_id, remote_squid_state)
            if remote_objects_list:
                active_cloned_ids_for_this_sender = set()
                for remote_obj_data in remote_objects_list:
                    if not all(k in remote_obj_data for k in ['id', 'type', 'x', 'y', 'filename']):
                        if self.debug_mode: self.logger.debug(f"Skipping incomplete remote object data from {sender_node_id}: {remote_obj_data.get('id', 'No ID')}")
                        continue
                    original_id_from_sender = remote_obj_data['id']
                    clone_id = f"clone_{sender_node_id}_{original_id_from_sender}"
                    active_cloned_ids_for_this_sender.add(clone_id)
                    self.process_remote_object(remote_obj_data, sender_node_id, clone_id)
                with self.remote_objects_lock:
                    ids_to_remove = [
                        obj_id for obj_id, obj_info in self.remote_objects.items()
                        if obj_info.get('source_node') == sender_node_id and obj_id not in active_cloned_ids_for_this_sender
                    ]
                    for obj_id_to_remove in ids_to_remove:
                        self.remove_remote_object(obj_id_to_remove)
            if self.tamagotchi_logic.squid and hasattr(self.tamagotchi_logic.squid, 'process_squid_detection') and remote_squid_state:
                self.tamagotchi_logic.squid.process_squid_detection(
                    remote_node_id=sender_node_id, is_detected=True, remote_squid_props=remote_squid_state
                )
        except Exception as e:
            if self.debug_mode: self.logger.error(f"Handling object_sync from {addr} failed: {e}", exc_info=True)

    def process_remote_object(self, remote_obj_data: Dict, source_node_id: str, clone_id: str):
        """Creates or updates a visual clone of a remote object."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene
        base_filename = os.path.basename(remote_obj_data['filename'])
        resolved_filename = os.path.join("images", base_filename)
        if not os.path.exists(resolved_filename):
            for subdir in ["decoration", "items", "food", "rocks"]:
                path_attempt = os.path.join("images", subdir, base_filename)
                if os.path.exists(path_attempt):
                    resolved_filename = path_attempt
                    break
            else:
                if self.debug_mode: self.logger.warning(f"Remote object image '{base_filename}' not found locally for {clone_id}. Skipping visual.")
                return
        with self.remote_objects_lock:
            if clone_id in self.remote_objects:
                existing_clone_info = self.remote_objects[clone_id]
                visual_item = existing_clone_info['visual']
                visual_item.setPos(remote_obj_data['x'], remote_obj_data['y'])
                visual_item.setScale(remote_obj_data.get('scale', 1.0))
                visual_item.setZValue(remote_obj_data.get('zValue', -5))
                visual_item.setVisible(not remote_obj_data.get('is_being_carried', False))
                existing_clone_info['last_update'] = time.time()
                existing_clone_info['data'] = remote_obj_data
                if not getattr(visual_item, 'is_foreign', False):
                     self.apply_foreign_object_tint(visual_item)
            else:
                if remote_obj_data.get('is_being_carried', False):
                    return
                try:
                    pixmap = QtGui.QPixmap(resolved_filename)
                    if pixmap.isNull():
                        if self.debug_mode: self.logger.error(f"Failed to load QPixmap for remote object '{resolved_filename}'.")
                        return
                    cloned_visual = QtWidgets.QGraphicsPixmapItem(pixmap)
                    cloned_visual.setPos(remote_obj_data['x'], remote_obj_data['y'])
                    cloned_visual.setScale(remote_obj_data.get('scale', 1.0))
                    cloned_visual.setOpacity(self.REMOTE_SQUID_OPACITY * 0.65)
                    cloned_visual.setZValue(remote_obj_data.get('zValue', -5))
                    setattr(cloned_visual, 'filename', resolved_filename)
                    setattr(cloned_visual, 'is_remote_clone', True)
                    setattr(cloned_visual, 'original_id_from_sender', remote_obj_data['id'])
                    self.apply_foreign_object_tint(cloned_visual)
                    scene.addItem(cloned_visual)
                    self.remote_objects[clone_id] = {
                        'visual': cloned_visual, 'type': remote_obj_data.get('type', 'unknown_clone'),
                        'source_node': source_node_id, 'last_update': time.time(), 'data': remote_obj_data
                    }
                    # if self.debug_mode: self.logger.debug(f"Created visual clone '{clone_id}' for remote object.")
                except Exception as e_create_clone:
                    if self.debug_mode: self.logger.error(f"Creating visual clone for '{clone_id}' failed: {e_create_clone}", exc_info=True)

    def handle_heartbeat(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles heartbeat messages from other peers."""
        if not self.logger: return
        if not self.network_node: return
        sender_node_id = message.get('node_id')
        if not sender_node_id or sender_node_id == self.network_node.node_id: return
        if self.status_widget:
            self.status_widget.update_peers(self.network_node.known_nodes)
            if sender_node_id not in self.remote_squids:
                self.status_widget.add_activity(f"Peer {sender_node_id[-6:]} detected via heartbeat.")
        elif self.status_bar and hasattr(self.status_bar, 'update_peers_count'):
            self.status_bar.update_peers_count(len(self.network_node.known_nodes))
        heartbeat_payload = message.get('payload', {})
        squid_pos_data = heartbeat_payload.get('squid_pos')
        if squid_pos_data and sender_node_id not in self.remote_squids:
            if self.debug_mode: self.logger.debug(f"Creating placeholder for {sender_node_id[-6:]} from heartbeat.")
            placeholder_squid_data = {
                'x': squid_pos_data[0], 'y': squid_pos_data[1], 'direction': 'right',
                'color': (150, 150, 150), 'node_id': sender_node_id, 'status': 'detected'
            }
            self.update_remote_squid(sender_node_id, placeholder_squid_data, is_new_arrival=True)

    def update_remote_squid(self, remote_node_id: str, squid_data_dict: Dict, is_new_arrival=False, high_visibility=False):
        """Updates or creates the visual representation of a remote squid."""
        if not self.logger: return False
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return False
        if not squid_data_dict or not all(key in squid_data_dict for key in ['x', 'y', 'direction']):
            if self.debug_mode: self.logger.warning(f"Insufficient data to update remote squid {remote_node_id}.")
            return False
        scene = self.tamagotchi_logic.user_interface.scene
        with self.remote_squids_lock:
            existing_squid_display = self.remote_squids.get(remote_node_id)
            if existing_squid_display:
                visual = existing_squid_display.get('visual')
                id_text = existing_squid_display.get('id_text')
                status_text = existing_squid_display.get('status_text')
                if visual:
                    visual.setPos(squid_data_dict['x'], squid_data_dict['y'])
                    self.update_remote_squid_image(existing_squid_display, squid_data_dict['direction'])
                new_status_str = "ARRIVING" if is_new_arrival else squid_data_dict.get('status', 'active')
                text_y_offset_id = -50
                text_y_offset_status = -35
                if id_text: id_text.setPos(squid_data_dict['x'], squid_data_dict['y'] + text_y_offset_id)
                if status_text:
                    status_text.setPlainText(new_status_str)
                    status_text.setPos(squid_data_dict['x'], squid_data_dict['y'] + text_y_offset_status)
                    if is_new_arrival or high_visibility:
                        status_text.setDefaultTextColor(QtGui.QColor(255, 223, 0))
                        status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                    elif status_text.toPlainText().upper() != "ARRIVING":
                        status_text.setDefaultTextColor(QtGui.QColor(200,200,200,230))
                        status_text.setFont(QtGui.QFont("Arial", 9))
                existing_squid_display['data'] = squid_data_dict
                existing_squid_display['last_update'] = time.time()
            else:
                try:
                    initial_direction = squid_data_dict.get('direction', 'right')
                    placeholder_pixmap = QtGui.QPixmap(60, 40)
                    squid_color_tuple = squid_data_dict.get('color', (100,150,255))
                    placeholder_pixmap.fill(QtGui.QColor(*squid_color_tuple))
                    visual = QtWidgets.QGraphicsPixmapItem(placeholder_pixmap)
                    visual.setPos(squid_data_dict['x'], squid_data_dict['y'])
                    scene.addItem(visual)
                    display_id_str = f"{remote_node_id[-6:]}"
                    id_text = scene.addText(display_id_str)
                    id_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 50)
                    id_text.setFont(QtGui.QFont("Arial", 8))
                    status_str = "ARRIVING" if is_new_arrival else squid_data_dict.get('status', 'active')
                    status_text = scene.addText(status_str)
                    status_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 35)
                    new_squid_display_data = {
                        'visual': visual, 'id_text': id_text, 'status_text': status_text,
                        'view_cone': None, 'last_update': time.time(), 'data': squid_data_dict
                    }
                    self.remote_squids[remote_node_id] = new_squid_display_data
                    self.update_remote_squid_image(new_squid_display_data, initial_direction)
                    if is_new_arrival or high_visibility:
                        visual.setZValue(15)
                        visual.setOpacity(1.0)
                        id_text.setDefaultTextColor(QtGui.QColor(240, 240, 100))
                        status_text.setDefaultTextColor(QtGui.QColor(255, 215, 0))
                        status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                        id_text.setZValue(16); status_text.setZValue(16)
                        self._create_enhanced_arrival_animation(visual, squid_data_dict['x'], squid_data_dict['y'])
                        QtCore.QTimer.singleShot(8000, lambda: self._reset_remote_squid_style(remote_node_id))
                    else:
                        self._reset_remote_squid_style(remote_node_id)
                except Exception as e_create_squid:
                    self.logger.error(f"Creating remote squid visual for {remote_node_id} failed: {e_create_squid}", exc_info=True)
                    if remote_node_id in self.remote_squids: del self.remote_squids[remote_node_id]
                    return False
        return True

    def _create_enhanced_arrival_animation(self, squid_visual_item: QtWidgets.QGraphicsPixmapItem, at_x: float, at_y: float):
        """Creates a more prominent visual animation for newly arriving remote squids."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene
        num_pulses = 2
        for i in range(num_pulses):
            pulse_circle = QtWidgets.QGraphicsEllipseItem(at_x - 10, at_y - 10, 20, 20)
            pulse_color = QtGui.QColor(173, 216, 230, 150)
            pulse_circle.setPen(QtGui.QPen(pulse_color, 1.5))
            pulse_circle.setBrush(QtCore.Qt.NoBrush)
            pulse_circle.setZValue(getattr(squid_visual_item, 'zValue', 5) -1)
            scene.addItem(pulse_circle)
            pulse_anim_group = QtCore.QParallelAnimationGroup()
            size_anim = QtCore.QPropertyAnimation(pulse_circle, b"rect")
            size_anim.setDuration(1200 + i*200)
            size_anim.setStartValue(QtCore.QRectF(at_x - 10, at_y - 10, 20, 20))
            size_anim.setEndValue(QtCore.QRectF(at_x - 50 - i*10, at_y - 50 - i*10, 100 + i*20, 100 + i*20))
            size_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
            pulse_opacity_effect = QtWidgets.QGraphicsOpacityEffect(pulse_circle)
            pulse_circle.setGraphicsEffect(pulse_opacity_effect)
            opacity_anim = QtCore.QPropertyAnimation(pulse_opacity_effect, b"opacity")
            opacity_anim.setDuration(1000 + i*200)
            opacity_anim.setStartValue(0.7)
            opacity_anim.setEndValue(0.0)
            opacity_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
            pulse_anim_group.addAnimation(size_anim)
            pulse_anim_group.addAnimation(opacity_anim)
            QtCore.QTimer.singleShot(i * 300, pulse_anim_group.start)
            pulse_anim_group.finished.connect(lambda item=pulse_circle: scene.removeItem(item) if item in scene.items() else None)
        scale_anim = QtCore.QPropertyAnimation(squid_visual_item, b"scale")
        scale_anim.setDuration(800)
        scale_anim.setKeyValueAt(0, 0.8)
        scale_anim.setKeyValueAt(0.5, 1.1)
        scale_anim.setKeyValueAt(1, 1.0)
        scale_anim.setEasingCurve(QtCore.QEasingCurve.OutBack)
        scale_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def handle_remote_squid_return(self, remote_node_id: str, controller: Any):
        """Initiates the process for a remote squid to return home."""
        if not self.logger: return
        if self.debug_mode: self.logger.debug(f"Remote squid {remote_node_id[-6:]} is being returned home by its controller.")
        activity_summary_data = controller.get_summary()
        home_direction_for_exit = controller.home_direction
        remote_squid_display_info = self.remote_squids.get(remote_node_id)
        if not remote_squid_display_info or not remote_squid_display_info.get('visual'):
            if self.debug_mode: self.logger.warning(f"Visual for returning remote squid {remote_node_id[-6:]} not found. Completing return directly.")
            self.complete_remote_squid_return(remote_node_id, activity_summary_data, home_direction_for_exit)
            return
        visual_item = remote_squid_display_info['visual']
        status_text = remote_squid_display_info.get('status_text')
        if status_text:
            status_text.setPlainText("RETURNING HOME...")
            status_text.setDefaultTextColor(QtGui.QColor(255, 165, 0))
            status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        opacity_eff = QtWidgets.QGraphicsOpacityEffect(visual_item)
        visual_item.setGraphicsEffect(opacity_eff)
        fade_out_animation = QtCore.QPropertyAnimation(opacity_eff, b"opacity")
        fade_out_animation.setDuration(1800)
        fade_out_animation.setStartValue(visual_item.opacity())
        fade_out_animation.setEndValue(0.0)
        fade_out_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)
        fade_out_animation.finished.connect(
            lambda: self.complete_remote_squid_return(remote_node_id, activity_summary_data, home_direction_for_exit)
        )
        fade_out_animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        if self.debug_mode: self.logger.info(f"Started fade-out for remote squid {remote_node_id[-6:]} returning home.")
        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(f"👋 Visitor squid {remote_node_id[-6:]} is heading back home!")

    def complete_remote_squid_return(self, remote_node_id: str, activity_summary: Dict, exit_direction: str):
        """Finalizes the return of a remote squid."""
        if not self.logger: return
        try:
            if self.network_node and self.network_node.is_connected:
                return_message_payload = {
                    'node_id': remote_node_id, 'activity_summary': activity_summary,
                    'return_direction': exit_direction
                }
                self.network_node.send_message('squid_return', return_message_payload)
                if self.debug_mode:
                    rocks = activity_summary.get('rocks_stolen',0)
                    self.logger.info(f"Sent 'squid_return' for {remote_node_id[-6:]} (summary: {rocks} rocks). Exit dir: {exit_direction}")
            self.remove_remote_squid(remote_node_id)
            if remote_node_id in self.remote_squid_controllers:
                del self.remote_squid_controllers[remote_node_id]
                if self.debug_mode: self.logger.info(f"Removed controller for returned remote squid {remote_node_id[-6:]}.")
        except Exception as e:
            self.logger.error(f"Completing remote squid return for {remote_node_id[-6:]} failed: {e}", exc_info=True)

    def update_remote_view_cone(self, remote_node_id: str, remote_squid_data: Dict):
        """Updates the visual representation of a remote squid's view cone."""
        if not self.logger: return
        if not self.SHOW_REMOTE_LABELS:
            if remote_node_id in self.remote_squids and self.remote_squids[remote_node_id].get('view_cone'):
                self._remove_view_cone_for_squid(remote_node_id)
            return
        if remote_node_id not in self.remote_squids or not self.tamagotchi_logic or \
           not hasattr(self.tamagotchi_logic, 'user_interface'):
            return
        scene = self.tamagotchi_logic.user_interface.scene
        squid_display_info = self.remote_squids[remote_node_id]
        existing_cone_item = squid_display_info.get('view_cone')
        if existing_cone_item and existing_cone_item in scene.items():
            scene.removeItem(existing_cone_item)
        squid_display_info['view_cone'] = None
        if not remote_squid_data.get('view_cone_visible', False):
            return
        squid_x = remote_squid_data['x']
        squid_y = remote_squid_data['y']
        visual_item = squid_display_info.get('visual')
        if visual_item:
            squid_center_x = visual_item.pos().x() + visual_item.boundingRect().width() / 2
            squid_center_y = visual_item.pos().y() + visual_item.boundingRect().height() / 2
        else:
            squid_center_x = squid_x + 30
            squid_center_y = squid_y + 20
        looking_direction_rad = remote_squid_data.get('looking_direction', 0.0)
        view_cone_angle_rad = remote_squid_data.get('view_cone_angle', math.radians(50))
        cone_half_angle = view_cone_angle_rad / 2.0
        cone_length = 150
        point1_origin = QtCore.QPointF(squid_center_x, squid_center_y)
        point2_edge1 = QtCore.QPointF(
            squid_center_x + cone_length * math.cos(looking_direction_rad - cone_half_angle),
            squid_center_y + cone_length * math.sin(looking_direction_rad - cone_half_angle)
        )
        point3_edge2 = QtCore.QPointF(
            squid_center_x + cone_length * math.cos(looking_direction_rad + cone_half_angle),
            squid_center_y + cone_length * math.sin(looking_direction_rad + cone_half_angle)
        )
        cone_polygon = QtGui.QPolygonF([point1_origin, point2_edge1, point3_edge2])
        new_cone_item = QtWidgets.QGraphicsPolygonItem(cone_polygon)
        squid_color = remote_squid_data.get('color', (150, 150, 255))
        new_cone_item.setPen(QtGui.QPen(QtGui.QColor(*squid_color, 0)))
        new_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(*squid_color, 25)))
        new_cone_item.setZValue(visual_item.zValue() - 1 if visual_item else 4)
        scene.addItem(new_cone_item)
        squid_display_info['view_cone'] = new_cone_item

    def _remove_view_cone_for_squid(self, remote_node_id: str):
        """Safely removes a view cone for a specific remote squid."""
        if not self.logger: return
        if remote_node_id in self.remote_squids and self.tamagotchi_logic and hasattr(self.tamagotchi_logic.user_interface, 'scene'):
            squid_display_info = self.remote_squids[remote_node_id]
            cone_item = squid_display_info.get('view_cone')
            if cone_item and cone_item in self.tamagotchi_logic.user_interface.scene.items():
                self.tamagotchi_logic.user_interface.scene.removeItem(cone_item)
            squid_display_info['view_cone'] = None

    def create_gift_decoration(self, from_remote_node_id: str) -> QtWidgets.QGraphicsPixmapItem | None:
        """Creates a new decoration item representing a received gift."""
        if not self.logger: return None
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return None
        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        available_decoration_images = []
        decoration_image_dirs = [os.path.join("images", "decoration"), "images"]
        for img_dir in decoration_image_dirs:
            if os.path.exists(img_dir):
                for filename in os.listdir(img_dir):
                    if filename.lower().endswith(('.png', '.jpg', '.gif')) and \
                       any(kw in filename.lower() for kw in ['decor', 'plant', 'toy', 'shell', 'coral', 'starfish', 'gem']):
                        available_decoration_images.append(os.path.join(img_dir, filename))
        if not available_decoration_images:
            default_gift_img = os.path.join("images", "plant.png")
            if not os.path.exists(default_gift_img):
                if self.debug_mode: self.logger.warning("Default gift image not found. Cannot create gift.")
                return None
            available_decoration_images.append(default_gift_img)
        chosen_gift_image_path = random.choice(available_decoration_images)
        try:
            gift_pixmap = QtGui.QPixmap(chosen_gift_image_path)
            if gift_pixmap.isNull():
                if self.debug_mode: self.logger.error(f"Failed to load gift image '{chosen_gift_image_path}'.")
                return None
            gift_item = None
            if hasattr(ui, 'ResizablePixmapItem'):
                gift_item = ui.ResizablePixmapItem(gift_pixmap, chosen_gift_image_path)
            else:
                gift_item = QtWidgets.QGraphicsPixmapItem(gift_pixmap)
                setattr(gift_item, 'filename', chosen_gift_image_path)
            setattr(gift_item, 'category', 'decoration')
            setattr(gift_item, 'is_gift_from_remote', True)
            setattr(gift_item, 'received_from_node', from_remote_node_id)
            gift_item.setToolTip(f"A surprise gift from tank {from_remote_node_id[-6:]}!")
            item_width = gift_pixmap.width()
            item_height = gift_pixmap.height()
            max_placement_x = ui.window_width - item_width - 30
            max_placement_y = ui.window_height - item_height - 30
            gift_pos_x = random.uniform(30, max(30, max_placement_x))
            gift_pos_y = random.uniform(30, max(30, max_placement_y))
            gift_item.setPos(gift_pos_x, gift_pos_y)
            self.apply_foreign_object_tint(gift_item)
            scene.addItem(gift_item)
            self._create_arrival_animation(gift_item)
            gift_indicator_label = scene.addText("🎁 Gift!")
            label_font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
            gift_indicator_label.setFont(label_font)
            gift_indicator_label.setDefaultTextColor(QtGui.QColor(255, 100, 100))
            label_x = gift_pos_x + (item_width / 2) - (gift_indicator_label.boundingRect().width() / 2)
            label_y = gift_pos_y - gift_indicator_label.boundingRect().height() - 5
            gift_indicator_label.setPos(label_x, label_y)
            gift_indicator_label.setZValue(gift_item.zValue() + 1)
            label_opacity_effect = QtWidgets.QGraphicsOpacityEffect(gift_indicator_label)
            gift_indicator_label.setGraphicsEffect(label_opacity_effect)
            label_fade_out_anim = QtCore.QPropertyAnimation(label_opacity_effect, b"opacity")
            label_fade_out_anim.setDuration(4000)
            label_fade_out_anim.setStartValue(1.0)
            label_fade_out_anim.setEndValue(0.0)
            label_fade_out_anim.finished.connect(lambda item=gift_indicator_label: scene.removeItem(item) if item in scene.items() else None)
            label_fade_out_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
            return gift_item
        except Exception as e_gift:
            if self.debug_mode: self.logger.error(f"Error creating gift decoration: {e_gift}", exc_info=True)
            return None

    def remove_remote_squid(self, node_id_to_remove: str):
        """Removes visual components of a specific remote squid."""
        if not self.logger: return
        if node_id_to_remove not in self.remote_squids: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene
        with self.remote_squids_lock:
            squid_display_elements = self.remote_squids.pop(node_id_to_remove, None)
        if squid_display_elements:
            visual_keys = ['visual', 'view_cone', 'id_text', 'status_text']
            for key in visual_keys:
                item_to_remove = squid_display_elements.get(key)
                if item_to_remove and item_to_remove in scene.items():
                    scene.removeItem(item_to_remove)
            if node_id_to_remove in self.connection_lines:
                line = self.connection_lines.pop(node_id_to_remove)
                if line in scene.items():
                    scene.removeItem(line)
            # if self.debug_mode: self.logger.debug(f"Removed all visuals for remote squid {node_id_to_remove[-6:]}.")
        if self.network_node: # network_node might be None during full cleanup
            if self.status_widget: self.status_widget.update_peers(self.network_node.known_nodes if self.network_node else {})
            elif self.status_bar and hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(len(self.network_node.known_nodes if self.network_node else {}))

    def remove_remote_object(self, full_clone_id: str):
        """Removes a specific cloned remote object."""
        if not self.logger: return
        if full_clone_id not in self.remote_objects: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene
        with self.remote_objects_lock:
            object_clone_info = self.remote_objects.pop(full_clone_id, None)
        if object_clone_info:
            visual_item = object_clone_info.get('visual')
            if visual_item and visual_item in scene.items():
                scene.removeItem(visual_item)
            # if self.debug_mode: self.logger.debug(f"Removed remote object clone: {full_clone_id}.")

    def throw_rock_network(self, rock_graphics_item: QtWidgets.QGraphicsPixmapItem, direction_thrown: str):
        """Broadcasts a 'rock_throw' event."""
        if not self.logger: return
        if not self.network_node or not self.network_node.is_connected or not rock_graphics_item:
            return
        try:
            rock_filename = getattr(rock_graphics_item, 'filename', "default_rock.png")
            initial_pos = rock_graphics_item.pos()
            rock_throw_payload = {
                'rock_data': {
                    'filename': rock_filename, 'direction': direction_thrown,
                    'initial_pos_x': initial_pos.x(), 'initial_pos_y': initial_pos.y(),
                    'scale': rock_graphics_item.scale() if hasattr(rock_graphics_item, 'scale') else 1.0,
                }
            }
            self.network_node.send_message('rock_throw', rock_throw_payload)
            if self.debug_mode:
                self.logger.debug(f"Broadcasted local rock throw: {os.path.basename(rock_filename)} towards {direction_thrown}.")
        except Exception as e_throw:
            if self.debug_mode: self.logger.error(f"Broadcasting rock throw failed: {e_throw}", exc_info=True)

    def cleanup(self):
        """Cleans up all resources used by the multiplayer plugin."""
        # Ensure logger is available for cleanup messages
        if self.logger is None: # Critical fallback if logger somehow became None before cleanup
            emergency_logger = logging.getLogger(f"{mp_constants.PLUGIN_NAME}_CleanupEmergency")
            if not emergency_logger.hasHandlers(): emergency_logger.addHandler(logging.StreamHandler())
            emergency_logger.setLevel(logging.INFO)
            self.logger = emergency_logger
            self.logger.warning("Logger was None at the start of cleanup. Using emergency logger.")

        self.logger.info(f"Initiating {mp_constants.PLUGIN_NAME} cleanup...")
        self.is_setup = False
        timers_to_manage = [
            'message_process_timer', 'controller_update_timer', 'controller_creation_timer',
            'cleanup_timer_basic', 'connection_timer_basic'
        ]
        for timer_attr_name in timers_to_manage:
            timer_instance = getattr(self, timer_attr_name, None)
            if timer_instance and isinstance(timer_instance, QtCore.QTimer) and timer_instance.isActive():
                timer_instance.stop()
                if self.debug_mode: self.logger.debug(f"Stopped timer '{timer_attr_name}'.")
            setattr(self, timer_attr_name, None)
        if self.sync_thread and self.sync_thread.is_alive():
             if self.debug_mode: self.logger.info("Sync thread was active during cleanup. As a daemon, it will exit with app.")
        self.sync_thread = None
        
        # NetworkNode cleanup logic (including trying to leave multicast group)
        if self.network_node:
            nn = self.network_node # temp reference
            self.network_node = None # Set to None early to prevent re-entry or use during async parts of its own cleanup

            if nn.is_connected:
                try:
                    nn.send_message(
                        'player_leave',
                        {'node_id': nn.node_id, 'reason': 'plugin_unloaded_or_disabled'}
                    )
                except Exception as e_leave:
                    if self.debug_mode: self.logger.error(f"Error sending player_leave message: {e_leave}", exc_info=True)
            
            if nn.socket: # Check if socket exists before trying to manipulate it
                try:
                    # Check for necessary attributes for multicast leave
                    if nn.is_connected and hasattr(nn, 'local_ip') and nn.local_ip and \
                       hasattr(mp_constants, 'MULTICAST_GROUP') and mp_constants.MULTICAST_GROUP:
                        # Dynamically import socket here if not globally imported and only needed for this
                        import socket as sock_module 
                        mreq_leave = sock_module.inet_aton(mp_constants.MULTICAST_GROUP) + sock_module.inet_aton(nn.local_ip)
                        nn.socket.setsockopt(sock_module.IPPROTO_IP, sock_module.IP_DROP_MEMBERSHIP, mreq_leave)
                except AttributeError as e_attr: # Catch if local_ip or MULTICAST_GROUP is None or socket methods missing
                     if self.debug_mode: self.logger.warning(f"Attribute error during multicast group leave (possibly expected if IP unknown): {e_attr}")
                except Exception as e_mcast_leave:
                     if self.debug_mode: self.logger.warning(f"Error leaving multicast group: {e_mcast_leave}", exc_info=True)
                finally:
                    try:
                        nn.socket.close()
                    except Exception: pass 
            nn.is_connected = False
            nn.socket = None
            # self.network_node = None # Already set above

        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
            with self.remote_squids_lock:
                for node_id_key in list(self.remote_squids.keys()): self.remove_remote_squid(node_id_key)
            with self.remote_objects_lock:
                for clone_id_key in list(self.remote_objects.keys()): self.remove_remote_object(clone_id_key)
        self.remote_squids.clear()
        self.remote_objects.clear()
        self.connection_lines.clear()
        self.remote_squid_controllers.clear()
        if self.status_widget:
             if hasattr(self.status_widget, 'update_connection_status'): self.status_widget.update_connection_status(False)
             if hasattr(self.status_widget, 'update_peers'): self.status_widget.update_peers({})
             if hasattr(self.status_widget, 'add_activity'): self.status_widget.add_activity(f"{mp_constants.PLUGIN_NAME} has been shut down.")
        elif self.status_bar:
            if hasattr(self.status_bar, 'update_network_status'): self.status_bar.update_network_status(False)
            if hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(0)
            if hasattr(self.status_bar, 'add_message'): self.status_bar.add_message(f"{mp_constants.PLUGIN_NAME} plugin shut down.")
        self.logger.info(f"{mp_constants.PLUGIN_NAME} plugin cleanup process completed.")

    def handle_squid_move(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles discrete 'squid_move' messages."""
        if not self.logger: return
        payload = message.get('payload', {})
        sender_node_id = message.get('node_id') # Assuming NetworkNode adds this from addr or payload
        if sender_node_id and sender_node_id in self.remote_squids:
            current_display_data = self.remote_squids[sender_node_id]
            visual = current_display_data.get('visual')
            if visual and all(k in payload for k in ['x', 'y', 'direction']):
                visual.setPos(payload['x'], payload['y'])
                self.update_remote_squid_image(current_display_data, payload['direction'])
            if 'data' in current_display_data and all(k in payload for k in ['x', 'y', 'direction']):
                current_display_data['data']['x'] = payload['x']
                current_display_data['data']['y'] = payload['y']
                current_display_data['data']['direction'] = payload['direction']

    def handle_rock_throw(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles 'rock_throw' messages from remote players."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene
        payload = message.get('payload', {}).get('rock_data', {})
        sender_node_id = message.get('node_id') # Assuming NetworkNode adds this
        if not payload or not sender_node_id: return
        if self.debug_mode: self.logger.debug(f"Received rock_throw from {sender_node_id[-6:]}, data: {payload}")
        rock_filename = payload.get('filename', os.path.join("images","rock.png"))
        try:
            pixmap = QtGui.QPixmap(rock_filename)
            if pixmap.isNull(): pixmap = QtGui.QPixmap(os.path.join("images","rock.png"))
            thrown_rock_item = QtWidgets.QGraphicsPixmapItem(pixmap)
            initial_x = payload.get('initial_pos_x', scene.width()/2)
            initial_y = payload.get('initial_pos_y', scene.height()/2)
            thrown_rock_item.setPos(initial_x, initial_y)
            thrown_rock_item.setScale(payload.get('scale', 0.8))
            thrown_rock_item.setZValue(20)
            self.apply_foreign_object_tint(thrown_rock_item)
            scene.addItem(thrown_rock_item)
            anim_group = QtCore.QParallelAnimationGroup()
            pos_anim = QtCore.QPropertyAnimation(thrown_rock_item, b"pos")
            pos_anim.setDuration(1500)
            pos_anim.setStartValue(QtCore.QPointF(initial_x, initial_y))
            throw_dir_str = payload.get('direction', 'right')
            target_x = scene.width() + 50 if throw_dir_str == 'right' else -50
            target_y = initial_y + random.uniform(-50, 50)
            pos_anim.setEndValue(QtCore.QPointF(target_x, target_y))
            pos_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
            anim_group.addAnimation(pos_anim)
            anim_group.finished.connect(lambda item=thrown_rock_item: scene.removeItem(item) if item in scene.items() else None)
            anim_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        except Exception as e_rock_throw_vis:
            if self.debug_mode: self.logger.error(f"Error visualizing remote rock throw: {e_rock_throw_vis}", exc_info=True)

    def handle_state_update(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles generic 'state_update' messages."""
        if not self.logger: return
        payload = message.get('payload', {})
        sender_node_id = message.get('node_id') # Assuming NetworkNode adds this
        if self.debug_mode: self.logger.debug(f"Received generic 'state_update' from {sender_node_id[-6:] if sender_node_id else 'Unknown'}. Payload: {payload}")
        # Add specific logic based on payload content