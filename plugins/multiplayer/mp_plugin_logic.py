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
from .remote_entity_manager import RemoteEntityManager # Ensure this is imported if type hinting or direct use
from .squid_multiplayer_autopilot import RemoteSquidController # Ensure this for autopilot logic

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
        self.remote_squid_controllers: Dict[str, Any] = {} # Should be RemoteSquidController
        self.pending_controller_creations: List[Dict[str, Any]] = []
        self.connection_lines: Dict[str, QtWidgets.QGraphicsLineItem] = {}
        self.last_message_times: Dict[str, float] = {}

        # --- Configuration ---
        self.MULTICAST_GROUP = mp_constants.MULTICAST_GROUP
        self.MULTICAST_PORT = mp_constants.MULTICAST_PORT
        self.SYNC_INTERVAL = mp_constants.SYNC_INTERVAL
        # MODIFIED for testing: Force full opacity
        self.REMOTE_SQUID_OPACITY = 1.0 # Was mp_constants.REMOTE_SQUID_OPACITY
        self.SHOW_REMOTE_LABELS = mp_constants.SHOW_REMOTE_LABELS
        self.SHOW_CONNECTION_LINES = mp_constants.SHOW_CONNECTION_LINES

        # --- UI Elements ---
        self.config_dialog: QtWidgets.QDialog | None = None
        self.status_widget: Any | None = None # Should be MultiplayerStatusWidget
        self.status_bar: Any | None = None

        # --- Flags ---
        self.is_setup = False
        self.debug_mode = False
        self.last_controller_update = time.time() 
        self.entity_manager: RemoteEntityManager | None = None # Added type hint
        self.config_manager = None # Placeholder, ensure this is set if used (e.g. in handle_squid_exit_message print)

    def _initialize_remote_entity_manager(self):
        """
        Initializes the RemoteEntityManager instance.
        This method encapsulates the logic for creating and configuring
        the RemoteEntityManager.
        """
        if not self.logger:
            # This case should ideally not happen if logger is set up in __init__ or early setup
            print("MPPluginLogic ERRA: Logger not available for _initialize_remote_entity_manager")
            self.entity_manager = None
            return

        if self.tamagotchi_logic and \
           hasattr(self.tamagotchi_logic, 'user_interface') and \
           self.tamagotchi_logic.user_interface and \
           hasattr(self.tamagotchi_logic.user_interface, 'image_cache'): # Check for image_cache

            ui = self.tamagotchi_logic.user_interface
            try:
                self.entity_manager = RemoteEntityManager(
                    scene=ui.scene,
                    window_width=ui.window_width,
                    window_height=ui.window_height,
                    #image_cache=ui.image_cache,  # Pass the image_cache instance
                    debug_mode=self.debug_mode, # self.debug_mode should be set in MpPluginLogic
                    logger=self.logger.getChild("RemoteEntityManager") # Pass a child logger
                )
                self.logger.info("RemoteEntityManager initialized successfully.")
            except ImportError: # Should not happen if imports are correct at file top
                self.logger.error("RemoteEntityManager import failed during initialization. Visuals for remote entities will be basic or non-functional.", exc_info=True)
                self.entity_manager = None
                # self.initialize_remote_representation() # Call your fallback if RemoteEntityManager fails
            except Exception as e_rem:
                self.logger.error(f"Error initializing RemoteEntityManager: {e_rem}", exc_info=True)
                self.entity_manager = None
                # self.initialize_remote_representation() # Call your fallback
        else:
            self.logger.warning("User interface, TamagotchiLogic, or ImageCache not available for RemoteEntityManager setup. Remote visuals may be limited or non-functional.")
            self.entity_manager = None
            # self.initialize_remote_representation() # Call your fallback


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
        self.logger.info("Attempting to enable Multiplayer...")

        # Plugin already set up?
        if not self.is_setup:
            self.logger.info("Multiplayer plugin is not set up. Calling setup()...")
            # Assuming self.plugin_manager and self.tamagotchi_logic_ref are available
            if not self.setup(self.plugin_manager, self.tamagotchi_logic_ref): # Pass necessary args
                self.logger.error("Multiplayer setup failed during enable(). Cannot enable.")
                return False
        else:
            self.logger.info("Multiplayer is already marked as set up. Re-enabling components.")

        # --- BEGIN NEW/MODIFIED SECTION ---
        # Ensure network node is ready and listening
        if self.network_node:
            # Ensure the socket structure is initialized (it should be by NetworkNode.__init__ or a previous setup)
            # but a re-check or re-init if disconnected can be robust.
            if not self.network_node.is_connected:
                self.logger.info("NetworkNode socket not connected, attempting to initialize in enable()...")
                if not self.network_node.initialize_socket_structure():
                    self.logger.error("Failed to initialize NetworkNode socket in enable(). Cannot proceed with enabling multiplayer.")
                    # Potentially set self.enabled = False or similar state management
                    return False # Or handle error appropriately

            # Explicitly start the listener thread if it's not already active
            if not self.network_node.is_listening():
                self.logger.info("NetworkNode listener not active, starting it explicitly in enable()...")
                if not self.network_node.start_listening():
                    self.logger.error("Failed to start NetworkNode listener in enable(). Multiplayer might not receive messages.")
                    # Decide if this is a fatal error for enabling or just a warning
                    # For now, let's treat it as potentially non-fatal but log an error.
                    # Depending on requirements, you might return False here.
                else:
                    self.logger.info(">>>>>> NetworkNode listener started successfully!")
            else:
                self.logger.info("NetworkNode listener was already active.")
        else:
            self.logger.error("NetworkNode not found after setup in enable(). Cannot enable multiplayer fully.")
            # Potentially set self.enabled = False
            return False # This is likely a critical failure
        # --- END NEW/MODIFIED SECTION ---

        # Resume original enable logic:
        # For example, re-initialize UI components, timers, etc.
        # Ensure any components that were disabled are re-enabled.

        # Re-initialize or ensure timers are running (if they were stopped in disable)
        if not self.message_process_timer or not self.message_process_timer.isActive():
            if not self.message_process_timer:
                self.message_process_timer = QtCore.QTimer()
                self.message_process_timer.timeout.connect(self._process_network_node_queue)
            self.message_process_timer.start(50)
            self.logger.info("Message processing timer started/restarted.")

        if not (hasattr(self, 'sync_timer') and self.sync_timer and self.sync_timer.isActive()):
            # Assuming start_sync_timer handles creation if necessary and starts it
            self.logger.info("Sync timer not active, starting/restarting it.")
            self.start_sync_timer()
        
        # Update status widget if applicable
        if self.status_widget:
            self.status_widget.update_status("Enabled", True)
            current_ip = self.network_node.local_ip if self.network_node else "N/A"
            self.status_widget.set_ip_address(current_ip)

        self.enabled = True # Mark as enabled
        self.logger.info("Multiplayer enabled successfully.")
        return True

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
            self.logger = self.plugin_manager.logger.getChild(mp_constants.PLUGIN_NAME) # Get a child logger is good practice
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
        
        # Attempt to get config_manager from plugin_manager if available (for the print in handle_squid_exit)
        if hasattr(plugin_manager_instance, 'config_manager'):
             self.config_manager = plugin_manager_instance.config_manager
        elif hasattr(tamagotchi_logic_instance, 'config_manager'): # Check on tamagotchi_logic as well
             self.config_manager = tamagotchi_logic_instance.config_manager
        else:
             self.logger.warning("ConfigManager not found for debug print in handle_squid_exit_message.")
             # Create a dummy if needed for the print to not error out, or handle it in the print
             class DummyConfigManager:
                 def get_node_id(self): return "UnknownNodeID_Setup" # Differentiate if needed
             if not hasattr(self, 'config_manager') or self.config_manager is None : # Set only if not already set
                self.config_manager = DummyConfigManager()


        self.tamagotchi_logic = tamagotchi_logic_instance

        if not TamagotchiLogic: # Class itself
            self.logger.critical("TamagotchiLogic module was not loaded (import failed). Cannot complete setup.")
            return False

        if self.tamagotchi_logic is None: # Instance
            self.logger.warning("TamagotchiLogic instance was not directly passed or was None. Attempting to find it via PluginManager.")
            if hasattr(self.plugin_manager, 'core_game_logic'):
                self.tamagotchi_logic = self.plugin_manager.core_game_logic
            elif hasattr(self.plugin_manager, 'tamagotchi_logic'): # Common attribute name
                self.tamagotchi_logic = self.plugin_manager.tamagotchi_logic
            else: # Fallback deep search
                self.tamagotchi_logic = self._find_tamagotchi_logic(self.plugin_manager)

        if not self.tamagotchi_logic:
            self.logger.critical("TamagotchiLogic instance not found. Plugin functionality will be severely limited.")
            # return False # Decided to proceed with limited functionality if UI parts are missing
        else:
            self.debug_mode = getattr(self.tamagotchi_logic, 'debug_mode', False)
            if self.logger and hasattr(self.logger, 'setLevel'): # Make sure logger has setLevel
                 self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
            self.logger.info(f"TamagotchiLogic instance found. Debug mode: {self.debug_mode}")

        node_id_val = f"squid_{uuid.uuid4().hex[:6]}"
        self.network_node = NetworkNode(node_id_val, logger=self.logger)
        self.network_node.debug_mode = self.debug_mode # Pass debug mode to network node
        
        if self.tamagotchi_logic: # Ensure tamagotchi_logic exists before setting attribute
            setattr(self.tamagotchi_logic, 'multiplayer_network_node', self.network_node)

        if not self.message_process_timer:
            self.message_process_timer = QtCore.QTimer()
            self.message_process_timer.timeout.connect(self._process_network_node_queue)
            self.message_process_timer.start(50) # Process queue every 50ms

        if not self.controller_update_timer:
            self.controller_update_timer = QtCore.QTimer()
            self.controller_update_timer.timeout.connect(self.update_remote_controllers)
            self.controller_update_timer.start(50) # Update controllers every 50ms

        if not self.controller_creation_timer:
             self._setup_controller_creation_timer() # For deferred controller creation

        self._register_hooks() # Register message handlers

        # Clear previous state
        self.remote_squids.clear()
        self.remote_objects.clear()
        self.connection_lines.clear()
        self.remote_squid_controllers.clear()
        self.last_controller_update = time.time()


        # === MODIFIED RemoteEntityManager Instantiation Block START ===
        if self.tamagotchi_logic and \
           hasattr(self.tamagotchi_logic, 'user_interface') and \
           self.tamagotchi_logic.user_interface:

            ui = self.tamagotchi_logic.user_interface # This is the GameWindow instance

            # Removed check for ui.image_cache as it's no longer passed or needed by RemoteEntityManager
            try:
                # RemoteEntityManager should be imported at the top of mp_plugin_logic.py
                self.entity_manager = RemoteEntityManager(
                    scene=ui.scene,
                    window_width=ui.window_width,
                    window_height=ui.window_height,
                    # image_cache=ui.image_cache,  # <<< THIS LINE IS REMOVED
                    debug_mode=self.debug_mode, # Correct: Pass the debug_mode boolean
                    logger=self.logger.getChild("RemoteEntityManager") # Good practice for logger
                )
                self.logger.info("RemoteEntityManager initialized.")
            except ImportError: # Should be caught if RemoteEntityManager isn't imported
                self.logger.error("RemoteEntityManager class import failed. Visuals for remote entities will be basic or non-functional.", exc_info=True)
                self.entity_manager = None
                self.initialize_remote_representation() # Your fallback
            except Exception as e_rem:
                self.logger.error(f"Error initializing RemoteEntityManager: {e_rem}", exc_info=True)
                self.entity_manager = None
                self.initialize_remote_representation() # Your fallback
        else:
            self.logger.warning("User interface or TamagotchiLogic not available for RemoteEntityManager setup. Remote visuals may be limited.")
            self.entity_manager = None
            self.initialize_remote_representation() # Your fallback
        # === MODIFIED RemoteEntityManager Instantiation Block END ===

        self.initialize_status_ui() # Initialize status widget or bar

        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'show_message') and self.network_node:
            self.tamagotchi_logic.show_message(f"Multiplayer active! Node ID: {self.network_node.node_id}")

        node_ip = self.network_node.local_ip if self.network_node else "N/A"
        node_port = self.MULTICAST_PORT # Use the constant
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
                fallback_path = os.path.join(base_image_path, "right1.png") # Default fallback
                squid_pixmap = QtGui.QPixmap(fallback_path)
                if squid_pixmap.isNull() and self.debug_mode:
                    self.logger.warning(f"Could not load squid image '{full_image_path}' or fallback '{fallback_path}'.")
                    # Create a colored square as an ultimate fallback if even "right1.png" fails
                    squid_pixmap = QtGui.QPixmap(60,40) # Default size
                    squid_color = remote_squid_display_data.get('data',{}).get('color',(128,128,128))
                    squid_pixmap.fill(QtGui.QColor(*squid_color))

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
                self.tamagotchi_logic.show_message(f"氏 Your squid exchanged gifts with {remote_node_id[-6:]}!")
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
        stats_form.addRow("Messages Sent (Total):", QtWidgets.QLabel(str(getattr(self.network_node, 'total_sent_count', 'N/A'))))
        stats_form.addRow("Messages Received (Total):", QtWidgets.QLabel(str(getattr(self.network_node, 'total_received_count', 'N/A'))))
        main_layout.addWidget(stats_group)


        def refresh_dashboard_data():
            # Update connection status
            is_connected = self.network_node.is_connected
            status_val_label.setText("Connected" if is_connected else "Disconnected")
            status_val_label.setStyleSheet("color: green; font-weight: bold;" if is_connected else "color: red; font-weight: bold;")

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


    def _find_tamagotchi_logic(self, search_object, depth=0, visited_ids=None):
        """Recursively searches for an attribute named 'tamagotchi_logic'."""
        if not self.logger: return None # Should not happen if called after setup
        if visited_ids is None: visited_ids = set()
        
        if id(search_object) in visited_ids or depth > 6: # Prevent deep recursion / cycles
            return None
        visited_ids.add(id(search_object))

        # Direct check: Is the search_object itself the TamagotchiLogic instance?
        if TamagotchiLogic and isinstance(search_object, TamagotchiLogic):
            return search_object
        
        # Check for a 'tamagotchi_logic' attribute specifically
        if hasattr(search_object, 'tamagotchi_logic'):
            tl_attr = getattr(search_object, 'tamagotchi_logic')
            if TamagotchiLogic and isinstance(tl_attr, TamagotchiLogic):
                return tl_attr
        
        # Iterate through attributes if it's not a basic type or module
        try:
            for attr_name in dir(search_object):
                if attr_name.startswith('_'): continue # Skip private/magic attributes

                try:
                    attr_value = getattr(search_object, attr_name)
                    
                    # Avoid recursing into very common or problematic types
                    if attr_value is None or isinstance(attr_value, (int, str, bool, float, list, dict, set, tuple, bytes)):
                        continue
                    if inspect.ismodule(attr_value) or inspect.isbuiltin(attr_value) or inspect.isroutine(attr_value):
                        continue
                    # Be careful with Qt parent traversals to avoid excessive depth or cycles
                    if isinstance(attr_value, (QtWidgets.QWidget, QtCore.QObject)):
                         if depth > 2 and attr_name in ['parent', 'parentWidget', 'parentItem']: # Limit depth for parent attributes
                            continue
                            
                    found_logic = self._find_tamagotchi_logic(attr_value, depth + 1, visited_ids)
                    if found_logic: return found_logic
                except (AttributeError, RecursionError, TypeError, ReferenceError): # Catch errors during getattr or recursion
                    continue
        except (RecursionError, TypeError, ReferenceError): # Catch errors from dir() or initial checks
            pass # Could happen with problematic objects
            
        return None

    def _animate_remote_squid_entry(self, squid_graphics_item, status_text_item, entry_direction_str):
        """MODIFIED: Animates (or rather, just shows) the visual entry of a remote squid."""
        if not self.logger: return
        if not squid_graphics_item: return

        # Directly set opacity to full (or the plugin's setting)
        squid_graphics_item.setOpacity(self.REMOTE_SQUID_OPACITY) # REMOTE_SQUID_OPACITY is 1.0 for testing
        squid_graphics_item.setScale(1.0) # Ensure normal scale

        if squid_graphics_item.graphicsEffect(): # Remove any prior effect
            squid_graphics_item.setGraphicsEffect(None)

        if status_text_item:
            status_text_item.setOpacity(1.0) # Make status text fully visible
            if status_text_item.graphicsEffect(): # Remove any prior effect
                status_text_item.setGraphicsEffect(None)
        
        if self.debug_mode:
            self.logger.debug(f"Static display for remote squid entry: {entry_direction_str}")


    def get_opposite_direction(self, direction_str: str) -> str:
        """Returns the opposite of a given cardinal direction string."""
        opposites = {'left': 'right', 'right': 'left', 'up': 'down', 'down': 'up'}
        return opposites.get(direction_str.lower(), 'right') # Default if unknown

    def create_entry_effect(self, center_x: float, center_y: float, direction_str: str = ""):
        """Creates a visual effect at the point where a remote squid enters the scene.
           MODIFIED: This effect will be static or very simple for testing."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene

        # Simplified static indicator (e.g., a small, briefly visible circle or text)
        # For testing, we can even skip this visual flourish if the goal is just to see the squid.
        if self.debug_mode:
            self.logger.debug(f"Skipping dynamic entry effect for static testing at ({center_x},{center_y}).")
        
        # If you still want a minimal static cue:
        # arrival_text_str = "New Visitor"
        # arrival_text_item = scene.addText(arrival_text_str)
        # arrival_font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
        # arrival_text_item.setFont(arrival_font)
        # text_metrics = QtGui.QFontMetrics(arrival_font)
        # text_rect = text_metrics.boundingRect(arrival_text_str)
        # arrival_text_item.setDefaultTextColor(QtGui.QColor(255, 215, 0)) # Gold
        # arrival_text_item.setPos(center_x - text_rect.width() / 2, center_y - 60) # Position above entry
        # arrival_text_item.setZValue(100)
        # arrival_text_item.setVisible(True)
        # # Timer to remove it after a short period if desired, or let it persist.
        # QtCore.QTimer.singleShot(3000, lambda: scene.removeItem(arrival_text_item) if arrival_text_item.scene() else None)

    def _setup_controller_immediately(self, node_id: str, squid_initial_data: Dict):
        """Creates and initializes a RemoteSquidController."""
        if not self.logger: return
        try:
            # from plugins.multiplayer.squid_multiplayer_autopilot import RemoteSquidController # Already at top
            pass # Ensure it's imported
        except ImportError:
            if self.debug_mode: self.logger.error("RemoteSquidController module not found. Remote squids will not be autonomous.")
            return

        if node_id in self.remote_squid_controllers:
            if self.debug_mode: self.logger.debug(f"Controller for squid {node_id[-6:]} already exists. Updating its data.")
            # Ensure squid_data includes x,y if updating position via controller
            self.remote_squid_controllers[node_id].squid_data.update(squid_initial_data)
            # Potentially trigger a state re-evaluation in the controller if data changed significantly
            # self.remote_squid_controllers[node_id].evaluate_state() # If such a method exists
            return

        if self.debug_mode: self.logger.info(f"Creating autopilot controller for remote squid {node_id[-6:]}.")
        try:
            controller_instance = RemoteSquidController(
                squid_data=squid_initial_data, # This now contains x,y from entry_details if available
                scene=self.tamagotchi_logic.user_interface.scene,
                plugin_instance=self, # Pass self (MultiplayerPlugin instance)
                debug_mode=self.debug_mode,
                remote_entity_manager=self.entity_manager # Pass the entity manager
            )
            self.remote_squid_controllers[node_id] = controller_instance
            if self.debug_mode: self.logger.info(f"Controller for {node_id[-6:]} created. Initial state: {getattr(controller_instance, 'state', 'N/A')}")
        except Exception as e_create:
            self.logger.error(f"Failed to create RemoteSquidController for {node_id[-6:]}: {e_create}", exc_info=True)
            return
            
        # Ensure the controller update timer is running
        if self.controller_update_timer and not self.controller_update_timer.isActive():
            self.controller_update_timer.start()
            if self.debug_mode: self.logger.debug("Restarted controller update timer.")


    def handle_squid_exit_message(self, node: Any, message: Dict, addr: tuple):
        # Ensure config_manager is available or provide a default for the print
        node_id_for_print = "UnknownNode_HandleExit"
        if hasattr(self, 'config_manager') and self.config_manager and hasattr(self.config_manager, 'get_node_id'):
            node_id_for_print = self.config_manager.get_node_id()
        elif self.network_node: # Fallback to network_node's ID if config_manager not fully set up
            node_id_for_print = self.network_node.node_id
        
        print(f"DEBUG_STEP_1: Node {node_id_for_print} - handle_squid_exit_message CALLED. Message type: {message.get('type')}, Full message: {message}")

        if not self.logger: 
            print("MPPluginLogic ERRA: Logger not available in handle_squid_exit_message")
            return False 

        try:
            self.logger.info(f"MY NODE ID {self.network_node.node_id if self.network_node else 'Unknown'} - Received squid_exit message: {message} from {addr}")

            exit_payload_outer = message.get('payload', {})
            exit_payload_inner = exit_payload_outer.get('payload', None) # This is the actual exit_data
            
            if not exit_payload_inner:
                self.logger.warning("squid_exit message missing a nested 'payload' key containing the actual exit data.")
                return False

            source_node_id = exit_payload_inner.get('node_id')
            if not source_node_id:
                self.logger.warning("squid_exit inner payload missing 'node_id'.")
                return False

            if self.network_node and source_node_id == self.network_node.node_id:
                # This instance is the one that sent the exit message. Ignore.
                self.logger.debug(f"Ignoring own squid_exit broadcast for {source_node_id}.")
                return False # Important: do not process self-exit as an arrival

            self.logger.info(f"Processing squid_exit from REMOTE node {source_node_id} for potential entry.")
            self.logger.info(f"Exit payload from remote: {exit_payload_inner}")

            if hasattr(self, 'entity_manager') and self.entity_manager:
                # update_remote_squid now expects the exit_payload_inner (actual exit_data)
                # It will handle making the squid visible immediately and statically.
                update_success = self.entity_manager.update_remote_squid(
                    source_node_id,
                    exit_payload_inner, 
                    is_new_arrival=True # Signal to RemoteEntityManager that this is a new arrival
                )
                # self.logger.info(f"Called entity_manager.update_remote_squid for {source_node_id}. Result: {update_success}")
                
                # The visual item is created/updated by entity_manager.
                # Autopilot creation can proceed if update_success (which is a boolean) is True.
                if update_success:
                    # Ensure RemoteSquidController is imported
                    # from .squid_multiplayer_autopilot import RemoteSquidController # (Already at top)

                    if source_node_id not in self.remote_squid_controllers:
                        self.logger.info(f"Creating new autopilot for remote squid {source_node_id}")
                        
                        # Prepare initial data for the autopilot.
                        # The autopilot might use entry_details to set its initial position/target.
                        entry_details = self.entity_manager.get_last_calculated_entry_details(source_node_id)
                        initial_autopilot_data = exit_payload_inner.copy() # Start with original exit data
                        if entry_details:
                            # Override x,y with calculated entry positions for this screen
                            initial_autopilot_data['x'], initial_autopilot_data['y'] = entry_details['entry_pos']
                            # Add the direction of entry on this screen, useful for autopilot's initial logic
                            initial_autopilot_data['entry_direction_on_this_screen'] = entry_details['entry_direction']
                        else: # Fallback if entry details somehow not available
                            self.logger.warning(f"Entry details not found for {source_node_id} when creating autopilot. Autopilot will use direct exit payload positions.")
                            # Autopilot will use x,y from exit_payload_inner if entry_details are missing
                        
                        try:
                            autopilot_controller = RemoteSquidController(
                                squid_data=initial_autopilot_data, # Pass full data, including potential entry pos & direction
                                scene=self.tamagotchi_logic.user_interface.scene,
                                plugin_instance=self, # Pass this MultiplayerPlugin instance
                                debug_mode=self.debug_mode,
                                remote_entity_manager=self.entity_manager # Pass manager reference
                            )
                            self.remote_squid_controllers[source_node_id] = autopilot_controller
                            self.logger.info(f"Autopilot for {source_node_id} created. Initial target might be set by controller based on entry data.")
                            
                            # Autopilot's constructor or its first update can now use the 'entry_direction_on_this_screen'
                            # and its calculated 'x' and 'y' to set an initial movement target.
                            # For example, the autopilot's __init__ or an initial_setup method could call:
                            # self.set_initial_entry_target() if 'entry_direction_on_this_screen' in self.squid_data: ...

                        except Exception as e_auto:
                             self.logger.error(f"Error creating RemoteSquidController for {source_node_id}: {e_auto}", exc_info=True)
                    else:
                        self.logger.info(f"Autopilot controller for {source_node_id} already exists. Updating its data if necessary.")
                        # Optionally update existing autopilot if needed:
                        # self.remote_squid_controllers[source_node_id].update_squid_data(exit_payload_inner) # if such a method exists and is appropriate
                else:
                    self.logger.warning(f"Failed to create or update remote squid {source_node_id} in entity_manager. Autopilot not created/updated.")
            else:
                self.logger.error("Remote entity manager (self.entity_manager) not found or not initialized!")
            
            return True # Indicate successful processing attempt

        except Exception as e:
            self.logger.error(f"Error in handle_squid_exit_message: {e}", exc_info=True)
            return False

    def _setup_controller_creation_timer(self):
        """(Fallback) Sets up a QTimer to process pending controller creations."""
        if not self.logger: return
        if self.controller_creation_timer and self.controller_creation_timer.isActive():
            return # Already running
        if not self.controller_creation_timer:
            self.controller_creation_timer = QtCore.QTimer()
            self.controller_creation_timer.timeout.connect(self._process_pending_controller_creations)
        self.controller_creation_timer.start(300) # Check every 300ms
        if self.debug_mode: self.logger.debug("Fallback controller creation timer started.")

    def _process_pending_controller_creations(self):
        """(Fallback) Processes remote squids waiting for controllers."""
        if not self.logger: return
        if not hasattr(self, 'pending_controller_creations') or not self.pending_controller_creations:
            return

        items_to_process = list(self.pending_controller_creations) # Copy for safe iteration
        self.pending_controller_creations.clear() # Clear original list

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
        if delta_time <= 0.001: return # Avoid division by zero or tiny updates
        self.last_controller_update = current_time

        for node_id, controller in list(self.remote_squid_controllers.items()): # Iterate over a copy
            try:
                controller.update(delta_time) # Call the controller's update method
                updated_squid_data_from_controller = controller.squid_data # Get potentially modified data

                # Update visuals if entity_manager is NOT being used or if this plugin directly manages basic visuals
                if not self.entity_manager and node_id in self.remote_squids:
                    remote_squid_display = self.remote_squids[node_id]
                    visual = remote_squid_display.get('visual')
                    status_text = remote_squid_display.get('status_text')

                    if visual:
                        visual.setPos(updated_squid_data_from_controller['x'], updated_squid_data_from_controller['y'])
                        self.update_remote_squid_image(remote_squid_display, updated_squid_data_from_controller['direction'])
                    
                    if status_text:
                        current_status_on_display = status_text.toPlainText()
                        new_status_from_controller = updated_squid_data_from_controller.get('status', 'exploring')
                        # Update text if it changed or if it's a special "arrival" type status
                        if current_status_on_display.upper() != new_status_from_controller.upper() or \
                           new_status_from_controller.upper() in ["ARRIVING", "ENTERING", "RETURNING..."]:
                            status_text.setPlainText(new_status_from_controller)
                        status_text.setPos(updated_squid_data_from_controller['x'], updated_squid_data_from_controller['y'] - 35) # Adjust offset

                    # Handle view cone update via this plugin's method if no entity_manager
                    if updated_squid_data_from_controller.get('view_cone_visible', False):
                        self.update_remote_view_cone(node_id, updated_squid_data_from_controller) # This is mp_plugin_logic's method
                    elif remote_squid_display.get('view_cone'): # If cone was visible but now isn't
                         if self.tamagotchi_logic and hasattr(self.tamagotchi_logic.user_interface, 'scene'):
                            cone = remote_squid_display['view_cone']
                            if cone in self.tamagotchi_logic.user_interface.scene.items():
                                self.tamagotchi_logic.user_interface.scene.removeItem(cone)
                            remote_squid_display['view_cone'] = None
                
                elif self.entity_manager:
                    # If entity_manager exists, it's responsible for updating the visual representation based on controller's data
                    # The controller should ideally call entity_manager.update_remote_squid directly,
                    # or this method needs to pass the controller's data to entity_manager.
                    # For now, assume controller's changes might be picked up by entity_manager if it polls,
                    # or better: controller calls entity_manager.
                    # Let's add a call here for robustness if controller doesn't.
                    self.entity_manager.update_remote_squid(node_id, updated_squid_data_from_controller, is_new_arrival=False)


            except Exception as e:
                self.logger.error(f"Updating controller for {node_id[-6:]} failed: {e}", exc_info=True)
                # Consider removing the controller if it consistently errors
                # del self.remote_squid_controllers[node_id]


    def calculate_entry_position(self, entry_side_direction: str) -> tuple:
        """Calculates X,Y coordinates for a squid entering this local screen."""
        if not self.logger: return (100,100) # Default fallback
        if not self.tamagotchi_logic or not self.tamagotchi_logic.user_interface:
            return (100, 100) # Fallback if UI not available
        
        window_w = self.tamagotchi_logic.user_interface.window_width
        window_h = self.tamagotchi_logic.user_interface.window_height
        margin = 70 # How far from the edge it should appear

        if entry_side_direction == 'left':   return (margin, window_h / 2)
        elif entry_side_direction == 'right':return (window_w - margin, window_h / 2)
        elif entry_side_direction == 'up':   return (window_w / 2, margin)
        elif entry_side_direction == 'down': return (window_w / 2, window_h - margin)
        
        return (window_w / 2, window_h / 2) # Default to center if direction unknown


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
                local_squid.hunger = max(0, local_squid.hunger - 10 * food_eaten) # Reduce hunger
                mm.add_short_term_memory('travel', 'ate_on_trip', f"Found {food_eaten} yummy treats on my trip!", 5)
            if rocks_interacted > 0:
                journey_desc += f"Played with {rocks_interacted} interesting rocks. "
                local_squid.happiness = min(100, local_squid.happiness + 3 * rocks_interacted) # Increase happiness
                mm.add_short_term_memory('travel', 'played_on_trip', f"Played with {rocks_interacted} cool rocks elsewhere!", 4)
            
            mm.add_short_term_memory('travel', 'completed_journey', journey_desc, importance=7)

            if food_eaten > 1 or rocks_interacted > 3 or rocks_brought_back > 0:
                mm.add_short_term_memory('emotion', 'happy_return', "It's great to be back home after an exciting adventure!", 6)
            else:
                mm.add_short_term_memory('emotion', 'calm_return', "Returned home. It was a quiet trip.", 3)

        if hasattr(local_squid, 'curiosity'): # Reduce curiosity after travel
            local_squid.curiosity = max(0, local_squid.curiosity - 25)

    def create_exit_effect(self, center_x: float, center_y: float, direction_str: str = ""):
        """Creates a visual effect when a local squid exits the screen.
           MODIFIED: This effect will be static or very simple for testing."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        # scene = self.tamagotchi_logic.user_interface.scene # Scene not used if no visual effects

        # Simplified static indicator (e.g., a small, briefly visible circle or text)
        if self.debug_mode:
            self.logger.debug(f"Skipping dynamic exit effect for static testing at ({center_x},{center_y}).")

        # If you still want a minimal static cue:
        # travel_text_str = "Off to explore!"
        # travel_text_item = scene.addText(travel_text_str)
        # travel_font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
        # travel_text_item.setFont(travel_font)
        # text_metrics = QtGui.QFontMetrics(travel_font)
        # text_rect = text_metrics.boundingRect(travel_text_str)
        # travel_text_item.setDefaultTextColor(QtGui.QColor(173, 216, 230)) # Light blue
        # travel_text_item.setPos(center_x - text_rect.width() / 2, center_y + 30) # Position below exit
        # travel_text_item.setZValue(100)
        # travel_text_item.setVisible(True)
        # QtCore.QTimer.singleShot(2500, lambda: scene.removeItem(travel_text_item) if travel_text_item.scene() else None)

    # Inside MultiplayerPlugin class in mp_plugin_logic.py

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
        local_squid.squid_item.setOpacity(1.0) 
        if local_squid.squid_item.graphicsEffect():
            local_squid.squid_item.graphicsEffect().setEnabled(False)
            local_squid.squid_item.setGraphicsEffect(None)

        self.apply_remote_experiences(local_squid, activity_summary)

        # --- START NEW/MODIFIED SECTION for handling stolen items ---
        stolen_item_id = activity_summary.get('stolen_item_id')
        stolen_item_type = activity_summary.get('stolen_item_type') # 'rock' or 'decoration'

        if stolen_item_id and stolen_item_type:
            if self.debug_mode:
                self.logger.info(f"Squid returned with stolen item: Type={stolen_item_type}, ID/Details='{stolen_item_id}'")

            # Call TamagotchiLogic to create the stolen item in the tank
            if hasattr(self.tamagotchi_logic, 'add_stolen_item_to_tank'):
                # Pass entry_coords so the item can appear near where the squid returned
                created_item = self.tamagotchi_logic.add_stolen_item_to_tank(
                    item_type=stolen_item_type,
                    item_details=stolen_item_id, # This could be a filename or other identifier
                    spawn_position=entry_coords 
                )
                if created_item: # add_stolen_item_to_tank should return the item or True
                    self.apply_foreign_object_tint(created_item) # Ensure red tint
                    if hasattr(self.tamagotchi_logic, 'show_message'):
                        self.tamagotchi_logic.show_message(f"脂 Your squid returned with a souvenir {stolen_item_type}!")
                    if hasattr(local_squid, 'memory_manager'):
                         local_squid.memory_manager.add_short_term_memory(
                            'achievement', f'{stolen_item_type}_heist',
                            f"Brought back a {stolen_item_type} from an adventure!", importance=8
                        )
                else:
                    if self.debug_mode: self.logger.warning(f"TamagotchiLogic.add_stolen_item_to_tank failed for {stolen_item_type}.")
            else:
                if self.debug_mode: self.logger.error("TamagotchiLogic does not have 'add_stolen_item_to_tank' method.")

        # Remove or adapt the old create_stolen_rocks if it's now redundant
        # num_stolen_rocks = activity_summary.get('rocks_stolen', 0) # This was from the old summary key
        # if num_stolen_rocks > 0 and not (stolen_item_type == 'rock' and stolen_item_id): # Avoid double-counting if new system handled it
        #     self.create_stolen_rocks(local_squid, num_stolen_rocks, entry_coords) # Old method
        #     if hasattr(self.tamagotchi_logic, 'show_message'):
        #         self.tamagotchi_logic.show_message(f"脂 Your squid returned with {num_stolen_rocks} souvenir rocks!")
        # --- END NEW/MODIFIED SECTION ---

        else: # No specific stolen item, just general return message
            if hasattr(self.tamagotchi_logic, 'show_message'):
                journey_time_sec = activity_summary.get('time_away', 0)
                time_str = f"{int(journey_time_sec/60)}m {int(journey_time_sec%60)}s"
                self.tamagotchi_logic.show_message(f"ｦ�Welcome back! Your squid explored for {time_str}.")

        local_squid.can_move = True 
        if hasattr(local_squid, 'is_transitioning'): local_squid.is_transitioning = False
        local_squid.status = "just returned home"

        if self.debug_mode: self.logger.debug(f"Local squid '{local_squid.name if hasattr(local_squid,'name') else ''}' returned to position {entry_coords} from {entry_side}.")

    except Exception as e:
        self.logger.error(f"Handling local squid's return failed: {e}", exc_info=True)

    def _create_arrival_animation(self, graphics_item: QtWidgets.QGraphicsPixmapItem):
        """MODIFIED: Creates a simple fade-in animation (now static) for newly arrived remote items."""
        if not self.logger: return
        if not graphics_item: return
        try:
            # For static testing, just ensure opacity and scale are correct
            target_opacity = self.REMOTE_SQUID_OPACITY # Should be 1.0
            if hasattr(graphics_item, 'is_remote_clone') and getattr(graphics_item, 'is_remote_clone'):
                # Cloned objects might have a slightly different base opacity if desired, but for squid, full.
                pass #  target_opacity *= 0.75 (example if clones were different)
            
            graphics_item.setOpacity(target_opacity)
            graphics_item.setScale(1.0) # Ensure normal scale

            if graphics_item.graphicsEffect(): # Remove any prior opacity effect
                graphics_item.setGraphicsEffect(None)

        except Exception as e:
            if self.debug_mode: self.logger.warning(f"Simple static arrival display error: {e}")
            if graphics_item: graphics_item.setOpacity(self.REMOTE_SQUID_OPACITY) # Fallback


    def _reset_remote_squid_style(self, node_id_or_item):
        """Resets the visual style of a remote squid to default (static, full opacity)."""
        if not self.logger: return
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
        
        if not squid_display_data: return # Squid not found

        visual_item = squid_display_data.get('visual')
        status_text_item = squid_display_data.get('status_text')
        id_text_item = squid_display_data.get('id_text')

        if visual_item:
            visual_item.setZValue(5) # Default Z-order for remote squids
            visual_item.setOpacity(self.REMOTE_SQUID_OPACITY) # Ensure full opacity
            visual_item.setScale(1.0) # Ensure normal scale
            if visual_item.graphicsEffect(): # Remove any effects (like shadow or previous opacity effects)
                visual_item.setGraphicsEffect(None)
        
        # Reset status text style
        if status_text_item:
            current_status_from_data = squid_display_data.get('data', {}).get('status', 'visiting')
            status_text_item.setPlainText(current_status_from_data)
            status_text_item.setDefaultTextColor(QtGui.QColor(200, 200, 200, 220)) # Default color
            status_text_item.setFont(QtGui.QFont("Arial", 9)) # Default font
            status_text_item.setZValue(6) # Above squid

        # Reset ID text style (usually less dynamic)
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
        if self.entity_manager:
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


    def initialize_remote_representation(self):
        """(Fallback) Initializes basic timers for managing remote entity visuals if entity_manager is not used."""
        if not self.logger: return
        if self.entity_manager: # If entity_manager is active, it handles these.
            if self.debug_mode: self.logger.debug("RemoteEntityManager is active, skipping fallback timers.")
            return

        if not self.cleanup_timer_basic:
            self.cleanup_timer_basic = QtCore.QTimer()
            self.cleanup_timer_basic.timeout.connect(self.cleanup_stale_nodes) # Fallback cleanup
            self.cleanup_timer_basic.start(7500) # Check every 7.5s
        
        if not self.connection_timer_basic:
            self.connection_timer_basic = QtCore.QTimer()
            self.connection_timer_basic.timeout.connect(self.update_connection_lines) # Fallback line drawing
            self.connection_timer_basic.start(1200) # Update lines every 1.2s


    def cleanup_stale_nodes(self):
        """(Fallback) Removes visuals of remote nodes that haven't sent updates, used if entity_manager is None."""
        if not self.logger: return
        if self.entity_manager: return # entity_manager handles its own cleanup

        if not self.network_node: return
        current_time = time.time()
        stale_threshold_seconds = 45.0 # Example: 45 seconds timeout
        
        nodes_to_remove_ids = []
        # Check known_nodes from NetworkNode
        for node_id, (_, last_seen_time, _) in list(self.network_node.known_nodes.items()):
            if current_time - last_seen_time > stale_threshold_seconds:
                nodes_to_remove_ids.append(node_id)
        
        for node_id_to_remove in nodes_to_remove_ids:
            if self.debug_mode: self.logger.debug(f"Basic Cleanup: Node {node_id_to_remove[-6:]} timed out. Removing.")
            if node_id_to_remove in self.network_node.known_nodes:
                del self.network_node.known_nodes[node_id_to_remove]
            
            # Remove visual representation using this plugin's direct management
            self.remove_remote_squid(node_id_to_remove) # This uses self.remote_squids
            
            if node_id_to_remove in self.remote_squid_controllers: # Also remove controller
                del self.remote_squid_controllers[node_id_to_remove]

        # Update UI status
        if self.network_node: # Check again as it might be cleaned up
            peers_now = self.network_node.known_nodes if self.network_node else {}
            if self.status_widget: self.status_widget.update_peers(peers_now)
            elif self.status_bar and hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(len(peers_now))


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
            "on_network_state_update": self.handle_state_update, # Generic state update
            # Add new 'squid_return' handler
            "on_network_squid_return": self.handle_squid_return 
        }

        for hook_name_to_register, handler_method_to_call in hook_handlers.items():
            if hook_name_to_register == "on_network_squid_exit": 
                node_id_for_print_hook = "UnknownNode_HookReg"
                if self.network_node: node_id_for_print_hook = self.network_node.node_id
                print(f"DEBUG_STEP_2B: MultiplayerPluginLogic {node_id_for_print_hook} is subscribing '{handler_method_to_call.__name__}' to hook: '{hook_name_to_register}'")

            self.plugin_manager.register_hook(hook_name_to_register) 
            self.plugin_manager.subscribe_to_hook(
                hook_name_to_register, 
                mp_constants.PLUGIN_NAME, 
                handler_method_to_call
            )
        
        # This hook is for the QTimer-based processing of the network queue, not direct network messages.
        # If _process_network_node_queue is solely called by its QTimer, this pre_update might be redundant.
        # However, it doesn't hurt to have it as a fallback or for other potential uses.
        self.plugin_manager.register_hook("pre_update") 
        self.plugin_manager.subscribe_to_hook("pre_update", mp_constants.PLUGIN_NAME, self._process_network_node_queue)

        if self.debug_mode: self.logger.debug("Network message hooks and pre_update hook registered.")


    def pre_update(self, *args, **kwargs):
        """Called by game's main update loop if subscribed to 'pre_update' hook."""
        # Current design uses QTimer for _process_network_node_queue.
        # This method can be used for other periodic tasks if needed.
        pass 


    def start_sync_timer(self):
        """Starts a daemon thread for periodic game state synchronization."""
        if not self.logger: return
        if self.sync_thread and self.sync_thread.is_alive():
            if self.debug_mode: self.logger.debug("Sync thread already running.")
            return

        def game_state_sync_loop():
            while True:
                if not self.is_setup: # Check if plugin is still supposed to be running
                    if self.debug_mode: self.logger.debug("SyncLoop: Plugin not setup or disabled, loop exiting.")
                    break
                try:
                    if self.network_node and self.network_node.is_connected and \
                       self.tamagotchi_logic and self.tamagotchi_logic.squid:
                        
                        # Dynamic sync interval based on local squid activity and peer count
                        is_local_squid_moving = getattr(self.tamagotchi_logic.squid, 'is_moving', False)
                        sync_delay_seconds = 0.3 if is_local_squid_moving else self.SYNC_INTERVAL # More frequent if moving
                        
                        num_peers = len(getattr(self.network_node, 'known_nodes', {}))
                        if num_peers > 8: sync_delay_seconds *= 1.5 # Reduce load with many peers
                        elif num_peers > 15: sync_delay_seconds *= 2.0
                        sync_delay_seconds = max(0.2, min(sync_delay_seconds, 3.0)) # Clamp interval

                        self.sync_game_state() # Send current state
                        time.sleep(sync_delay_seconds)
                    else:
                        # If not connected or prerequisites missing, wait longer before retrying
                        time.sleep(2.5) 
                except ReferenceError: # Can happen during interpreter shutdown
                    if self.debug_mode: self.logger.debug("SyncLoop: ReferenceError (likely app shutting down), loop exiting.")
                    break
                except Exception as e_sync:
                    if self.debug_mode: self.logger.error(f"Error in game_state_sync_loop: {e_sync}", exc_info=True)
                    time.sleep(3.0) # Wait a bit longer after an error
        
        self.sync_thread = threading.Thread(target=game_state_sync_loop, daemon=True)
        self.sync_thread.start()
        if self.debug_mode: self.logger.info("Game state synchronization thread started.")


    def sync_game_state(self):
        """Collects and sends current local game state."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'squid') or \
           not self.network_node or not self.network_node.is_connected:
            return # Prerequisites not met

        try:
            squid_current_state = self._get_squid_state()
            objects_current_state = self._get_objects_state() # Get state of syncable objects

            sync_payload = {
                'squid': squid_current_state,
                'objects': objects_current_state,
                'node_info': {'id': self.network_node.node_id, 'ip': self.network_node.local_ip}
            }
            self.network_node.send_message('object_sync', sync_payload) # Use 'object_sync' for combined state
            
            # Send heartbeat periodically as well
            time_now = time.time()
            if time_now - self.last_message_times.get('heartbeat_sent', 0) > 8.0: # Every 8 seconds
                heartbeat_payload = {
                    'node_id': self.network_node.node_id, 'status': 'active',
                    'squid_pos': (squid_current_state['x'], squid_current_state['y']) # Include position in heartbeat
                }
                self.network_node.send_message('heartbeat', heartbeat_payload)
                self.last_message_times['heartbeat_sent'] = time_now
        except Exception as e:
            self.logger.error(f"ERROR during sync_game_state: {e}", exc_info=True)


    def _get_squid_state(self) -> Dict:
        """Compiles and returns a dictionary of the local squid's current state."""
        if not self.logger: return {}
        if not self.tamagotchi_logic or not self.tamagotchi_logic.squid or not self.network_node:
            return {} # Not enough info to build state

        squid = self.tamagotchi_logic.squid
        view_direction_rad = self.get_actual_view_direction(squid) # Get view cone direction

        return {
            'x': squid.squid_x, 'y': squid.squid_y, 'direction': squid.squid_direction,
            'looking_direction': view_direction_rad, # For view cone
            'view_cone_angle': getattr(squid, 'view_cone_angle_rad', math.radians(60)),
            'hunger': squid.hunger, 'happiness': squid.happiness,
            'status': getattr(squid, 'status', "idle"), # Current action/status
            'carrying_rock': getattr(squid, 'carrying_rock', False),
            'is_sleeping': getattr(squid, 'is_sleeping', False),
            'color': self.get_squid_color(), # Get consistent color based on node ID
            'node_id': self.network_node.node_id, # Include node_id for identification
            'view_cone_visible': getattr(squid, 'view_cone_visible', False), # Is view cone active
            'squid_width': getattr(squid, 'squid_width', 60), # For rendering remote squid
            'squid_height': getattr(squid, 'squid_height', 40) # For rendering remote squid
        }


    def get_actual_view_direction(self, squid_instance) -> float:
        """Determines the squid's current viewing direction in radians."""
        if hasattr(squid_instance, 'current_view_angle_radians'): # If a dynamic view angle exists
            return squid_instance.current_view_angle_radians
        
        # Fallback to movement direction if no specific view angle
        direction_to_radians_map = {
            'right': 0.0, 
            'left': math.pi, 
            'up': 1.5 * math.pi, # -math.pi/2 or 3*math.pi/2
            'down': 0.5 * math.pi  # math.pi/2
        }
        return direction_to_radians_map.get(getattr(squid_instance, 'squid_direction', 'right'), 0.0)


    def get_squid_color(self) -> tuple:
        """Generates a persistent color (R,G,B) for the local squid based on its node ID."""
        if not hasattr(self, '_local_squid_color_cache'): # Cache to avoid recalculation
            node_id_str = "default_node" # Fallback
            if self.network_node and self.network_node.node_id:
                node_id_str = self.network_node.node_id
            
            # Simple hash-like function to generate color from node_id
            hash_value = 0
            for char_code in node_id_str.encode('utf-8'): # Use byte values of chars
                hash_value = (hash_value * 37 + char_code) & 0xFFFFFF # Keep it within 24-bit color range
            
            r = (hash_value >> 16) & 0xFF
            g = (hash_value >> 8) & 0xFF
            b = hash_value & 0xFF
            
            # Ensure colors are reasonably bright and distinct
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
            for item in ui.scene.items(): # Iterate through all items in the scene
                if not isinstance(item, QtWidgets.QGraphicsPixmapItem) or not hasattr(item, 'filename'):
                    continue # Skip non-pixmap items or items without a filename
                
                if not item.isVisible(): # Skip invisible items
                    continue
                
                if getattr(item, 'is_remote_clone', False): # Skip clones of remote objects
                    continue

                object_type_str = self._determine_object_type(item)
                valid_types_to_sync = ['rock', 'food', 'poop', 'decoration'] # Define what to sync
                if object_type_str not in valid_types_to_sync:
                    continue

                item_pos = item.pos()
                # Create a somewhat unique ID for the object based on filename and rough position
                obj_id = f"{os.path.basename(item.filename)}_{int(item_pos.x())}_{int(item_pos.y())}"
                
                object_data = {
                    'id': obj_id, 
                    'type': object_type_str, 
                    'x': item_pos.x(), 
                    'y': item_pos.y(),
                    'filename': item.filename, # Path to the image file
                    'scale': item.scale() if hasattr(item, 'scale') else 1.0,
                    'zValue': item.zValue(),
                    'is_being_carried': getattr(item, 'is_being_carried', False) # If squid is carrying it
                }
                syncable_objects_list.append(object_data)
        except RuntimeError: # Scene might change during iteration
             if self.debug_mode: self.logger.warning("Runtime error while iterating scene items for sync. Skipping this cycle.")
             return [] # Return empty or partially filled list
        except Exception as e:
            if self.debug_mode: self.logger.error(f"Getting object states for sync failed: {e}", exc_info=True)
        return syncable_objects_list

    def _determine_object_type(self, scene_item: QtWidgets.QGraphicsItem) -> str:
        """Determines a string type for a scene item based on attributes or filename."""
        # Prioritize explicit 'category' or 'object_type' attributes
        if hasattr(scene_item, 'category') and isinstance(getattr(scene_item, 'category'), str):
            return getattr(scene_item, 'category')
        if hasattr(scene_item, 'object_type') and isinstance(getattr(scene_item, 'object_type'), str):
            return getattr(scene_item, 'object_type')

        # Fallback to filename analysis if it's a QGraphicsPixmapItem with a filename
        if isinstance(scene_item, QtWidgets.QGraphicsPixmapItem) and hasattr(scene_item, 'filename'):
            filename_lower = getattr(scene_item, 'filename', '').lower()
            if not filename_lower: return 'unknown_pixmap' # If filename is empty

            if 'rock' in filename_lower: return 'rock'
            if any(food_kw in filename_lower for food_kw in ['food', 'sushi', 'apple', 'cheese', 'berry']): return 'food'
            if 'poop' in filename_lower: return 'poop'
            # Check common decoration paths or keywords
            if os.path.join("images", "decoration") in filename_lower.replace("\\", "/") or \
               any(kw in filename_lower for kw in ['decor', 'plant', 'toy', 'shell', 'coral', 'starfish', 'gem']):
                return 'decoration'
                
        return 'generic_item' # Default if type cannot be determined


    def handle_object_sync(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles incoming 'object_sync' messages from remote peers."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return

        try:
            sync_payload = message.get('payload', {})
            remote_squid_state = sync_payload.get('squid', {}) # Data about the sender's squid
            remote_objects_list = sync_payload.get('objects', []) # List of objects from sender
            source_node_info = sync_payload.get('node_info', {})
            sender_node_id = source_node_info.get('id') or remote_squid_state.get('node_id') # Get sender's ID

            if not sender_node_id:
                if self.debug_mode: self.logger.warning("Received object_sync with no identifiable sender node_id.")
                return
            
            if self.network_node and sender_node_id == self.network_node.node_id: return # Ignore own sync messages

            # Update the visual of the remote squid based on their state
            if remote_squid_state:
                # If entity_manager exists, it will handle the update. Otherwise, basic update.
                if self.entity_manager:
                    self.entity_manager.update_remote_squid(sender_node_id, remote_squid_state, is_new_arrival=False)
                else:
                    self.update_remote_squid(sender_node_id, remote_squid_state, is_new_arrival=False) # Fallback

            # Process remote objects
            if remote_objects_list:
                active_cloned_ids_for_this_sender = set()
                for remote_obj_data in remote_objects_list:
                    if not all(k in remote_obj_data for k in ['id', 'type', 'x', 'y', 'filename']):
                        if self.debug_mode: self.logger.debug(f"Skipping incomplete remote object data from {sender_node_id}: {remote_obj_data.get('id', 'No ID')}")
                        continue
                    
                    original_id_from_sender = remote_obj_data['id']
                    # Create a unique ID for the clone in this instance's scene
                    clone_id = f"clone_{sender_node_id}_{original_id_from_sender}"
                    active_cloned_ids_for_this_sender.add(clone_id)
                    
                    # Process (create or update) the visual clone of the remote object
                    self.process_remote_object(remote_obj_data, sender_node_id, clone_id)
                
                # Cleanup: Remove clones of objects that are no longer in the sender's sync list
                with self.remote_objects_lock: # Ensure thread safety for self.remote_objects
                    ids_to_remove = [
                        obj_id for obj_id, obj_info in self.remote_objects.items()
                        if obj_info.get('source_node') == sender_node_id and obj_id not in active_cloned_ids_for_this_sender
                    ]
                    for obj_id_to_remove in ids_to_remove:
                        self.remove_remote_object(obj_id_to_remove) # Method to remove visual and from dict

            # Optional: Trigger local squid's reaction to seeing a remote squid
            if self.tamagotchi_logic.squid and hasattr(self.tamagotchi_logic.squid, 'process_squid_detection') and remote_squid_state:
                self.tamagotchi_logic.squid.process_squid_detection(
                    remote_node_id=sender_node_id, is_detected=True, remote_squid_props=remote_squid_state
                )
        except Exception as e:
            if self.debug_mode: self.logger.error(f"Handling object_sync from {addr} failed: {e}", exc_info=True)


    def process_remote_object(self, remote_obj_data: Dict, source_node_id: str, clone_id: str):
        """Creates or updates a visual clone of a remote object in the local scene."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        
        scene = self.tamagotchi_logic.user_interface.scene
        base_filename = os.path.basename(remote_obj_data['filename']) # Get just the filename
        
        # Try to find the image in common local paths
        resolved_filename = os.path.join("images", base_filename) # Default path
        if not os.path.exists(resolved_filename):
            for subdir in ["decoration", "items", "food", "rocks"]: # Common subdirectories
                path_attempt = os.path.join("images", subdir, base_filename)
                if os.path.exists(path_attempt):
                    resolved_filename = path_attempt
                    break
            else: # If image not found locally
                if self.debug_mode: self.logger.warning(f"Remote object image '{base_filename}' not found locally for {clone_id}. Skipping visual.")
                return

        with self.remote_objects_lock: # Thread safety for self.remote_objects dictionary
            if clone_id in self.remote_objects: # If clone already exists, update it
                existing_clone_info = self.remote_objects[clone_id]
                visual_item = existing_clone_info['visual']
                
                visual_item.setPos(remote_obj_data['x'], remote_obj_data['y'])
                visual_item.setScale(remote_obj_data.get('scale', 1.0))
                visual_item.setZValue(remote_obj_data.get('zValue', -5)) # Default Z for background items
                visual_item.setVisible(not remote_obj_data.get('is_being_carried', False)) # Hide if carried by remote squid
                
                existing_clone_info['last_update'] = time.time()
                existing_clone_info['data'] = remote_obj_data # Store latest data
                
                # Ensure tint is applied (might have been removed or changed)
                if not getattr(visual_item, 'is_foreign', False):
                     self.apply_foreign_object_tint(visual_item)
            else: # New clone, create it
                if remote_obj_data.get('is_being_carried', False): # Don't create visual if it's being carried
                    return

                try:
                    pixmap = QtGui.QPixmap(resolved_filename)
                    if pixmap.isNull():
                        if self.debug_mode: self.logger.error(f"Failed to load QPixmap for remote object '{resolved_filename}'.")
                        return
                    
                    cloned_visual = QtWidgets.QGraphicsPixmapItem(pixmap)
                    cloned_visual.setPos(remote_obj_data['x'], remote_obj_data['y'])
                    cloned_visual.setScale(remote_obj_data.get('scale', 1.0))
                    # Cloned objects are less prominent than remote squids
                    cloned_visual.setOpacity(self.REMOTE_SQUID_OPACITY * 0.65) # Slightly more transparent
                    cloned_visual.setZValue(remote_obj_data.get('zValue', -5))
                    
                    setattr(cloned_visual, 'filename', resolved_filename) # Store original filename for reference
                    setattr(cloned_visual, 'is_remote_clone', True) # Mark as a clone
                    setattr(cloned_visual, 'original_id_from_sender', remote_obj_data['id']) # Store original ID
                    
                    self.apply_foreign_object_tint(cloned_visual) # Apply visual tint
                    scene.addItem(cloned_visual)
                    
                    self.remote_objects[clone_id] = {
                        'visual': cloned_visual, 
                        'type': remote_obj_data.get('type', 'unknown_clone'),
                        'source_node': source_node_id, 
                        'last_update': time.time(), 
                        'data': remote_obj_data
                    }
                except Exception as e_create_clone:
                    if self.debug_mode: self.logger.error(f"Creating visual clone for '{clone_id}' failed: {e_create_clone}", exc_info=True)


    def handle_heartbeat(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles heartbeat messages from other peers."""
        if not self.logger: return
        if not self.network_node: return # This instance's network node must exist

        sender_node_id = message.get('payload', {}).get('node_id') # Heartbeat payload contains sender's ID
        if not sender_node_id or sender_node_id == self.network_node.node_id: return # Ignore own or invalid heartbeats

        # Update UI (status widget or bar) with known peers
        if self.status_widget:
            self.status_widget.update_peers(self.network_node.known_nodes) # known_nodes is updated by NetworkNode
            if sender_node_id not in self.remote_squids: # If this is the first sign of this peer
                self.status_widget.add_activity(f"Peer {sender_node_id[-6:]} detected via heartbeat.")
        elif self.status_bar and hasattr(self.status_bar, 'update_peers_count'):
            self.status_bar.update_peers_count(len(self.network_node.known_nodes))

        heartbeat_payload = message.get('payload', {})
        squid_pos_data = heartbeat_payload.get('squid_pos') # Heartbeat might include basic position
        
        # If this peer is new and sent position, create a basic placeholder visual
        if squid_pos_data and sender_node_id not in self.remote_squids:
            if self.debug_mode: self.logger.debug(f"Creating placeholder for {sender_node_id[-6:]} from heartbeat.")
            placeholder_squid_data = {
                'x': squid_pos_data[0], 'y': squid_pos_data[1], 'direction': 'right', # Default direction
                'color': (150, 150, 150), 'node_id': sender_node_id, 'status': 'detected_via_heartbeat',
                'squid_width': 60, 'squid_height': 40 # Default dimensions
            }
            # Use entity_manager if available, otherwise fallback
            if self.entity_manager:
                self.entity_manager.update_remote_squid(sender_node_id, placeholder_squid_data, is_new_arrival=True)
            else:
                self.update_remote_squid(sender_node_id, placeholder_squid_data, is_new_arrival=True)


    def update_remote_squid(self, remote_node_id: str, squid_data_dict: Dict, is_new_arrival=False, high_visibility=False):
        """Updates or creates the visual representation of a remote squid.
           This method now primarily defers to self.entity_manager if available."""
        if not self.logger: return False
        
        if self.entity_manager:
            # entity_manager.update_remote_squid will handle all visual creation and updates
            # Pass is_new_arrival along, high_visibility is implicitly handled by static display now
            success = self.entity_manager.update_remote_squid(remote_node_id, squid_data_dict, is_new_arrival)
            if success and is_new_arrival:
                # If entity_manager handled it, log for clarity, autopilot logic is in handle_squid_exit.
                if self.debug_mode: self.logger.debug(f"RemoteEntityManager handled update/creation for {remote_node_id}.")
            elif not success:
                 if self.debug_mode: self.logger.warning(f"RemoteEntityManager failed to update/create {remote_node_id}.")
            return success

        # --- Fallback logic if entity_manager is NOT available (original basic logic) ---
        self.logger.warning("entity_manager NOT found. Using fallback remote squid update logic.")
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return False
        if not squid_data_dict or not all(key in squid_data_dict for key in ['x', 'y', 'direction']):
            if self.debug_mode: self.logger.warning(f"Fallback: Insufficient data for remote squid {remote_node_id}.")
            return False
        
        scene = self.tamagotchi_logic.user_interface.scene
        with self.remote_squids_lock: # Ensure lock for fallback access too
            existing_squid_display = self.remote_squids.get(remote_node_id)
            if existing_squid_display:
                visual = existing_squid_display.get('visual')
                id_text = existing_squid_display.get('id_text')
                status_text = existing_squid_display.get('status_text')

                if visual:
                    visual.setPos(squid_data_dict['x'], squid_data_dict['y'])
                    visual.setOpacity(self.REMOTE_SQUID_OPACITY) # Fallback ensure opacity
                    visual.setScale(1.0) # Fallback ensure scale
                    self.update_remote_squid_image(existing_squid_display, squid_data_dict['direction'])
                
                new_status_str = "ARRIVING" if is_new_arrival else squid_data_dict.get('status', 'active')
                if id_text: id_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 50) # Adjust as needed
                if status_text:
                    status_text.setPlainText(new_status_str)
                    status_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 35) # Adjust
                    # Static text styling, no animation-dependent changes
                    status_text.setDefaultTextColor(QtGui.QColor(200,200,200,230))
                    status_text.setFont(QtGui.QFont("Arial", 9))
                    if is_new_arrival: # Slight emphasis for new arrivals' status
                        status_text.setDefaultTextColor(QtGui.QColor(255, 223, 0)) # Gold
                        status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))

                existing_squid_display['data'] = squid_data_dict
                existing_squid_display['last_update'] = time.time()
            else: # New squid, fallback creation
                try:
                    initial_direction = squid_data_dict.get('direction', 'right')
                    # Attempt to load image, fallback to placeholder
                    base_image_path = "images"
                    squid_image_file = f"{initial_direction.lower()}1.png"
                    full_image_path = os.path.join(base_image_path, squid_image_file)
                    
                    squid_pixmap = QtGui.QPixmap(full_image_path)
                    if squid_pixmap.isNull():
                        self.logger.warning(f"Fallback: Image {full_image_path} not found. Using color placeholder.")
                        squid_width = squid_data_dict.get('squid_width', 60)
                        squid_height = squid_data_dict.get('squid_height', 40)
                        squid_pixmap = QtGui.QPixmap(int(squid_width), int(squid_height))
                        squid_color_tuple = squid_data_dict.get('color', (100,150,255)) # Default color
                        squid_pixmap.fill(QtGui.QColor(*squid_color_tuple))

                    visual = QtWidgets.QGraphicsPixmapItem(squid_pixmap)
                    visual.setPos(squid_data_dict['x'], squid_data_dict['y'])
                    visual.setOpacity(self.REMOTE_SQUID_OPACITY) # Full opacity (1.0)
                    visual.setScale(1.0) # Normal scale
                    visual.setZValue(5) # Default Z order
                    scene.addItem(visual)

                    # ID Text
                    display_id_str = f"{remote_node_id[-6:]}" # Show last 6 chars of ID
                    id_text = scene.addText(display_id_str) # Basic text item
                    id_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 50) # Position above visual
                    id_text.setFont(QtGui.QFont("Arial", 8))
                    id_text.setDefaultTextColor(QtGui.QColor(200,200,200,180)) # Semi-transparent white
                    id_text.setZValue(6) # Above squid visual
                    id_text.setVisible(self.SHOW_REMOTE_LABELS)

                    # Status Text
                    status_str = "ARRIVING" if is_new_arrival else squid_data_dict.get('status', 'active')
                    status_text = scene.addText(status_str)
                    status_text.setPos(squid_data_dict['x'], squid_data_dict['y'] - 35) # Position above visual
                    status_text.setFont(QtGui.QFont("Arial", 9))
                    status_text.setDefaultTextColor(QtGui.QColor(200,200,200,230))
                    if is_new_arrival: # Emphasize for new arrivals
                        status_text.setDefaultTextColor(QtGui.QColor(255, 215, 0)) # Gold
                        status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
                    status_text.setZValue(6) # Above squid visual
                    status_text.setVisible(self.SHOW_REMOTE_LABELS)
                    
                    new_squid_display_data = {
                        'visual': visual, 'id_text': id_text, 'status_text': status_text,
                        'view_cone': None, 'last_update': time.time(), 'data': squid_data_dict
                    }
                    self.remote_squids[remote_node_id] = new_squid_display_data
                    # update_remote_squid_image is implicitly handled by direct pixmap load or placeholder
                    if self.debug_mode: self.logger.debug(f"Fallback: Created static remote squid visual for {remote_node_id}.")

                except Exception as e_create_squid_fb:
                    self.logger.error(f"Fallback: Creating remote squid visual for {remote_node_id} failed: {e_create_squid_fb}", exc_info=True)
                    if remote_node_id in self.remote_squids: del self.remote_squids[remote_node_id] # Cleanup partial creation
                    return False
        return True


    def _create_enhanced_arrival_animation(self, squid_visual_item: QtWidgets.QGraphicsPixmapItem, at_x: float, at_y: float):
        """MODIFIED: Creates a more prominent visual animation (now static) for newly arriving remote squids."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        # scene = self.tamagotchi_logic.user_interface.scene # Scene not used if no visual effects

        if squid_visual_item:
            squid_visual_item.setOpacity(self.REMOTE_SQUID_OPACITY) # Ensure full visibility (1.0)
            squid_visual_item.setScale(1.0) # Ensure normal scale
            if squid_visual_item.graphicsEffect(): # Remove any prior effect
                 squid_visual_item.setGraphicsEffect(None)
        
        if self.debug_mode:
            self.logger.debug(f"Static display for enhanced arrival at ({at_x}, {at_y}).")


    def handle_remote_squid_return(self, remote_node_id: str, controller: Any): # Type hint for controller if available
        """Initiates the process for a remote squid (controlled by autopilot) to return to its home instance."""
        if not self.logger: return
        if self.debug_mode: self.logger.debug(f"Remote squid {remote_node_id[-6:]} is being returned home by its controller.")

        activity_summary_data = controller.get_summary() # Get summary of activities from controller
        home_direction_for_exit = controller.home_direction # Direction it should exit this screen

        # If entity_manager is handling visuals, tell it to start the removal process
        if self.entity_manager and hasattr(self.entity_manager, 'initiate_squid_departure_animation'):
            self.entity_manager.initiate_squid_departure_animation(
                remote_node_id,
                lambda: self.complete_remote_squid_return(remote_node_id, activity_summary_data, home_direction_for_exit)
            )
            if hasattr(self.tamagotchi_logic, 'show_message'):
                 self.tamagotchi_logic.show_message(f"窓 Visitor squid {remote_node_id[-6:]} is heading back home!")
            return

        # Fallback: Basic immediate removal or simple fade if no entity_manager animation
        remote_squid_display_info = self.remote_squids.get(remote_node_id)
        if not remote_squid_display_info or not remote_squid_display_info.get('visual'):
            if self.debug_mode: self.logger.warning(f"Visual for returning remote squid {remote_node_id[-6:]} not found. Completing return directly.")
            self.complete_remote_squid_return(remote_node_id, activity_summary_data, home_direction_for_exit)
            return

        visual_item = remote_squid_display_info['visual']
        status_text = remote_squid_display_info.get('status_text')
        if status_text: # Update status text
            status_text.setPlainText("RETURNING HOME...")
            status_text.setDefaultTextColor(QtGui.QColor(255, 165, 0)) # Orange
            status_text.setFont(QtGui.QFont("Arial", 10, QtGui.QFont.Bold))
        
        # For static testing, remove immediately after sending message
        self.logger.info(f"Static removal for remote squid {remote_node_id[-6:]} returning home.")
        self.complete_remote_squid_return(remote_node_id, activity_summary_data, home_direction_for_exit)
        
        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(f"窓 Visitor squid {remote_node_id[-6:]} is heading back home!")


    def complete_remote_squid_return(self, remote_node_id: str, activity_summary: Dict, exit_direction: str):
        """Finalizes the return of a remote squid: sends message and removes local visuals."""
        if not self.logger: return
        try:
            # Send 'squid_return' message to the network so the original instance knows its squid is back
            if self.network_node and self.network_node.is_connected:
                return_message_payload = {
                    'node_id': remote_node_id, # ID of the squid that is returning
                    'activity_summary': activity_summary, # What it did on this instance
                    'return_direction': exit_direction # How it should re-enter its home screen
                }
                self.network_node.send_message('squid_return', return_message_payload)
                if self.debug_mode:
                    rocks = activity_summary.get('rocks_stolen',0)
                    self.logger.info(f"Sent 'squid_return' for {remote_node_id[-6:]} (summary: {rocks} rocks). Exit dir: {exit_direction}")
            
            # Remove the remote squid's visual representation from this instance
            if self.entity_manager:
                self.entity_manager.remove_remote_squid(remote_node_id)
            else: # Fallback
                self.remove_remote_squid(remote_node_id) # This plugin's method for basic removal

            # Remove its controller
            if remote_node_id in self.remote_squid_controllers:
                del self.remote_squid_controllers[remote_node_id]
                if self.debug_mode: self.logger.info(f"Removed controller for returned remote squid {remote_node_id[-6:]}.")
        except Exception as e:
            self.logger.error(f"Completing remote squid return for {remote_node_id[-6:]} failed: {e}", exc_info=True)


    def update_remote_view_cone(self, remote_node_id: str, remote_squid_data: Dict):
        """Updates the visual representation of a remote squid's view cone.
           This is the mp_plugin_logic's own implementation, potentially a fallback if entity_manager is not used
           or if this plugin needs to draw cones for controllers it manages directly."""
        if not self.logger: return
        
        # If entity_manager is present and handles view cones, defer to it.
        if self.entity_manager and hasattr(self.entity_manager, 'update_remote_view_cone'):
            # Ensure entity_manager's update_remote_view_cone is compatible or adapt the call
            # This assumes entity_manager.update_remote_view_cone(node_id, data) signature
            self.entity_manager.update_remote_view_cone(remote_node_id, remote_squid_data)
            return

        # --- Fallback or direct implementation if no entity_manager for this ---
        if not self.SHOW_REMOTE_LABELS: # View cones are often tied to label visibility
            if remote_node_id in self.remote_squids and self.remote_squids[remote_node_id].get('view_cone'):
                self._remove_view_cone_for_squid(remote_node_id) # Helper to remove existing cone
            return

        if remote_node_id not in self.remote_squids or not self.tamagotchi_logic or \
           not hasattr(self.tamagotchi_logic, 'user_interface'):
            return

        scene = self.tamagotchi_logic.user_interface.scene
        squid_display_info = self.remote_squids[remote_node_id] # This plugin's own remote_squids dict
        
        # Remove existing cone if any
        self._remove_view_cone_for_squid(remote_node_id) 
        
        if not remote_squid_data.get('view_cone_visible', False): # If cone should not be visible
            return

        # Get squid's visual item from this plugin's tracking (if fallback)
        visual_item = squid_display_info.get('visual') 
        if not visual_item: 
            if self.debug_mode: self.logger.warning(f"Fallback: No visual item for {remote_node_id} to draw view cone.")
            return

        # Use visual item's current position and size for cone origin
        squid_center_x = visual_item.pos().x() + visual_item.boundingRect().width() / 2
        squid_center_y = visual_item.pos().y() + visual_item.boundingRect().height() / 2
        
        looking_direction_rad = remote_squid_data.get('looking_direction', 0.0) # In radians
        view_cone_angle_rad = remote_squid_data.get('view_cone_angle', math.radians(50)) # Default cone angle
        cone_half_angle = view_cone_angle_rad / 2.0
        cone_length = 150 # Length of the cone

        # Calculate points of the cone triangle
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
        
        squid_color = remote_squid_data.get('color', (150, 150, 255)) # Use squid's color for cone
        try:
            cone_q_color = QtGui.QColor(*squid_color)
        except TypeError:
            cone_q_color = QtGui.QColor(150,150,255) # Fallback color

        new_cone_item.setPen(QtGui.QPen(QtGui.QColor(cone_q_color.red(), cone_q_color.green(), cone_q_color.blue(), 0))) # Transparent border
        new_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(cone_q_color.red(), cone_q_color.green(), cone_q_color.blue(), 25))) # Semi-transparent fill
        new_cone_item.setZValue(visual_item.zValue() - 1) # Draw behind squid
        
        scene.addItem(new_cone_item)
        squid_display_info['view_cone'] = new_cone_item # Store reference


    def _remove_view_cone_for_squid(self, remote_node_id: str):
        """Safely removes a view cone for a specific remote squid (used by fallback logic)."""
        if not self.logger: return
        # This check is for this plugin's remote_squids dictionary
        if remote_node_id in self.remote_squids and self.tamagotchi_logic and hasattr(self.tamagotchi_logic.user_interface, 'scene'):
            squid_display_info = self.remote_squids[remote_node_id]
            cone_item = squid_display_info.get('view_cone')
            if cone_item and cone_item.scene(): # Check if it has a scene before removing
                self.tamagotchi_logic.user_interface.scene.removeItem(cone_item)
            squid_display_info['view_cone'] = None # Clear reference


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


            # Optional: Add a temporary "氏 Gift!" text label above it
            gift_indicator_label = scene.addText("氏 Gift!")
            label_font = QtGui.QFont("Arial", 10, QtGui.QFont.Bold)
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


    def remove_remote_squid(self, node_id_to_remove: str):
        """Removes visual components of a specific remote squid (used by fallback or direct management)."""
        if not self.logger: return
        if node_id_to_remove not in self.remote_squids: return # Not in this plugin's tracking
        
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene

        with self.remote_squids_lock: # Thread safety for self.remote_squids
            squid_display_elements = self.remote_squids.pop(node_id_to_remove, None)
        
        if squid_display_elements:
            visual_keys = ['visual', 'view_cone', 'id_text', 'status_text']
            for key in visual_keys:
                item_to_remove = squid_display_elements.get(key)
                if item_to_remove and item_to_remove.scene(): # Check if item has a scene
                    scene.removeItem(item_to_remove)
            
            # Remove associated connection line if managed by this plugin directly
            if node_id_to_remove in self.connection_lines:
                line = self.connection_lines.pop(node_id_to_remove)
                if line.scene(): scene.removeItem(line)
            
            if self.debug_mode: self.logger.debug(f"Fallback: Removed all visuals for remote squid {node_id_to_remove[-6:]}.")

        # Update UI status if network_node is still valid
        if self.network_node: 
            if self.status_widget: self.status_widget.update_peers(self.network_node.known_nodes if self.network_node else {})
            elif self.status_bar and hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(len(self.network_node.known_nodes if self.network_node else {}))


    def remove_remote_object(self, full_clone_id: str):
        """Removes a specific cloned remote object (used by fallback or direct management)."""
        if not self.logger: return
        if full_clone_id not in self.remote_objects: return # Not in this plugin's tracking
        
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        scene = self.tamagotchi_logic.user_interface.scene

        with self.remote_objects_lock: # Thread safety for self.remote_objects
            object_clone_info = self.remote_objects.pop(full_clone_id, None)
        
        if object_clone_info:
            visual_item = object_clone_info.get('visual')
            if visual_item and visual_item.scene(): # Check if item has a scene
                scene.removeItem(visual_item)
            
            if self.debug_mode: self.logger.debug(f"Fallback: Removed remote object clone: {full_clone_id}.")


    def throw_rock_network(self, rock_graphics_item: QtWidgets.QGraphicsPixmapItem, direction_thrown: str):
        """Broadcasts a 'rock_throw' event when the local squid throws a rock."""
        if not self.logger: return
        if not self.network_node or not self.network_node.is_connected or not rock_graphics_item:
            return # Prerequisites not met

        try:
            rock_filename = getattr(rock_graphics_item, 'filename', "default_rock.png") # Get filename
            initial_pos = rock_graphics_item.pos() # Position when thrown
            
            rock_throw_payload = {
                'rock_data': {
                    'filename': rock_filename, 
                    'direction': direction_thrown,
                    'initial_pos_x': initial_pos.x(), 
                    'initial_pos_y': initial_pos.y(),
                    'scale': rock_graphics_item.scale() if hasattr(rock_graphics_item, 'scale') else 1.0,
                }
            }
            self.network_node.send_message('rock_throw', rock_throw_payload) # Send message
            if self.debug_mode:
                self.logger.debug(f"Broadcasted local rock throw: {os.path.basename(rock_filename)} towards {direction_thrown}.")
        except Exception as e_throw:
            if self.debug_mode: self.logger.error(f"Broadcasting rock throw failed: {e_throw}", exc_info=True)


    def cleanup(self):
        """Cleans up all resources used by the multiplayer plugin."""
        if self.logger is None: 
            emergency_logger = logging.getLogger(f"{mp_constants.PLUGIN_NAME}_CleanupEmergency")
            if not emergency_logger.hasHandlers(): emergency_logger.addHandler(logging.StreamHandler())
            emergency_logger.setLevel(logging.INFO)
            self.logger = emergency_logger
            self.logger.warning("Logger was None at the start of cleanup. Using emergency logger.")

        self.logger.info(f"Initiating {mp_constants.PLUGIN_NAME} cleanup...")
        self.is_setup = False # Mark as not setup to stop background threads/timers

        # Stop all QTimers
        timers_to_manage = [
            'message_process_timer', 'controller_update_timer', 'controller_creation_timer',
            'cleanup_timer_basic', 'connection_timer_basic'
        ]
        for timer_attr_name in timers_to_manage:
            timer_instance = getattr(self, timer_attr_name, None)
            if timer_instance and isinstance(timer_instance, QtCore.QTimer) and timer_instance.isActive():
                timer_instance.stop()
                if self.debug_mode: self.logger.debug(f"Stopped timer '{timer_attr_name}'.")
            setattr(self, timer_attr_name, None) # Clear reference

        # Sync thread is a daemon, will exit with app. Signal it to stop if it checks is_setup.
        if self.sync_thread and self.sync_thread.is_alive():
             if self.debug_mode: self.logger.info("Sync thread was active during cleanup. As a daemon, it will exit with app or when its loop condition (is_setup) fails.")
        self.sync_thread = None # Clear reference
        
        # NetworkNode cleanup
        if self.network_node:
            nn_ref = self.network_node # Temporary reference for cleanup
            self.network_node = None # Nullify early to prevent re-use during its own shutdown

            if nn_ref.is_connected: # Send leave message if connected
                try:
                    nn_ref.send_message(
                        'player_leave',
                        {'node_id': nn_ref.node_id, 'reason': 'plugin_unloaded_or_disabled'}
                    )
                except Exception as e_leave: # Socket might already be closed
                    if self.debug_mode: self.logger.error(f"Error sending player_leave message (socket may be closed): {e_leave}", exc_info=False) # No exc_info if expected
            
            # Close socket and leave multicast group
            if nn_ref.socket: 
                try:
                    if nn_ref.is_connected and hasattr(nn_ref, 'local_ip') and nn_ref.local_ip and \
                       hasattr(mp_constants, 'MULTICAST_GROUP') and mp_constants.MULTICAST_GROUP:
                        import socket as sock_module # Local import for cleanup
                        mreq_leave = sock_module.inet_aton(mp_constants.MULTICAST_GROUP) + sock_module.inet_aton(nn_ref.local_ip)
                        nn_ref.socket.setsockopt(sock_module.IPPROTO_IP, sock_module.IP_DROP_MEMBERSHIP, mreq_leave)
                except AttributeError as e_attr: 
                     if self.debug_mode: self.logger.warning(f"Attribute error during multicast group leave: {e_attr}")
                except Exception as e_mcast_leave:
                     if self.debug_mode: self.logger.warning(f"Error leaving multicast group: {e_mcast_leave}", exc_info=True)
                finally:
                    try:
                        nn_ref.socket.close()
                    except Exception: pass # Ignore errors on closing already closed socket
            nn_ref.is_connected = False
            nn_ref.socket = None
        
        # Cleanup visuals if entity_manager is not handling it or as a final sweep
        if self.entity_manager:
            self.entity_manager.cleanup_all() # Tell entity_manager to clean its own entities
        else: # Fallback: this plugin cleans its own directly managed visuals
            if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
                with self.remote_squids_lock:
                    for node_id_key in list(self.remote_squids.keys()): self.remove_remote_squid(node_id_key)
                with self.remote_objects_lock:
                    for clone_id_key in list(self.remote_objects.keys()): self.remove_remote_object(clone_id_key)
        
        self.remote_squids.clear()
        self.remote_objects.clear()
        self.connection_lines.clear() # Should be empty if lines removed correctly
        self.remote_squid_controllers.clear()

        # Update UI status
        if self.status_widget:
             if hasattr(self.status_widget, 'update_connection_status'): self.status_widget.update_connection_status(False)
             if hasattr(self.status_widget, 'update_peers'): self.status_widget.update_peers({})
             if hasattr(self.status_widget, 'add_activity'): self.status_widget.add_activity(f"{mp_constants.PLUGIN_NAME} has been shut down.")
        elif self.status_bar: # Fallback
            if hasattr(self.status_bar, 'update_network_status'): self.status_bar.update_network_status(False)
            if hasattr(self.status_bar, 'update_peers_count'): self.status_bar.update_peers_count(0)
            if hasattr(self.status_bar, 'showMessage'): self.status_bar.showMessage(f"{mp_constants.PLUGIN_NAME} plugin shut down.", 5000)
        
        self.logger.info(f"{mp_constants.PLUGIN_NAME} plugin cleanup process completed.")


    def handle_squid_move(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles discrete 'squid_move' messages (less frequent than full sync)."""
        if not self.logger: return
        
        payload = message.get('payload', {})
        sender_node_id = payload.get('node_id') # Assume payload contains node_id
        
        if not sender_node_id: 
            sender_node_id = message.get('node_id') # Fallback if NetworkNode added it to top level
            if not sender_node_id:
                if self.debug_mode: self.logger.warning("squid_move message missing sender_node_id.")
                return

        if self.network_node and sender_node_id == self.network_node.node_id: return # Ignore own move messages

        # Defer to entity_manager if available for visual updates
        if self.entity_manager:
            # Ensure payload matches what entity_manager.update_remote_squid expects
            # It needs x, y, direction, and other relevant fields from _get_squid_state
            self.entity_manager.update_remote_squid(sender_node_id, payload, is_new_arrival=False)
        elif sender_node_id in self.remote_squids: # Fallback basic update
            current_display_data = self.remote_squids[sender_node_id]
            visual = current_display_data.get('visual')
            if visual and all(k in payload for k in ['x', 'y', 'direction']):
                visual.setPos(payload['x'], payload['y'])
                self.update_remote_squid_image(current_display_data, payload['direction']) # Update image based on direction
            
            # Update stored data for this squid
            if 'data' in current_display_data:
                current_display_data['data'].update(payload) # Merge new data
                current_display_data['last_update'] = time.time()


    def handle_rock_throw(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles 'rock_throw' messages from remote players, creating a visual effect."""
        if not self.logger: return
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'): return
        
        scene = self.tamagotchi_logic.user_interface.scene
        payload_outer = message.get('payload', {}) # Payload from NetworkNode (contains original sender's payload)
        rock_throw_data = payload_outer.get('rock_data', {}) # Actual rock data
        
        # Get sender_node_id (NetworkNode should add this based on sender's address if not in payload)
        sender_node_id = payload_outer.get('node_id') or message.get('node_id') 
        
        if not rock_throw_data or not sender_node_id: 
            if self.debug_mode: self.logger.warning(f"Incomplete rock_throw message: data={rock_throw_data}, sender={sender_node_id}")
            return
        
        if self.network_node and sender_node_id == self.network_node.node_id: return # Ignore own rock throws

        if self.debug_mode: self.logger.debug(f"Received rock_throw from {sender_node_id[-6:]}, data: {rock_throw_data}")

        # Create visual for the thrown rock
        rock_filename = rock_throw_data.get('filename', os.path.join("images","rock.png")) # Default rock image
        try:
            pixmap = QtGui.QPixmap(rock_filename)
            if pixmap.isNull(): # Fallback if specified image fails
                pixmap = QtGui.QPixmap(os.path.join("images","rock.png")) 
            
            thrown_rock_item = QtWidgets.QGraphicsPixmapItem(pixmap)
            initial_x = rock_throw_data.get('initial_pos_x', scene.width()/2) # Default to center
            initial_y = rock_throw_data.get('initial_pos_y', scene.height()/2)
            thrown_rock_item.setPos(initial_x, initial_y)
            thrown_rock_item.setScale(rock_throw_data.get('scale', 0.8)) # Use scale from payload
            thrown_rock_item.setZValue(20) # High Z-value to be visible
            
            self.apply_foreign_object_tint(thrown_rock_item) # Mark as from remote
            scene.addItem(thrown_rock_item)
            
            # Static display for testing - no animation
            # The rock will just appear and then be removed if it goes off-screen or by other logic.
            # For a simple effect, you could make it disappear after a short time.
            if self.debug_mode: self.logger.debug(f"Static remote rock '{os.path.basename(rock_filename)}' displayed from {sender_node_id[-6:]}.")
            QtCore.QTimer.singleShot(1500, lambda item=thrown_rock_item: item.scene().removeItem(item) if item.scene() else None)


        except Exception as e_rock_throw_vis:
            if self.debug_mode: self.logger.error(f"Error visualizing remote rock throw: {e_rock_throw_vis}", exc_info=True)


    def handle_state_update(self, node: NetworkNode, message: Dict, addr: tuple):
        """Handles generic 'state_update' messages. Could be used for various game events."""
        if not self.logger: return
        
        payload = message.get('payload', {})
        # Sender ID might be in top-level message from NetworkNode or within payload
        sender_node_id = message.get('node_id') or payload.get('node_id') 

        if self.debug_mode: self.logger.debug(f"Received generic 'state_update' from {sender_node_id[-6:] if sender_node_id else 'Unknown'}. Payload: {payload}")
        
        # Example: If state_update contains specific info about a remote squid's special action
        # if sender_node_id and 'special_action' in payload:
        #     action_type = payload['special_action']
        #     if self.entity_manager and hasattr(self.entity_manager, 'trigger_remote_squid_special_effect'):
        #         self.entity_manager.trigger_remote_squid_special_effect(sender_node_id, action_type, payload)
        #     elif self.debug_mode:
        #         self.logger.info(f"Remote squid {sender_node_id[-6:]} performed special action: {action_type}")

        # Add more specific logic here based on the content and purpose of 'state_update' messages.