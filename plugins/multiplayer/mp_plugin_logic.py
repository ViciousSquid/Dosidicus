# File: mp_plugin_logic.py

import logging

_LOG = logging.getLogger(__name__)


# import sys # sys.path is handled in main.py
import inspect # For _find_tamagotchi_logic
import uuid
import time
# import socket # Network operations are in NetworkNode
import threading
from typing import Dict, List, Any
from PyQt5 import QtCore, QtWidgets

# --- Local Imports ---
import logging # Added for logger
from . import mp_constants # Access constants like mp_constants.PLUGIN_NAME
from .mp_network_node import NetworkNode
from .remote_entity_manager import RemoteEntityManager # Ensure this is imported if type hinting or direct use
from src.lifecycle import MULTIPLAYER_RISK_NOTICE, MULTIPLAYER_RISK_TITLE
from .identity import SquidIdentity
from .consent import (ConsentPolicy, MODE_OPEN)
from .peer_ledger import PeerLedger
from .encounter import (EncounterSession)
from .encounter_sensors import ConspecificView
from .host_body import HostBody
from .visitor_mind import VisitorMind

# TamagotchiLogic is imported in main.py and should be in sys.path
# If type hinting is needed here and main.py's import might not be seen by linters:
try:
    from src.tamagotchi_logic import TamagotchiLogic
except ImportError:
    TamagotchiLogic = None
from .mp_visits import VisitProtocolMixin
from .mp_social import FightsAndMatingMixin
from .mp_friends import FriendsMixin
from .mp_remote_squids import RemoteSquidsMixin
from .mp_sync import StateSyncMixin
from .mp_interface import MultiplayerInterfaceMixin


