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
import traceback
import math
from typing import Dict, List, Any, Tuple
from PyQt5 import QtCore, QtGui, QtWidgets

# Import from local multiplayer modules
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
        self.message_process_timer: QtCore.QTimer | None = None # For processing NetworkNode's queue
        self.controller_update_timer: QtCore.QTimer | None = None # For remote squid AI
        self.controller_creation_timer: QtCore.QTimer | None = None # Fallback for controller creation
        self.cleanup_timer_basic: QtCore.QTimer | None = None # For basic stale node cleanup
        self.connection_timer_basic: QtCore.QTimer | None = None # For basic connection line updates

        # --- State and Data ---
        self.remote_squids: Dict[str, Dict[str, Any]] = {} # node_id -> {visual, data, ...}
        self.remote_objects: Dict[str, Dict[str, Any]] = {} # clone_id -> {visual, data, ...}
        self.remote_squid_controllers: Dict[str, Any] = {} # node_id -> RemoteSquidController instance
        self.pending_controller_creations: List[Dict[str, Any]] = []
        self.connection_lines: Dict[str, QtWidgets.QGraphicsLineItem] = {}
        self.last_message_times: Dict[str, float] = {} # For rate-limiting certain messages

        # --- Configuration (initialized from mp_constants, can be changed at runtime) ---
        self.MULTICAST_GROUP = mp_constants.MULTICAST_GROUP
        self.MULTICAST_PORT = mp_constants.MULTICAST_PORT
        self.SYNC_INTERVAL = mp_constants.SYNC_INTERVAL
        self.REMOTE_SQUID_OPACITY = mp_constants.REMOTE_SQUID_OPACITY
        self.SHOW_REMOTE_LABELS = mp_constants.SHOW_REMOTE_LABELS
        self.SHOW_CONNECTION_LINES = mp_constants.SHOW_CONNECTION_LINES

        # --- UI Elements ---
        self.config_dialog: QtWidgets.QDialog | None = None
        self.status_widget: Any | None = None # Dedicated multiplayer status widget
        self.status_bar: Any | None = None    # Fallback status bar component from main UI

        # --- Flags ---
        self.is_setup = False # This line was added in the previous recommendation to fix the AttributeError
        self.debug_mode = False # Usually set based on tamagotchi_logic.debug_mode

        # This queue is if the plugin itself needs to queue tasks for its main thread operations,
        # separate from NetworkNode's incoming_queue which is for raw network messages.
        # For now, NetworkNode.process_messages is called by a timer in this plugin.
        # self.internal_task_queue = queue.Queue()


    def debug_autopilot_status(self):
        """Debug the status of all autopilot controllers for remote squids."""
        if not hasattr(self, 'remote_squid_controllers') or not self.remote_squid_controllers:
            print("Multiplayer: No remote squid controllers are currently active.")
            return

        print(f"\n=== AUTOPILOT DEBUG ({len(self.remote_squid_controllers)} controllers) ===")
        for node_id, controller in self.remote_squid_controllers.items():
            squid_name = node_id[-6:] # Short ID for readability
            print(f"Squid {squid_name}:")
            print(f"  State: {getattr(controller, 'state', 'N/A')}")
            squid_data = getattr(controller, 'squid_data', {})
            pos_x = squid_data.get('x', 0.0)
            pos_y = squid_data.get('y', 0.0)
            print(f"  Position: ({pos_x:.1f}, {pos_y:.1f})")
            print(f"  Direction: {squid_data.get('direction', 'N/A')}")
            print(f"  Home Dir: {getattr(controller, 'home_direction', 'N/A')}")
            time_away = getattr(controller, 'time_away', 0.0)
            max_time = getattr(controller, 'max_time_away', 0.0)
            print(f"  Time Away: {time_away:.1f}s / {max_time:.1f}s")
            food_count = getattr(controller, 'food_eaten_count', 0)
            rock_count = getattr(controller, 'rock_interaction_count', 0)
            print(f"  Activities: {food_count} food, {rock_count} rocks")
            target_obj = getattr(controller, 'target_object', None)
            print(f"  Target: {'Yes (' + type(target_obj).__name__ + ')' if target_obj else 'No'}")
        print("=====================================\n")

    def enable(self):
        """Enables the multiplayer plugin, performing setup if necessary."""
        print("Multiplayer: Enabling plugin...")
        try:
            # Safely check for the 'is_setup' attribute.
            # If it doesn't exist, getattr will return False (the default value provided).
            is_currently_setup = getattr(self, 'is_setup', False)

            if not is_currently_setup:
                # This block runs if 'is_setup' is False.
                
                # 1. Ensure self.plugin_manager is available.
                # It might be pre-set by the plugin system.
                # If not, and self.tamagotchi_logic is somehow already set and has plugin_manager, try that.
                if self.plugin_manager is None:
                    if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic and \
                       hasattr(self.tamagotchi_logic, 'plugin_manager'):
                        self.plugin_manager = getattr(self.tamagotchi_logic, 'plugin_manager', None)
                
                if self.plugin_manager is None:
                    print("Multiplayer Error: Cannot enable, plugin_manager not found (required for setup).")
                    return False

                # 2. Obtain the tamagotchi_logic_instance required by the setup method.
                tamagotchi_logic_ref = getattr(self, 'tamagotchi_logic', None) # Check if already on self

                if tamagotchi_logic_ref is None:
                    # If not on self, try to get it from the plugin_manager, as it might hold a reference.
                    tamagotchi_logic_ref = getattr(self.plugin_manager, 'tamagotchi_logic', None)
                
                if tamagotchi_logic_ref is None:
                    # As a more thorough fallback, use the _find_tamagotchi_logic utility.
                    # This is useful if plugin_manager is a more complex object (e.g., the main app instance)
                    # that contains tamagotchi_logic somewhere within its structure.
                    print("Multiplayer: TamagotchiLogic not found directly, attempting deep search...")
                    tamagotchi_logic_ref = self._find_tamagotchi_logic(self.plugin_manager)

                if tamagotchi_logic_ref is None:
                    print("Multiplayer Error: TamagotchiLogic instance could not be found. Setup cannot proceed.")
                    return False
                
                # Now, we should have both self.plugin_manager and tamagotchi_logic_ref.
                # Call setup with both required arguments.
                # The setup method itself will set self.tamagotchi_logic = tamagotchi_logic_ref.
                if not self.setup(self.plugin_manager, tamagotchi_logic_ref):
                    print("Multiplayer Error: Setup failed during enable.")
                    return False
                # After a successful setup, self.is_setup should be True.

            # --- Post-setup actions (continue with the rest of the original enable method) ---

            # Ensure network node is active
            # Add checks for self.network_node existence before accessing its attributes
            if hasattr(self, 'network_node') and self.network_node and not self.network_node.is_connected:
                print("Multiplayer: Network node not connected, attempting to initialize socket...")
                self.network_node.initialize_socket()

            # Start synchronization thread if not already running
            # Add checks for self.sync_thread existence
            if not (hasattr(self, 'sync_thread') and self.sync_thread and self.sync_thread.is_alive()):
                if hasattr(self, 'start_sync_timer'): # Check if method exists
                    self.start_sync_timer()
                else:
                    print("Multiplayer Warning: start_sync_timer method not found.")


            # Show and update status UI
            # Add checks for self.status_widget existence
            if hasattr(self, 'status_widget') and self.status_widget:
                self.status_widget.show()
                is_connected_now = hasattr(self, 'network_node') and self.network_node and self.network_node.is_connected
                node_id_now = self.network_node.node_id if hasattr(self, 'network_node') and self.network_node else "N/A"
                self.status_widget.update_connection_status(is_connected_now, node_id_now)
                if hasattr(self, 'network_node') and self.network_node and hasattr(self.network_node, 'known_nodes'):
                    self.status_widget.update_peers(self.network_node.known_nodes)

            print("Multiplayer plugin enabled successfully.")
            return True
        except Exception as e:
            print(f"Multiplayer: Error enabling plugin: {e}")
            traceback.print_exc() # This is good for debugging, prints the full error trace
            return False


    def disable(self):
        """Disables the multiplayer plugin and cleans up resources."""
        print("Multiplayer: Disabling plugin...")
        if self.network_node and self.network_node.is_connected:
            self.network_node.send_message(
                'player_leave',
                {'node_id': self.network_node.node_id, 'reason': 'plugin_disabled'}
            )
            # self.network_node.is_connected = False # Let cleanup handle socket closure

        self.cleanup() # Calls methods to stop timers, clear visuals, etc.

        if self.status_widget: self.status_widget.hide()
        if self.status_bar: # Fallback
            self.status_bar.update_network_status(False)
            self.status_bar.update_peers_count(0)

        print("Multiplayer plugin disabled.")


    def setup(self, plugin_manager_instance, tamagotchi_logic_instance):
        """
        Sets up the multiplayer plugin. Called when the plugin is first loaded or enabled.
        Args:
            plugin_manager_instance: A reference to the main plugin manager.
        """
        print("Multiplayer: Starting setup...")
        self.plugin_manager = plugin_manager_instance
        if not TamagotchiLogic: # Guard against missing TamagotchiLogic
            print("Multiplayer Critical Error: TamagotchiLogic module not loaded. Cannot complete setup.")
            return False

        # --- Initialize Core Logic ---
        # Attempt to get TamagotchiLogic instance
        if hasattr(self.plugin_manager, 'core_game_logic'): # Ideal: Plugin manager provides it
            self.tamagotchi_logic = self.plugin_manager.core_game_logic
        elif hasattr(self.plugin_manager, 'tamagotchi_logic'): # Common alternative name
            self.tamagotchi_logic = self.plugin_manager.tamagotchi_logic
        else: # Fallback: try to find it if plugin_manager is a complex object (e.g., the main app instance)
            self.tamagotchi_logic = self._find_tamagotchi_logic(self.plugin_manager)

        if not self.tamagotchi_logic:
            print("Multiplayer Critical Error: TamagotchiLogic instance not found. Plugin functionality will be severely limited.")
            # Depending on strictness, could return False here. For now, allow to proceed.
        else:
            self.debug_mode = getattr(self.tamagotchi_logic, 'debug_mode', False)
            print(f"Multiplayer: TamagotchiLogic found. Debug mode: {self.debug_mode}")


        # --- Initialize Network Node ---
        node_id_val = f"squid_{uuid.uuid4().hex[:6]}" # Shorter for display
        self.network_node = NetworkNode(node_id_val)
        self.network_node.debug_mode = self.debug_mode # Pass debug setting to network node
        # Link network_node to tamagotchi_logic if it expects it (for global access perhaps)
        if self.tamagotchi_logic:
            setattr(self.tamagotchi_logic, 'multiplayer_network_node', self.network_node)


        # --- Setup Timers ---
        # Timer for processing messages from NetworkNode's queue
        if not self.message_process_timer: # Check if already created (e.g. by previous setup attempt)
            self.message_process_timer = QtCore.QTimer()
            self.message_process_timer.timeout.connect(self._process_network_node_queue)
            self.message_process_timer.start(50) # Process messages every 50ms (20Hz)

        # Timer for updating remote squid controllers (AI, movement)
        if not self.controller_update_timer:
            self.controller_update_timer = QtCore.QTimer()
            self.controller_update_timer.timeout.connect(self.update_remote_controllers)
            self.controller_update_timer.start(50) # Target 20 FPS for controller updates

        # Fallback timer for creating controllers (if immediate creation fails or is deferred)
        if not self.controller_creation_timer:
             self._setup_controller_creation_timer() # This method creates and starts the timer

        # --- Register Hooks ---
        self._register_hooks() # Sets up handlers for network messages

        # --- Initialize Remote Entity Management ---
        self.remote_squids.clear()
        self.remote_objects.clear()
        self.connection_lines.clear()
        self.remote_squid_controllers.clear()
        self.last_controller_update = time.time()

        # Check for optional advanced entity manager or use basic timers
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
            try: # Attempt to use a dedicated RemoteEntityManager if available
                from plugins.multiplayer.remote_entity_manager import RemoteEntityManager
                self.entity_manager = RemoteEntityManager(
                    self.tamagotchi_logic.user_interface.scene,
                    self.tamagotchi_logic.user_interface.window_width,
                    self.tamagotchi_logic.user_interface.window_height,
                    self.debug_mode
                )
                print("Multiplayer: Using dedicated RemoteEntityManager.")
            except ImportError:
                print("Multiplayer: RemoteEntityManager not found. Using basic timers for cleanup/lines.")
                self.entity_manager = None
                self.initialize_remote_representation() # Fallback to basic timers

        # --- Initialize UI Components ---
        self.initialize_status_ui() # Sets up the multiplayer status display widget or bar

        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'show_message') and self.network_node:
            self.tamagotchi_logic.show_message(f"Multiplayer active! Node ID: {self.network_node.node_id}")

        node_ip = self.network_node.local_ip if self.network_node else "N/A"
        node_port = self.MULTICAST_PORT # This plugin instance's configured port
        print(f"Multiplayer setup complete. Node: {node_id_val} on IP: {node_ip}. Listening for multicast on port: {node_port}")
        self.is_setup = True
        return True

    def _process_network_node_queue(self):
        """Called by a QTimer to process messages from the NetworkNode's incoming_queue."""
        if self.network_node and self.plugin_manager:
            try:
                # Ask NetworkNode to process its own queue and trigger hooks via plugin_manager
                self.network_node.process_messages(self.plugin_manager)
            except Exception as e:
                if self.debug_mode:
                    print(f"Multiplayer: Error in _process_network_node_queue: {e}")
                    # traceback.print_exc()


    def setup_minimal_network(self):
        """(Helper) Creates a basic network interface if one is required but not found."""
        print("Multiplayer: Setting up minimal network interface...")
        class MinimalNetworkInterface:
            def create_socket(self, socket_type='udp'):
                import socket # Local import
                return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.plugin_manager:
            self.plugin_manager.plugins['network_interface'] = {
                'instance': MinimalNetworkInterface(), 'name': 'Minimal Network Interface', 'version': '0.1'
            }
            print("Multiplayer: Minimal network interface registered.")


    def update_remote_squid_image(self, remote_squid_display_data: Dict, direction: str):
        """Updates the visual image of a remote squid based on its direction."""
        visual_item = remote_squid_display_data.get('visual')
        if not visual_item or not isinstance(visual_item, QtWidgets.QGraphicsPixmapItem):
            return False

        # Construct path to squid image (e.g., "images/left1.png")
        # Ensure your "images" folder is accessible or paths are correctly resolved.
        try:
            base_image_path = "images" # Relative to where the game runs or resources are stored
            squid_image_file = f"{direction.lower()}1.png"
            full_image_path = os.path.join(base_image_path, squid_image_file)

            squid_pixmap = QtGui.QPixmap(full_image_path)
            if squid_pixmap.isNull(): # Image not found or failed to load
                # Try a default fallback image
                fallback_path = os.path.join(base_image_path, "right1.png")
                squid_pixmap = QtGui.QPixmap(fallback_path)
                if squid_pixmap.isNull() and self.debug_mode:
                    print(f"Multiplayer Warning: Could not load squid image '{full_image_path}' or fallback.")
                    return False
            visual_item.setPixmap(squid_pixmap)
            return True
        except Exception as e:
            if self.debug_mode:
                print(f"Multiplayer Error updating remote squid image for direction '{direction}': {e}")
            return False


    def handle_squid_interaction(self, local_squid, remote_node_id, remote_squid_data):
        """Handles interactions between the local squid and a detected remote squid."""
        if not local_squid or not remote_squid_data or not self.tamagotchi_logic: return

        local_pos = (local_squid.squid_x, local_squid.squid_y)
        remote_pos = (remote_squid_data.get('x',0.0), remote_squid_data.get('y',0.0))
        distance = math.hypot(local_pos[0] - remote_pos[0], local_pos[1] - remote_pos[1])

        interaction_distance_threshold = 80 # Pixels for interaction range
        if distance < interaction_distance_threshold:
            # Example interaction: greeting animation (visual effect)
            # self.create_greeting_animation(local_pos, remote_pos) # Placeholder

            # Add a memory of meeting this remote squid
            if hasattr(local_squid, 'memory_manager') and hasattr(local_squid.memory_manager, 'add_short_term_memory'):
                local_squid.memory_manager.add_short_term_memory(
                    category='social', event_type='squid_meeting',
                    description=f"Met squid {remote_node_id[-6:]} from another tank.",
                    importance=5
                )
            # Attempt a gift exchange
            self.attempt_gift_exchange(local_squid, remote_node_id)


    def attempt_gift_exchange(self, local_squid, remote_node_id: str):
        """Allows squids to exchange a random decoration item if conditions are met."""
        if random.random() > 0.15: return False # 15% chance per interaction for a gift exchange
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return False

        ui = self.tamagotchi_logic.user_interface
        # Find a visible, non-foreign decoration owned by the local player
        local_decorations = [
            item for item in ui.scene.items()
            if isinstance(item, QtWidgets.QGraphicsPixmapItem) and
               getattr(item, 'category', '') == 'decoration' and
               item.isVisible() and not getattr(item, 'is_foreign', False) and
               not getattr(item, 'is_gift_from_remote', False) # Don't trade away fresh gifts
        ]
        if not local_decorations: return False

        gift_to_send_away = random.choice(local_decorations) # Local item to "send"
        # Create a new decoration representing a gift received from the remote squid
        received_gift_item = self.create_gift_decoration(remote_node_id)

        if received_gift_item: # If a gift was successfully "received"
            # Make the local "sent" gift disappear (or mark as sent)
            gift_to_send_away.setVisible(False)
            # Optionally, remove it after a delay or add to a "sent away" list
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
        if item_to_remove and self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
            scene = self.tamagotchi_logic.user_interface.scene
            if item_to_remove in scene.items():
                scene.removeItem(item_to_remove)
                if self.debug_mode: print(f"Multiplayer: Removed gifted item '{getattr(item_to_remove,'filename','N/A')}' from scene.")


    def create_stolen_rocks(self, local_squid, num_rocks: int, entry_position: tuple):
        """Creates rock items in the local scene, representing rocks 'stolen' by the local squid from a remote tank."""
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface') or num_rocks <= 0:
            return

        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        # Find available rock images
        rock_image_files = []
        search_paths = [os.path.join("images", "decoration"), "images"]
        for path in search_paths:
            if os.path.exists(path):
                for filename in os.listdir(path):
                    if 'rock' in filename.lower() and filename.lower().endswith(('.png', '.jpg')):
                        rock_image_files.append(os.path.join(path, filename))
        if not rock_image_files:
            rock_image_files.append(os.path.join("images", "rock.png")) # Default fallback

        entry_x, entry_y = entry_position
        for i in range(num_rocks):
            try:
                chosen_rock_file = random.choice(rock_image_files)
                # Calculate position in a small cluster around the entry point
                angle_offset = random.uniform(-math.pi / 4, math.pi / 4) # Randomize angle
                angle = (i * (2 * math.pi / num_rocks)) + angle_offset
                dist = random.uniform(60, 100) # Randomize distance from center
                rock_x = entry_x + dist * math.cos(angle)
                rock_y = entry_y + dist * math.sin(angle)

                rock_pixmap = QtGui.QPixmap(chosen_rock_file)
                if rock_pixmap.isNull(): continue

                rock_graphics_item = None
                if hasattr(ui, 'ResizablePixmapItem'): # Use custom item if available
                    rock_graphics_item = ui.ResizablePixmapItem(rock_pixmap, chosen_rock_file)
                else:
                    rock_graphics_item = QtWidgets.QGraphicsPixmapItem(rock_pixmap)
                    setattr(rock_graphics_item, 'filename', chosen_rock_file) # Ensure filename attribute

                # Set properties for the "stolen" rock
                setattr(rock_graphics_item, 'category', 'rock')
                setattr(rock_graphics_item, 'can_be_picked_up', True)
                setattr(rock_graphics_item, 'is_stolen_from_remote', True) # Mark as stolen
                setattr(rock_graphics_item, 'is_foreign', True) # It's from another tank
                rock_graphics_item.setPos(rock_x, rock_y)
                scene.addItem(rock_graphics_item)
                self.apply_foreign_object_tint(rock_graphics_item) # Apply visual tint

                # Arrival animation for the rock
                opacity_anim = QtCore.QPropertyAnimation(rock_graphics_item, b"opacity")
                opacity_anim.setDuration(1200)
                opacity_anim.setStartValue(0.2)
                opacity_anim.setEndValue(1.0)
                opacity_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
            except Exception as e:
                if self.debug_mode: print(f"Multiplayer: Error creating stolen rock visuals: {e}")

        # Add memory to the local squid about the successful heist
        if hasattr(local_squid, 'memory_manager'):
            local_squid.memory_manager.add_short_term_memory(
                'achievement', 'rock_heist',
                f"Brought back {num_rocks} rocks from an adventure!", importance=8
            )


    def apply_foreign_object_tint(self, q_graphics_item: QtWidgets.QGraphicsPixmapItem):
        """Applies a visual tint (e.g., slight redness) to indicate an object is from a remote instance."""
        # Ensure item is a QGraphicsPixmapItem for safety, though hints help
        if not isinstance(q_graphics_item, QtWidgets.QGraphicsPixmapItem): return

        # Check if a colorize effect already exists, update it if so
        existing_effect = q_graphics_item.graphicsEffect()
        if isinstance(existing_effect, QtWidgets.QGraphicsColorizeEffect):
            existing_effect.setColor(QtGui.QColor(255, 120, 120, 200)) # Slightly transparent red
            existing_effect.setStrength(0.3) # Adjust strength
        else: # Apply new effect
            colorize_effect = QtWidgets.QGraphicsColorizeEffect()
            colorize_effect.setColor(QtGui.QColor(255, 120, 120, 200)) # Tint color (e.g., reddish)
            colorize_effect.setStrength(0.3)  # Intensity of the tint (0.0 to 1.0)
            q_graphics_item.setGraphicsEffect(colorize_effect)
        setattr(q_graphics_item, 'is_foreign', True) # Mark with a flag


    def show_network_dashboard(self):
        """Displays a dialog with detailed network status and peer information."""
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface') or not self.network_node:
            print("Multiplayer: Cannot show network dashboard - UI or NetworkNode missing.")
            return

        parent_window = self.tamagotchi_logic.user_interface.window
        dashboard_dialog = QtWidgets.QDialog(parent_window)
        dashboard_dialog.setWindowTitle("Multiplayer Network Dashboard")
        dashboard_dialog.setMinimumSize(550, 450)
        main_layout = QtWidgets.QVBoxLayout(dashboard_dialog)

        # --- Connection Info Section ---
        conn_info_group = QtWidgets.QGroupBox("My Connection")
        conn_info_form = QtWidgets.QFormLayout(conn_info_group)
        node_id_label = QtWidgets.QLabel(self.network_node.node_id)
        ip_label = QtWidgets.QLabel(self.network_node.local_ip)
        status_val_label = QtWidgets.QLabel() # Will be updated by refresh function
        conn_info_form.addRow("Node ID:", node_id_label)
        conn_info_form.addRow("Local IP:", ip_label)
        conn_info_form.addRow("Status:", status_val_label)
        main_layout.addWidget(conn_info_group)

        # --- Connected Peers Section ---
        peers_group = QtWidgets.QGroupBox("Detected Peers")
        peers_layout = QtWidgets.QVBoxLayout(peers_group)
        peers_table_widget = QtWidgets.QTableWidget()
        peers_table_widget.setColumnCount(4)
        peers_table_widget.setHorizontalHeaderLabels(["Node ID", "IP Address", "Last Seen", "Status"])
        peers_table_widget.horizontalHeader().setStretchLastSection(True)
        peers_table_widget.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers) # Read-only
        peers_table_widget.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        peers_layout.addWidget(peers_table_widget)
        main_layout.addWidget(peers_group)

        # --- Statistics Section (Example) ---
        stats_group = QtWidgets.QGroupBox("Network Statistics (Conceptual)")
        stats_form = QtWidgets.QFormLayout(stats_group)
        # These would need actual tracking in NetworkNode or this plugin
        stats_form.addRow("Messages Sent (Total):", QtWidgets.QLabel(str(getattr(self.network_node, 'total_sent_count', 'N/A'))))
        stats_form.addRow("Messages Received (Total):", QtWidgets.QLabel(str(getattr(self.network_node, 'total_received_count', 'N/A'))))
        main_layout.addWidget(stats_group)

        # --- Refresh and Update Logic ---
        def refresh_dashboard_data():
            # Update connection status
            is_connected = self.network_node.is_connected
            status_val_label.setText("Connected" if is_connected else "Disconnected")
            status_val_label.setStyleSheet("color: green; font-weight: bold;" if is_connected else "color: red; font-weight: bold;")

            # Update peers table
            peers_table_widget.setRowCount(0) # Clear table
            if self.network_node:
                for row, (node_id, (ip, last_seen, _)) in enumerate(self.network_node.known_nodes.items()):
                    peers_table_widget.insertRow(row)
                    peers_table_widget.setItem(row, 0, QtWidgets.QTableWidgetItem(node_id))
                    peers_table_widget.setItem(row, 1, QtWidgets.QTableWidgetItem(ip))
                    time_delta_secs = time.time() - last_seen
                    time_ago_str = f"{int(time_delta_secs)}s ago"
                    peers_table_widget.setItem(row, 2, QtWidgets.QTableWidgetItem(time_ago_str))
                    peer_status_str = "Active" if time_delta_secs < 20 else "Inactive" # 20s threshold for active
                    status_cell_item = QtWidgets.QTableWidgetItem(peer_status_str)
                    status_cell_item.setForeground(QtGui.QBrush(QtGui.QColor("green" if peer_status_str == "Active" else "gray")))
                    peers_table_widget.setItem(row, 3, status_cell_item)
            peers_table_widget.resizeColumnsToContents()
        
        refresh_dashboard_data() # Initial population

        # --- Buttons ---
        button_box = QtWidgets.QDialogButtonBox()
        refresh_btn = button_box.addButton("Refresh", QtWidgets.QDialogButtonBox.ActionRole)
        close_btn = button_box.addButton(QtWidgets.QDialogButtonBox.Close)
        refresh_btn.clicked.connect(refresh_dashboard_data)
        close_btn.clicked.connect(dashboard_dialog.accept)
        main_layout.addWidget(button_box)

        dashboard_dialog.exec_()


    def initialize_status_ui(self):
        """Initializes UI components for displaying multiplayer status (e.g., a dedicated widget or status bar integration)."""
        try:
            if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'):
                print("Multiplayer Warning: Status UI cannot be initialized - user_interface not found.")
                return

            ui = self.tamagotchi_logic.user_interface
            # Try to use a dedicated MultiplayerStatusWidget first
            try:
                from plugins.multiplayer.multiplayer_status_widget import MultiplayerStatusWidget
                # Ensure only one instance is created and managed
                if not hasattr(ui, '_mp_status_widget_instance_'):
                    ui._mp_status_widget_instance_ = MultiplayerStatusWidget(ui.window)
                    ui._mp_status_widget_instance_.move(
                        ui.window.width() - ui._mp_status_widget_instance_.width() - 15, 15 # Position top-right
                    )
                    ui._mp_status_widget_instance_.hide() # Hidden by default, shown when plugin enabled
                self.status_widget = ui._mp_status_widget_instance_

                # Pass necessary references or callbacks to the status widget
                if self.network_node and hasattr(self.status_widget, 'set_network_node_reference'):
                    self.status_widget.set_network_node_reference(self.network_node)

                print("Multiplayer: Dedicated status widget initialized.")
            except ImportError:
                print("Multiplayer: MultiplayerStatusWidget not found. Will attempt fallback status bar integration.")
                self.initialize_status_bar() # Fallback to main status bar
            except Exception as e_msw: # Catch errors during MultiplayerStatusWidget instantiation
                print(f"Multiplayer: Error initializing MultiplayerStatusWidget: {e_msw}. Using fallback.")
                self.initialize_status_bar()
        except Exception as e:
            print(f"Multiplayer Error: Could not initialize status UI: {e}")
            # traceback.print_exc()


    def _find_tamagotchi_logic(self, search_object, depth=0, visited_ids=None):
        """
        Recursively searches for an attribute named 'tamagotchi_logic' or an instance
        of TamagotchiLogic within a given object structure.
        Args:
            search_object: The object to start searching from.
            depth: Current recursion depth (to prevent infinite loops).
            visited_ids: A set of object IDs already visited in the current search path.
        Returns:
            The TamagotchiLogic instance if found, else None.
        """
        if visited_ids is None: visited_ids = set()
        if id(search_object) in visited_ids or depth > 6: # Max depth increased slightly
            return None
        visited_ids.add(id(search_object))

        # Direct check: Is the object itself TamagotchiLogic?
        if TamagotchiLogic and isinstance(search_object, TamagotchiLogic):
            return search_object
        # Direct check: Does it have a 'tamagotchi_logic' attribute that is an instance?
        if hasattr(search_object, 'tamagotchi_logic'):
            tl_attr = getattr(search_object, 'tamagotchi_logic')
            if TamagotchiLogic and isinstance(tl_attr, TamagotchiLogic):
                return tl_attr

        # Iterate through attributes for deeper search (carefully)
        try:
            for attr_name in dir(search_object):
                if attr_name.startswith('_'): continue # Skip private/special attributes

                try:
                    attr_value = getattr(search_object, attr_name)
                    # Avoid recursing into common non-game-logic types or already checked types
                    if attr_value is None or isinstance(attr_value, (int, str, bool, float, list, dict, set, tuple, bytes)):
                        continue
                    if inspect.ismodule(attr_value) or inspect.isbuiltin(attr_value) or inspect.isroutine(attr_value):
                        continue
                    # Avoid common Qt parent objects that might lead to deep UI tree recursion
                    if isinstance(attr_value, (QtWidgets.QWidget, QtCore.QObject)):
                         if depth > 2 and attr_name in ['parent', 'parentWidget', 'parentItem']: # Limit UI tree recursion
                            continue

                    found_logic = self._find_tamagotchi_logic(attr_value, depth + 1, visited_ids)
                    if found_logic: return found_logic
                except (AttributeError, RecursionError, TypeError, ReferenceError):
                    continue # Ignore errors getting or inspecting attributes
        except (RecursionError, TypeError, ReferenceError): # Errors during dir() or iteration
            pass
        return None


    def _animate_remote_squid_entry(self, squid_graphics_item, status_text_item, entry_direction_str):
        """Animates the visual entry of a remote squid (e.g., fade-in)."""
        if not squid_graphics_item: return

        # Opacity animation for the squid's visual
        squid_opacity_effect = QtWidgets.QGraphicsOpacityEffect(squid_graphics_item)
        squid_graphics_item.setGraphicsEffect(squid_opacity_effect)
        squid_fade_in_anim = QtCore.QPropertyAnimation(squid_opacity_effect, b"opacity")
        squid_fade_in_anim.setDuration(1200) # Duration of fade-in
        squid_fade_in_anim.setStartValue(0.1) # Start nearly transparent
        squid_fade_in_anim.setEndValue(self.REMOTE_SQUID_OPACITY) # Fade to standard remote opacity
        squid_fade_in_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)

        # Parallel animation group
        entry_animation_group = QtCore.QParallelAnimationGroup()
        entry_animation_group.addAnimation(squid_fade_in_anim)

        # Animate status text if provided
        if status_text_item:
            text_opacity_effect = QtWidgets.QGraphicsOpacityEffect(status_text_item)
            status_text_item.setGraphicsEffect(text_opacity_effect)
            text_fade_in_anim = QtCore.QPropertyAnimation(text_opacity_effect, b"opacity")
            text_fade_in_anim.setDuration(1200)
            text_fade_in_anim.setStartValue(0.1)
            text_fade_in_anim.setEndValue(1.0) # Text fully opaque
            text_fade_in_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
            entry_animation_group.addAnimation(text_fade_in_anim)

        entry_animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped) # Auto-delete on finish


    def get_opposite_direction(self, direction_str: str) -> str:
        """Returns the opposite of a given cardinal direction string."""
        opposites = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}
        return opposites.get(direction_str.lower(), 'right') # Default if direction is unknown


    def create_entry_effect(self, center_x: float, center_y: float, direction_str: str = ""):
        """Creates a visual effect (e.g., ripple) at the point where a remote squid enters the scene."""
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene

        # Expanding ripple effect
        ripple_item = QtWidgets.QGraphicsEllipseItem(center_x - 5, center_y - 5, 10, 10) # Start small
        ripple_item.setPen(QtGui.QPen(QtGui.QColor(135, 206, 250, 180), 2)) # Light sky blue, semi-transparent
        ripple_item.setBrush(QtGui.QBrush(QtGui.QColor(135, 206, 250, 100)))
        ripple_item.setZValue(95) # High Z-order, but potentially below entry text
        scene.addItem(ripple_item)

        ripple_opacity_effect = QtWidgets.QGraphicsOpacityEffect(ripple_item)
        ripple_item.setGraphicsEffect(ripple_opacity_effect)

        ripple_anim_group = QtCore.QParallelAnimationGroup()
        # Size animation (expanding outwards)
        size_animation = QtCore.QPropertyAnimation(ripple_item, b"rect")
        size_animation.setDuration(1000) # 1 second duration
        size_animation.setStartValue(QtCore.QRectF(center_x - 5, center_y - 5, 10, 10))
        size_animation.setEndValue(QtCore.QRectF(center_x - 60, center_y - 60, 120, 120)) # Expands to 120x120
        size_animation.setEasingCurve(QtCore.QEasingCurve.OutExpo) # Expo easing for a quick burst
        # Opacity animation (fading out)
        opacity_animation = QtCore.QPropertyAnimation(ripple_opacity_effect, b"opacity")
        opacity_animation.setDuration(1000)
        opacity_animation.setStartValue(0.8)
        opacity_animation.setEndValue(0.0)
        opacity_animation.setEasingCurve(QtCore.QEasingCurve.OutExpo)

        ripple_anim_group.addAnimation(size_animation)
        ripple_anim_group.addAnimation(opacity_animation)
        # Cleanup ripple item after animation finishes
        ripple_anim_group.finished.connect(lambda: scene.removeItem(ripple_item) if ripple_item in scene.items() else None)
        ripple_anim_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

        # "NEW ARRIVAL" text effect
        arrival_text_str = "✨ New Visitor! ✨"
        arrival_text_item = scene.addText(arrival_text_str)
        arrival_font = QtGui.QFont("Arial", 12, QtGui.QFont.Bold)
        arrival_text_item.setFont(arrival_font)
        text_metrics = QtGui.QFontMetrics(arrival_font)
        text_rect = text_metrics.boundingRect(arrival_text_str)
        arrival_text_item.setDefaultTextColor(QtGui.QColor(255, 215, 0)) # Gold color
        arrival_text_item.setPos(center_x - text_rect.width() / 2, center_y - 80) # Position above entry point
        arrival_text_item.setZValue(100) # On top of other effects

        text_opacity_effect = QtWidgets.QGraphicsOpacityEffect(arrival_text_item)
        arrival_text_item.setGraphicsEffect(text_opacity_effect)
        text_fade_anim = QtCore.QPropertyAnimation(text_opacity_effect, b"opacity")
        text_fade_anim.setDuration(3500) # Text visible for 3.5 seconds
        text_fade_anim.setStartValue(0.0) # Fade in
        text_fade_anim.setKeyValueAt(0.2, 1.0)  # Fully visible after 20% of duration
        text_fade_anim.setKeyValueAt(0.8, 1.0)  # Stay visible
        text_fade_anim.setEndValue(0.0)      # Fade out
        text_fade_anim.finished.connect(lambda: scene.removeItem(arrival_text_item) if arrival_text_item in scene.items() else None)
        text_fade_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)


    def _setup_controller_immediately(self, node_id: str, squid_initial_data: Dict):
        """
        Creates and initializes a RemoteSquidController for a newly arrived remote squid.
        Ensures the controller update timer is running.
        """
        try:
            # Dynamically import the controller to avoid hard dependency if module is missing
            from plugins.multiplayer.squid_multiplayer_autopilot import RemoteSquidController
        except ImportError:
            if self.debug_mode: print("Multiplayer Error: RemoteSquidController module not found. Remote squids will not be autonomous.")
            return # Cannot create controller

        if node_id in self.remote_squid_controllers: # Avoid duplicate controllers
            if self.debug_mode: print(f"Multiplayer: Controller for squid {node_id[-6:]} already exists. Updating its data.")
            self.remote_squid_controllers[node_id].squid_data.update(squid_initial_data)
            return

        if self.debug_mode: print(f"Multiplayer: Creating autopilot controller for remote squid {node_id[-6:]}.")
        try:
            controller_instance = RemoteSquidController(
                squid_data=squid_initial_data, # Initial state (x, y, direction, etc.)
                scene=self.tamagotchi_logic.user_interface.scene, # Reference to the game scene
                plugin_instance=self, # Pass this MultiplayerPlugin instance for callbacks (e.g., on return)
                debug_mode=self.debug_mode
            )
            self.remote_squid_controllers[node_id] = controller_instance
            if self.debug_mode: print(f"Multiplayer: Controller for {node_id[-6:]} created. Initial state: {getattr(controller_instance, 'state', 'N/A')}")
        except Exception as e_create:
            print(f"Multiplayer Error: Failed to create RemoteSquidController for {node_id[-6:]}: {e_create}")
            # traceback.print_exc() # For detailed debugging
            return

        # Ensure the main controller update timer is active
        if self.controller_update_timer and not self.controller_update_timer.isActive():
            self.controller_update_timer.start() # Restart if stopped for some reason
            if self.debug_mode: print("Multiplayer: Restarted controller update timer.")


    def handle_squid_exit_message(self, node: NetworkNode, message: Dict, addr: tuple):
        """
        Handles a 'squid_exit' message, indicating a squid from another instance
        has exited its screen and may enter this one.
        """
        try:
            if self.debug_mode: print(f"Multiplayer: Received squid_exit message from {message.get('node_id', 'UnknownNode')}.")
            exit_payload = message.get('payload', {}) # The actual data sent by the exiting squid's instance

            # Validate essential data from the payload
            required_fields = ['node_id', 'direction', 'position', 'color'] # 'position' should be a dict {'x':val, 'y':val}
            if not all(field in exit_payload for field in required_fields):
                if self.debug_mode: print(f"Multiplayer: Squid_exit message missing required fields. Data: {exit_payload}")
                return False

            source_node_id = exit_payload['node_id']
            # Prevent processing an exit message from our own node if it somehow looped back
            if self.network_node and source_node_id == self.network_node.node_id:
                if self.debug_mode: print("Multiplayer: Ignoring self-originated squid_exit message.")
                return False

            # Determine entry coordinates and facing direction for the arriving squid
            exit_direction_from_remote = exit_payload['direction'] # e.g., 'left' (exited left edge of their screen)
            remote_pos_at_exit = exit_payload['position'] # {'x': ..., 'y': ...} on their screen
            
            # Get current local window dimensions
            if not self.tamagotchi_logic or not self.tamagotchi_logic.user_interface: return False
            local_window_width = self.tamagotchi_logic.user_interface.window_width
            local_window_height = self.tamagotchi_logic.user_interface.window_height
            entry_margin = 80 # How far from the edge the squid should appear

            entry_x, entry_y = 0.0, 0.0
            entry_facing_direction = "" # Direction the squid should be facing upon entry here

            # Logic based on how the remote squid exited *its* screen
            if exit_direction_from_remote == 'left': # Exited their left, enters our right
                entry_x = local_window_width - entry_margin
                entry_y = remote_pos_at_exit.get('y', local_window_height / 2)
                entry_facing_direction = 'left' # Enters from right, looking left
            elif exit_direction_from_remote == 'right': # Exited their right, enters our left
                entry_x = entry_margin
                entry_y = remote_pos_at_exit.get('y', local_window_height / 2)
                entry_facing_direction = 'right' # Enters from left, looking right
            elif exit_direction_from_remote == 'up': # Exited their top, enters our bottom
                entry_x = remote_pos_at_exit.get('x', local_window_width / 2)
                entry_y = local_window_height - entry_margin
                entry_facing_direction = 'up' # Enters from bottom, looking up
            elif exit_direction_from_remote == 'down': # Exited their bottom, enters our top
                entry_x = remote_pos_at_exit.get('x', local_window_width / 2)
                entry_y = entry_margin
                entry_facing_direction = 'down' # Enters from top, looking down
            else:
                if self.debug_mode: print(f"Multiplayer: Unknown exit direction '{exit_direction_from_remote}' in squid_exit message.")
                return False

            # Clamp entry coordinates to be within visible bounds (plus margin)
            entry_y = max(entry_margin, min(entry_y, local_window_height - entry_margin))
            entry_x = max(entry_margin, min(entry_x, local_window_width - entry_margin))

            # Prepare data for the new remote squid
            arriving_squid_data = {
                'x': entry_x, 'y': entry_y, 'direction': entry_facing_direction,
                'color': exit_payload['color'], 'status': 'ARRIVING', # Initial status
                'view_cone_visible': exit_payload.get('view_cone_visible', False), # Carry over view cone state
                'carrying_rock': exit_payload.get('carrying_rock', False), # Carry over rock state
                'hunger': exit_payload.get('hunger', 50), 'happiness': exit_payload.get('happiness', 50),
                'is_sleeping': exit_payload.get('is_sleeping', False),
                'entry_time': time.time(), # Timestamp of arrival
                'home_direction': self.get_opposite_direction(exit_direction_from_remote) # Direction to go to return to its "home" screen
            }

            # Create visual entry effect at the arrival point
            self.create_entry_effect(entry_x, entry_y, entry_facing_direction)
            # Create or update the visual representation of the remote squid
            update_success = self.update_remote_squid(source_node_id, arriving_squid_data, is_new_arrival=True, high_visibility=True)
            if self.debug_mode: print(f"Multiplayer: Remote squid {source_node_id[-6:]} visual created/updated at ({entry_x:.1f}, {entry_y:.1f}). Success: {update_success}")

            # Immediately set up its controller for autonomous behavior
            if update_success:
                self._setup_controller_immediately(source_node_id, arriving_squid_data)

            if hasattr(self.tamagotchi_logic, 'show_message'):
                self.tamagotchi_logic.show_message(
                    f"👋 A visitor squid ({source_node_id[-6:]}) is arriving from the {exit_direction_from_remote} side!"
                )
            return True
        except Exception as e:
            print(f"Multiplayer CRITICAL ERROR in handle_squid_exit_message: {e}")
            traceback.print_exc()
            return False


    def _setup_controller_creation_timer(self):
        """(Fallback) Sets up a QTimer to periodically process any pending remote squid controller creations."""
        if self.controller_creation_timer and self.controller_creation_timer.isActive():
            return # Timer already running
        if not self.controller_creation_timer:
            self.controller_creation_timer = QtCore.QTimer()
            self.controller_creation_timer.timeout.connect(self._process_pending_controller_creations)
        self.controller_creation_timer.start(300) # Check every 300ms
        if self.debug_mode: print("Multiplayer: Fallback controller creation timer started.")


    def _process_pending_controller_creations(self):
        """(Fallback) Processes a list of remote squids waiting for their controllers to be created."""
        if not hasattr(self, 'pending_controller_creations') or not self.pending_controller_creations:
            return

        # Process all pending items in this call
        items_to_process = list(self.pending_controller_creations) # Iterate on a copy
        self.pending_controller_creations.clear() # Clear original list

        for creation_task in items_to_process:
            node_id = creation_task.get('node_id')
            squid_data = creation_task.get('squid_data')
            if not node_id or not squid_data: continue

            # Attempt to create controller if not already existing (double check)
            if node_id not in self.remote_squid_controllers:
                if self.debug_mode: print(f"Multiplayer (Fallback): Creating controller for squid {node_id[-6:]}.")
                self._setup_controller_immediately(node_id, squid_data) # Use the immediate setup method
            elif self.debug_mode: # Controller was created by another path
                print(f"Multiplayer (Fallback): Controller for {node_id[-6:]} already exists, skipping duplicate creation.")


    def update_remote_controllers(self):
        """Called by a QTimer to update all active RemoteSquidController instances."""
        if not hasattr(self, 'remote_squid_controllers') or not self.remote_squid_controllers:
            return

        current_time = time.time()
        delta_time = current_time - self.last_controller_update
        if delta_time <= 0.001: return # Avoid updates with too small or zero delta_time
        self.last_controller_update = current_time

        # Iterate over a copy of controller items in case the dictionary is modified during update (e.g., squid returns home)
        for node_id, controller in list(self.remote_squid_controllers.items()):
            try:
                controller.update(delta_time) # Let the controller update its squid's state
                updated_squid_data = controller.squid_data # Get the latest data from the controller

                # Update the visual representation of the remote squid
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
                        # Only update text if it actually changed to avoid flicker, unless it's a special status
                        if current_status_on_display.upper() != new_status_from_controller.upper() or \
                           new_status_from_controller.upper() in ["ARRIVING", "ENTERING", "RETURNING..."]:
                            status_text.setPlainText(new_status_from_controller)
                        status_text.setPos(updated_squid_data['x'], updated_squid_data['y'] - 35) # Adjust Y offset
                    
                    # Update view cone based on controller's data if it's managed
                    if updated_squid_data.get('view_cone_visible', False):
                        self.update_remote_view_cone(node_id, updated_squid_data)
                    elif remote_squid_display.get('view_cone'): # Remove if not visible
                         if self.tamagotchi_logic and hasattr(self.tamagotchi_logic.user_interface, 'scene'):
                            cone = remote_squid_display['view_cone']
                            if cone in self.tamagotchi_logic.user_interface.scene.items():
                                self.tamagotchi_logic.user_interface.scene.removeItem(cone)
                            remote_squid_display['view_cone'] = None

                else: # Visual for this remote squid is gone, but controller still exists
                    if self.debug_mode: print(f"Multiplayer: Visual for remote squid {node_id[-6:]} missing. Removing its controller.")
                    del self.remote_squid_controllers[node_id] # Clean up orphaned controller
            except Exception as e:
                print(f"Multiplayer Error: Updating controller for {node_id[-6:]} failed: {e}")
                # traceback.print_exc() # For detailed debugging; can be very verbose


    def calculate_entry_position(self, entry_side_direction: str) -> tuple:
        """
        Calculates the X,Y coordinates for a squid entering *this* local screen
        based on the side it's coming from.
        Args:
            entry_side_direction: 'left', 'right', 'up', or 'down' indicating the edge it enters from.
        Returns:
            A tuple (x, y) for the entry position.
        """
        if not self.tamagotchi_logic or not self.tamagotchi_logic.user_interface:
            return (100, 100) # Default fallback if UI info is unavailable

        window_w = self.tamagotchi_logic.user_interface.window_width
        window_h = self.tamagotchi_logic.user_interface.window_height
        margin = 70 # How far inside the edge the squid appears

        if entry_side_direction == 'left':   return (margin, window_h / 2)
        elif entry_side_direction == 'right':return (window_w - margin, window_h / 2)
        elif entry_side_direction == 'up':   return (window_w / 2, margin)
        elif entry_side_direction == 'down': return (window_w / 2, window_h - margin)
        # Default to center if direction is unknown
        return (window_w / 2, window_h / 2)


    def apply_remote_experiences(self, local_squid, activity_summary: Dict):
        """
        Applies the summarized experiences (food eaten, rocks played with, etc.)
        from a remote journey to the local squid upon its return.
        """
        if not local_squid or not activity_summary: return

        food_eaten = activity_summary.get('food_eaten', 0)
        rocks_interacted = activity_summary.get('rock_interactions', 0)
        rocks_brought_back = activity_summary.get('rocks_stolen', 0) # "Stolen" from remote tank's view
        time_away_seconds = activity_summary.get('time_away', 0)
        time_str = f"{int(time_away_seconds/60)}m {int(time_away_seconds%60)}s"
        journey_desc = f"Returned from a {time_str} journey to another tank. "

        if hasattr(local_squid, 'memory_manager'):
            mm = local_squid.memory_manager
            if food_eaten > 0:
                journey_desc += f"Ate {food_eaten} snacks there. "
                local_squid.hunger = max(0, local_squid.hunger - 10 * food_eaten) # Reduce hunger
                mm.add_short_term_memory('travel', 'ate_on_trip', f"Found {food_eaten} yummy treats on my trip!", 5)
            if rocks_interacted > 0:
                journey_desc += f"Played with {rocks_interacted} interesting rocks. "
                local_squid.happiness = min(100, local_squid.happiness + 3 * rocks_interacted) # Increase happiness
                mm.add_short_term_memory('travel', 'played_on_trip', f"Played with {rocks_interacted} cool rocks elsewhere!", 4)
            # Rocks brought back are handled by create_stolen_rocks and its memory entry.

            # Overall journey memory
            mm.add_short_term_memory('travel', 'completed_journey', journey_desc, importance=7)

            # Emotional memory based on experience
            if food_eaten > 1 or rocks_interacted > 3 or rocks_brought_back > 0:
                mm.add_short_term_memory('emotion', 'happy_return', "It's great to be back home after an exciting adventure!", 6)
            else:
                mm.add_short_term_memory('emotion', 'calm_return', "Returned home. It was a quiet trip.", 3)

        # Satisfy some curiosity from exploring
        if hasattr(local_squid, 'curiosity'):
            local_squid.curiosity = max(0, local_squid.curiosity - 25)


    def create_exit_effect(self, center_x: float, center_y: float, direction_str: str = ""):
        """Creates a visual effect (e.g., ripple) when a local squid exits the screen to travel."""
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene

        # Imploding or shrinking ripple for exit
        ripple_item = QtWidgets.QGraphicsEllipseItem(center_x - 40, center_y - 40, 80, 80) # Start larger
        ripple_item.setPen(QtGui.QPen(QtGui.QColor(255, 100, 100, 150), 2)) # Reddish for exit
        ripple_item.setBrush(QtGui.QBrush(QtGui.QColor(255, 100, 100, 80)))
        ripple_item.setZValue(90)
        scene.addItem(ripple_item)

        ripple_opacity_effect = QtWidgets.QGraphicsOpacityEffect(ripple_item)
        ripple_item.setGraphicsEffect(ripple_opacity_effect)

        exit_anim_group = QtCore.QParallelAnimationGroup()
        # Size animation (shrinking inwards)
        size_animation = QtCore.QPropertyAnimation(ripple_item, b"rect")
        size_animation.setDuration(800)
        size_animation.setStartValue(QtCore.QRectF(center_x - 40, center_y - 40, 80, 80))
        size_animation.setEndValue(QtCore.QRectF(center_x - 5, center_y - 5, 10, 10)) # Shrinks to small
        size_animation.setEasingCurve(QtCore.QEasingCurve.InExpo)
        # Opacity animation (fading out as it shrinks)
        opacity_animation = QtCore.QPropertyAnimation(ripple_opacity_effect, b"opacity")
        opacity_animation.setDuration(800)
        opacity_animation.setStartValue(0.7)
        opacity_animation.setEndValue(0.0)
        opacity_animation.setEasingCurve(QtCore.QEasingCurve.InExpo)

        exit_anim_group.addAnimation(size_animation)
        exit_anim_group.addAnimation(opacity_animation)
        exit_anim_group.finished.connect(lambda: scene.removeItem(ripple_item) if ripple_item in scene.items() else None)
        exit_anim_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

        # "Safe Travels!" text
        travel_text_str = "🚀 Off to explore! 🚀"
        travel_text_item = scene.addText(travel_text_str)
        travel_font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
        travel_text_item.setFont(travel_font)
        text_metrics = QtGui.QFontMetrics(travel_font)
        text_rect = text_metrics.boundingRect(travel_text_str)
        travel_text_item.setDefaultTextColor(QtGui.QColor(173, 216, 230)) # Light Blue
        travel_text_item.setPos(center_x - text_rect.width() / 2, center_y + 30) # Position below exit point
        travel_text_item.setZValue(100)

        text_opacity_effect_exit = QtWidgets.QGraphicsOpacityEffect(travel_text_item)
        travel_text_item.setGraphicsEffect(text_opacity_effect_exit)
        text_fade_anim_exit = QtCore.QPropertyAnimation(text_opacity_effect_exit, b"opacity")
        text_fade_anim_exit.setDuration(2500)
        text_fade_anim_exit.setStartValue(1.0) # Start visible
        text_fade_anim_exit.setEndValue(0.0)      # Fade out
        text_fade_anim_exit.finished.connect(lambda: scene.removeItem(travel_text_item) if travel_text_item in scene.items() else None)
        text_fade_anim_exit.start(QtCore.QAbstractAnimation.DeleteWhenStopped)


    def handle_squid_return(self, node: NetworkNode, message: Dict, addr: tuple):
        """
        Handles a 'squid_return' message, indicating the player's own squid
        has returned from an adventure in another player's tank.
        """
        try:
            return_payload = message.get('payload', {})
            returning_node_id = return_payload.get('node_id')

            # This message is specifically for OUR squid returning. Validate its node_id.
            if not self.network_node or returning_node_id != self.network_node.node_id:
                if self.debug_mode:
                    expected_id = self.network_node.node_id if self.network_node else "N/A"
                    print(f"Multiplayer: Squid_return message ignored. Expected node '{expected_id}', got '{returning_node_id}'.")
                return

            local_squid = self.tamagotchi_logic.squid
            if not local_squid or not local_squid.squid_item: # Ensure local squid and its visual item exist
                if self.debug_mode: print("Multiplayer: Local squid or its visual item not found for return.")
                return

            activity_summary = return_payload.get('activity_summary', {})
            # This direction indicates the side of OUR screen the squid should enter from.
            entry_side = return_payload.get('return_direction', 'left') # Default entry from left
            entry_coords = self.calculate_entry_position(entry_side)

            # Make the squid visible and position it
            local_squid.squid_x, local_squid.squid_y = entry_coords[0], entry_coords[1]
            local_squid.squid_item.setPos(local_squid.squid_x, local_squid.squid_y)
            local_squid.squid_item.setVisible(True)

            # Smooth fade-in animation for reappearance
            squid_opacity_effect = QtWidgets.QGraphicsOpacityEffect(local_squid.squid_item)
            local_squid.squid_item.setGraphicsEffect(squid_opacity_effect)
            fade_in_animation = QtCore.QPropertyAnimation(squid_opacity_effect, b"opacity")
            fade_in_animation.setDuration(1500) # Gentle fade-in
            fade_in_animation.setStartValue(0.0) # Start fully transparent
            fade_in_animation.setEndValue(1.0)   # End fully opaque
            fade_in_animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

            # Apply effects of the journey (stats, memories)
            self.apply_remote_experiences(local_squid, activity_summary)

            # Create any "stolen" rocks if applicable
            num_stolen_rocks = activity_summary.get('rocks_stolen', 0)
            if num_stolen_rocks > 0:
                self.create_stolen_rocks(local_squid, num_stolen_rocks, entry_coords)
                if hasattr(self.tamagotchi_logic, 'show_message'):
                    self.tamagotchi_logic.show_message(f"🎉 Your squid returned with {num_stolen_rocks} souvenir rocks!")
            else: # Standard welcome back message
                if hasattr(self.tamagotchi_logic, 'show_message'):
                    journey_time_sec = activity_summary.get('time_away', 0)
                    time_str = f"{int(journey_time_sec/60)}m {int(journey_time_sec%60)}s"
                    self.tamagotchi_logic.show_message(f"🦑 Welcome back! Your squid explored for {time_str}.")

            # Reset squid's state flags
            local_squid.can_move = True
            if hasattr(local_squid, 'is_transitioning'): local_squid.is_transitioning = False
            local_squid.status = "just returned home" # Update status
            if self.debug_mode: print(f"Multiplayer: Local squid '{local_squid.name if hasattr(local_squid,'name') else ''}' returned to position {entry_coords} from {entry_side}.")

        except Exception as e:
            print(f"Multiplayer Error: Handling local squid's return failed: {e}")
            traceback.print_exc()


    def _create_arrival_animation(self, graphics_item: QtWidgets.QGraphicsPixmapItem):
        """Creates a simple, gentle fade-in animation for newly arrived remote items (squids or objects)."""
        if not graphics_item: return
        try:
            opacity_effect = QtWidgets.QGraphicsOpacityEffect(graphics_item)
            graphics_item.setGraphicsEffect(opacity_effect) # Apply effect to the item

            fade_in_anim = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
            fade_in_anim.setDuration(1000) # 1 second fade-in
            fade_in_anim.setStartValue(0.2) # Start slightly visible
            # Target opacity depends on item type (squid vs object)
            target_opacity = self.REMOTE_SQUID_OPACITY
            if hasattr(graphics_item, 'is_remote_clone') and getattr(graphics_item, 'is_remote_clone'): # If it's a cloned object
                target_opacity *= 0.75 # Make cloned objects a bit more transparent than remote squids

            fade_in_anim.setEndValue(target_opacity)
            fade_in_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic) # Smooth easing
            fade_in_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped) # Auto-cleanup animation

            # For remote squids, a timer might reset their style after a brief "highlighted" entry.
            # This simple animation is just for the fade-in.
        except Exception as e:
            if self.debug_mode: print(f"Multiplayer: Simple arrival animation error: {e}")
            if graphics_item: graphics_item.setOpacity(self.REMOTE_SQUID_OPACITY) # Fallback: just set opacity


    def _reset_remote_squid_style(self, node_id_or_item):
        """Resets the visual style of a remote squid (e.g., after a temporary highlight animation)."""
        node_id = None
        squid_display_data = None

        if isinstance(node_id_or_item, str): # If node_id is passed
            node_id = node_id_or_item
            squid_display_data = self.remote_squids.get(node_id)
        elif isinstance(node_id_or_item, QtWidgets.QGraphicsPixmapItem): # If visual item is passed
            for nid, s_data in self.remote_squids.items():
                if s_data.get('visual') == node_id_or_item:
                    node_id = nid
                    squid_display_data = s_data
                    break
        if not squid_display_data: return # Squid not found or data incomplete

        visual_item = squid_display_data.get('visual')
        status_text_item = squid_display_data.get('status_text')
        id_text_item = squid_display_data.get('id_text')

        # Reset visual properties to standard remote squid appearance
        if visual_item:
            visual_item.setZValue(5) # Standard Z-order for remote squids
            visual_item.setOpacity(self.REMOTE_SQUID_OPACITY)
            # Remove any temporary graphics effects (like glows) if they were added for entry
            if visual_item.graphicsEffect() and isinstance(visual_item.graphicsEffect(), QtWidgets.QGraphicsDropShadowEffect):
                visual_item.setGraphicsEffect(None)

        # Reset status text style
        if status_text_item:
            current_status_from_data = squid_display_data.get('data', {}).get('status', 'visiting')
            status_text_item.setPlainText(current_status_from_data)
            status_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200, 220)) # Standard remote text color
            status_text_item.setFont(QtGui.QFont("Arial", 9)) # Standard remote text font
            status_text_item.setZValue(6)

        # Reset ID text style
        if id_text_item:
            id_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200, 180))
            id_text_item.setFont(QtGui.QFont("Arial", 8))
            id_text_item.setZValue(6)


    def register_menu_actions(self, main_ui_window: QtWidgets.QMainWindow, target_menu: QtWidgets.QMenu):
        """Registers menu actions related to the multiplayer plugin in the application's menu."""
        # --- About Action ---
        about_action = QtWidgets.QAction(f"About {mp_constants.PLUGIN_NAME}...", main_ui_window)
        about_action.triggered.connect(self.show_about_dialog)
        target_menu.addAction(about_action)

        # --- Configuration Action ---
        config_action = QtWidgets.QAction("Network Settings...", main_ui_window)
        config_action.triggered.connect(self.show_config_dialog)
        target_menu.addAction(config_action)

        # --- Network Dashboard Action ---
        dashboard_action = QtWidgets.QAction("Network Dashboard...", main_ui_window)
        dashboard_action.triggered.connect(self.show_network_dashboard)
        target_menu.addAction(dashboard_action)

        target_menu.addSeparator()

        # --- Refresh Connections Action ---
        refresh_connections_action = QtWidgets.QAction("Refresh Connections", main_ui_window)
        refresh_connections_action.triggered.connect(self.refresh_connections)
        target_menu.addAction(refresh_connections_action)

        # --- Toggle Connection Lines Action ---
        # Store action to update its checked state later
        self.mp_menu_toggle_connection_lines_action = QtWidgets.QAction("Show Connection Lines", main_ui_window)
        self.mp_menu_toggle_connection_lines_action.setCheckable(True)
        self.mp_menu_toggle_connection_lines_action.setChecked(self.SHOW_CONNECTION_LINES) # Use instance variable
        self.mp_menu_toggle_connection_lines_action.triggered.connect(self.toggle_connection_lines) # Pass boolean state
        target_menu.addAction(self.mp_menu_toggle_connection_lines_action)

        # --- Debug Actions (only if debug mode is enabled) ---
        if self.debug_mode:
            target_menu.addSeparator()
            debug_autopilot_action = QtWidgets.QAction("Debug Autopilot Status", main_ui_window)
            debug_autopilot_action.triggered.connect(self.debug_autopilot_status)
            target_menu.addAction(debug_autopilot_action)


    def update_menu_states(self):
        """Called when the menu is about to be shown, to update the state of checkable items."""
        if hasattr(self, 'mp_menu_toggle_connection_lines_action'):
            self.mp_menu_toggle_connection_lines_action.setChecked(self.SHOW_CONNECTION_LINES)


    def show_about_dialog(self):
        """Displays an 'About' dialog with information about the multiplayer plugin."""
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
        try:
            # Dynamically import the config dialog to avoid issues if the file is missing
            # Assumes multiplayer_config_dialog.py is in the same directory or a 'plugins/multiplayer/' subdirectory
            from .multiplayer_config_dialog import MultiplayerConfigDialog
        except ImportError:
            print("Multiplayer Error: MultiplayerConfigDialog class/file not found.")
            parent_win = self.tamagotchi_logic.user_interface.window if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface') else None
            QtWidgets.QMessageBox.critical(parent_win, "Configuration Error", "The multiplayer settings dialog could not be loaded.")
            return

        parent_window = None
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
            parent_window = self.tamagotchi_logic.user_interface.window

        # Create or reuse the config dialog instance
        # Pass current plugin settings to the dialog. The dialog should have methods to update these on the plugin.
        if not self.config_dialog or not self.config_dialog.isVisible(): # Create new if first time or closed
            self.config_dialog = MultiplayerConfigDialog(
                plugin_instance=self, # Pass the plugin instance for callbacks/updates
                parent=parent_window,
                initial_settings={ # Pass current settings from the plugin instance
                    'multicast_group': self.MULTICAST_GROUP,
                    'port': self.MULTICAST_PORT,
                    'sync_interval': self.SYNC_INTERVAL,
                    'remote_opacity': self.REMOTE_SQUID_OPACITY,
                    'show_labels': self.SHOW_REMOTE_LABELS,
                    'show_connections': self.SHOW_CONNECTION_LINES,
                    'debug_mode': self.debug_mode,
                    'auto_reconnect': self.network_node.auto_reconnect if self.network_node else True,
                    'use_compression': self.network_node.use_compression if self.network_node else True
                }
            )
        else: # If dialog already exists, update its fields before showing
            self.config_dialog.load_settings({
                    'multicast_group': self.MULTICAST_GROUP,
                    'port': self.MULTICAST_PORT,
                    'sync_interval': self.SYNC_INTERVAL,
                    'remote_opacity': self.REMOTE_SQUID_OPACITY,
                    'show_labels': self.SHOW_REMOTE_LABELS,
                    'show_connections': self.SHOW_CONNECTION_LINES,
                    'debug_mode': self.debug_mode,
                    'auto_reconnect': self.network_node.auto_reconnect if self.network_node else True,
                    'use_compression': self.network_node.use_compression if self.network_node else True
                })

        self.config_dialog.exec_() # Show as a modal dialog
        # After the dialog closes (OK/Apply), the dialog itself should have updated the plugin's settings


    def toggle_connection_lines(self, checked_state: bool):
        """Toggles the visibility of connection lines based on menu action."""
        self.SHOW_CONNECTION_LINES = checked_state # Update instance variable

        # Immediately update visual state of existing lines
        if hasattr(self.tamagotchi_logic, 'user_interface') and self.tamagotchi_logic.user_interface:
            scene = self.tamagotchi_logic.user_interface.scene
            for line_item in self.connection_lines.values():
                if line_item in scene.items(): # Ensure item is still valid
                    line_item.setVisible(self.SHOW_CONNECTION_LINES)

            # If lines are being disabled, remove them all now.
            # If enabling, update_connection_lines() will recreate them on its next cycle.
            if not self.SHOW_CONNECTION_LINES:
                for node_id_key in list(self.connection_lines.keys()): # Iterate on copy
                    line_to_remove = self.connection_lines.pop(node_id_key)
                    if line_to_remove in scene.items():
                        scene.removeItem(line_to_remove)

        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(f"Connection lines to remote squids {'shown' if checked_state else 'hidden'}.")


    def refresh_connections(self):
        """Manually triggers a network presence announcement (heartbeat) and attempts to reconnect if needed."""
        if not self.network_node:
            if hasattr(self.tamagotchi_logic, 'show_message'):
                self.tamagotchi_logic.show_message("Multiplayer: Network component not initialized. Cannot refresh.")
            return

        # Attempt to reconnect if not currently connected
        if not self.network_node.is_connected:
            if self.debug_mode: print("Multiplayer: Attempting to reconnect before refresh...")
            self.network_node.try_reconnect() # This attempts to re-establish the socket

        # Send a heartbeat to announce presence, regardless of current visual peer count
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
        elif self.debug_mode:
            print(message_to_show)

        # Update UI status immediately
        current_peers_count = len(self.network_node.known_nodes)
        if self.status_widget:
            self.status_widget.update_peers(self.network_node.known_nodes)
            self.status_widget.add_activity(f"Connections refreshed. {current_peers_count} peers currently detected.")
        elif self.status_bar: # Fallback
            self.status_bar.update_peers_count(current_peers_count)
            if hasattr(self.status_bar, 'add_message'):
                 self.status_bar.add_message(f"Refreshed. {current_peers_count} peers.")


    def initialize_remote_representation(self):
        """(Fallback) Initializes basic timers for managing remote entity visuals if a dedicated manager isn't used."""
        # This is for basic cleanup of stale nodes and updating connection lines periodically.
        if not self.cleanup_timer_basic:
            self.cleanup_timer_basic = QtCore.QTimer()
            self.cleanup_timer_basic.timeout.connect(self.cleanup_stale_nodes)
            self.cleanup_timer_basic.start(7500)  # Check for stale nodes every 7.5 seconds

        if not self.connection_timer_basic:
            self.connection_timer_basic = QtCore.QTimer()
            self.connection_timer_basic.timeout.connect(self.update_connection_lines)
            self.connection_timer_basic.start(1200)  # Update connection lines every 1.2 seconds


    def cleanup_stale_nodes(self):
        """(Fallback) Removes visual representations of remote nodes that haven't sent updates recently."""
        if not self.network_node: return
        current_time = time.time()
        # More generous threshold for basic cleanup, as sync might be less frequent.
        # Active remote squid controllers might have their own timeout logic.
        stale_threshold_seconds = 45.0
        nodes_to_remove_ids = []

        # Check NetworkNode's list of known peers
        for node_id, (_, last_seen_time, _) in list(self.network_node.known_nodes.items()): # Iterate copy
            if current_time - last_seen_time > stale_threshold_seconds:
                nodes_to_remove_ids.append(node_id)

        for node_id_to_remove in nodes_to_remove_ids:
            if self.debug_mode: print(f"Multiplayer (Basic Cleanup): Node {node_id_to_remove[-6:]} timed out. Removing.")
            # Remove from NetworkNode's known list
            if node_id_to_remove in self.network_node.known_nodes:
                del self.network_node.known_nodes[node_id_to_remove]
            # Remove visual representation and controller
            self.remove_remote_squid(node_id_to_remove) # Handles visuals
            if node_id_to_remove in self.remote_squid_controllers:
                del self.remote_squid_controllers[node_id_to_remove] # Remove associated controller

        # Update peer count in UI
        if self.network_node: # Recheck as it might become None during complex shutdown
            peers_now = self.network_node.known_nodes if self.network_node else {}
            if self.status_widget: self.status_widget.update_peers(peers_now)
            elif self.status_bar: self.status_bar.update_peers_count(len(peers_now))


    def update_connection_lines(self):
        """(Fallback) Updates visual lines connecting the local squid to visible remote squids."""
        if not self.SHOW_CONNECTION_LINES or not self.tamagotchi_logic or \
           not self.tamagotchi_logic.squid or not self.tamagotchi_logic.user_interface or \
           not self.tamagotchi_logic.squid.squid_item: # Ensure local squid visual exists
            return

        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        local_squid_visual = self.tamagotchi_logic.squid.squid_item

        # Calculate center of local squid's visual
        local_rect = local_squid_visual.boundingRect()
        local_center_pos = local_squid_visual.pos() + local_rect.center()

        active_remote_node_ids = set() # Keep track of nodes that currently have lines

        for node_id, remote_squid_info in self.remote_squids.items():
            remote_visual = remote_squid_info.get('visual')
            if not remote_visual or not remote_visual.isVisible() or remote_visual not in scene.items():
                continue # Skip if remote squid is not visible or its visual is invalid

            active_remote_node_ids.add(node_id)
            remote_rect = remote_visual.boundingRect()
            remote_center_pos = remote_visual.pos() + remote_rect.center()

            # Define pen style for the line
            line_color_data = remote_squid_info.get('data', {}).get('color', (100, 100, 255)) # Default blueish
            pen = QtGui.QPen(QtGui.QColor(*line_color_data, 120)) # Semi-transparent alpha
            pen.setWidth(2)
            pen.setStyle(QtCore.Qt.DashLine)

            # Create or update the line item
            if node_id in self.connection_lines: # Line exists, update it
                line = self.connection_lines[node_id]
                if line not in scene.items(): # Re-add if it was somehow removed
                    scene.addItem(line)
                line.setLine(local_center_pos.x(), local_center_pos.y(), remote_center_pos.x(), remote_center_pos.y())
                line.setPen(pen) # Update style (e.g., if remote color changes)
                line.setVisible(True) # Ensure it's visible
            else: # New line needed
                line = QtWidgets.QGraphicsLineItem(
                    local_center_pos.x(), local_center_pos.y(), remote_center_pos.x(), remote_center_pos.y()
                )
                line.setPen(pen)
                line.setZValue(-10) # Draw behind all squids and most objects
                scene.addItem(line)
                self.connection_lines[node_id] = line
        
        # Remove lines for remote squids that are no longer active/visible
        for node_id_key in list(self.connection_lines.keys()): # Iterate copy
            if node_id_key not in active_remote_node_ids:
                line_to_remove = self.connection_lines.pop(node_id_key)
                if line_to_remove in scene.items():
                    scene.removeItem(line_to_remove)


    def _register_hooks(self):
        """Registers handlers for various network message types (hooks) with the plugin manager."""
        if not self.plugin_manager:
            print("Multiplayer Error: Cannot register hooks, plugin_manager is not set.")
            return

        # Define a mapping of hook names (derived from message types) to their handler methods
        hook_handlers = {
            "network_squid_move": self.handle_squid_move,       # For discrete movement updates (if not part of full sync)
            "network_object_sync": self.handle_object_sync,     # Main state synchronization for squids and objects
            "network_rock_throw": self.handle_rock_throw,       # When a remote player throws a rock
            "network_heartbeat": self.handle_heartbeat,         # Regular presence/status updates from peers
            "network_state_update": self.handle_state_update,   # Generic state changes (less common)
            "network_squid_exit": self.handle_squid_exit_message, # A remote squid exits its screen towards us
            "network_squid_return": self.handle_squid_return    # Our squid returns from a remote visit
            # Add "network_player_join", "network_player_leave" if specific logic needed beyond heartbeat/timeout
        }

        # Register each hook and subscribe the handler method
        for hook_name, handler_method in hook_handlers.items():
            self.plugin_manager.register_hook(hook_name) # Ensure the hook name itself is known to the manager
            self.plugin_manager.subscribe_to_hook(
                hook_name,
                mp_constants.PLUGIN_NAME, # Identify this plugin as the subscriber
                handler_method
            )
        
        # Special hook: 'pre_update' from the game loop to process NetworkNode's message queue
        # This ensures network messages are processed in the main thread context.
        self.plugin_manager.register_hook("pre_update")
        self.plugin_manager.subscribe_to_hook("pre_update", mp_constants.PLUGIN_NAME, self._process_network_node_queue)

        if self.debug_mode: print("Multiplayer: Network message hooks registered.")


    def pre_update(self, *args, **kwargs): # This is the method subscribed to "pre_update"
        """
        Called by the game's main update loop (via plugin manager hook).
        This method is DEPRECATED here if _process_network_node_queue is directly connected to a QTimer
        or if the plugin manager calls _process_network_node_queue via the "pre_update" hook.
        If using the timer approach, this method might not be needed for message processing.
        """
        # The current design uses a QTimer calling `_process_network_node_queue` directly.
        # If `pre_update` hook from plugin manager is preferred for this, then connect this method
        # to the `pre_update` hook and have it call `_process_network_node_queue`.
        # For now, assuming QTimer handles it. If `pre_update` is used, it should call:
        # self._process_network_node_queue()
        pass # See _process_network_node_queue and its QTimer.

    def start_sync_timer(self):
        """Starts a daemon thread for periodic game state synchronization."""
        if self.sync_thread and self.sync_thread.is_alive():
            if self.debug_mode: print("Multiplayer: Sync thread already running.")
            return

        def game_state_sync_loop():
            while True:
                if not self.is_setup: # Check if plugin is still active/setup
                    if self.debug_mode: print("Multiplayer SyncLoop: Plugin not setup or disabled, loop exiting.")
                    break
                try:
                    if self.network_node and self.network_node.is_connected and \
                       self.tamagotchi_logic and self.tamagotchi_logic.squid: # Ensure all parts are ready

                        # Adaptive sync interval based on local squid activity
                        is_local_squid_moving = getattr(self.tamagotchi_logic.squid, 'is_moving', False)
                        sync_delay_seconds = 0.3 if is_local_squid_moving else self.SYNC_INTERVAL # Faster if moving

                        # Adjust sync frequency based on number of peers (reduce load with more peers)
                        num_peers = len(getattr(self.network_node, 'known_nodes', {}))
                        if num_peers > 8: sync_delay_seconds *= 1.5
                        elif num_peers > 15: sync_delay_seconds *= 2.0
                        
                        # Clamp delay to reasonable min/max values
                        sync_delay_seconds = max(0.2, min(sync_delay_seconds, 3.0))

                        self.sync_game_state() # Perform the actual state synchronization
                        time.sleep(sync_delay_seconds)
                    else: # Not ready to sync (e.g., disconnected, no squid)
                        time.sleep(2.5) # Wait longer before re-checking
                except ReferenceError: # Can happen if Qt objects are accessed after being deleted during shutdown
                    if self.debug_mode: print("Multiplayer SyncLoop: ReferenceError (likely app shutting down), loop exiting.")
                    break
                except Exception as e_sync:
                    if self.debug_mode: print(f"Multiplayer Error in game_state_sync_loop: {e_sync}")
                    # traceback.print_exc() # For detailed debugging
                    time.sleep(3.0) # Longer pause after an error

        self.sync_thread = threading.Thread(target=game_state_sync_loop, daemon=True)
        self.sync_thread.start()
        if self.debug_mode: print("Multiplayer: Game state synchronization thread started.")


    def sync_game_state(self):
        """Collects and sends the current local game state (squid, key objects) over the network."""
        # Basic checks to ensure essential components are available
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'squid') or \
           not self.network_node or not self.network_node.is_connected:
            # if self.debug_mode: print("Multiplayer DEBUG: sync_game_state prerequisites not met.")
            return

        try:
            # --- Gather Local Squid State ---
            squid_current_state = self._get_squid_state() # Method to compile squid data

            # --- Gather Key Game Objects State ---
            # This can be performance-intensive if many objects or frequent updates.
            # Consider strategies like delta-syncing or only syncing objects within a certain radius if needed.
            objects_current_state = self._get_objects_state() # Method to compile object data

            # --- Send Synchronization Message ---
            # Typically 'object_sync' is a comprehensive message with both squid and object states.
            sync_payload = {
                'squid': squid_current_state,
                'objects': objects_current_state,
                'node_info': { # Basic info about this node
                    'id': self.network_node.node_id,
                    'ip': self.network_node.local_ip
                    # Could add game version, etc. here for compatibility checks
                }
            }
            self.network_node.send_message('object_sync', sync_payload)
            # if self.debug_mode: print(f"Multiplayer DEBUG: Sent 'object_sync' with {len(objects_current_state)} objects.")

            # --- Send Heartbeat (less frequently than full sync) ---
            time_now = time.time()
            # Send heartbeat every ~5-10 seconds to maintain presence
            if time_now - self.last_message_times.get('heartbeat_sent', 0) > 8.0:
                heartbeat_payload = {
                    'node_id': self.network_node.node_id,
                    'status': 'active', # Basic status
                    'squid_pos': (squid_current_state['x'], squid_current_state['y']) # Minimal position update
                }
                self.network_node.send_message('heartbeat', heartbeat_payload)
                self.last_message_times['heartbeat_sent'] = time_now
                # if self.debug_mode: print("Multiplayer DEBUG: Heartbeat sent.")
        except Exception as e:
            print(f"Multiplayer ERROR during sync_game_state: {e}")
            # traceback.print_exc() # For detailed debugging


    def _get_squid_state(self) -> Dict:
        """Compiles and returns a dictionary representing the current state of the local squid."""
        if not self.tamagotchi_logic or not self.tamagotchi_logic.squid or not self.network_node:
            return {} # Return empty if essential components are missing

        squid = self.tamagotchi_logic.squid
        view_direction_rad = self.get_actual_view_direction(squid) # Get looking direction in radians

        return {
            'x': squid.squid_x,
            'y': squid.squid_y,
            'direction': squid.squid_direction, # Cardinal direction string ("left", "right", etc.)
            'looking_direction': view_direction_rad, # Angle in radians for precise orientation
            'view_cone_angle': getattr(squid, 'view_cone_angle_rad', math.radians(60)), # View cone width in radians
            'hunger': squid.hunger,
            'happiness': squid.happiness,
            'status': getattr(squid, 'status', "idle"), # Current action or state string
            'carrying_rock': getattr(squid, 'carrying_rock', False),
            'is_sleeping': getattr(squid, 'is_sleeping', False),
            'color': self.get_squid_color(), # Method to get a consistent color tuple (R,G,B)
            'node_id': self.network_node.node_id, # This node's ID, associating the squid with it
            'view_cone_visible': getattr(squid, 'view_cone_visible', False) # Is the view cone currently drawn?
            # Add other relevant squid attributes here (e.g., energy, age, name if networked)
        }


    def get_actual_view_direction(self, squid_instance) -> float:
        """
        Determines the squid's current viewing direction as an angle in radians.
        0 radians is to the right, PI/2 is down, PI is left, 3PI/2 is up.
        """
        # Prefer an explicit view angle if the squid object tracks it (e.g., for independent head turning)
        if hasattr(squid_instance, 'current_view_angle_radians'):
            return squid_instance.current_view_angle_radians
        # Fallback: derive from cardinal movement direction
        direction_to_radians_map = {
            'right': 0.0,
            'left': math.pi,
            'up': 1.5 * math.pi,  # -PI/2 or 3PI/2
            'down': 0.5 * math.pi # PI/2
        }
        return direction_to_radians_map.get(getattr(squid_instance, 'squid_direction', 'right'), 0.0)


    def get_squid_color(self) -> tuple:
        """Generates a pseudo-random but persistent color (R,G,B) for the local squid based on its node_id."""
        # Cache the color once generated to ensure consistency and performance
        if not hasattr(self, '_local_squid_color_cache'):
            node_id_str = "default_node"
            if self.network_node and self.network_node.node_id:
                node_id_str = self.network_node.node_id

            # Simple hashing of node_id to generate color components
            # This ensures the same node_id always gets the same color.
            hash_value = 0
            for char_code in node_id_str.encode('utf-8'): # Use byte values for hashing
                hash_value = (hash_value * 37 + char_code) & 0xFFFFFF # Keep it within 24-bit color range

            r = (hash_value >> 16) & 0xFF
            g = (hash_value >> 8) & 0xFF
            b = hash_value & 0xFF

            # Adjust components to ensure decent visibility (avoid very dark/light colors if needed)
            # Example: ensure each component is at least, say, 50 and at most 200 for pastel-like.
            r = max(80, min(r, 220))
            g = max(80, min(g, 220))
            b = max(80, min(b, 220))
            self._local_squid_color_cache = (r, g, b)
        return self._local_squid_color_cache


    def _get_objects_state(self) -> List[Dict]:
        """Collects and returns a list of dictionaries, each representing a syncable game object's state."""
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'):
            return []

        ui = self.tamagotchi_logic.user_interface
        syncable_objects_list = []
        try:
            for item in ui.scene.items(): # Iterate through all items in the QGraphicsScene
                # Filter for items that should be synced (e.g., specific types, visible, not remote clones)
                if not isinstance(item, QtWidgets.QGraphicsPixmapItem) or not hasattr(item, 'filename'):
                    continue # Must be a pixmap item with a filename to be easily identifiable/recreatable
                if not item.isVisible(): # Don't sync invisible items (unless specific game logic requires it)
                    continue
                # Avoid re-syncing objects that are already clones of remote objects present in this scene
                if getattr(item, 'is_remote_clone', False):
                    continue

                object_type_str = self._determine_object_type(item)
                # Define which object types are eligible for synchronization
                valid_types_to_sync = ['rock', 'food', 'poop', 'decoration'] # Example list
                if object_type_str not in valid_types_to_sync:
                    continue

                item_pos = item.pos()
                # Object ID: Needs to be consistent for the *original* item on its home instance.
                # If items have unique game IDs, use that. Otherwise, a combination of properties.
                # Using filename + initial position can be a pseudo-ID for static items. Moving items are harder.
                # For this example, assume items are identified by filename and current position for simplicity,
                # which means remote instances will just mirror current state.
                obj_id = f"{os.path.basename(item.filename)}_{int(item_pos.x())}_{int(item_pos.y())}"

                object_data = {
                    'id': obj_id, # This ID is relative to the sending client's perspective
                    'type': object_type_str,
                    'x': item_pos.x(),
                    'y': item_pos.y(),
                    'filename': item.filename, # Path to image file; ensure this path is usable by remote clients
                                               # (e.g., relative to a shared resource root, or just basename + type)
                    'scale': item.scale() if hasattr(item, 'scale') else 1.0,
                    'zValue': item.zValue(), # For correct draw order
                    'is_being_carried': getattr(item, 'is_being_carried', False) # If squid is carrying it
                    # Add other relevant properties: rotation, custom data, etc.
                }
                syncable_objects_list.append(object_data)
        except RuntimeError: # Scene might be modified during iteration in rare threaded cases (less likely with Qt main thread)
             if self.debug_mode: print("Multiplayer: Runtime error while iterating scene items for sync. Skipping this cycle.")
             return [] # Return empty or previously gathered list
        except Exception as e:
            if self.debug_mode: print(f"Multiplayer Error: Getting object states for sync failed: {e}")
            # traceback.print_exc()
        return syncable_objects_list


    def _determine_object_type(self, scene_item: QtWidgets.QGraphicsItem) -> str:
        """Determines a string type for a given scene item based on its properties or filename."""
        # Prioritize an explicit 'category' or 'type' attribute on the item
        if hasattr(scene_item, 'category') and isinstance(getattr(scene_item, 'category'), str):
            return getattr(scene_item, 'category')
        if hasattr(scene_item, 'object_type') and isinstance(getattr(scene_item, 'object_type'), str):
            return getattr(scene_item, 'object_type')

        # Fallback: Infer from filename if it's a QGraphicsPixmapItem
        if isinstance(scene_item, QtWidgets.QGraphicsPixmapItem) and hasattr(scene_item, 'filename'):
            filename_lower = getattr(scene_item, 'filename', '').lower()
            if not filename_lower: return 'unknown_pixmap'

            if 'rock' in filename_lower: return 'rock'
            if any(food_kw in filename_lower for food_kw in ['food', 'sushi', 'apple', 'cheese', 'berry']): return 'food'
            if 'poop' in filename_lower: return 'poop'
            # Check if it's in a 'decoration' subfolder or has 'decor' in name
            if os.path.join("images", "decoration") in filename_lower.replace("\\", "/") or \
               'decor' in filename_lower or 'plant' in filename_lower or 'toy' in filename_lower:
                return 'decoration'
        return 'generic_item' # Default for items not matching specific criteria


    def handle_object_sync(self, node: NetworkNode, message: Dict, addr: tuple):
        """
        Handles an incoming 'object_sync' message from a remote peer.
        This updates the local representation of the remote squid and its owned objects.
        """
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        try:
            sync_payload = message.get('payload', {})
            remote_squid_state = sync_payload.get('squid', {})
            remote_objects_list = sync_payload.get('objects', [])
            source_node_info = sync_payload.get('node_info', {})
            sender_node_id = source_node_info.get('id') or remote_squid_state.get('node_id') # Get sender ID

            if not sender_node_id: # Message is unusable without knowing who sent it
                if self.debug_mode: print("Multiplayer: Received object_sync with no identifiable sender node_id.")
                return
            # Ignore sync messages from self (should not happen if NetworkNode filters correctly)
            if self.network_node and sender_node_id == self.network_node.node_id: return

            # --- Update Remote Squid's Visual ---
            if remote_squid_state: # If squid data is present in the sync
                self.update_remote_squid(sender_node_id, remote_squid_state)

            # --- Process Synced Objects from the Remote Peer ---
            # These are objects owned/managed by the sender. We create/update clones of them.
            if remote_objects_list:
                active_cloned_ids_for_this_sender = set()
                for remote_obj_data in remote_objects_list:
                    # Basic validation of received object data
                    if not all(k in remote_obj_data for k in ['id', 'type', 'x', 'y', 'filename']):
                        if self.debug_mode: print(f"Multiplayer: Skipping incomplete remote object data from {sender_node_id}: {remote_obj_data.get('id', 'No ID')}")
                        continue
                    
                    # Create a unique ID for the *clone* of this remote object in our scene
                    # This helps distinguish it from local objects or clones from other senders.
                    original_id_from_sender = remote_obj_data['id']
                    clone_id = f"clone_{sender_node_id}_{original_id_from_sender}"
                    active_cloned_ids_for_this_sender.add(clone_id)
                    
                    self.process_remote_object(remote_obj_data, sender_node_id, clone_id)

                # Cleanup: Remove clones of objects that were NOT in this sync message from this sender
                # This implies objects not sent are no longer active/visible on the sender's side.
                with self.remote_objects_lock:
                    ids_to_remove = [
                        obj_id for obj_id, obj_info in self.remote_objects.items()
                        if obj_info.get('source_node') == sender_node_id and obj_id not in active_cloned_ids_for_this_sender
                    ]
                    for obj_id_to_remove in ids_to_remove:
                        self.remove_remote_object(obj_id_to_remove)


            # Notify local squid's AI about the presence/state of the remote squid (optional)
            if self.tamagotchi_logic.squid and hasattr(self.tamagotchi_logic.squid, 'process_squid_detection') and remote_squid_state:
                self.tamagotchi_logic.squid.process_squid_detection(
                    remote_node_id=sender_node_id,
                    is_detected=True, # Assuming presence if sync received
                    remote_squid_props=remote_squid_state # Pass full state for AI decisions
                )
        except Exception as e:
            if self.debug_mode: print(f"Multiplayer Error: Handling object_sync from {addr} failed: {e}")
            # traceback.print_exc()


    def process_remote_object(self, remote_obj_data: Dict, source_node_id: str, clone_id: str):
        """
        Creates or updates a visual clone of a remote object in the local scene.
        Args:
            remote_obj_data: Dictionary of the remote object's properties.
            source_node_id: The ID of the node that owns the original object.
            clone_id: The unique ID assigned to the clone of this object in the local scene.
        """
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene

        # --- Resolve Filename ---
        # The filename from remote_obj_data might be relative to their setup.
        # Try to resolve it locally. Assume a shared "images" resource structure.
        base_filename = os.path.basename(remote_obj_data['filename'])
        resolved_filename = os.path.join("images", base_filename) # Simplistic resolution
        # More robust: check in "images/decoration", "images/items", etc.
        if not os.path.exists(resolved_filename):
            # Try common subdirs if initial path fails
            for subdir in ["decoration", "items", "food", "rocks"]: # Add relevant subdirs
                path_attempt = os.path.join("images", subdir, base_filename)
                if os.path.exists(path_attempt):
                    resolved_filename = path_attempt
                    break
            else: # If still not found after checking common subdirs
                if self.debug_mode: print(f"Multiplayer: Remote object image '{base_filename}' not found locally for {clone_id}. Skipping visual.")
                return

        # --- Update or Create Clone ---
        with self.remote_objects_lock: # Ensure thread-safe access to self.remote_objects
            if clone_id in self.remote_objects: # Clone already exists, update its properties
                existing_clone_info = self.remote_objects[clone_id]
                visual_item = existing_clone_info['visual']
                visual_item.setPos(remote_obj_data['x'], remote_obj_data['y'])
                visual_item.setScale(remote_obj_data.get('scale', 1.0))
                visual_item.setZValue(remote_obj_data.get('zValue', -5)) # Default Z for remote object clones
                # Hide clone if original is marked as carried (unless special logic to show carried items)
                visual_item.setVisible(not remote_obj_data.get('is_being_carried', False))
                existing_clone_info['last_update'] = time.time()
                existing_clone_info['data'] = remote_obj_data # Update cached data
                # Ensure tint for foreign objects is still applied
                if not getattr(visual_item, 'is_foreign', False):
                     self.apply_foreign_object_tint(visual_item)
            else: # New remote object clone needs to be created
                # Don't create visual for items that are marked as being carried by the remote squid (initially)
                if remote_obj_data.get('is_being_carried', False):
                    # Could store data without visual if needed for logic, but usually not for clones.
                    return

                try:
                    pixmap = QtGui.QPixmap(resolved_filename)
                    if pixmap.isNull():
                        if self.debug_mode: print(f"Multiplayer: Failed to load QPixmap for remote object '{resolved_filename}'.")
                        return

                    cloned_visual = QtWidgets.QGraphicsPixmapItem(pixmap)
                    cloned_visual.setPos(remote_obj_data['x'], remote_obj_data['y'])
                    cloned_visual.setScale(remote_obj_data.get('scale', 1.0))
                    # Cloned objects are typically more transparent than remote squids
                    cloned_visual.setOpacity(self.REMOTE_SQUID_OPACITY * 0.65)
                    cloned_visual.setZValue(remote_obj_data.get('zValue', -5)) # Draw behind local items
                    setattr(cloned_visual, 'filename', resolved_filename) # Store resolved path
                    setattr(cloned_visual, 'is_remote_clone', True) # Mark as a clone
                    setattr(cloned_visual, 'original_id_from_sender', remote_obj_data['id']) # Store original ID

                    self.apply_foreign_object_tint(cloned_visual) # Apply visual tint
                    scene.addItem(cloned_visual)

                    self.remote_objects[clone_id] = {
                        'visual': cloned_visual,
                        'type': remote_obj_data.get('type', 'unknown_clone'),
                        'source_node': source_node_id, # Node that owns the original
                        'last_update': time.time(),
                        'data': remote_obj_data # Store the full received data for this object
                    }
                    # if self.debug_mode: print(f"Multiplayer: Created visual clone '{clone_id}' for remote object.")
                except Exception as e_create_clone:
                    if self.debug_mode: print(f"Multiplayer Error: Creating visual clone for '{clone_id}' failed: {e_create_clone}")
                    # traceback.print_exc()


    def handle_heartbeat(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles heartbeat messages received from other peers."""
        if not self.network_node: return

        sender_node_id = message.get('node_id')
        if not sender_node_id or sender_node_id == self.network_node.node_id: return # Ignore self or invalid

        # NetworkNode.receive_messages already updates known_nodes with last_seen.
        # This handler is for additional logic based on heartbeats.

        # Update UI status (peer count, activity log)
        if self.status_widget:
            self.status_widget.update_peers(self.network_node.known_nodes) # Refresh full peer list
            # Check if this is a newly detected peer (not in our remote_squids visual list yet)
            if sender_node_id not in self.remote_squids:
                self.status_widget.add_activity(f"Peer {sender_node_id[-6:]} detected via heartbeat.")
        elif self.status_bar: # Fallback
            self.status_bar.update_peers_count(len(self.network_node.known_nodes))

        # If heartbeat includes minimal squid data (e.g., position), create a basic visual if none exists.
        # This provides faster initial visibility before a full object_sync arrives.
        heartbeat_payload = message.get('payload', {})
        squid_pos_data = heartbeat_payload.get('squid_pos') # Expecting (x,y) tuple
        if squid_pos_data and sender_node_id not in self.remote_squids:
            if self.debug_mode: print(f"Multiplayer: Creating placeholder for {sender_node_id[-6:]} from heartbeat.")
            placeholder_squid_data = {
                'x': squid_pos_data[0], 'y': squid_pos_data[1],
                'direction': 'right', # Default direction
                'color': (150, 150, 150), # Default placeholder color
                'node_id': sender_node_id, # Associate with the sender
                'status': 'detected'
            }
            self.update_remote_squid(sender_node_id, placeholder_squid_data, is_new_arrival=True)


    def update_remote_squid(self, remote_node_id: str, squid_data_dict: Dict, is_new_arrival=False, high_visibility=False):
        """
        Updates or creates the visual representation of a remote squid in the scene.
        Args:
            remote_node_id: The unique ID of the remote squid's node.
            squid_data_dict: A dictionary containing the squid's state (x, y, direction, color, etc.).
            is_new_arrival: Boolean, True if this is the first time we're seeing this squid (triggers entry effects).
            high_visibility: Boolean, True to make the squid extra visible temporarily.
        Returns:
            True if successful, False otherwise.
        """
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return False
        # Basic validation of incoming data
        if not squid_data_dict or not all(key in squid_data_dict for key in ['x', 'y', 'direction']):
            if self.debug_mode: print(f"Multiplayer Warning: Insufficient data to update remote squid {remote_node_id}.")
            return False
        
        scene = self.tamagotchi_logic.user_interface.scene
        
        with self.remote_squids_lock: # Thread-safe access to remote_squids dictionary
            existing_squid_display = self.remote_squids.get(remote_node_id)

            if existing_squid_display: # Squid already known, update its visuals
                visual = existing_squid_display.get('visual')
                id_text = existing_squid_display.get('id_text')
                status_text = existing_squid_display.get('status_text')

                if visual:
                    visual.setPos(squid_data_dict['x'], squid_data_dict['y'])
                    self.update_remote_squid_image(existing_squid_display, squid_data_dict['direction'])
                
                # Update text labels (position and content)
                new_status_str = "ARRIVING" if is_new_arrival else squid_data_dict.get('status', 'active')
                text_y_offset_id = -50 # Above squid
                text_y_offset_status = -35 # Slightly lower than ID

                if id_text: id_text.setPos(squid_data_dict['x'], squid_data_dict['y'] + text_y_offset_id)
                if status_text:
                    status_text.setPlainText(new_status_str)
                    status_text.setPos(squid_data_dict['x'], squid_data_dict['y'] + text_y_offset_status)
                    if is_new_arrival or high_visibility: # Special style for arrival/highlight
                        status_text.setDefaultTextColor(QtGui.QColor(255, 223, 0)) # Gold
                        status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                    elif status_text.toPlainText().upper() != "ARRIVING": # Reset if not arriving
                        status_text.setDefaultTextColor(QtGui.QColor(200,200,200,230)) # Standard remote text
                        status_text.setFont(QtGui.QFont("Arial", 9))


                # Cache the latest full data
                existing_squid_display['data'] = squid_data_dict
                existing_squid_display['last_update'] = time.time()
            else: # New remote squid to create
                try:
                    # --- Create Visual Item for Squid ---
                    initial_direction = squid_data_dict.get('direction', 'right')
                    # Path construction moved to update_remote_squid_image, call it after item creation
                    # For now, create a placeholder pixmap that update_remote_squid_image will replace.
                    placeholder_pixmap = QtGui.QPixmap(60, 40) # Dimensions for squid
                    squid_color_tuple = squid_data_dict.get('color', (100,150,255)) # Default color if not in data
                    placeholder_pixmap.fill(QtGui.QColor(*squid_color_tuple))
                    visual = QtWidgets.QGraphicsPixmapItem(placeholder_pixmap)
                    visual.setPos(squid_data_dict['x'], squid_data_dict['y'])
                    scene.addItem(visual) # Add to scene early

                    # --- Create Text Labels (ID and Status) ---
                    # ID Text (shortened node ID for display)
                    display_id_str = f"{remote_node_id[-6:]}" # e.g., last 6 chars
                    id_text = scene.addText(display_id_str)
                    id_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 50)
                    id_text.setFont(QtGui.QFont("Arial", 8))
                    # Status Text
                    status_str = "ARRIVING" if is_new_arrival else squid_data_dict.get('status', 'active')
                    status_text = scene.addText(status_str)
                    status_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 35)


                    # Store all parts in the tracking dictionary
                    new_squid_display_data = {
                        'visual': visual, 'id_text': id_text, 'status_text': status_text,
                        'view_cone': None, # View cone graphics item, created/updated separately
                        'last_update': time.time(), 'data': squid_data_dict
                    }
                    self.remote_squids[remote_node_id] = new_squid_display_data
                    
                    # Set initial image using the helper method
                    self.update_remote_squid_image(new_squid_display_data, initial_direction)


                    # Apply styles based on arrival/visibility flags
                    if is_new_arrival or high_visibility:
                        visual.setZValue(15) # Prominent Z-order for arrivals
                        visual.setOpacity(1.0) # Fully opaque
                        id_text.setDefaultTextColor(QtGui.QColor(240, 240, 100)) # Bright ID text
                        status_text.setDefaultTextColor(QtGui.QColor(255, 215, 0)) # Gold status text
                        status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                        id_text.setZValue(16); status_text.setZValue(16) # Texts above visual
                        # Trigger enhanced arrival animation
                        self._create_enhanced_arrival_animation(visual, squid_data_dict['x'], squid_data_dict['y'])
                        # Schedule a style reset to normal remote appearance after a few seconds
                        QtCore.QTimer.singleShot(8000, lambda: self._reset_remote_squid_style(remote_node_id))
                    else: # Standard appearance for already present remote squids
                        self._reset_remote_squid_style(remote_node_id) # Apply standard style immediately

                except Exception as e_create_squid:
                    print(f"Multiplayer Error: Creating remote squid visual for {remote_node_id} failed: {e_create_squid}")
                    # traceback.print_exc()
                    # Clean up partially created items if error occurred
                    if remote_node_id in self.remote_squids: del self.remote_squids[remote_node_id]
                    # scene.removeItem might be needed for items already added if error is late
                    return False
        return True


    def _create_enhanced_arrival_animation(self, squid_visual_item: QtWidgets.QGraphicsPixmapItem, at_x: float, at_y: float):
        """Creates a more prominent visual animation for newly arriving remote squids."""
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene

        # --- Pulsing Circles Effect --- (subtle indication of entry)
        num_pulses = 2
        for i in range(num_pulses):
            pulse_circle = QtWidgets.QGraphicsEllipseItem(at_x - 10, at_y - 10, 20, 20) # Start small
            pulse_color = QtGui.QColor(173, 216, 230, 150) # Light blue, semi-transparent
            pulse_circle.setPen(QtGui.QPen(pulse_color, 1.5))
            pulse_circle.setBrush(QtCore.Qt.NoBrush) # No fill, just outline
            pulse_circle.setZValue(getattr(squid_visual_item, 'zValue', 5) -1) # Just behind the squid
            scene.addItem(pulse_circle)

            # Animation for this pulse circle
            pulse_anim_group = QtCore.QParallelAnimationGroup()
            # Expand size
            size_anim = QtCore.QPropertyAnimation(pulse_circle, b"rect")
            size_anim.setDuration(1200 + i*200) # Staggered duration
            size_anim.setStartValue(QtCore.QRectF(at_x - 10, at_y - 10, 20, 20))
            size_anim.setEndValue(QtCore.QRectF(at_x - 50 - i*10, at_y - 50 - i*10, 100 + i*20, 100 + i*20)) # Expand outwards
            size_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)
            # Fade out opacity
            pulse_opacity_effect = QtWidgets.QGraphicsOpacityEffect(pulse_circle)
            pulse_circle.setGraphicsEffect(pulse_opacity_effect)
            opacity_anim = QtCore.QPropertyAnimation(pulse_opacity_effect, b"opacity")
            opacity_anim.setDuration(1000 + i*200)
            opacity_anim.setStartValue(0.7)
            opacity_anim.setEndValue(0.0)
            opacity_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad)

            pulse_anim_group.addAnimation(size_anim)
            pulse_anim_group.addAnimation(opacity_anim)
            # Stagger start of each pulse animation slightly
            QtCore.QTimer.singleShot(i * 300, pulse_anim_group.start) # Staggered start
            pulse_anim_group.finished.connect(lambda item=pulse_circle: scene.removeItem(item) if item in scene.items() else None)


        # --- "Visitor Arrived!" Text Animation --- (Optional, can be chat message too)
        # This part is similar to create_entry_effect's text, so ensure they don't clash if both used.
        # For now, let update_remote_squid handle the main status text ("ARRIVING").
        # This enhanced animation focuses on the pulsing circles and potential brief squid visual effect.

        # --- Brief Glow/Scale effect on the squid visual itself ---
        # Scale animation (small bounce)
        scale_anim = QtCore.QPropertyAnimation(squid_visual_item, b"scale")
        scale_anim.setDuration(800)
        scale_anim.setKeyValueAt(0, 0.8) # Start slightly small
        scale_anim.setKeyValueAt(0.5, 1.1) # Bounce larger
        scale_anim.setKeyValueAt(1, 1.0) # Settle to normal scale
        scale_anim.setEasingCurve(QtCore.QEasingCurve.OutBack) # "Overshoot" easing for bounce
        scale_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)


    def handle_remote_squid_return(self, remote_node_id: str, controller: Any):
        """
        Initiates the process for a remote squid (controlled by this instance)
        to "return home" to its original instance.
        Args:
            remote_node_id: The ID of the remote squid.
            controller: The RemoteSquidController instance managing this squid.
        """
        if self.debug_mode: print(f"Multiplayer: Remote squid {remote_node_id[-6:]} is being returned home by its controller.")

        activity_summary_data = controller.get_summary() # Get activity log from controller
        home_direction_for_exit = controller.home_direction # Direction it needs to move to "exit" this screen

        remote_squid_display_info = self.remote_squids.get(remote_node_id)
        if not remote_squid_display_info or not remote_squid_display_info.get('visual'):
            if self.debug_mode: print(f"Multiplayer: Visual for returning remote squid {remote_node_id[-6:]} not found. Completing return directly.")
            # If no visual, complete the return process immediately without animation
            self.complete_remote_squid_return(remote_node_id, activity_summary_data, home_direction_for_exit)
            return

        visual_item = remote_squid_display_info['visual']
        status_text = remote_squid_display_info.get('status_text')
        if status_text: # Update status to "RETURNING..."
            status_text.setPlainText("RETURNING HOME...")
            status_text.setDefaultTextColor(QtGui.QColor(255, 165, 0)) # Orange color for returning
            status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))

        # --- Fade-out Animation ---
        opacity_eff = QtWidgets.QGraphicsOpacityEffect(visual_item)
        visual_item.setGraphicsEffect(opacity_eff)
        fade_out_animation = QtCore.QPropertyAnimation(opacity_eff, b"opacity")
        fade_out_animation.setDuration(1800) # Longer fade for departure
        fade_out_animation.setStartValue(visual_item.opacity()) # Start from current opacity
        fade_out_animation.setEndValue(0.0) # Fade to fully transparent
        fade_out_animation.setEasingCurve(QtCore.QEasingCurve.InQuad)
        # Connect finished signal to call the completion method
        fade_out_animation.finished.connect(
            lambda: self.complete_remote_squid_return(remote_node_id, activity_summary_data, home_direction_for_exit)
        )
        fade_out_animation.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

        if self.debug_mode: print(f"Multiplayer: Started fade-out for remote squid {remote_node_id[-6:]} returning home.")
        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(f"👋 Visitor squid {remote_node_id[-6:]} is heading back home!")


    def complete_remote_squid_return(self, remote_node_id: str, activity_summary: Dict, exit_direction: str):
        """
        Finalizes the return of a remote squid. Sends a 'squid_return' message to its original owner
        and cleans up local representations (visuals, controller).
        Args:
            remote_node_id: ID of the squid that has "left".
            activity_summary: Data about its activities while visiting.
            exit_direction: The direction the squid was moving to leave this screen.
        """
        try:
            # --- Send 'squid_return' Message ---
            # This message informs the squid's original instance that it has "returned"
            # and includes a summary of its activities here.
            if self.network_node and self.network_node.is_connected:
                return_message_payload = {
                    'node_id': remote_node_id, # ID of the squid that is returning
                    'activity_summary': activity_summary,
                    'return_direction': exit_direction # The direction it exited this instance's screen
                }
                self.network_node.send_message('squid_return', return_message_payload)
                if self.debug_mode:
                    rocks = activity_summary.get('rocks_stolen',0)
                    print(f"Multiplayer: Sent 'squid_return' for {remote_node_id[-6:]} (summary: {rocks} rocks). Exit dir: {exit_direction}")

            # --- Clean Up Local Representations ---
            # Remove visual elements from the scene
            self.remove_remote_squid(remote_node_id)
            # Remove and clean up its controller
            if remote_node_id in self.remote_squid_controllers:
                # Controller might have cleanup, though python's GC handles most if no cycles
                # controller_to_remove = self.remote_squid_controllers.pop(remote_node_id)
                # if hasattr(controller_to_remove, 'cleanup'): controller_to_remove.cleanup()
                del self.remote_squid_controllers[remote_node_id]
                if self.debug_mode: print(f"Multiplayer: Removed controller for returned remote squid {remote_node_id[-6:]}.")

        except Exception as e:
            print(f"Multiplayer Error: Completing remote squid return for {remote_node_id[-6:]} failed: {e}")
            # traceback.print_exc()


    def update_remote_view_cone(self, remote_node_id: str, remote_squid_data: Dict):
        """Updates the visual representation of a remote squid's view cone."""
        if not self.SHOW_REMOTE_LABELS: # Assuming view cones are tied to "show labels" for now
            # If a cone exists, remove it if this setting is off
            if remote_node_id in self.remote_squids and self.remote_squids[remote_node_id].get('view_cone'):
                self._remove_view_cone_for_squid(remote_node_id)
            return

        if remote_node_id not in self.remote_squids or not self.tamagotchi_logic or \
           not hasattr(self.tamagotchi_logic, 'user_interface'):
            return

        scene = self.tamagotchi_logic.user_interface.scene
        squid_display_info = self.remote_squids[remote_node_id]
        existing_cone_item = squid_display_info.get('view_cone')

        # Remove old cone if it exists
        if existing_cone_item and existing_cone_item in scene.items():
            scene.removeItem(existing_cone_item)
        squid_display_info['view_cone'] = None # Clear old reference

        # Create new cone only if the remote squid's view cone is supposed to be visible
        if not remote_squid_data.get('view_cone_visible', False):
            return

        # --- Calculate Cone Geometry ---
        squid_x = remote_squid_data['x']
        squid_y = remote_squid_data['y']
        # Approximate center of the squid visual for cone origin
        # TODO: Get actual visual item's bounding rect center if possible for accuracy
        visual_item = squid_display_info.get('visual')
        if visual_item:
            squid_center_x = visual_item.pos().x() + visual_item.boundingRect().width() / 2
            squid_center_y = visual_item.pos().y() + visual_item.boundingRect().height() / 2
        else: # Fallback if visual not available yet
            squid_center_x = squid_x + 30 # Approx. half width
            squid_center_y = squid_y + 20 # Approx. half height

        # Angle the squid is looking, in radians (0 is right, PI/2 is down, etc.)
        looking_direction_rad = remote_squid_data.get('looking_direction', 0.0)
        # Width of the view cone, in radians (total angle)
        view_cone_angle_rad = remote_squid_data.get('view_cone_angle', math.radians(50)) # Default 50 degrees wide
        cone_half_angle = view_cone_angle_rad / 2.0
        cone_length = 150 # Visual length of the cone

        # Define the three points of the cone triangle
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

        # --- Create and Style Cone Item ---
        new_cone_item = QtWidgets.QGraphicsPolygonItem(cone_polygon)
        squid_color = remote_squid_data.get('color', (150, 150, 255)) # Use squid's color
        new_cone_item.setPen(QtGui.QPen(QtGui.QColor(*squid_color, 0))) # No border for cone
        new_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(*squid_color, 25))) # Very transparent fill
        # Draw cone behind the squid visual
        new_cone_item.setZValue(visual_item.zValue() - 1 if visual_item else 4)

        scene.addItem(new_cone_item)
        squid_display_info['view_cone'] = new_cone_item # Store reference

    def _remove_view_cone_for_squid(self, remote_node_id: str):
        """Helper to safely remove a view cone for a specific remote squid."""
        if remote_node_id in self.remote_squids and self.tamagotchi_logic and hasattr(self.tamagotchi_logic.user_interface, 'scene'):
            squid_display_info = self.remote_squids[remote_node_id]
            cone_item = squid_display_info.get('view_cone')
            if cone_item and cone_item in self.tamagotchi_logic.user_interface.scene.items():
                self.tamagotchi_logic.user_interface.scene.removeItem(cone_item)
            squid_display_info['view_cone'] = None


    def create_gift_decoration(self, from_remote_node_id: str) -> QtWidgets.QGraphicsPixmapItem | None:
        """Creates a new decoration item in the scene, representing a gift received from a remote squid."""
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return None
        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene

        # --- Select a Random Decoration Image ---
        available_decoration_images = []
        # Define paths to search for decoration images
        decoration_image_dirs = [os.path.join("images", "decoration"), "images"]
        for img_dir in decoration_image_dirs:
            if os.path.exists(img_dir):
                for filename in os.listdir(img_dir):
                    if filename.lower().endswith(('.png', '.jpg', '.gif')) and \
                       any(kw in filename.lower() for kw in ['decor', 'plant', 'toy', 'shell', 'coral', 'starfish', 'gem']): # Keywords
                        available_decoration_images.append(os.path.join(img_dir, filename))
        
        if not available_decoration_images: # Fallback if no specific decorations found
            default_gift_img = os.path.join("images", "plant.png") # Example default
            if not os.path.exists(default_gift_img):
                if self.debug_mode: print("Multiplayer: Default gift image not found. Cannot create gift.")
                return None
            available_decoration_images.append(default_gift_img)

        chosen_gift_image_path = random.choice(available_decoration_images)

        try:
            gift_pixmap = QtGui.QPixmap(chosen_gift_image_path)
            if gift_pixmap.isNull():
                if self.debug_mode: print(f"Multiplayer: Failed to load gift image '{chosen_gift_image_path}'.")
                return None

            # --- Create Graphics Item for the Gift ---
            gift_item = None
            if hasattr(ui, 'ResizablePixmapItem'): # Prefer custom resizable item if available
                gift_item = ui.ResizablePixmapItem(gift_pixmap, chosen_gift_image_path)
            else: # Use standard QGraphicsPixmapItem
                gift_item = QtWidgets.QGraphicsPixmapItem(gift_pixmap)
                setattr(gift_item, 'filename', chosen_gift_image_path) # Ensure filename attribute

            setattr(gift_item, 'category', 'decoration') # Mark as a decoration
            setattr(gift_item, 'is_gift_from_remote', True) # Special flag for gifts
            setattr(gift_item, 'received_from_node', from_remote_node_id) # Track sender
            gift_item.setToolTip(f"A surprise gift from tank {from_remote_node_id[-6:]}!")

            # --- Position the Gift Randomly ---
            # Try to find a somewhat empty spot, avoiding overlap with many items.
            # This is a simple placement, more complex logic could be used.
            item_width = gift_pixmap.width()
            item_height = gift_pixmap.height()
            max_placement_x = ui.window_width - item_width - 30  # 30px margin
            max_placement_y = ui.window_height - item_height - 30
            gift_pos_x = random.uniform(30, max(30, max_placement_x))
            gift_pos_y = random.uniform(30, max(30, max_placement_y))
            gift_item.setPos(gift_pos_x, gift_pos_y)

            self.apply_foreign_object_tint(gift_item) # Tint to indicate it's from "elsewhere"
            scene.addItem(gift_item)
            self._create_arrival_animation(gift_item) # Simple fade-in for the new gift

            # Add a temporary "🎁 Gift!" label above it
            gift_indicator_label = scene.addText("🎁 Gift!")
            label_font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
            gift_indicator_label.setFont(label_font)
            gift_indicator_label.setDefaultTextColor(QtGui.QColor(255, 100, 100)) # Festive color
            # Position label above the gift item
            label_x = gift_pos_x + (item_width / 2) - (gift_indicator_label.boundingRect().width() / 2)
            label_y = gift_pos_y - gift_indicator_label.boundingRect().height() - 5
            gift_indicator_label.setPos(label_x, label_y)
            gift_indicator_label.setZValue(gift_item.zValue() + 1) # Ensure label is on top of gift
            # Make label fade out after a few seconds
            label_opacity_effect = QtWidgets.QGraphicsOpacityEffect(gift_indicator_label)
            gift_indicator_label.setGraphicsEffect(label_opacity_effect)
            label_fade_out_anim = QtCore.QPropertyAnimation(label_opacity_effect, b"opacity")
            label_fade_out_anim.setDuration(4000) # Visible for 4 seconds
            label_fade_out_anim.setStartValue(1.0)
            label_fade_out_anim.setEndValue(0.0)
            label_fade_out_anim.finished.connect(lambda item=gift_indicator_label: scene.removeItem(item) if item in scene.items() else None)
            label_fade_out_anim.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

            return gift_item
        except Exception as e_gift:
            if self.debug_mode: print(f"Multiplayer Error creating gift decoration: {e_gift}")
            # traceback.print_exc()
            return None


    def remove_remote_squid(self, node_id_to_remove: str):
        """Removes all visual components of a specific remote squid from the scene."""
        if node_id_to_remove not in self.remote_squids: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return

        scene = self.tamagotchi_logic.user_interface.scene
        with self.remote_squids_lock: # Ensure thread-safe modification
            squid_display_elements = self.remote_squids.pop(node_id_to_remove, None) # Remove and get data

        if squid_display_elements:
            # List of visual component keys to remove
            visual_keys = ['visual', 'view_cone', 'id_text', 'status_text']
            for key in visual_keys:
                item_to_remove = squid_display_elements.get(key)
                if item_to_remove and item_to_remove in scene.items(): # Check if item exists and is in scene
                    scene.removeItem(item_to_remove)
            
            # Also remove any associated connection line
            if node_id_to_remove in self.connection_lines:
                line = self.connection_lines.pop(node_id_to_remove)
                if line in scene.items():
                    scene.removeItem(line)
            
            # if self.debug_mode: print(f"Multiplayer: Removed all visuals for remote squid {node_id_to_remove[-6:]}.")

        # Notify UI about peer list change
        if self.network_node:
            if self.status_widget: self.status_widget.update_peers(self.network_node.known_nodes)
            elif self.status_bar: self.status_bar.update_peers_count(len(self.network_node.known_nodes))


    def remove_remote_object(self, full_clone_id: str):
        """Removes a specific cloned remote object from the scene."""
        if full_clone_id not in self.remote_objects: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return

        scene = self.tamagotchi_logic.user_interface.scene
        with self.remote_objects_lock: # Thread-safe
            object_clone_info = self.remote_objects.pop(full_clone_id, None)

        if object_clone_info:
            visual_item = object_clone_info.get('visual')
            if visual_item and visual_item in scene.items():
                scene.removeItem(visual_item)
            # Remove other associated elements like labels if they existed
            # if self.debug_mode: print(f"Multiplayer: Removed remote object clone: {full_clone_id}.")


    def throw_rock_network(self, rock_graphics_item: QtWidgets.QGraphicsPixmapItem, direction_thrown: str):
        """Broadcasts a 'rock_throw' event when the local player's squid throws a rock."""
        if not self.network_node or not self.network_node.is_connected or not rock_graphics_item:
            return

        try:
            rock_filename = getattr(rock_graphics_item, 'filename', "default_rock.png") # Get filename if available
            initial_pos = rock_graphics_item.pos() # QPointF

            rock_throw_payload = {
                'rock_data': {
                    'filename': rock_filename, # So remote clients can recreate the visual
                    'direction': direction_thrown, # "left" or "right"
                    'initial_pos_x': initial_pos.x(),
                    'initial_pos_y': initial_pos.y(),
                    'scale': rock_graphics_item.scale() if hasattr(rock_graphics_item, 'scale') else 1.0,
                    # Could add thrower_node_id, velocity, angular_velocity if physics are more detailed
                }
            }
            self.network_node.send_message('rock_throw', rock_throw_payload)
            if self.debug_mode:
                print(f"Multiplayer: Broadcasted local rock throw: {os.path.basename(rock_filename)} towards {direction_thrown}.")
        except Exception as e_throw:
            if self.debug_mode: print(f"Multiplayer Error: Broadcasting rock throw failed: {e_throw}")


    def cleanup(self):
        """Cleans up all resources used by the multiplayer plugin (timers, threads, visuals, network node)."""
        print("Multiplayer: Initiating plugin cleanup...")
        self.is_setup = False # Mark as no longer setup/active

        # --- Stop Timers ---
        # Safely stop all QTimers associated with this plugin instance
        timers_to_manage = [
            'message_process_timer', 'controller_update_timer', 'controller_creation_timer',
            'cleanup_timer_basic', 'connection_timer_basic'
        ]
        for timer_attr_name in timers_to_manage:
            timer_instance = getattr(self, timer_attr_name, None)
            if timer_instance and isinstance(timer_instance, QtCore.QTimer) and timer_instance.isActive():
                timer_instance.stop()
                if self.debug_mode: print(f"Multiplayer: Stopped timer '{timer_attr_name}'.")
            setattr(self, timer_attr_name, None) # Clear reference

        # --- Signal Threads to Stop (if applicable) ---
        # For daemon threads like sync_thread, they will stop when the main app exits.
        # If a clean shutdown mechanism is needed for the thread (e.g., using an event):
        # if hasattr(self, 'sync_thread_stop_event') and self.sync_thread_stop_event:
        #    self.sync_thread_stop_event.set() # Signal thread to terminate its loop
        if self.sync_thread and self.sync_thread.is_alive():
             if self.debug_mode: print("Multiplayer: Sync thread was active during cleanup. As a daemon, it will exit with app.")
        self.sync_thread = None # Clear reference


        # --- Network Node Cleanup ---
        if self.network_node:
            if self.network_node.is_connected:
                try: # Send a final "leaving" message
                    self.network_node.send_message(
                        'player_leave',
                        {'node_id': self.network_node.node_id, 'reason': 'plugin_unloaded_or_disabled'}
                    )
                except Exception as e_leave:
                    if self.debug_mode: print(f"Multiplayer: Error sending player_leave message: {e_leave}")
            # Close the socket and clean up NetworkNode resources
            if hasattr(self.network_node.socket, 'close'):
                try:
                    # Unregister from multicast group before closing socket
                    if self.network_node.is_connected and self.network_node.local_ip and MULTICAST_GROUP: # Check for necessary attributes
                        mreq_leave = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(self.network_node.local_ip)
                        self.network_node.socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq_leave)
                except Exception as e_mcast_leave: # Ignore errors if already closed or invalid
                     if self.debug_mode: print(f"Multiplayer: Error leaving multicast group: {e_mcast_leave}")
                finally: # Ensure socket close is attempted
                    try:
                        self.network_node.socket.close()
                    except Exception: pass # Ignore errors on final close
            self.network_node.is_connected = False
            self.network_node.socket = None # Clear socket reference
        self.network_node = None # Clear NetworkNode instance reference

        # --- Clear Visual Representations ---
        # Must be done carefully if scene is managed by Qt's main thread
        # If this cleanup is called from a non-main thread, scene modifications are unsafe.
        # Assuming cleanup is triggered from main thread context (e.g., plugin disable UI action).
        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
            with self.remote_squids_lock:
                for node_id_key in list(self.remote_squids.keys()): self.remove_remote_squid(node_id_key)
            with self.remote_objects_lock:
                for clone_id_key in list(self.remote_objects.keys()): self.remove_remote_object(clone_id_key)
        # Ensure dictionaries are cleared
        self.remote_squids.clear()
        self.remote_objects.clear()
        self.connection_lines.clear()
        self.remote_squid_controllers.clear()

        # --- UI Updates for Cleanup ---
        if self.status_widget: # If dedicated status widget exists
             if hasattr(self.status_widget, 'update_connection_status'): self.status_widget.update_connection_status(False)
             if hasattr(self.status_widget, 'update_peers'): self.status_widget.update_peers({})
             if hasattr(self.status_widget, 'add_activity'): self.status_widget.add_activity("Multiplayer has been shut down.")
             # self.status_widget.hide() # This should be handled by disable() if that's the trigger
        elif self.status_bar: # Fallback main status bar
            if hasattr(self.status_bar, 'update_network_status'): self.status_bar.update_network_status(False)
            if hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(0)
            if hasattr(self.status_bar, 'add_message'): self.status_bar.add_message("Multiplayer plugin shut down.")

        print("Multiplayer plugin cleanup process completed.")

    # --- (Placeholder Handlers for Network Messages - to be fleshed out or rely on object_sync) ---
    def handle_squid_move(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles discrete 'squid_move' messages if used separately from full object_sync."""
        # This is often covered by the more comprehensive 'object_sync' message.
        # If used for high-frequency, low-latency position updates:
        payload = message.get('payload', {})
        sender_node_id = message.get('node_id')
        if sender_node_id and sender_node_id in self.remote_squids:
            # Assuming payload contains at least {'x': ..., 'y': ..., 'direction': ...}
            # Minimal update without full data processing, useful if object_sync is slower.
            current_display_data = self.remote_squids[sender_node_id]
            visual = current_display_data.get('visual')
            if visual:
                visual.setPos(payload['x'], payload['y'])
                self.update_remote_squid_image(current_display_data, payload['direction'])
            # Update minimal data cache
            if 'data' in current_display_data:
                current_display_data['data']['x'] = payload['x']
                current_display_data['data']['y'] = payload['y']
                current_display_data['data']['direction'] = payload['direction']

    def handle_rock_throw(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles 'rock_throw' messages from remote players."""
        # This would involve creating a visual representation of the thrown rock
        # and animating its trajectory based on received data.
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene
        payload = message.get('payload', {}).get('rock_data', {})
        sender_node_id = message.get('node_id')

        if not payload or not sender_node_id: return
        if self.debug_mode: print(f"Multiplayer: Received rock_throw from {sender_node_id[-6:]}, data: {payload}")

        # Example: Create a temporary visual for the thrown rock
        rock_filename = payload.get('filename', os.path.join("images","rock.png")) # Default if not specified
        try:
            pixmap = QtGui.QPixmap(rock_filename)
            if pixmap.isNull(): pixmap = QtGui.QPixmap(os.path.join("images","rock.png")) # Ultimate fallback

            thrown_rock_item = QtWidgets.QGraphicsPixmapItem(pixmap)
            initial_x = payload.get('initial_pos_x', scene.width()/2)
            initial_y = payload.get('initial_pos_y', scene.height()/2)
            thrown_rock_item.setPos(initial_x, initial_y)
            thrown_rock_item.setScale(payload.get('scale', 0.8)) # Smaller scale for thrown rocks
            thrown_rock_item.setZValue(20) # High Z to be visible during flight
            self.apply_foreign_object_tint(thrown_rock_item) # Mark as foreign
            scene.addItem(thrown_rock_item)

            # --- Animation for the thrown rock ---
            # This is a simplified example; real physics would be more complex.
            anim_group = QtCore.QParallelAnimationGroup()
            pos_anim = QtCore.QPropertyAnimation(thrown_rock_item, b"pos")
            pos_anim.setDuration(1500) # Flight time
            pos_anim.setStartValue(QtCore.QPointF(initial_x, initial_y))
            # Target position (e.g., flies off screen)
            throw_dir_str = payload.get('direction', 'right')
            target_x = scene.width() + 50 if throw_dir_str == 'right' else -50
            target_y = initial_y + random.uniform(-50, 50) # Slight vertical arc
            pos_anim.setEndValue(QtCore.QPointF(target_x, target_y))
            pos_anim.setEasingCurve(QtCore.QEasingCurve.OutQuad) # Arc-like trajectory easing

            # Optional: Rotation animation
            # rot_anim = QtCore.QPropertyAnimation(thrown_rock_item, b"rotation") ...

            anim_group.addAnimation(pos_anim)
            anim_group.finished.connect(lambda item=thrown_rock_item: scene.removeItem(item) if item in scene.items() else None)
            anim_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

        except Exception as e_rock_throw_vis:
            if self.debug_mode: print(f"Multiplayer: Error visualizing remote rock throw: {e_rock_throw_vis}")


    def handle_state_update(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles generic 'state_update' messages. Payload structure needs to be defined by sender."""
        # This is a placeholder for custom game state changes that don't fit other categories.
        # Example: a remote player triggered a global weather change, or a shared event.
        payload = message.get('payload', {})
        sender_node_id = message.get('node_id')
        if self.debug_mode: print(f"Multiplayer: Received generic 'state_update' from {sender_node_id[-6:]}. Payload: {payload}")
        # Add logic here based on the content of 'payload' for specific state updates.