import os
import sys

# Get the path to the project root (one directory up from the current plugin directory)
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)
# Add the current directory to sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Now you can import from src using standard import
from src.tamagotchi_logic import TamagotchiLogic

import json
import uuid
import time
import socket
import threading
import queue
import zlib
import random
import traceback
import math
from typing import Dict, List, Any, Tuple
from PyQt5 import QtCore, QtGui, QtWidgets

from .multiplayer_config_dialog import MultiplayerConfigDialog

# Plugin Metadata
PLUGIN_NAME = "Multiplayer"
PLUGIN_VERSION = "1.1.3"
PLUGIN_AUTHOR = "ViciousSquid"
PLUGIN_DESCRIPTION = "Enables network sync for squids and objects (Experimental)"
PLUGIN_REQUIRES = ["network_interface"]

# Network Constants 
MULTICAST_GROUP = '224.3.29.71'  
MULTICAST_PORT = 10000
SYNC_INTERVAL = 1.0  # Seconds between sync broadcasts

# Visual settings
REMOTE_SQUID_OPACITY = 0.8
SHOW_REMOTE_LABELS = True 
SHOW_CONNECTION_LINES = True
MAX_PACKET_SIZE = 65507  # Max UDP packet size

class NetworkNode:
    def __init__(self, node_id=None):
        """
        Represents a networked node in the multiplayer system
        
        Args:
            node_id (str, optional): Unique identifier for this node. 
                                     Generated if not provided.
        """
        # Import locally to avoid dependency issues
        try:
            from plugins.multiplayer.network_utilities import NetworkUtilities
            self.node_id = node_id or NetworkUtilities.generate_node_id()
            self.utils = NetworkUtilities
        except ImportError:
            import uuid
            self.node_id = node_id or f"squid_{uuid.uuid4().hex[:8]}"
            self.utils = None
        
        # Get local IP
        self.local_ip = self._get_local_ip()
        self.socket = None
        self.initialized = False
        self.is_connected = False
        self.last_connection_attempt = 0
        self.connection_retry_interval = 5.0  # Seconds between reconnection attempts
        self.auto_reconnect = True
        self.use_compression = True
        
        # Queues for incoming and outgoing messages
        self.incoming_queue = queue.Queue()
        self.outgoing_queue = queue.Queue()
        
        # Synchronization tracking
        self.known_nodes = {}  # Maps node_id to (ip, last_seen_time, squid_data)
        self.last_sync_time = 0
        self.debug_mode = False
        
        # Initialize the socket with error handling
        try:
            self.initialize_socket()
        except Exception as e:
            print(f"Error initializing socket (will work in limited mode): {e}")
            self.is_connected = False
    
    def initialize_socket(self):
        """Initialize the network socket with robust error handling"""
        try:
            # Import socket here to handle missing module gracefully
            import socket
            
            # If socket already exists, close it first
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Multicast setup
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            
            try:
                # Binding with retries on different ports if necessary
                max_attempts = 3
                attempt = 0
                port = MULTICAST_PORT
                
                while attempt < max_attempts:
                    try:
                        self.socket.bind(('', port))
                        break
                    except OSError as bind_error:
                        attempt += 1
                        if attempt >= max_attempts:
                            raise bind_error
                        # Try a different port
                        port = MULTICAST_PORT + attempt
                        print(f"Port {port-1} in use, trying {port}...")
                
                # Join multicast group
                mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(self.local_ip)
                self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                
                # Set socket timeout to prevent blocking
                self.socket.settimeout(0.1)
                
                self.is_connected = True
                self.initialized = True
                self.last_connection_attempt = time.time()
                
                if self.debug_mode:
                    print(f"[Network] Successfully initialized socket on {self.local_ip}:{port}")
                
            except Exception as bind_error:
                print(f"[Network] Error binding socket (continuing in limited mode): {bind_error}")
                self.is_connected = False
        
        except ImportError:
            print("[Network] Socket module not available, running in mock mode")
            self.is_connected = False
        except Exception as e:
            print(f"[Network] Error creating socket: {e}")
            self.socket = None
            self.is_connected = False
            
        # Record time of attempt
        self.last_connection_attempt = time.time()
        return self.is_connected
    
    def try_reconnect(self):
        """Attempt to reconnect if auto-reconnect is enabled"""
        if not self.auto_reconnect:
            return False
            
        current_time = time.time()
        if current_time - self.last_connection_attempt < self.connection_retry_interval:
            return False  # Too soon to retry
            
        if self.debug_mode:
            print("[Network] Attempting to reconnect...")
            
        return self.initialize_socket()
    
    def _get_local_ip(self):
        """Determine the local IP address with fallback to localhost"""
        try:
            # Create a temporary socket to connect to an external server
            import socket
            temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_socket.connect(('8.8.8.8', 80))
            local_ip = temp_socket.getsockname()[0]
            temp_socket.close()
            return local_ip
        except (ImportError, Exception) as e:
            print(f"[Network] Error getting local IP: {e}")
            return '127.0.0.1'
        
    def send_message_batch(self, messages):
        """Send multiple messages in a single packet
        
        Args:
            messages: List of (message_type, payload) tuples
        """
        if not self.is_connected:
            if self.auto_reconnect:
                self.try_reconnect()
            if not self.is_connected or not self.socket:
                return False
        
        batch = {
            'node_id': self.node_id,
            'timestamp': time.time(),
            'batch': True,
            'messages': [
                {
                    'type': msg_type,
                    'payload': payload
                } for msg_type, payload in messages
            ]
        }
        
        # Compress and send
        try:
            compressed_msg = self.utils.compress_message(batch) if self.utils else json.dumps(batch).encode('utf-8')
            self.socket.sendto(compressed_msg, (MULTICAST_GROUP, MULTICAST_PORT))
            return True
        except Exception as e:
            print(f"Error sending batch: {e}")
            self.is_connected = False
            return False
    
    def send_message(self, message_type: str, payload: Dict[str, Any]):
        """
        Send a message to the multicast group
        
        Args:
            message_type (str): Type of message being sent
            payload (Dict): Message payload
        """
        # Try to reconnect if not connected
        if not self.is_connected:
            if self.auto_reconnect:
                self.try_reconnect()
            if not self.is_connected or not self.socket:
                if self.debug_mode:
                    print(f"[Network] Cannot send message: socket not connected")
                return False
            
        message = {
            'node_id': self.node_id,
            'timestamp': time.time(),
            'type': message_type,
            'payload': payload
        }
        
        # Compress message to reduce network overhead
        try:
            # Use utility class if available, otherwise use direct compression
            if self.utils and self.use_compression:
                compressed_msg = self.utils.compress_message(message)
            else:
                # Fallback compression
                serialized_msg = json.dumps(message).encode('utf-8')
                try:
                    import zlib
                    compressed_msg = zlib.compress(serialized_msg)
                except ImportError:
                    compressed_msg = serialized_msg
            
            try:
                self.socket.sendto(
                    compressed_msg, 
                    (MULTICAST_GROUP, MULTICAST_PORT)
                )
                if self.debug_mode:
                    print(f"[Network] Sent {message_type} message ({len(compressed_msg)} bytes)")
                return True
            except Exception as send_error:
                print(f"Network send error: {send_error}")
                # Mark as disconnected if send fails
                self.is_connected = False
                return False
        except Exception as e:
            print(f"Message preparation error: {e}")
            return False
    
    def receive_messages(self):
        """
        Receive and process incoming messages with robust error handling
        """
        # Try to reconnect if not connected
        if not self.is_connected:
            if self.auto_reconnect:
                self.try_reconnect()
            if not self.is_connected or not self.socket:
                return []
        
        messages = []
        try:
            # Try to import select, but handle if not available
            try:
                import select
                
                # Try to receive data with timeout
                ready = select.select([self.socket], [], [], 0.01)
                if ready[0]:
                    # Receive data
                    data, addr = self.socket.recvfrom(MAX_PACKET_SIZE)
                    
                    # Process the message
                    if self.utils and self.use_compression:
                        message = self.utils.decompress_message(data)
                    else:
                        # Fallback decompression
                        try:
                            import zlib
                            decompressed_data = zlib.decompress(data).decode('utf-8')
                        except (ImportError, zlib.error):
                            decompressed_data = data.decode('utf-8')
                        
                        message = json.loads(decompressed_data)
                    
                    # Ignore messages from self
                    if message['node_id'] == self.node_id:
                        return messages
                    
                    # Update known nodes
                    self.known_nodes[message['node_id']] = (
                        addr[0], 
                        time.time(), 
                        message.get('payload', {}).get('squid', {})
                    )
                    
                    # Add to incoming queue for processing
                    self.incoming_queue.put((message, addr))
                    messages.append((message, addr))
            except ImportError:
                # select module not available
                if self.debug_mode:
                    print("[Network] select module not available, skipping receive")
                    
        except socket.timeout:
            # No data available, just continue
            pass
        except socket.error as sock_err:
            if self.debug_mode:
                print(f"Socket error during receive: {sock_err}")
            # Mark as disconnected on socket error
            self.is_connected = False
        except Exception as e:
            print(f"Network receive error: {e}")
            
        return messages
    
    def process_messages(self, plugin_manager):
        """Process received messages with prioritization"""
        messages_processed = 0
        
        try:
            # Sort messages by priority
            priority_messages = []
            normal_messages = []
            
            # Process up to 20 messages at a time
            for _ in range(20):
                if self.incoming_queue.empty():
                    break
                    
                message, addr = self.incoming_queue.get(block=False)
                
                # Skip messages from self
                if message['node_id'] == self.node_id:
                    continue
                    
                # Prioritize certain message types
                message_type = message.get('type', 'unknown')
                if message_type in ['squid_move', 'squid_exit', 'player_join', 'player_leave']:
                    priority_messages.append((message, addr))
                else:
                    normal_messages.append((message, addr))
            
            # Process priority messages first
            for message, addr in priority_messages:
                self._process_single_message(message, addr, plugin_manager)
                messages_processed += 1
                
            # Then process normal messages
            for message, addr in normal_messages:
                self._process_single_message(message, addr, plugin_manager)
                messages_processed += 1
                    
        except Exception as e:
            if hasattr(e, '__module__') and e.__module__ == 'queue' and e.__class__.__name__ == 'Empty':
                pass  # Silently handle empty queue
            else:
                print(f"Error processing messages: {e}")
                import traceback
                traceback.print_exc()
        
        return messages_processed

    def _process_single_message(self, message, addr, plugin_manager):
        """Process a single message"""
        # Determine hook name based on message type
        message_type = message.get('type', 'unknown')
        hook_name = f"network_{message_type}"
        
        # Trigger the appropriate hook with the message
        if hasattr(plugin_manager, 'trigger_hook'):
            plugin_manager.trigger_hook(
                hook_name,
                node=self,
                message=message,
                addr=addr
            )
    