class MultiplayerPlugin(
        VisitProtocolMixin,
        FightsAndMatingMixin,
        FriendsMixin,
        RemoteSquidsMixin,
        StateSyncMixin,
        MultiplayerInterfaceMixin,
):
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
        self.sync_timer = None
        self._last_world_sync = 0.0
        self.message_process_timer: QtCore.QTimer | None = None
        self.controller_update_timer: QtCore.QTimer | None = None
        self.controller_creation_timer: QtCore.QTimer | None = None
        self.cleanup_timer_basic: QtCore.QTimer | None = None
        self.connection_timer_basic: QtCore.QTimer | None = None

        # --- State and Data ---
        self.remote_squids: Dict[str, Dict[str, Any]] = {}
        self.remote_objects: Dict[str, Dict[str, Any]] = {}
        self._peers_heard: set = set()  # node ids a heartbeat has come from
        self._peers_last_heard: Dict[str, float] = {}  # node id -> last heartbeat
        self._asked_to_visit = ''   # the one host this squid last asked to visit
        self._fight_starts: Dict[str, Dict[str, Any]] = {}  # fight id -> who started it, why
        self.remote_squid_controllers: Dict[str, Any] = {} # Should be RemoteSquidController
        self.pending_controller_creations: List[Dict[str, Any]] = []
        self.connection_lines: Dict[str, QtWidgets.QGraphicsLineItem] = {}
        self.last_message_times: Dict[str, float] = {}

        # --- Encounters ---
        # Identity is the squid's own persistent uuid, not node_id: node_id is
        # regenerated every setup and cannot answer "is this the same squid I
        # met last week".
        self.local_identity: SquidIdentity | None = None
        self.peer_identities: Dict[str, SquidIdentity] = {}   # node_id -> identity
        self.consent_policy = ConsentPolicy(mode=MODE_OPEN)
        self.conspecific_view = ConspecificView()
        self.peer_ledger: PeerLedger | None = None
        self.open_encounters: Dict[str, EncounterSession] = {}   # peer uuid -> session

        # --- The remote-mind round trip ---
        # host_body is this tank acting as a visiting squid's body; visitor_mind
        # is this squid's brain while its body is in someone else's tank. Both
        # exist at once because every instance is both a host and a potential
        # visitor.
        self.host_body: HostBody | None = None
        self.visitor_mind: VisitorMind | None = None
        self.visit_node_ids: Dict[str, str] = {}   # peer uuid -> node_id
        self._fight_cooldown_until: Dict[str, float] = {}   # peer uuid -> time
        self._last_round_trip = 0.0

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
        # 1. Try to get the global flag from config.ini
        try:
            self.debug_mode = self.plugin_manager.config_manager.get_debug_flag("multiplayer_debug", fallback=False)
        except Exception:
            # 2. Any problem (no ConfigManager, no key, etc.) → stay quiet
            self.debug_mode = False

        # 3. Push the value to every sub-component that cares
        if self.network_node:
            self.network_node.debug_mode = self.debug_mode
        if getattr(self, 'entity_manager', None):
            self.entity_manager.debug_mode = self.debug_mode
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
                self.entity_manager.resident_frame = self._resident_swim_frame
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


    # NOTE: this used to be defined INSIDE debug_autopilot_status(), one
    # indent level too deep - so it was a local function that method built
    # and threw away, and MultiplayerPlugin had no enable() at all.
    def enable(self):
        self.logger.info("Attempting to enable Multiplayer...")
        if not self.confirm_risk_once():
            self.logger.info("Multiplayer left off: the player did not accept the risk.")
            return False

        # --- NEW: Debug log all key objects ---
        self.logger.debug(f"[ENABLE] status_widget: {self.status_widget}")
        self.logger.debug(f"[ENABLE] entity_manager: {self.entity_manager}")
        self.logger.debug(f"[ENABLE] network_node: {self.network_node}")
        self.logger.debug(f"[ENABLE] tamagotchi_logic: {self.tamagotchi_logic}")
        self.logger.debug(f"[ENABLE] config_manager: {getattr(self, 'config_manager', None)}")
        # --- END DEBUG LOG ---

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
        if self.message_process_timer:
            if not self.message_process_timer.isActive():
                self.message_process_timer.start(50)
                self.logger.info("Message processing timer restarted.")
        else:
            self.logger.warning("message_process_timer is None in enable(). Skipping.")

        self.start_sync_timer()

        # Update status widget if applicable
        if self.status_widget:
            try:
                self.status_widget.update_status("Enabled", True)
                current_ip = self.network_node.local_ip if self.network_node else "N/A"
                if hasattr(self.status_widget, 'set_ip_address'):
                    self.status_widget.set_ip_address(current_ip)
                else:
                    self.logger.warning("status_widget has no set_ip_address method.")
            except Exception as e:
                self.logger.error(f"Error updating status_widget in enable(): {e}", exc_info=True)
        else:
            self.logger.warning("status_widget is None in enable(). Skipping UI update.")

        self.enabled = True # Mark as enabled
        self.logger.info("Multiplayer enabled successfully.")
        return True

    #: Asked once, the first time multiplayer is enabled on this installation.
    RISK_TITLE = MULTIPLAYER_RISK_TITLE
    RISK_NOTICE = MULTIPLAYER_RISK_NOTICE

    def confirm_risk_once(self) -> bool:
        """Ask before multiplayer first goes on. True means go ahead.

        Encounters change a squid for good, and can end its life (see
        src/lifecycle.py). Only a yes is remembered (config.ini), so it is
        asked once per installation; a no leaves multiplayer off, and the
        question is asked again the next time it is switched on.
        """
        from src.config_manager import ConfigManager
        config = ConfigManager()
        if config.get_multiplayer_risk_notice_shown():
            return True
        ui = getattr(self.tamagotchi_logic, 'user_interface', None)
        answer = QtWidgets.QMessageBox.question(
            getattr(ui, 'window', None), self.RISK_TITLE,
            f"{self.RISK_TITLE}\n\n{self.RISK_NOTICE}",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No)
        if answer != QtWidgets.QMessageBox.Yes:
            return False
        config.set_multiplayer_risk_notice_shown()
        return True

    def disable(self):
        """Disables the multiplayer plugin and cleans up resources."""
        if self.sync_timer is not None:
            self.sync_timer.stop()
        if not self.logger: # Should be set by now
             print("Multiplayer ERRA: Logger not set in disable()") # Fallback to print if logger is broken
             return
        self.logger.info(f"Disabling {mp_constants.PLUGIN_NAME}...")
        if self.network_node and self.network_node.is_connected:
            self.network_node.send_message(
                'player_leave',
                {'node_id': self.network_node.node_id, 'reason': 'plugin_disabled'}
            )

        # A squid that is away when the plugin stops has to come home. Its
        # body is on someone else's machine and its brain is here; leaving it
        # in that state is the one unrecoverable failure this design has.
        if self.visitor_mind is not None and self.visitor_mind.perception.away:
            self.visitor_mind.end_visit(reason='departed', notify=True)
        if self.host_body is not None:
            for actor in list(self.host_body.visitors.values()):
                self.end_visit_as_host(actor, reason='ejected')

        # Close whatever encounters were still open, so an experience the
        # squid was in the middle of having is not simply lost.
        for peer_uuid in list(self.open_encounters):
            try:
                self.close_encounter(peer_uuid)
            except Exception as exc:
                self.logger.error(f"Could not close encounter with {peer_uuid}: {exc}")
        self.conspecific_view.clear()
        self._peers_last_heard.clear()
        self._perceive_aquariums()          # no aquarium is nearby any more

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
        self._restore_friends()

        # START LISTENING.
        #
        # Nothing did. NetworkNode.__init__ builds the socket, binds it and
        # joins the multicast group - which is why the dashboard said
        # "Connected" - but the thread that actually READS the socket is
        # started by start_listening(), and the only call to it in this plugin
        # had ended up inside debug_autopilot_status(), which returns early
        # whenever there are no remote controllers. There never are at
        # startup, so the listener never started.
        #
        # Sending was unaffected, so every instance broadcast happily into a
        # group nobody was reading. incoming_queue stayed empty, known_nodes
        # stayed empty, and no peer was ever detected - on one machine or
        # across a LAN.
        if not self.network_node.is_listening():
            if self.network_node.start_listening():
                self.logger.info(
                    f"[MCAST] Listening for peers on {self.MULTICAST_GROUP}:{self.MULTICAST_PORT}")
            else:
                self.logger.error(
                    "[MCAST] Could not start the listener thread. This instance "
                    "can send but will never see another squid.")

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
                self.entity_manager.resident_frame = self._resident_swim_frame
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

        # --- Encounters: make another squid something the brain can sense ---
        self.install_encounter_sensors()

        if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'show_message') and self.network_node:
            self.tamagotchi_logic.show_message(f"Multiplayer active! Node ID: {self.network_node.node_id}")

        node_ip = self.network_node.local_ip if self.network_node else "N/A"
        node_port = self.MULTICAST_PORT # Use the constant
        self.logger.info(f"Setup complete. Node: {node_id_val} on IP: {node_ip}. Listening for multicast on port: {node_port}")
        self.is_setup = True
        self.start_sync_timer()
        return True

    def _network_health_check(self):
        """Keep the connection lines fresh, and the listener alive.

        NetworkNode.watchdog_check() existed and nothing called it, so a
        listener thread that died stayed dead for the rest of the session.
        """
        if self.network_node is not None:
            try:
                self.network_node.watchdog_check()
            except Exception as exc:
                self.logger.error(f"Listener watchdog failed: {exc}")
        self.update_connection_lines()

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

    def shutdown(self) -> None:
        """Called by PluginManager.unload_plugin, e.g. on New Game.

        There was no shutdown, so unloading the plugin left its socket open,
        its listener and sync threads running, and any visit in progress
        pointing at a squid that had been replaced. Disabling is the one path
        that already ends visits on both sides and closes the node.
        """
        if self.logger is None or not self.is_setup:
            return
        self.disable()

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

    from PyQt5 import QtCore, QtGui, QtWidgets

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
            "on_network_object_sync": self.handle_object_sync,
            "on_network_heartbeat": self.handle_heartbeat,
            "on_network_state_update": self.handle_state_update, # Generic state update
            # Not listened for: squid_return, rock_throw and squid_move. Nothing
            # sends them since the remote mind replaced the copied visitor, and
            # each acted on whatever any peer said - squid_return moved this
            # squid and rewrote its drives from an untrusted summary;
            # rock_throw loaded an image from a path the peer chose.
            # The remote-mind round trip. Four messages, two roles: this
            # instance is a host to other people's squid and the home of its
            # own, so it subscribes to both directions.
            "on_network_perception_frame": self.handle_perception_frame,
            "on_network_action_intent": self.handle_action_intent,
            "on_network_consequence": self.handle_consequence,
            "on_network_visit_end": self.handle_visit_end,
            "on_network_visit_response": self.handle_visit_response,
            "on_network_gamete": self.handle_gamete,
            # Not a network message: a rock the resident threw struck a squid.
            "on_rock_hit": self.handle_rock_hit,
            # Not a network message: the core tells plugins its squid died.
            "on_squid_died": self.handle_resident_died,
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
            'cleanup_timer_basic', 'connection_timer_basic', 'sync_timer'
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
            
            # Stop and join the listener before closing its socket. Closing
            # only the socket left the reconnect loop running through New Game.
            nn_ref.close()

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


        # Example: If state_update contains specific info about a remote squid's special action
        # if sender_node_id and 'special_action' in payload:
        #     action_type = payload['special_action']
        #     if self.entity_manager and hasattr(self.entity_manager, 'trigger_remote_squid_special_effect'):
        #         self.entity_manager.trigger_remote_squid_special_effect(sender_node_id, action_type, payload)
        #     elif self.debug_mode:
        #         self.logger.info(f"Remote squid {sender_node_id[-6:]} performed special action: {action_type}")

        # Add more specific logic here based on the content and purpose of 'state_update' messages.