class MultiplayerPlugin:
    def __init__(self):
        
        self.network_lock = threading.RLock()
        self.remote_squids_lock = threading.RLock()
        self.remote_objects_lock = threading.RLock()
        self.network_node = None
        self.plugin_manager = None
        self.tamagotchi_logic = None
        self.sync_timer = None
        self.remote_squids = {}
        self.remote_objects = {}
        self.last_message_times = {}
        self.debug_mode = False
        self.config_dialog = None
        self.status_bar = None
        self.connection_lines = {}
        self.is_setup = False
        self.incoming_queue = queue.Queue()
    
        # Module Constants
        self.MULTICAST_GROUP = MULTICAST_GROUP
        self.MULTICAST_PORT = MULTICAST_PORT
        self.SYNC_INTERVAL = SYNC_INTERVAL
        self.REMOTE_SQUID_OPACITY = REMOTE_SQUID_OPACITY
        self.SHOW_REMOTE_LABELS = SHOW_REMOTE_LABELS
        self.SHOW_CONNECTION_LINES = SHOW_CONNECTION_LINES

    def debug_autopilot_status(self):
        """Debug the status of all autopilot controllers"""
        if not hasattr(self, 'remote_squid_controllers'):
            print("No remote squid controllers exist")
            return
        
        print(f"\n=== AUTOPILOT DEBUG ({len(self.remote_squid_controllers)} controllers) ===")
        
        for node_id, controller in self.remote_squid_controllers.items():
            print(f"Squid {node_id[-4:]}:")
            print(f"  State: {controller.state}")
            print(f"  Position: ({controller.squid_data['x']:.1f}, {controller.squid_data['y']:.1f})")
            print(f"  Direction: {controller.squid_data['direction']}")
            print(f"  Home direction: {controller.home_direction}")
            print(f"  Time away: {controller.time_away:.1f}s / {controller.max_time_away:.1f}s")
            print(f"  Activities: {controller.food_eaten_count} food, {controller.rock_interaction_count} rocks")
            
            if controller.target_object:
                print(f"  Has target: Yes ({type(controller.target_object).__name__})")
            else:
                print(f"  Has target: No")
        
        print("=====================================\n")

    def enable(self):
        """Enable the multiplayer plugin"""
        try:
            if not hasattr(self, 'is_setup') or not self.is_setup:
                # If plugin_manager is None, try to get it from tamagotchi_logic
                if self.plugin_manager is None and hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
                    self.plugin_manager = self.tamagotchi_logic.plugin_manager
                
                # Make sure we have a plugin manager before continuing
                if self.plugin_manager is None:
                    print("Error: Cannot enable multiplayer plugin - no plugin manager available")
                    return False
                    
                success = self.setup(self.plugin_manager)
                if not success:
                    return False
                self.is_setup = True
            
            # Start network operations
            if self.network_node and not self.network_node.is_connected:
                self.network_node.initialize_socket()
            
            # Start timers
            if not hasattr(self, 'sync_thread') or not self.sync_thread.is_alive():
                self.start_sync_timer()
            
            print("Multiplayer plugin successfully enabled")
            return True
        except Exception as e:
            print(f"Error enabling multiplayer plugin: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def disable(self):
        """Disable the multiplayer plugin"""
        # Send disconnect message
        if self.network_node and self.network_node.is_connected:
            self.network_node.send_message(
                'player_leave',
                {
                    'node_id': self.network_node.node_id,
                    'reason': 'plugin_disabled'
                }
            )
            self.network_node.is_connected = False
        
        # Clean up visuals
        self.cleanup()
        
        # Update status bar
        if hasattr(self, 'status_bar') and self.status_bar:
            self.status_bar.update_network_status(False)
            self.status_bar.update_peers_count(0)

    def setup_minimal_network(self):
        """Create a basic network implementation"""
            
        print("Creating minimal network implementation for multiplayer plugin")
        
        # Create a mock network interface that will work for basic functionality
        class MinimalNetworkInterface:
            def __init__(self):
                pass
                
            def create_socket(self, socket_type='udp'):
                import socket
                return socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                
        # Add this to the plugin manager
        self.plugin_manager.plugins['network_interface'] = {
            'name': 'network_interface',
            'version': '1.0.0',
            'author': 'System',
            'description': 'Minimal network implementation',
            'instance': MinimalNetworkInterface(),
            'is_setup': True
        }
        
        print("Minimal network interface created")

    def initialize_status_ui(self):
        """Initialize the status UI components"""
        try:
            if not hasattr(self.tamagotchi_logic, 'user_interface'):
                return
                
            ui = self.tamagotchi_logic.user_interface
            
            try:
                # Try to use the dedicated status widget if available
                from plugins.multiplayer.multiplayer_status_widget import MultiplayerStatusWidget
                
                # Create status widget if it doesn't exist
                if not hasattr(ui, 'multiplayer_status'):
                    ui.multiplayer_status = MultiplayerStatusWidget(ui.window)
                    
                    # Position in top-right corner
                    ui.multiplayer_status.move(
                        ui.window_width - ui.multiplayer_status.width() - 10, 
                        10
                    )
                    
                    # Hide by default (will be shown when enabled)
                    ui.multiplayer_status.hide()
                
                # Store reference
                self.status_widget = ui.multiplayer_status
                
                # Update with current status
                if self.network_node and self.network_node.is_connected:
                    self.status_widget.update_connection_status(True, self.network_node.node_id)
                    if hasattr(self.network_node, 'known_nodes'):
                        self.status_widget.update_peers(self.network_node.known_nodes)
                else:
                    self.status_widget.update_connection_status(False)
                
                # Show the widget
                self.status_widget.show()
                
                print("Multiplayer status widget initialized")
                
            except ImportError:
                print("Could not import MultiplayerStatusWidget, using fallback status bar")
                # Use status bar component as fallback
                self.initialize_status_bar()
        
        except Exception as e:
            print(f"Error initializing status UI: {e}")

    def _find_tamagotchi_logic(self, obj, depth=0):
        """
        Recursively search for Tamagotchi logic in an object
        
        Args:
            obj: Object to search
            depth: Current recursion depth
        
        Returns:
            Tamagotchi logic if found, None otherwise
        """
        # Prevent infinite recursion
        if depth > 3:
            return None
        
        # Print debug information
        print(f"{'  ' * depth}Searching object of type: {type(obj)}")
        
        # Check direct attribute
        if hasattr(obj, 'tamagotchi_logic'):
            print(f"{'  ' * depth}Found tamagotchi_logic via direct attribute")
            return obj.tamagotchi_logic
        
        # Check if the object itself might be the tamagotchi logic
        if obj.__class__.__name__ == 'TamagotchiLogic':
            print(f"{'  ' * depth}Object is TamagotchiLogic")
            return obj
        
        # Try to iterate through object attributes
        try:
            # Iterate through attributes, avoiding infinite recursion
            for attr_name in dir(obj):
                # Skip private and built-in attributes
                if attr_name.startswith('__'):
                    continue
                
                try:
                    attr = getattr(obj, attr_name)
                    
                    # Skip methods and functions
                    if inspect.ismethod(attr) or inspect.isfunction(attr):
                        continue
                    
                    # Skip None and primitive types
                    if attr is None or isinstance(attr, (int, str, bool, float)):
                        continue
                    
                    # Recursive search
                    result = self._find_tamagotchi_logic(attr, depth + 1)
                    if result is not None:
                        print(f"{'  ' * depth}Found tamagotchi_logic via recursive search")
                        return result
                except Exception as e:
                    print(f"{'  ' * depth}Error checking attribute {attr_name}: {e}")
        except Exception as e:
            print(f"{'  ' * depth}Error iterating attributes: {e}")
        
        return None
    
    def _animate_remote_squid_entry(self, squid_item, status_text, entry_direction):
        """
        Animate the entry of a remote squid
        
        Args:
            squid_item: QGraphicsPixmapItem of the squid
            status_text: QGraphicsTextItem for the squid's status
            entry_direction: Direction of entry
        """
        # Create position animation
        start_pos = squid_item.pos()
        target_pos = QtCore.QPointF(
            start_pos.x() + (100 if entry_direction in ["left", "right"] else 0),
            start_pos.y() + (100 if entry_direction in ["up", "down"] else 0)
        )
        
        # Position animation
        pos_animation = QtCore.QPropertyAnimation(squid_item, b"pos")
        pos_animation.setDuration(1000)
        pos_animation.setStartValue(start_pos)
        pos_animation.setEndValue(target_pos)
        pos_animation.setEasingCurve(QtCore.QEasingCurve.OutQuad)
        
        # Opacity animation
        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        squid_item.setGraphicsEffect(opacity_effect)
        opacity_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        opacity_animation.setDuration(1000)
        opacity_animation.setStartValue(0.2)
        opacity_animation.setEndValue(0.7)
        
        # Text position animation
        text_pos_animation = QtCore.QPropertyAnimation(status_text, b"pos")
        text_pos_animation.setDuration(1000)
        text_pos_animation.setStartValue(status_text.pos())
        text_pos_animation.setEndValue(QtCore.QPointF(
            target_pos.x(),
            target_pos.y() - 50
        ))
        
        # Create animation group
        animation_group = QtCore.QParallelAnimationGroup()
        animation_group.addAnimation(pos_animation)
        animation_group.addAnimation(opacity_animation)
        animation_group.addAnimation(text_pos_animation)
        
        # Start animations
        animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def get_opposite_direction(self, direction):
        """
        Get the opposite direction for entry
        
        Args:
            direction: Original exit direction
        
        Returns:
            str: Opposite direction
        """
        opposite_directions = {
            'left': 'right',
            'right': 'left',
            'up': 'down',
            'down': 'up'
        }
        return opposite_directions.get(direction, 'right')  # Default to right if unknown
    
    def handle_squid_exit_message(self, node, message, addr):
        """Handle squid boundary exit with improved transition and autopilot"""
        try:
            # Import RemoteSquidController
            from plugins.multiplayer.squid_multiplayer_autopilot import RemoteSquidController
            
            # Validate message
            try:
                from plugins.multiplayer.packet_validator import PacketValidator
                valid, error = PacketValidator.validate_message(message)
                if not valid:
                    print(f"Invalid squid_exit message: {error}")
                    return False
            except ImportError:
                # Basic validation if validator unavailable
                if 'payload' not in message:
                    print("Missing payload in squid_exit message")
                    return False
            
            # Extract critical exit information
            payload = message.get('payload', {})
            exit_data = payload.get('payload', payload)
            
            # Validate required fields
            required_fields = ['node_id', 'direction', 'position', 'color']
            if not all(field in exit_data for field in required_fields):
                print(f"Missing required fields in squid exit. Need: {required_fields}")
                print(f"Received data: {exit_data}")
                return False
            
            # Extract data
            source_node_id = exit_data['node_id']
            exit_direction = exit_data['direction']
            position = exit_data['position']
            color = exit_data['color']
            
            # Get state data if available
            state_data = exit_data.get('state', {})
            
            # Determine entry point dynamically
            window_width = exit_data.get('window_width', 1280)
            window_height = exit_data.get('window_height', 900)
            
            # Calculate entry coordinates based on exit direction
            if exit_direction == 'left':
                entry_x = window_width - 253  # Right side of window
                entry_y = position.get('y', window_height // 2)
                entry_direction = 'right'  # Coming from the right
            elif exit_direction == 'right':
                entry_x = 100  # Left side of window
                entry_y = position.get('y', window_height // 2)
                entry_direction = 'left'  # Coming from the left
            elif exit_direction == 'up':
                entry_x = window_width // 2
                entry_y = window_height - 253  # Bottom of window
                entry_direction = 'down'  # Coming from the bottom
            elif exit_direction == 'down':
                entry_x = window_width // 2
                entry_y = 100  # Top of window
                entry_direction = 'up'  # Coming from the top
            else:
                print(f"Unknown exit direction: {exit_direction}")
                return False
            
            # Prepare squid data for remote representation
            squid_data = {
                'x': entry_x,
                'y': entry_y,
                'direction': entry_direction,
                'color': color,
                'status': 'ENTERING',
                'view_cone_visible': exit_data.get('view_cone_visible', False),
                'carrying_rock': state_data.get('carrying_rock', False),
                'hunger': state_data.get('hunger', 50),
                'happiness': state_data.get('happiness', 50),
                'is_sleeping': state_data.get('is_sleeping', False),
                'entry_direction': entry_direction,  # Store entry direction for return trip
                'entry_time': time.time(),
                'window_width': self.tamagotchi_logic.user_interface.window_width,
                'window_height': self.tamagotchi_logic.user_interface.window_height,
                'home_direction': self.get_opposite_direction(exit_direction)
            }
            
            # Create or update remote squid representation
            if hasattr(self, 'entity_manager'):
                result = self.entity_manager.update_remote_squid(
                    source_node_id, 
                    squid_data, 
                    is_new_arrival=True
                )
            else:
                result = self.update_remote_squid(
                    source_node_id, 
                    squid_data, 
                    is_new_arrival=True
                )
            
            # Store controller creation parameters to be handled in main thread
            if not hasattr(self, 'pending_controller_creations'):
                self.pending_controller_creations = []
                
            # Queue controller creation for main thread
            self.pending_controller_creations.append({
                'node_id': source_node_id,
                'squid_data': squid_data,
                'timestamp': time.time()
            })
            
            # Ensure the controller creation timer is running
            if not hasattr(self, 'controller_creation_timer') or not self.controller_creation_timer.isActive():
                # Create the timer in the main thread
                QtCore.QTimer.singleShot(0, self._setup_controller_creation_timer)
            
            # Broadcast acknowledgment
            if self.network_node and self.network_node.is_connected:
                self.network_node.send_message(
                    'new_squid_arrival', 
                    {
                        'node_id': source_node_id,
                        'status': 'ACKNOWLEDGED',
                        'entry_point': {
                            'x': entry_x,
                            'y': entry_y
                        }
                    }
                )
            
            # Notify local squid about remote squid presence
            if hasattr(self.tamagotchi_logic.squid, 'process_squid_detection'):
                self.tamagotchi_logic.squid.process_squid_detection(source_node_id, True)
            
            # User notification
            if hasattr(self.tamagotchi_logic, 'show_message'):
                self.tamagotchi_logic.show_message(
                    f"🌐 Remote squid {source_node_id[-4:]} crossed from {exit_direction}"
                )
            
            return result
        
        except Exception as e:
            print(f"CRITICAL ERROR in squid exit handler: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def _setup_controller_creation_timer(self):
        """Set up a timer to process pending controller creations in the main thread"""
        self.controller_creation_timer = QtCore.QTimer()
        self.controller_creation_timer.timeout.connect(self._process_pending_controller_creations)
        self.controller_creation_timer.start(100)  # Check every 100ms
        
        if self.debug_mode:
            print(f"Started controller creation timer")

    
    def _process_pending_controller_creations(self):
        """Process any pending controller creations in the main thread"""
        if not hasattr(self, 'pending_controller_creations') or not self.pending_controller_creations:
            return
            
        # Process all pending creations
        from plugins.multiplayer.squid_multiplayer_autopilot import RemoteSquidController
        
        for creation_data in list(self.pending_controller_creations):
            try:
                node_id = creation_data['node_id']
                squid_data = creation_data['squid_data']
                
                # Initialize remote_squid_controllers if needed
                if not hasattr(self, 'remote_squid_controllers'):
                    self.remote_squid_controllers = {}
                    
                # Create controller
                if self.debug_mode:
                    print(f"Creating autopilot controller for squid {node_id[-4:]}")
                    
                self.remote_squid_controllers[node_id] = RemoteSquidController(
                    squid_data=squid_data,
                    scene=self.tamagotchi_logic.user_interface.scene,
                    debug_mode=self.debug_mode
                )
                
                if self.debug_mode:
                    print(f"Controller created successfully in state: {self.remote_squid_controllers[node_id].state}")
                    
                # Remove from pending list
                self.pending_controller_creations.remove(creation_data)
                
            except Exception as e:
                print(f"Error creating remote squid controller: {e}")
                import traceback
                traceback.print_exc()
                
                # Remove failed creation to avoid retrying endlessly
                self.pending_controller_creations.remove(creation_data)
        
        # Start controller update timer if needed
        if self.remote_squid_controllers and (not hasattr(self, 'controller_update_timer') or not self.controller_update_timer.isActive()):
            self.controller_update_timer = QtCore.QTimer()
            self.controller_update_timer.timeout.connect(self.update_remote_controllers)
            self.controller_update_timer.start(50)  # 50ms update interval (20 FPS)
            
            if self.debug_mode:
                print(f"Started controller update timer at 20 FPS")


    def _get_opposite_direction(self, direction):
        """
        Get the opposite of the given direction
        
        Args:
            direction (str): Original exit direction
        
        Returns:
            str: Opposite direction
        """
        opposite_directions = {
            'left': 'right',
            'right': 'left',
            'up': 'down',
            'down': 'up'
        }
        return opposite_directions.get(direction, 'right')
        
    def _calculate_entry_x(self, direction, window_width):
        """Dynamically calculate entry x-coordinate based on exit direction"""
        if direction == 'right':
            return 0  # Enter from left side
        elif direction == 'left':
            return window_width - 253  # Enter from right side
        elif direction == 'up':
            return window_width // 2  # Enter from middle bottom
        elif direction == 'down':
            return window_width // 2  # Enter from middle top
        return window_width // 2
    
    def update_remote_controllers(self):
        """Update all remote squid controllers"""
        if not hasattr(self, 'remote_squid_controllers'):
            return
            
        # Calculate delta time
        current_time = time.time()
        delta_time = current_time - getattr(self, 'last_controller_update', current_time)
        self.last_controller_update = current_time
        
        # Update each controller
        for node_id, controller in list(self.remote_squid_controllers.items()):
            try:
                # Update controller AI
                controller.update(delta_time)
                
                # Get updated squid data
                squid_data = controller.squid_data
                
                # Update visual representation safely
                if node_id in self.remote_squids:
                    remote_squid = self.remote_squids[node_id]
                    
                    # Update position
                    if 'visual' in remote_squid:
                        remote_squid['visual'].setPos(squid_data['x'], squid_data['y'])
                    
                    # Update direction image
                    if 'visual' in remote_squid and 'direction' in squid_data:
                        self.update_remote_squid_image(remote_squid, squid_data['direction'])
                    
                    # Update status text
                    if 'status_text' in remote_squid:
                        status = squid_data.get('status', 'visiting')
                        remote_squid['status_text'].setPlainText(status)
                        remote_squid['status_text'].setPos(
                            squid_data['x'],
                            squid_data['y'] - 30
                        )
                else:
                    # Remote squid visual disappeared, cleanup controller
                    if self.debug_mode:
                        print(f"Remote squid {node_id} visual missing, removing controller")
                    del self.remote_squid_controllers[node_id]
                    
            except Exception as e:
                print(f"Error updating controller for {node_id}: {e}")


    def calculate_entry_position(self, direction):
        """Calculate entry position for a returning squid"""
        # Get window dimensions
        width = self.tamagotchi_logic.user_interface.window_width
        height = self.tamagotchi_logic.user_interface.window_height
        
        # Default to center if direction unknown
        if not direction:
            return (width // 2, height // 2)
        
        # Calculate based on direction
        if direction == 'left':
            return (100, height // 2)
        elif direction == 'right':
            return (width - 200, height // 2)
        elif direction == 'up':
            return (width // 2, 100)
        elif direction == 'down':
            return (width // 2, height - 200)
        
        # Default fallback
        return (width // 2, height // 2)
    
    def apply_remote_experiences(self, squid, activity_summary):
        """Apply the effects of remote activities to the returning squid"""
        # Extract activity data
        food_eaten = activity_summary.get('food_eaten', 0)
        rock_interactions = activity_summary.get('rock_interactions', 0)
        distance_traveled = activity_summary.get('distance_traveled', 0)
        time_away = activity_summary.get('time_away', 0)
        
        # Apply hunger reduction from food
        if food_eaten > 0:
            hunger_reduction = min(15 * food_eaten, 60)  # Cap at 60 points
            squid.hunger = max(0, squid.hunger - hunger_reduction)
            
            # Create memory
            squid.memory_manager.add_short_term_memory(
                'travel', 'remote_feeding',
                f"Ate {food_eaten} food items while exploring another tank"
            )
        
        # Apply happiness/satisfaction from rock interactions
        if rock_interactions > 0:
            happiness_boost = min(5 * rock_interactions, 30)  # Cap at 30 points
            satisfaction_boost = min(10 * rock_interactions, 40)  # Cap at 40 points
            
            squid.happiness = min(100, squid.happiness + happiness_boost)
            squid.satisfaction = min(100, squid.satisfaction + satisfaction_boost)
            
            # Create memory
            squid.memory_manager.add_short_term_memory(
                'travel', 'remote_rocks',
                f"Played with {rock_interactions} rocks in another tank"
            )
        
        # Apply tiredness from distance traveled
        if distance_traveled > 0:
            # Convert to approximate pixels
            tiredness = distance_traveled / 1000  # One point per 1000 pixels
            squid.sleepiness = min(100, squid.sleepiness + tiredness)
        
        # Apply anxiety reduction from successful journey
        anxiety_reduction = min(20, time_away / 60 * 10)  # 10 points per minute, max 20
        squid.anxiety = max(0, squid.anxiety - anxiety_reduction)
        
        # Apply curiosity reduction (satisfied from exploration)
        curiosity_reduction = min(30, time_away / 30 * 10)  # 10 points per 30 seconds, max 30
        squid.curiosity = max(0, squid.curiosity - curiosity_reduction)
        
        # Create overall journey memory with higher importance
        minutes = int(time_away / 60)
        seconds = int(time_away % 60)
        
        journey_memory = (
            f"Completed a journey to another tank lasting {minutes}m {seconds}s. "
            f"Ate {food_eaten} food items, interacted with {rock_interactions} rocks, "
            f"and traveled approximately {int(distance_traveled)} pixels."
        )
        
        squid.memory_manager.add_short_term_memory(
            'travel', 'completed_journey',
            journey_memory,
            importance=8  # Higher importance for memorable journey
        )


    def handle_squid_return(self, node, message, addr):
        """Handle a squid returning from another instance"""
        try:
            # Extract data
            payload = message.get('payload', {})
            node_id = payload.get('node_id')
            activity_summary = payload.get('activity_summary', {})
            return_direction = payload.get('return_direction')
            
            # Verify this is actually our squid
            if node_id != getattr(self.tamagotchi_logic.network_node, 'node_id', None):
                if self.debug_mode:
                    print(f"Received return for node {node_id}, but we are {getattr(self.tamagotchi_logic.network_node, 'node_id', 'unknown')}")
                return
                
            # Calculate entry position based on return direction
            entry_pos = self.calculate_entry_position(return_direction)
            
            # Fade in the local squid
            squid = self.tamagotchi_logic.squid
            
            # Set position
            squid.squid_x = entry_pos[0]
            squid.squid_y = entry_pos[1]
            squid.squid_item.setPos(squid.squid_x, squid.squid_y)
            
            # Create fade in animation
            fade_in = QtCore.QPropertyAnimation(squid.squid_item, b"opacity")
            fade_in.setDuration(1000)
            fade_in.setStartValue(0.0)
            fade_in.setEndValue(1.0)
            fade_in.start()
            
            # Update squid properties based on activities
            self.apply_remote_experiences(squid, activity_summary)
            
            # Show welcome back message
            if hasattr(self.tamagotchi_logic, 'show_message'):
                time_away = activity_summary.get('time_away', 0)
                minutes_away = int(time_away / 60)
                seconds_away = int(time_away % 60)
                
                self.tamagotchi_logic.show_message(
                    f"Your squid returned after {minutes_away}m {seconds_away}s in another tank!"
                )
                
            # Re-enable movement
            squid.can_move = True
            squid.is_transitioning = False
            
        except Exception as e:
            print(f"Error handling squid return: {e}")
            import traceback
            traceback.print_exc()


    def _create_arrival_animation(self, visual_item):
        """Create an attention-grabbing animation for newly arrived squids"""
        try:
            # Use a simple opacity effect which is safer across threads
            opacity_effect = QtWidgets.QGraphicsOpacityEffect()
            visual_item.setGraphicsEffect(opacity_effect)
            
            # Create fade in effect
            fade_in = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
            fade_in.setDuration(1000)
            fade_in.setStartValue(0.3)
            fade_in.setEndValue(self.REMOTE_SQUID_OPACITY)
            fade_in.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
            
            # Schedule reset using a single-shot timer (thread-safe)
            QtCore.QTimer.singleShot(5000, lambda: self._reset_remote_squid_style(visual_item))
        except Exception as e:
            print(f"Animation error: {e}")
            # Fallback - just set the opacity directly
            visual_item.setOpacity(0.7)

    def _reset_remote_squid_style(self, visual_item):
        """Reset visual style of remote squid after entry period"""
        # Find which squid this belongs to
        for node_id, squid_data in self.remote_squids.items():
            if squid_data['visual'] == visual_item:
                # Reset status text
                if 'status_text' in squid_data:
                    squid_data['status_text'].setDefaultTextColor(QtGui.QColor(200, 200, 200))
                    squid_data['status_text'].setFont(QtGui.QFont("Arial", 10))
                    squid_data['status_text'].setPlainText("visiting")
                
                # Reset visual properties
                visual_item.setZValue(-1)
                visual_item.setOpacity(REMOTE_SQUID_OPACITY)
                
                # Reset ID text
                if 'id_text' in squid_data:
                    squid_data['id_text'].setZValue(-1)
                    
                break
    
    def setup(self, plugin_manager):
        """Set up the multiplayer plugin with better dependency handling"""
        try:
            # Store plugin manager reference
            self.plugin_manager = plugin_manager
            
            # Add these lines to ensure the settings are properly initialized
            self.MULTICAST_GROUP = MULTICAST_GROUP
            self.MULTICAST_PORT = MULTICAST_PORT
            self.SYNC_INTERVAL = SYNC_INTERVAL
            self.REMOTE_SQUID_OPACITY = REMOTE_SQUID_OPACITY 
            self.SHOW_REMOTE_LABELS = SHOW_REMOTE_LABELS
            self.SHOW_CONNECTION_LINES = SHOW_CONNECTION_LINES

            self.message_process_timer = QtCore.QTimer()
            self.message_process_timer.timeout.connect(self.process_queued_messages)
            self.message_process_timer.start(50)  # Process messages every 50ms
            
            # Try to import dependencies
            try:
                import socket
                import threading
                import json
                network_available = True
            except ImportError as e:
                print(f"Warning: Missing dependency for multiplayer: {e}")
                network_available = False
            
            # Extract debug mode setting
            if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
                self.debug_mode = getattr(self.tamagotchi_logic, 'debug_mode', False)
            
            # Get or create tamagotchi_logic reference
            if not hasattr(self, 'tamagotchi_logic') or self.tamagotchi_logic is None:
                if hasattr(plugin_manager, 'tamagotchi_logic'):
                    self.tamagotchi_logic = plugin_manager.tamagotchi_logic
                    print("Found tamagotchi_logic from plugin_manager")
                else:
                    print("WARNING: Could not find tamagotchi_logic")
                    return False
            
            # Create unique node ID
            import uuid
            node_id = f"squid_{uuid.uuid4().hex[:8]}"
            self.network_node = NetworkNode(node_id)
            self.network_node.debug_mode = self.debug_mode
            
            print(f"Network Node Created:")
            print(f"  Node ID: {node_id}")
            print(f"  Local IP: {self.network_node.local_ip}")
            print(f"  Is Connected: {self.network_node.is_connected}")
            
            # Initialize event system 
            try:
                from plugins.multiplayer.multiplayer_events import MultiplayerEventDispatcher
                self.event_dispatcher = MultiplayerEventDispatcher()
                self.event_dispatcher.debug_mode = self.debug_mode
            except ImportError:
                print("Could not import MultiplayerEventDispatcher, using fallback")
                self.event_dispatcher = None
            
            # Start network threads if networking is available
            if network_available:
                # Start network receive thread 
                receive_thread = threading.Thread(
                    target=self.network_receive_loop, 
                    daemon=True
                )
                receive_thread.start()
                
                # Start synchronization thread
                self.start_sync_timer()
            else:
                print("Network functionality limited due to missing dependencies")
            
            # Register network hooks
            self._register_hooks()
            
            # Initialize remote entity management
            try:
                ui = self.tamagotchi_logic.user_interface
                scene = ui.scene
                
                # Initialize RemoteSquidController collection
                self.remote_squid_controllers = {}
                self.last_controller_update = time.time()
                
                # Set up controller update timer
                self.controller_update_timer = QtCore.QTimer()
                self.controller_update_timer.timeout.connect(self.update_remote_controllers)
                self.controller_update_timer.start(50)  # 20 FPS updates
                
                try:
                    # Import autopilot module
                    from plugins.multiplayer.squid_multiplayer_autopilot import RemoteSquidController
                    print("Successfully imported RemoteSquidController")
                except ImportError as e:
                    print(f"Warning: RemoteSquidController module not found: {e}")
                    print("Movement of remote squids will be limited")
                
                try:
                    # Try to use the dedicated entity manager if available
                    from plugins.multiplayer.remote_entity_manager import RemoteEntityManager
                    self.entity_manager = RemoteEntityManager(
                        scene,
                        ui.window_width,
                        ui.window_height,
                        self.debug_mode
                    )
                    print("Using dedicated RemoteEntityManager")
                except ImportError:
                    print("Could not import RemoteEntityManager, using existing implementation")
                    # Initialize the traditional way
                    self.initialize_remote_representation()
            except Exception as e:
                print(f"Error initializing remote representation: {e}")
                # Create fallback representation system
                self.remote_squids = {}
                self.remote_objects = {}
                self.connection_lines = {}
                self.remote_squid_controllers = {}
            
            # Initialize status UI component if possible
            self.initialize_status_ui()
            
            # If tamagotchi_logic exists, explicitly set network_node
            if self.tamagotchi_logic:
                self.tamagotchi_logic.network_node = self.network_node
            
            # Show connection message
            if (hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic and 
                hasattr(self.tamagotchi_logic, 'show_message')):
                self.tamagotchi_logic.show_message(f"Connected to squid network as {node_id}")
            
            # Log status
            print(f"Multiplayer initialized with node ID: {node_id}")
            print(f"Listening on {self.network_node.local_ip}:{MULTICAST_PORT}")
            
            return True
        
        except Exception as e:
            print(f"Error in multiplayer setup: {e}")
            import traceback
            traceback.print_exc()
            return False
        
    def process_queued_messages(self):
        """Process messages from the queue in the main thread"""
        # Process up to 10 messages at a time to avoid blocking
        processed = 0
        while not self.incoming_queue.empty() and processed < 10:
            try:
                message, addr = self.incoming_queue.get_nowait()
                if self.plugin_manager:
                    message_type = message.get('type', 'unknown')
                    hook_name = f"network_{message_type}"
                    self.plugin_manager.trigger_hook(hook_name, node=self.network_node, message=message, addr=addr)
                processed += 1
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error processing queued message: {e}")
    
    def network_receive_loop(self):
        """Continuous loop for receiving network messages"""
        import select  # Import here to avoid global import issues
        while True:
            try:
                # Only try to receive if the node is connected
                if self.network_node and self.network_node.is_connected:
                    messages = self.network_node.receive_messages()
                    
                    # Instead of processing directly, queue messages for main thread processing
                    for message in messages:
                        # Add to queue for main thread to process
                        self.incoming_queue.put(message)
                    
                # Add a small delay to prevent CPU hogging
                time.sleep(0.01)
                
            except Exception as e:
                print(f"Error in network receive loop: {e}")
                time.sleep(1)  # Longer delay after error
    
    def initialize_status_bar(self):
        """Initialize the status bar if available"""
        try:
            if (self.tamagotchi_logic and 
                hasattr(self.tamagotchi_logic, 'user_interface') and
                self.tamagotchi_logic.user_interface):
                
                ui = self.tamagotchi_logic.user_interface
                
                # Check if status bar already exists
                if hasattr(ui, 'status_bar'):
                    self.status_bar = ui.status_bar
                else:
                    # Import and create status bar
                    from status_bar_component import StatusBarComponent
                    ui.status_bar = StatusBarComponent(ui.window)
                    self.status_bar = ui.status_bar
                
                # Update network status
                if self.status_bar:
                    if self.network_node and self.network_node.is_connected:
                        self.status_bar.update_network_status(True, self.network_node.node_id)
                    else:
                        self.status_bar.update_network_status(False)
        
        except Exception as e:
            print(f"Error initializing status bar: {e}")
    
    def register_menu_actions(self, ui, menu):
        """
        Register menu actions for the Multiplayer plugin
        
        Args:
            ui: The main user interface
            menu: The menu to add actions to
        """
        # About action
        about_action = QtWidgets.QAction('About Multiplayer', ui.window)
        about_action.triggered.connect(self.show_about_dialog)
        menu.addAction(about_action)
        
        # Configuration action
        config_action = QtWidgets.QAction('Network Settings', ui.window)
        config_action.triggered.connect(self.show_config_dialog)
        menu.addAction(config_action)
        
        # Refresh connections action
        refresh_action = QtWidgets.QAction('Refresh Connections', ui.window)
        refresh_action.triggered.connect(self.refresh_connections)
        menu.addAction(refresh_action)
        
        # Toggle connection lines
        connections_action = QtWidgets.QAction('Show Connection Lines', ui.window)
        connections_action.setCheckable(True)
        connections_action.setChecked(self.SHOW_CONNECTION_LINES)
        connections_action.triggered.connect(
            lambda checked: self.toggle_connection_lines(checked)
        )
        menu.addAction(connections_action)
        
        # Only add debug action if debug mode is enabled
        if hasattr(self, 'debug_mode') and self.debug_mode:
            menu.addSeparator()  # Add separator before debug items
            debug_action = QtWidgets.QAction('Debug Autopilot Status', ui.window)
            debug_action.triggered.connect(self.debug_autopilot_status)
            menu.addAction(debug_action)

    def update_menu_states(self):
        """Update menu item states when menu is about to show"""
        if hasattr(self, 'connection_action'):
            self.connection_action.setChecked(SHOW_CONNECTION_LINES)

    def show_about_dialog(self):
        """Show about dialog for the multiplayer plugin"""
        about_text = (
            f"<b>Multiplayer Plugin</b><br><br>"
            f"Version: {PLUGIN_VERSION}<br>"
            f"Author: {PLUGIN_AUTHOR}<br><br>"
            f"{PLUGIN_DESCRIPTION}<br><br>"
            f"Node ID: {getattr(self.network_node, 'node_id', 'N/A')}<br>"
            f"IP: {getattr(self.network_node, 'local_ip', 'N/A')}"
        )
        
        msg = QtWidgets.QMessageBox()
        msg.setWindowTitle("About Multiplayer Plugin")
        msg.setTextFormat(QtCore.Qt.RichText)
        msg.setText(about_text)
        msg.setIcon(QtWidgets.QMessageBox.Information)
        msg.exec_()
    
    def show_config_dialog(self):
        """Show the multiplayer configuration dialog"""
        from multiplayer_config_dialog import MultiplayerConfigDialog
        
        if not self.config_dialog:
            parent = None
            if self.tamagotchi_logic and hasattr(self.tamagotchi_logic, 'user_interface'):
                parent = self.tamagotchi_logic.user_interface.window
            
            self.config_dialog = MultiplayerConfigDialog(
                plugin=self,  # plugin instance
                parent=parent,
                multicast_group=MULTICAST_GROUP,
                port=MULTICAST_PORT,
                sync_interval=SYNC_INTERVAL,
                remote_opacity=REMOTE_SQUID_OPACITY,
                show_labels=SHOW_REMOTE_LABELS,
                show_connections=SHOW_CONNECTION_LINES
            )
        
        self.config_dialog.exec_()

    def register_menu_actions(self, ui, menu):
        """
        Register menu actions for the Multiplayer plugin
        
        Args:
            ui: The main user interface
            menu: The menu to add actions to
        """
        # About action
        about_action = QtWidgets.QAction('About Multiplayer', ui.window)
        about_action.triggered.connect(self.show_about_dialog)
        menu.addAction(about_action)
        
        # Configuration action
        config_action = QtWidgets.QAction('Network Settings', ui.window)
        config_action.triggered.connect(self.show_config_dialog)
        menu.addAction(config_action)
        
        # Refresh connections action
        refresh_action = QtWidgets.QAction('Refresh Connections', ui.window)
        refresh_action.triggered.connect(self.refresh_connections)
        menu.addAction(refresh_action)
        
        # Toggle connection lines
        connections_action = QtWidgets.QAction('Show Connection Lines', ui.window)
        connections_action.setCheckable(True)
        connections_action.setChecked(SHOW_CONNECTION_LINES)
        connections_action.triggered.connect(
            lambda checked: self.toggle_connection_lines(checked)
        )
        menu.addAction(connections_action)
    
    def toggle_connection_lines(self, enabled):
        """Toggle visibility of connection lines to remote squids"""
        global SHOW_CONNECTION_LINES
        SHOW_CONNECTION_LINES = enabled
        
        # Update existing connection lines if a UI is available
        if hasattr(self, 'tamagotchi_logic') and hasattr(self.tamagotchi_logic, 'user_interface'):
            ui = self.tamagotchi_logic.user_interface
            
            for line in self.connection_lines.values():
                if line in ui.scene.items():
                    line.setVisible(enabled)
        
        # Optional: Add a status message
        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(
                f"Connection lines {'enabled' if enabled else 'disabled'}"
            )
    
    def refresh_connections(self):
        """Refresh all network connections"""
        if not self.network_node:
            return
            
        # Send a heartbeat to announce presence
        self.network_node.send_message(
            'heartbeat',
            {
                'node_id': self.network_node.node_id,
                'status': 'active',
                'refresh': True
            }
        )
        
        # Update the status bar
        if self.status_bar:
            peers_count = len(self.network_node.known_nodes)
            self.status_bar.update_peers_count(peers_count)
            self.status_bar.add_message(f"Refreshed connections. {peers_count} peers detected.")
    
    def initialize_remote_representation(self):
        """Initialize visual representations for remote entities"""
        # Will be populated as remote squids are discovered
        self.remote_squids = {}
        self.remote_objects = {}
        self.connection_lines = {}
        
        # Create a timer to cleanup stale remote nodes
        self.cleanup_timer = QtCore.QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_stale_nodes)
        self.cleanup_timer.start(5000)  # Run every 5 seconds
        
        # Create another timer to update connection lines
        self.connection_timer = QtCore.QTimer()
        self.connection_timer.timeout.connect(self.update_connection_lines)
        self.connection_timer.start(1000)  # Update every second
    
    def cleanup_stale_nodes(self):
        """Remove nodes that haven't been seen recently"""
        if not self.network_node:
            return
            
        current_time = time.time()
        stale_threshold = 10.0  # Consider nodes stale after 10 seconds
        
        # Find stale nodes
        stale_nodes = []
        for node_id, (ip, last_seen, _) in self.network_node.known_nodes.items():
            if current_time - last_seen > stale_threshold:
                stale_nodes.append(node_id)
                
                # Remove visual representation if it exists
                if node_id in self.remote_squids:
                    self.remove_remote_squid(node_id)
        
        # Remove stale nodes
        for node_id in stale_nodes:
            del self.network_node.known_nodes[node_id]
            if self.debug_mode:
                print(f"[Network] Removed stale node: {node_id}")
        
        # Update status bar with peer count
        if self.status_bar:
            peers_count = len(self.network_node.known_nodes)
            self.status_bar.update_peers_count(peers_count)
    
    def update_connection_lines(self):
        """Update the visual lines connecting to remote squids"""
        if not SHOW_CONNECTION_LINES or not self.tamagotchi_logic:
            return
            
        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        squid = self.tamagotchi_logic.squid
        
        # Get local squid position
        local_pos = (squid.squid_x + squid.squid_width/2, squid.squid_y + squid.squid_height/2)
        
        # Update/create lines for each remote squid
        for node_id, squid_data in self.remote_squids.items():
            # Skip if no visual
            if 'visual' not in squid_data:
                continue
                
            remote_visual = squid_data['visual']
            remote_pos = remote_visual.pos()
            remote_center = (remote_pos.x() + 30, remote_pos.y() + 20)  # Center of ellipse
            
            # Create or update connection line
            if node_id in self.connection_lines:
                line = self.connection_lines[node_id]
                line.setLine(local_pos[0], local_pos[1], remote_center[0], remote_center[1])
            else:
                # Create new line
                line = QtWidgets.QGraphicsLineItem(
                    local_pos[0], local_pos[1], remote_center[0], remote_center[1]
                )
                
                # Style the line
                color = squid_data.get('data', {}).get('color', (100, 100, 255))
                pen = QtGui.QPen(QtGui.QColor(*color, 100))
                pen.setWidth(2)
                pen.setStyle(QtCore.Qt.DashLine)
                line.setPen(pen)
                
                # Add to scene and store reference
                line.setZValue(-5)  # Below squids
                line.setVisible(SHOW_CONNECTION_LINES)
                scene.addItem(line)
                self.connection_lines[node_id] = line
    
    def _register_hooks(self):
        """
        Register network-related hooks
        """
        hooks = [
            "network_squid_move",
            "network_squid_action",
            "network_object_sync",
            "network_rock_throw",
            "network_player_join",
            "network_player_leave",
            "network_heartbeat",
            "network_state_update",
            "network_squid_exit"
        ]

        for hook in hooks:
            self.plugin_manager.register_hook(hook)

        # Make sure this subscription exists and is correct
        self.plugin_manager.subscribe_to_hook(
            "network_squid_exit",
            "multiplayer",  # Lowercase to match plugin_manager's keys
            self.handle_squid_exit_message
        )

        self.plugin_manager.subscribe_to_hook(
            "network_object_sync",
            PLUGIN_NAME,
            self.handle_object_sync
        )

        self.plugin_manager.subscribe_to_hook(
            "network_squid_move",
            PLUGIN_NAME,
            self.handle_squid_move
        )

        self.plugin_manager.subscribe_to_hook(
            "network_rock_throw",
            PLUGIN_NAME,
            self.handle_rock_throw
        )

        self.plugin_manager.subscribe_to_hook(
            "network_state_update",
            PLUGIN_NAME,
            self.handle_state_update
        )

        self.plugin_manager.subscribe_to_hook(
            "network_heartbeat",
            PLUGIN_NAME,
            self.handle_heartbeat
        )

        # Subscribe to pre-update hook for processing network messages
        self.plugin_manager.subscribe_to_hook(
            "pre_update",
            PLUGIN_NAME,
            self.pre_update
        )
        self.plugin_manager.register_hook("network_squid_return")
        self.plugin_manager.subscribe_to_hook(
            "network_squid_return",
            PLUGIN_NAME,
            self.handle_squid_return
        )


    
    def pre_update(self, *args, **kwargs):
        """Process any pending network messages before update"""
        if self.network_node:
            try:
                self.network_node.process_messages(self.plugin_manager)
            except Exception as e:
                if self.debug_mode:
                    print(f"Error processing messages in pre_update: {e}")
    
    def start_sync_timer(self):
        """Start adaptive periodic synchronization of game state"""
        def sync_state():
            while True:
                try:
                    if self.network_node and self.network_node.is_connected:
                        # Calculate appropriate sync interval based on activity
                        squid = self.tamagotchi_logic.squid
                        is_moving = hasattr(squid, 'is_moving') and squid.is_moving
                        
                        # More frequent updates when moving
                        if is_moving:
                            sync_delay = 0.25  # 4 updates per second when active
                        else:
                            sync_delay = 1.0  # 1 update per second when idle
                            
                        # Also consider number of peers
                        peers_count = len(getattr(self.network_node, 'known_nodes', {}))
                        if peers_count > 10:
                            sync_delay *= 1.5  # Reduce frequency with many peers
                            
                        self.sync_game_state()
                        time.sleep(sync_delay)
                    else:
                        time.sleep(1.0)  # Regular sleep when disconnected
                except Exception as e:
                    if self.debug_mode:
                        print(f"Error in sync_state: {e}")
                    time.sleep(1.0)
        
        sync_thread = threading.Thread(
            target=sync_state, 
            daemon=True
        )
        sync_thread.start()
    
    def sync_game_state(self):
        """
        Synchronize the current game state across the network
        """
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'squid'):
            return
        
        try:
            # Get current squid state
            squid_state = self._get_squid_state()
            
            # Get relevant objects to sync
            objects_state = self._get_objects_state()
            
            print(f"DEBUG: Found {len(objects_state)} objects to sync")
            print(f"DEBUG: Network node connected: {self.network_node.is_connected}")
            
            # Send synchronization message
            if self.network_node and self.network_node.is_connected:
                print(f"DEBUG: Sending sync message with {len(objects_state)} objects")
                self.network_node.send_message(
                    'object_sync', 
                    {
                        'squid': squid_state,
                        'objects': objects_state,
                        'node_info': {
                            'id': self.network_node.node_id,
                            'ip': self.network_node.local_ip
                        }
                    }
                )
                print("DEBUG: Sync message sent")
            else:
                print("DEBUG: Cannot send sync - network not connected")
            
            # Send heartbeat less frequently
            current_time = time.time()
            if current_time - self.last_message_times.get('heartbeat', 0) > 3.0:  # Every 3 seconds
                if self.network_node and self.network_node.is_connected:
                    print("DEBUG: Sending heartbeat message")
                    self.network_node.send_message(
                        'heartbeat',
                        {
                            'node_id': self.network_node.node_id,
                            'status': 'active',
                            'squid': {
                                'exists': True,
                                'position': (squid_state['x'], squid_state['y'])
                            }
                        }
                    )
                    self.last_message_times['heartbeat'] = current_time
                    print("DEBUG: Heartbeat sent")
                else:
                    print("DEBUG: Cannot send heartbeat - network not connected")
        
        except Exception as e:
            print(f"ERROR in sync_game_state: {e}")
            import traceback
            traceback.print_exc()
    
    def _get_squid_state(self):
        """
        Get the current squid state for network synchronization
        
        Returns:
            Dict: Squid state information
        """
        squid = self.tamagotchi_logic.squid
        direction_looking = self.get_actual_view_direction(squid)
        
        return {
            'x': squid.squid_x,
            'y': squid.squid_y,
            'direction': squid.squid_direction,
            'looking_direction': direction_looking,
            'view_cone_angle': getattr(squid, 'view_cone_angle', 1.0),
            'hunger': squid.hunger,
            'happiness': squid.happiness,
            'status': getattr(squid, 'status', "unknown"),
            'carrying_rock': getattr(squid, 'carrying_rock', False),
            'is_sleeping': squid.is_sleeping,
            'color': self.get_squid_color(),
            'node_id': self.network_node.node_id,
            'view_cone_visible': getattr(squid, 'view_cone_visible', False)
        }
    
    def get_actual_view_direction(self, squid):
        """Get the actual direction the squid is looking based on view cone or movement"""
        if hasattr(squid, 'current_view_angle'):
            return squid.current_view_angle
        
        # Fall back to mapping from movement direction to angle
        direction_to_angle = {
            'right': 0,
            'up': math.pi * 1.5,
            'left': math.pi,
            'down': math.pi * 0.5
        }
        return direction_to_angle.get(squid.squid_direction, 0)
    
    def get_squid_color(self):
        """Generate a persistent color for this squid based on node_id"""
        # Use the first 6 characters of the node_id hash to create a color
        if not hasattr(self, '_squid_color'):
            node_id = self.network_node.node_id
            # Create a hash of the node_id
            hash_val = 0
            for char in node_id:
                hash_val = (hash_val * 31 + ord(char)) & 0xFFFFFF
            
            # Generate RGB components from the hash
            r = (hash_val & 0xFF0000) >> 16
            g = (hash_val & 0x00FF00) >> 8
            b = hash_val & 0x0000FF
            
            # Ensure some minimum brightness
            r = max(r, 100)
            g = max(g, 100)
            b = max(b, 100)
            
            self._squid_color = (r, g, b)
        
        return self._squid_color
    
    def _get_objects_state(self):
        """
        Get the current game objects state for network synchronization
        
        Returns:
            List[Dict]: List of game object states
        """
        if not hasattr(self.tamagotchi_logic, 'user_interface'):
            return []
                
        ui = self.tamagotchi_logic.user_interface
        objects = []
        
        try:
            # Collect rocks, food, poop, decorations
            for item in ui.scene.items():
                if hasattr(item, 'filename') and isinstance(item, QtWidgets.QGraphicsPixmapItem):
                    
                    # Generate a stable object ID based on position and filename
                    pos = item.pos()
                    obj_id = f"{item.filename}_{int(pos.x())}_{int(pos.y())}"
                    
                    # Get scale if available, default to 1.0
                    scale = getattr(item, 'scale', lambda: 1.0)()
                    
                    objects.append({
                        'id': obj_id,
                        'type': self._determine_object_type(item),
                        'x': pos.x(),
                        'y': pos.y(),
                        'filename': item.filename,
                        'is_being_carried': getattr(item, 'is_being_carried', False),
                        'scale': scale
                    })
                    
                    if self.debug_mode:
                        print(f"Adding object for sync: {obj_id}, {item.filename}, {pos.x()}, {pos.y()}")
        except Exception as e:
            if self.debug_mode:
                print(f"Error getting object state: {e}")
                import traceback
                traceback.print_exc()
        
        return objects
    
    def _determine_object_type(self, item):
        """Determine the type of an object based on its properties"""
        if not hasattr(item, 'filename'):
            return 'unknown'
            
        filename = item.filename.lower()
        
        if 'rock' in filename:
            return 'rock'
        elif 'food' in filename or 'sushi' in filename or 'cheese' in filename:
            return 'food'
        elif 'poop' in filename:
            return 'poop'
        else:
            # Check for decoration category if available
            if hasattr(item, 'category'):
                return item.category
            return 'decoration'
    
    def handle_object_sync(self, node, message, addr):
        """
        Handle incoming object sync message
        
        Args:
            node: Network node
            message: Message data
            addr: Sender address
        """
        if not self.tamagotchi_logic or not hasattr(self.tamagotchi_logic, 'user_interface'):
            return
            
        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        
        try:
            # Get the remote squid data
            squid_data = message['payload'].get('squid', {})
            node_id = squid_data.get('node_id') or message['node_id']
            
            # Update or create remote squid representation
            self.update_remote_squid(node_id, squid_data)
            
            # Process remote objects
            if 'objects' in message['payload']:
                remote_objects = message['payload']['objects']
                self.process_remote_objects(remote_objects, node_id)
                
            # Notify local squid about remote squid presence
            if hasattr(self.tamagotchi_logic.squid, 'process_squid_detection'):
                self.tamagotchi_logic.squid.process_squid_detection(node_id, True)
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error handling object sync: {e}")
                traceback.print_exc()
    
    def handle_heartbeat(self, node, message, addr):
        """Handle heartbeat messages from other nodes"""
        if not self.tamagotchi_logic:
            return
            
        node_id = message['node_id']
        
        # Update status bar
        if self.status_bar:
            peers_count = len(node.known_nodes)
            self.status_bar.update_peers_count(peers_count)
            
            # Add a message about new peer if this is a new node
            if node_id not in self.remote_squids:
                self.status_bar.add_message(f"New remote squid detected: {node_id}")
    
    def update_remote_squid(self, node_id, squid_data, is_new_arrival=False):
        """Update or create a remote squid visualization"""
        if not squid_data or not all(k in squid_data for k in ['x', 'y']):
            return False
        
        # Check if we already have this remote squid
        if node_id in self.remote_squids:
            # Update existing squid
            remote_squid = self.remote_squids[node_id]
            remote_squid['visual'].setPos(squid_data['x'], squid_data['y'])
            
            # Update view cone if needed
            if 'view_cone_visible' in squid_data and squid_data['view_cone_visible']:
                self.update_remote_view_cone(node_id, squid_data)
            else:
                # Hide view cone if it exists
                if 'view_cone' in remote_squid and remote_squid['view_cone'] in self.scene.items():
                    self.scene.removeItem(remote_squid['view_cone'])
                    remote_squid['view_cone'] = None
                    
            
            # Update status text
            if 'status_text' in remote_squid:
                status = "ENTERING" if is_new_arrival else squid_data.get('status', 'unknown')
                remote_squid['status_text'].setPlainText(f"{status}")
                remote_squid['status_text'].setPos(
                    squid_data['x'], 
                    squid_data['y'] - 30
                )
                
                # Make text more visible for entering squids
                if is_new_arrival:
                    remote_squid['status_text'].setDefaultTextColor(QtGui.QColor(255, 255, 0))
                    remote_squid['status_text'].setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        else:
            # Create new remote squid representation
            try:
                # Load the appropriate squid image based on direction
                direction = squid_data.get('direction', 'right')
                squid_image = f"{direction}1.png"
                squid_pixmap = QtGui.QPixmap(os.path.join("images", squid_image))
                remote_visual = QtWidgets.QGraphicsPixmapItem(squid_pixmap)
                remote_visual.setPos(squid_data['x'], squid_data['y'])
                
                # Change Z-value here - increase to appear in front of background
                remote_visual.setZValue(10)  # Changed from -1 or 5 to 10
                
                remote_visual.setOpacity(self.REMOTE_SQUID_OPACITY)
                
                # Add ID text
                id_text = self.scene.addText(f"Remote Squid ({node_id[-4:]})")
                id_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                id_text.setPos(squid_data['x'], squid_data['y'] - 45)
                id_text.setScale(0.8)
                
                # Update Z-value for text as well
                id_text.setZValue(10)  # Changed to match the squid
                
                id_text.setVisible(self.show_labels)
                
                # Add status text with emphasis on "ENTERING"
                status_text = self.scene.addText("ENTERING" if is_new_arrival else squid_data.get('status', 'unknown'))
                if is_new_arrival:
                    status_text.setDefaultTextColor(QtGui.QColor(255, 255, 0))
                    status_text.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
                else:
                    status_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                status_text.setPos(squid_data['x'], squid_data['y'] - 30)
                status_text.setScale(0.7)
                
                # Update Z-value for status text
                status_text.setZValue(10)  # Changed to match the squid
                
                status_text.setVisible(self.show_labels)
                
                # Add to scene
                self.scene.addItem(remote_visual)
                
                # Store in tracking dict
                self.remote_squids[node_id] = {
                    'visual': remote_visual,
                    'id_text': id_text,
                    'status_text': status_text,
                    'view_cone': None,
                    'last_update': time.time(),
                    'data': squid_data
                }
                
                # Add view cone if needed
                if 'view_cone_visible' in squid_data and squid_data['view_cone_visible']:
                    self.update_remote_view_cone(node_id, squid_data)
                    
                # Create arrival animation for new squids
                if is_new_arrival:
                    self._create_arrival_animation(remote_visual)
            
            except Exception as e:
                print(f"Error creating remote squid: {e}")
                import traceback
                traceback.print_exc()
                return False
        
        # Update last seen time
        if node_id in self.remote_squids:
            self.remote_squids[node_id]['last_update'] = time.time()
            self.remote_squids[node_id]['data'] = squid_data
        
        return True
            
    def handle_remote_squid_return(self, node_id, controller):
        """Handle a remote squid returning to its home instance"""
        if self.debug_mode:
            print(f"Remote squid {node_id[-4:]} returning home")
        
        # Get summary of activities
        activity_summary = controller.get_summary()
        
        # Start fade out animation
        remote_squid = self.remote_squids.get(node_id)
        if not remote_squid or 'visual' not in remote_squid:
            if self.debug_mode:
                print(f"Cannot find visual for squid {node_id}")
            return
        
        visual = remote_squid['visual']
        
        # Add returning status to UI
        if 'status_text' in remote_squid:
            remote_squid['status_text'].setPlainText("RETURNING HOME")
            remote_squid['status_text'].setDefaultTextColor(QtGui.QColor(255, 215, 0))  # Gold color
        
        # Create fade out animation
        try:
            opacity_effect = QtWidgets.QGraphicsOpacityEffect(visual)
            visual.setGraphicsEffect(opacity_effect)
            
            fade_out = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
            fade_out.setDuration(1000)
            fade_out.setStartValue(visual.opacity())
            fade_out.setEndValue(0.0)
            fade_out.finished.connect(
                lambda: self.complete_remote_squid_return(node_id, activity_summary)
            )
            fade_out.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
            
            if self.debug_mode:
                print(f"Started fade-out animation for {node_id}")
        except Exception as e:
            print(f"Error creating fade-out animation: {e}")
            # Call completion directly if animation fails
            self.complete_remote_squid_return(node_id, activity_summary)
        
        # Show message about squid returning
        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(
                f"Remote squid {node_id[-4:]} is returning home"
            )

    def complete_remote_squid_return(self, node_id, activity_summary):
        """Complete the return process and send data back to home instance"""
        try:
            # Get the remote squid's direction
            direction = None
            if node_id in self.remote_squid_controllers:
                direction = self.remote_squid_controllers[node_id].home_direction
            
            # Remove remote squid visual
            if node_id in self.remote_squids:
                self.remove_remote_squid(node_id)
            
            # Send return message with activity summary
            if self.network_node and self.network_node.is_connected:
                self.network_node.send_message(
                    'squid_return', 
                    {
                        'node_id': node_id,
                        'activity_summary': activity_summary,
                        'return_direction': direction
                    }
                )
                
                if self.debug_mode:
                    print(f"Sent return message for {node_id} with summary: {activity_summary}")
            
            # Clean up controller
            if node_id in self.remote_squid_controllers:
                del self.remote_squid_controllers[node_id]
                
        except Exception as e:
            print(f"Error completing remote squid return: {e}")
            import traceback
            traceback.print_exc()

    
    def update_remote_view_cone(self, node_id, squid_data):
        """Update view cone only when necessary"""
        if node_id not in self.remote_squids:
            return

        # Skip if remote squid is too far from player's view
        local_squid = self.tamagotchi_logic.squid
        remote_x, remote_y = squid_data['x'], squid_data['y']
        local_x, local_y = local_squid.squid_x, local_squid.squid_y

        # Calculate distance
        distance = math.sqrt((remote_x - local_x)**2 + (remote_y - local_y)**2)

        # Skip view cone updates for distant squids
        if distance > 500:  # Arbitrary distance threshold
            # Remove existing view cone if it exists
            remote_squid = self.remote_squids[node_id]
            if 'view_cone' in remote_squid and remote_squid['view_cone'] in self.tamagotchi_logic.user_interface.scene.items():
                self.tamagotchi_logic.user_interface.scene.removeItem(remote_squid['view_cone'])
                remote_squid['view_cone'] = None
            return

        ui = self.tamagotchi_logic.user_interface
        remote_squid = self.remote_squids[node_id]

        # Remove existing view cone if it exists
        if 'view_cone' in remote_squid and remote_squid['view_cone'] in ui.scene.items():
            ui.scene.removeItem(remote_squid['view_cone'])

        # Get view cone parameters
        squid_x = squid_data['x']
        squid_y = squid_data['y']
        view_cone_item.setZValue(9)
        squid_width = 60  # Default width
        squid_height = 40  # Default height

        squid_center_x = squid_x + squid_width / 2
        squid_center_y = squid_y + squid_height / 2

        # Get viewing direction angle - default to 0 (right)
        looking_direction = squid_data.get('looking_direction', 0)

        # Set view cone angle
        view_cone_angle = squid_data.get('view_cone_angle', 1.0)

        # Calculate cone length
        cone_length = max(ui.window_width, ui.window_height)

        # Create polygon for view cone
        cone_points = [
            QtCore.QPointF(squid_center_x, squid_center_y),
            QtCore.QPointF(
                squid_center_x + math.cos(looking_direction - view_cone_angle/2) * cone_length,
                squid_center_y + math.sin(looking_direction - view_cone_angle/2) * cone_length
            ),
            QtCore.QPointF(
                squid_center_x + math.cos(looking_direction + view_cone_angle/2) * cone_length,
                squid_center_y + math.sin(looking_direction + view_cone_angle/2) * cone_length
            )
        ]

        cone_polygon = QtGui.QPolygonF(cone_points)

        # Create view cone item
        view_cone_item = QtWidgets.QGraphicsPolygonItem(cone_polygon)

        # Use squid color for the view cone
        color = squid_data.get('color', (150, 150, 255))
        view_cone_item.setPen(QtGui.QPen(QtGui.QColor(*color)))
        view_cone_item.setBrush(QtGui.QBrush(QtGui.QColor(*color, 30)))

        view_cone_item.setZValue(-2)  # Behind the squid

        # Add to scene
        ui.scene.addItem(view_cone_item)

        # Store in our tracking dict
        remote_squid['view_cone'] = view_cone_item

    
    def process_remote_objects(self, remote_objects, source_node_id):
        """
        Process objects from remote node and create/update their representation
        
        Args:
            remote_objects: List of object data from remote node
            source_node_id: ID of the source node
        """
        # Skip processing if we don't have the UI
        if not hasattr(self.tamagotchi_logic, 'user_interface'):
            print("No user interface available for remote objects")
            return
                
        ui = self.tamagotchi_logic.user_interface
        scene = ui.scene
        
        if self.debug_mode:
            print(f"Processing {len(remote_objects)} remote objects from {source_node_id}")
        
        # Process each remote object
        for obj in remote_objects:
            obj_id = obj.get('id')
            
            # Skip if no valid ID
            if not obj_id:
                continue
                    
            # Skip if being carried (owner should handle)
            if obj.get('is_being_carried', False):
                continue
                    
            # Full ID includes source node to avoid collisions
            full_id = f"{source_node_id}_{obj_id}"
            
            if self.debug_mode:
                print(f"Processing remote object: {full_id}")
                print(f"Object data: {obj}")
            
            if full_id in self.remote_objects:
                # Update existing object
                remote_obj = self.remote_objects[full_id]
                remote_obj['visual'].setPos(obj['x'], obj['y'])
                remote_obj['last_update'] = time.time()
                
                if self.debug_mode:
                    print(f"Updated existing remote object: {full_id}")
            else:
                # Create new object if we can
                try:
                    obj_type = obj.get('type', 'unknown')
                    filename = obj.get('filename')
                    
                    # Verify filename exists
                    if not filename:
                        print(f"Error: No filename for remote object {full_id}")
                        continue
                    
                    # Check if file exists
                    if not os.path.exists(filename):
                        print(f"Error: File not found: {filename}")
                        continue
                    
                    if self.debug_mode:
                        print(f"Creating remote object from {filename}")
                    
                    # Create pixmap item with transparency
                    pixmap = QtGui.QPixmap(filename)
                    visual = QtWidgets.QGraphicsPixmapItem(pixmap)
                    visual.setPos(obj['x'], obj['y'])
                    visual.setScale(obj.get('scale', 1.0))
                    visual.setOpacity(0.7)  # Make it semi-transparent to distinguish
                    visual.setZValue(-1)  # Behind local objects
                    
                    # Add to scene
                    scene.addItem(visual)
                    
                    # Store in tracking dict
                    self.remote_objects[full_id] = {
                        'visual': visual,
                        'type': obj_type,
                        'source_node': source_node_id,
                        'last_update': time.time(),
                        'data': obj
                    }
                    
                    # Add a small label to indicate remote object
                    remote_label = scene.addText("Remote")
                    remote_label.setDefaultTextColor(QtGui.QColor(150, 150, 150))
                    remote_label.setPos(obj['x'], obj['y'] - 20)
                    remote_label.setScale(0.6)
                    self.remote_objects[full_id]['label'] = remote_label
                    
                    if self.debug_mode:
                        print(f"Successfully created remote object: {full_id}")
                    
                except Exception as e:
                    print(f"Error creating remote object: {e}")
                    import traceback
                    traceback.print_exc()
    
    def handle_rock_throw(self, node, message, addr):
        """
        Handle rock throw events from other nodes
        
        Args:
            node: Network node
            message: Message data
            addr: Sender address
        """
        if not self.tamagotchi_logic:
            return
            
        source_node_id = message['node_id']
        rock_data = message['payload'].get('rock_data', {})
        
        # Try to notify the squid's rock interaction manager
        if hasattr(self.tamagotchi_logic, 'rock_interaction'):
            self.tamagotchi_logic.rock_interaction.handle_remote_rock_throw(
                source_node_id, rock_data
            )
    
    def handle_squid_move(self, node, message, addr):
        """
        Handle squid movement data from other nodes
        
        Args:
            node: Network node  
            message: Message data
            addr: Sender address
        """
        # For now, relies on the regular sync messages to update positions
        pass
    
    def handle_state_update(self, node, message, addr):
        """
        Handle general state updates from other nodes
        
        Args:
            node: Network node
            message: Message data  
            addr: Sender address
        """
        pass
    
    def remove_remote_squid(self, node_id):
        """Remove a remote squid and all its components"""
        if node_id not in self.remote_squids:
            return
            
        ui = self.tamagotchi_logic.user_interface
        squid_data = self.remote_squids[node_id]
        
        # Remove all visual components
        for key in ['visual', 'view_cone', 'id_text', 'status_text']:
            if key in squid_data and squid_data[key] in ui.scene.items():
                ui.scene.removeItem(squid_data[key])
        
        # Remove connection line
        if node_id in self.connection_lines:
            if self.connection_lines[node_id] in ui.scene.items():
                ui.scene.removeItem(self.connection_lines[node_id])
            del self.connection_lines[node_id]
        
        # Remove from tracking
        del self.remote_squids[node_id]
        
        # Show notification
        if hasattr(self.tamagotchi_logic, 'show_message'):
            self.tamagotchi_logic.show_message(f"Remote squid {node_id[-4:]} disconnected")
    
    def remove_remote_object(self, obj_id):
        """Remove a remote object"""
        if obj_id not in self.remote_objects:
            return
            
        ui = self.tamagotchi_logic.user_interface
        obj_data = self.remote_objects[obj_id]
        
        # Remove visual
        if 'visual' in obj_data and obj_data['visual'] in ui.scene.items():
            ui.scene.removeItem(obj_data['visual'])
            
        # Remove label if it exists
        if 'label' in obj_data and obj_data['label'] in ui.scene.items():
            ui.scene.removeItem(obj_data['label'])
        
        # Remove from tracking
        del self.remote_objects[obj_id]
    
    def throw_rock_network(self, rock, direction):
        """
        Broadcast a rock throw event to the network
        
        Args:
            rock: The rock being thrown
            direction: Direction of throw ("left" or "right")
        """
        if not self.network_node or not self.network_node.is_connected:
            return
            
        try:
            # Get rock metadata
            rock_filename = getattr(rock, 'filename', "unknown_rock")
            rock_pos = rock.pos()
            
            # Send rock throw message
            self.network_node.send_message(
                'rock_throw',
                {
                    'rock_data': {
                        'rock_filename': rock_filename,
                        'direction': direction,
                        'initial_pos': {
                            'x': rock_pos.x(),
                            'y': rock_pos.y()
                        }
                    }
                }
            )
            
            if self.debug_mode:
                print(f"Broadcast rock throw: {direction} at ({rock_pos.x()}, {rock_pos.y()})")
                
        except Exception as e:
            if self.debug_mode:
                print(f"Error broadcasting rock throw: {e}")
    
    def cleanup(self):
        """Clean up resources when plugin is disabled or unloaded"""
        # Remove all remote squids
        for node_id in list(self.remote_squids.keys()):
            self.remove_remote_squid(node_id)
            
        # Remove all remote objects
        for obj_id in list(self.remote_objects.keys()):
            self.remove_remote_object(obj_id)
            
        # Send a goodbye message
        if self.network_node and self.network_node.is_connected:
            try:
                self.network_node.send_message(
                    'player_leave',
                    {
                        'node_id': self.network_node.node_id,
                        'reason': 'plugin_unloaded'
                    }
                )
            except:
                pass
                
        # Update status bar
        if self.status_bar:
            self.status_bar.update_network_status(False)
            self.status_bar.update_peers_count(0)
            self.status_bar.add_message("Multiplayer disconnected")

def initialize(plugin_manager):
    """Initialize the multiplayer plugin"""
    try:
        #print("Initializing multiplayer plugin (with no dependency checks)")
        
        # Create plugin instance
        plugin = MultiplayerPlugin()
        
        # Important: Set the plugin_manager reference on the instance
        plugin.plugin_manager = plugin_manager
        
        # Store the plugin instance
        plugin_name = 'multiplayer'  # Lowercase to match plugin manager's key
        plugin_manager.plugins[plugin_name] = {
            'instance': plugin,
            'name': PLUGIN_NAME,
            'version': PLUGIN_VERSION,
            'author': PLUGIN_AUTHOR,
            'description': PLUGIN_DESCRIPTION,
            'requires': [],  # Remove dependency requirements completely
            'module': None,  # Will be set by plugin manager
            'is_setup': False  # Track if plugin is initialized
        }
        
        # Note: We are NOT adding the plugin to enabled_plugins here
        # This is what makes it disabled by default
        
        #print(f"Successfully initialized Multiplayer plugin (disabled by default)")
        return True
    except Exception as e:
        print(f"Error initializing Multiplayer plugin: {e}")
        import traceback
        traceback.print_exc()
        return False