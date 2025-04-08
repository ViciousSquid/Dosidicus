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

from plugins.multiplayer.multiplayer_config_dialog import MultiplayerConfigDialog
from plugins.multiplayer.status_bar_component import StatusBarComponent

# Plugin Metadata
PLUGIN_NAME = "Multiplayer"
PLUGIN_VERSION = "1.2.0"
PLUGIN_AUTHOR = "ViciousSquid"
PLUGIN_DESCRIPTION = "Enables networked multiplayer for squids including squid detection and object synchronization"
PLUGIN_REQUIRES = ["network_interface"]

# Network Constants 
MULTICAST_GROUP = '224.3.29.71'  
MULTICAST_PORT = 10000
SYNC_INTERVAL = 0.5  # Seconds between sync broadcasts

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
        self.node_id = node_id or str(uuid.uuid4())
        self.local_ip = self._get_local_ip()
        self.socket = None
        self.initialized = False
        self.is_connected = False
        
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
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            
            # Multicast setup
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            
            try:
                # Binding
                self.socket.bind(('', MULTICAST_PORT))
                
                # Join multicast group
                mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(self.local_ip)
                self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                
                self.is_connected = True
                self.initialized = True
                
                if self.debug_mode:
                    print(f"[Network] Successfully initialized socket on {self.local_ip}:{MULTICAST_PORT}")
                
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
    
    def send_message(self, message_type: str, payload: Dict[str, Any]):
        """
        Send a message to the multicast group
        
        Args:
            message_type (str): Type of message being sent
            payload (Dict): Message payload
        """
        if not self.is_connected or not self.socket:
            if self.debug_mode:
                print(f"[Network] Cannot send message: socket not connected")
            return
            
        message = {
            'node_id': self.node_id,
            'timestamp': time.time(),
            'type': message_type,
            'payload': payload
        }
        
        # Compress message to reduce network overhead
        try:
            serialized_msg = json.dumps(message).encode('utf-8')
            
            # Try to use zlib compression, but handle if not available
            try:
                import zlib
                compressed_msg = zlib.compress(serialized_msg)
            except ImportError:
                # Fallback if zlib not available
                compressed_msg = serialized_msg
            
            self.socket.sendto(
                compressed_msg, 
                (MULTICAST_GROUP, MULTICAST_PORT)
            )
            if self.debug_mode:
                print(f"[Network] Sent {message_type} message ({len(compressed_msg)} bytes)")
        except Exception as e:
            print(f"Network send error: {e}")
    
    def receive_messages(self):
        """
        Continuously receive and process incoming messages with robust error handling
        """
        if not self.is_connected or not self.socket:
            if self.debug_mode:
                print("[Network] Cannot receive messages: socket not connected")
            time.sleep(1)  # Avoid tight loop if socket is not available
            return
                
        try:
            # Make socket non-blocking
            self.socket.setblocking(0)
            
            # Try to import select, but handle if not available
            try:
                import select
                
                # Try to receive data with timeout
                ready = select.select([self.socket], [], [], 0.1)
                if ready[0]:
                    # Receive compressed message
                    data, addr = self.socket.recvfrom(MAX_PACKET_SIZE)
                    
                    # Try to decompress with zlib, but handle if not available
                    try:
                        import zlib
                        decompressed_data = zlib.decompress(data).decode('utf-8')
                    except ImportError:
                        # Fallback if zlib not available
                        decompressed_data = data.decode('utf-8')
                    
                    message = json.loads(decompressed_data)
                    
                    # Debug print ALL message types
                    print(f"[Network] Received {message['type']} message from {addr[0]}")
                    
                    # Ignore messages from self
                    if message['node_id'] == self.node_id:
                        return
                    
                    # Update known nodes
                    self.known_nodes[message['node_id']] = (addr[0], time.time(), message.get('payload', {}).get('squid', {}))
                    
                    # Add to incoming queue for processing
                    self.incoming_queue.put((message, addr))
            except ImportError:
                # select module not available
                if self.debug_mode:
                    print("[Network] select module not available, skipping receive")
                    
        except socket.error:
            # No data available, just continue
            pass
        except Exception as e:
            print(f"Network receive error: {e}")
            import traceback
            traceback.print_exc()
    
    def process_messages(self, plugin_manager):
        """Process messages in the incoming queue"""
        if not plugin_manager:
            return
                
        while not self.incoming_queue.empty():
            try:
                message, addr = self.incoming_queue.get_nowait()
                
                # Debug the message type
                print(f"Processing message type: {message['type']}")
                
                # Trigger appropriate hooks based on message type
                hook_name = f"network_{message['type']}"
                print(f"Triggering hook: {hook_name}")
                
                plugin_manager.trigger_hook(
                    hook_name, 
                    node=self, 
                    message=message,
                    addr=addr
                )
            except queue.Empty:
                break
            except Exception as e:
                print(f"Error processing message: {e}")
                import traceback
                traceback.print_exc()

class MultiplayerPlugin:
    def __init__(self):
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
        print("\n***** SQUID EXIT HANDLER CALLED *****")
        print(f"Message type: {message['type']}")
        print(f"Message payload: {message.get('payload', {})}")

        # Check basic requirements
        if not hasattr(self, 'tamagotchi_logic'):
            print("ERROR: No tamagotchi_logic attribute")
            return False

        if not hasattr(self.tamagotchi_logic, 'user_interface'):
            print("ERROR: No user_interface")
            return False

        ui = self.tamagotchi_logic.user_interface

        try:
            # Extract payload
            payload = message.get('payload', {})
            if not payload:
                print("ERROR: Empty payload in squid_exit message")
                return False

            # Detailed logging of payload
            print("Full Payload Details:")
            for key, value in payload.items():
                print(f"  {key}: {value}")

            # Extract critical information with fallback values
            source_node_id = payload.get('node_id', 'unknown_node')
            direction = payload.get('direction', 'unknown')
            position = payload.get('position', {})
            color = payload.get('color', (150, 150, 255))
            squid_width = payload.get('squid_width', 200)
            squid_height = payload.get('squid_height', 150)

            print(f"Extracted Details:")
            print(f"  Source Node ID: {source_node_id}")
            print(f"  Exit Direction: {direction}")
            print(f"  Position: {position}")
            print(f"  Color: {color}")

            # Ensure position is valid
            if not position or 'x' not in position or 'y' not in position:
                print("[ERROR] Invalid or missing position in payload")
                return False

            # Create remote squid representation
            scene = ui.scene

            # Load remote squid image
            remote_squid_pixmap = QtGui.QPixmap(os.path.join("images", f"{direction}1.png"))
            remote_squid_item = QtWidgets.QGraphicsPixmapItem(remote_squid_pixmap)

            # Position near an exit point based on direction
            scene_rect = scene.sceneRect()
            print(f"Scene Rectangle: {scene_rect}")

            # Calculate entry point based on exit direction
            if direction == "left":
                entry_x = 50  # Left edge
                entry_y = scene_rect.height() // 2
            elif direction == "right":
                entry_x = scene_rect.width() - 250  # Right edge
                entry_y = scene_rect.height() // 2
            elif direction == "up":
                entry_x = scene_rect.width() // 2
                entry_y = 50  # Top edge
            elif direction == "down":
                entry_x = scene_rect.width() // 2
                entry_y = scene_rect.height() - 250  # Bottom edge
            else:
                entry_x = scene_rect.width() // 2
                entry_y = scene_rect.height() // 2  # Default to center

            # Set initial position with full transparency
            remote_squid_item.setPos(entry_x, entry_y)
            remote_squid_item.setOpacity(0.0)  # Start completely invisible
            remote_squid_item.setZValue(10)  # Ensure visibility

            # Add metadata to the item
            remote_squid_item.node_id = source_node_id
            remote_squid_item.is_remote = True

            # Add to scene
            scene.addItem(remote_squid_item)

            # Create subtle text indicator
            status_text = scene.addText(
                f"Remote Squid\n{source_node_id[-8:]}",
                QtGui.QFont("Arial", 10)
            )
            status_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
            status_text.setPos(entry_x, entry_y - 50)
            status_text.setOpacity(0.0)  # Start invisible
            status_text.setZValue(11)  # Slightly above squid

            # Create fade-in animation for squid
            opacity_effect = QtWidgets.QGraphicsOpacityEffect()
            remote_squid_item.setGraphicsEffect(opacity_effect)

            fade_in_anim = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
            fade_in_anim.setDuration(2000)  # 2-second fade-in
            fade_in_anim.setStartValue(0.0)
            fade_in_anim.setEndValue(0.7)  # Semi-transparent remote squid
            fade_in_anim.setEasingCurve(QtCore.QEasingCurve.InQuad)

            # Create fade-in animation for text
            text_opacity_effect = QtWidgets.QGraphicsOpacityEffect()
            status_text.setGraphicsEffect(text_opacity_effect)

            text_fade_in_anim = QtCore.QPropertyAnimation(text_opacity_effect, b"opacity")
            text_fade_in_anim.setDuration(2000)
            text_fade_in_anim.setStartValue(0.0)
            text_fade_in_anim.setEndValue(1.0)
            text_fade_in_anim.setEasingCurve(QtCore.QEasingCurve.InQuad)

            # Create parallel animation group
            animation_group = QtCore.QParallelAnimationGroup()
            animation_group.addAnimation(fade_in_anim)
            animation_group.addAnimation(text_fade_in_anim)

            # Connect a completion handler
            def on_animation_complete():
                print(f"Remote squid entry animation complete for {source_node_id}")

            animation_group.finished.connect(on_animation_complete)

            # Start animations
            animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

            print("Successfully completed squid entry animation")
            return True

        except Exception as e:
            print(f"CRITICAL ERROR in squid_exit handler: {e}")
            import traceback
            traceback.print_exc()
            return False


    def update_remote_squid(self, node_id, squid_data, is_new_arrival=False):
        """Update the visual representation of a remote squid with improved visibility for new arrivals"""
        if not squid_data or not all(k in squid_data for k in ['x', 'y']):
            return

        ui = self.tamagotchi_logic.user_interface
        
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
                if 'view_cone' in remote_squid and remote_squid['view_cone'] in ui.scene.items():
                    ui.scene.removeItem(remote_squid['view_cone'])
                    remote_squid['view_cone'] = None
            
            # Update status text with "ENTERING" for new arrivals
            if 'status_text' in remote_squid:
                status = "ENTERING" if is_new_arrival else squid_data.get('status', 'unknown')
                remote_squid['status_text'].setPlainText(f"{status}")
                remote_squid['status_text'].setPos(
                    squid_data['x'], 
                    squid_data['y'] - 30
                )
                
                # Make text more visible for entering squids
                if is_new_arrival:
                    remote_squid['status_text'].setDefaultTextColor(QtGui.QColor(255, 255, 0))  # Bright yellow
                    remote_squid['status_text'].setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
                    
                    # Create arrival animation
                    self._create_arrival_animation(remote_squid['visual'])
        else:
            # Create new remote squid representation
            try:
                # Create colored ellipse for remote squid with higher opacity for new arrivals
                opacity = 1.0 if is_new_arrival else REMOTE_SQUID_OPACITY
                color = squid_data.get('color', (150, 150, 255))
                remote_visual = QtWidgets.QGraphicsEllipseItem(0, 0, 60, 40)
                remote_visual.setBrush(QtGui.QBrush(QtGui.QColor(*color, 180)))
                remote_visual.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
                remote_visual.setPos(squid_data['x'], squid_data['y'])
                remote_visual.setZValue(5 if is_new_arrival else -1)  # New squids appear on top
                remote_visual.setOpacity(opacity)
                
                # Add ID text with better visibility
                id_text = ui.scene.addText(f"Remote Squid ({node_id[-4:]})")
                id_text.setDefaultTextColor(QtGui.QColor(*color))
                id_text.setPos(squid_data['x'], squid_data['y'] - 45)
                id_text.setScale(0.8)
                id_text.setZValue(5 if is_new_arrival else -1)
                id_text.setVisible(True)  # Always show labels for new arrivals
                
                # Make font bold for new arrivals
                if is_new_arrival:
                    font = id_text.font()
                    font.setBold(True)
                    id_text.setFont(font)
                
                # Add status text with emphasis on "ENTERING"
                status_text = ui.scene.addText("ENTERING" if is_new_arrival else squid_data.get('status', 'unknown'))
                if is_new_arrival:
                    status_text.setDefaultTextColor(QtGui.QColor(255, 255, 0))  # Bright yellow
                    status_text.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
                else:
                    status_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                status_text.setPos(squid_data['x'], squid_data['y'] - 30)
                status_text.setScale(0.7)
                status_text.setZValue(5 if is_new_arrival else -1)
                status_text.setVisible(True)  # Always show status for new arrivals
                
                # Add to scene
                ui.scene.addItem(remote_visual)
                
                # Store in our tracking dict
                self.remote_squids[node_id] = {
                    'visual': remote_visual,
                    'id_text': id_text,
                    'status_text': status_text,
                    'view_cone': None,
                    'last_update': time.time(),
                    'data': squid_data
                }
                
                # Show notification message
                if hasattr(self.tamagotchi_logic, 'show_message'):
                    if is_new_arrival:
                        self.tamagotchi_logic.show_message(f"⚠️ Foreign squid {node_id[-4:]} entered your tank!")
                    else:
                        self.tamagotchi_logic.show_message(f"Remote squid {node_id[-4:]} connected!")
                
                # Add view cone if needed
                if 'view_cone_visible' in squid_data and squid_data['view_cone_visible']:
                    self.update_remote_view_cone(node_id, squid_data)
                    
                # Create connection line
                self.update_connection_lines()
                
                # Create arrival animation for new squids
                if is_new_arrival:
                    self._create_arrival_animation(remote_visual)
            
            except Exception as e:
                if self.debug_mode:
                    print(f"Error creating remote squid: {e}")
                    traceback.print_exc()
        
        # Update last seen time
        if node_id in self.remote_squids:
            self.remote_squids[node_id]['last_update'] = time.time()
            self.remote_squids[node_id]['data'] = squid_data

    def _create_arrival_animation(self, visual_item):
        """Create attention-grabbing animation for newly arrived squids"""
        # Save original scale
        original_scale = visual_item.scale()
        
        # Create scale animation
        scale_animation = QtCore.QPropertyAnimation(visual_item, b"scale")
        scale_animation.setDuration(500)
        scale_animation.setStartValue(1.5)  # Start larger
        scale_animation.setEndValue(1.0)  # End at normal size
        scale_animation.setEasingCurve(QtCore.QEasingCurve.OutBounce)
        
        # Create opacity animation
        opacity_effect = QtWidgets.QGraphicsOpacityEffect()
        visual_item.setGraphicsEffect(opacity_effect)
        opacity_animation = QtCore.QPropertyAnimation(opacity_effect, b"opacity")
        opacity_animation.setDuration(500)
        opacity_animation.setStartValue(0.5)
        opacity_animation.setEndValue(1.0)
        
        # Create animation group
        animation_group = QtCore.QParallelAnimationGroup()
        animation_group.addAnimation(scale_animation)
        animation_group.addAnimation(opacity_animation)
        
        # Start animation
        animation_group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)
        
        # Reset to normal after a delay
        QtCore.QTimer.singleShot(5000, lambda: self._reset_remote_squid_style(visual_item))

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
        """
        Set up the multiplayer plugin
        
        Args:
            plugin_manager (PluginManager): Plugin manager instance
        """
        try:
            print("\n===== MULTIPLAYER PLUGIN SETUP =====")
            print(f"Plugin Manager: {plugin_manager}")
            
            # Store plugin manager reference
            self.plugin_manager = plugin_manager
            
            # Extract debug mode setting
            if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic is not None:
                self.debug_mode = getattr(self.tamagotchi_logic, 'debug_mode', False)
            
            # Get or create tamagotchi_logic reference
            if not hasattr(self, 'tamagotchi_logic') or self.tamagotchi_logic is None:
                # Try to get tamagotchi_logic from plugin_manager
                if hasattr(plugin_manager, 'tamagotchi_logic'):
                    self.tamagotchi_logic = plugin_manager.tamagotchi_logic
                    print("Found tamagotchi_logic from plugin_manager")
                
                # If still None, try to find it elsewhere
                if self.tamagotchi_logic is None:
                    print("WARNING: Could not find tamagotchi_logic")
            
            # Create unique node ID
            import uuid
            node_id = f"squid_{uuid.uuid4().hex[:8]}"
            self.network_node = NetworkNode(node_id)
            self.network_node.debug_mode = True  # Enable detailed network logging
            
            print(f"Network Node Created:")
            print(f"  Node ID: {node_id}")
            print(f"  Local IP: {self.network_node.local_ip}")
            print(f"  Is Connected: {self.network_node.is_connected}")
            
            # Start network receive thread (with error handling)
            try:
                import threading
                receive_thread = threading.Thread(
                    target=self.network_receive_loop, 
                    daemon=True
                )
                receive_thread.start()
                print("Network receive thread started successfully")
            except Exception as thread_error:
                print(f"Error starting network thread: {thread_error}")
            
            # Start synchronization timer (with error handling)
            try:
                self.start_sync_timer()
                print("Sync timer started successfully")
            except Exception as timer_error:
                print(f"Error starting sync timer: {timer_error}")
            
            # Register network hooks
            self._register_hooks()
            print("Network hooks registered successfully")
            
            # Create remote squid representation objects
            self.initialize_remote_representation()
            print("Remote representation initialized")
            
            # Show connection message
            if (hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic and 
                hasattr(self.tamagotchi_logic, 'show_message')):
                self.tamagotchi_logic.show_message(f"Connected to squid network as {node_id}")
            
            # Update status bar
            if (hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic and 
                hasattr(self.tamagotchi_logic, 'user_interface')):
                ui = self.tamagotchi_logic.user_interface
                
                if hasattr(ui, 'status_bar'):
                    ui.status_bar.update_network_status(True, node_id)
                    ui.status_bar.add_message(f"Multiplayer initialized. Your node ID: {node_id}")
            
            # Log status
            print(f"Multiplayer initialized with node ID: {node_id}")
            print(f"Listening on {self.network_node.local_ip}:{MULTICAST_PORT}")
            print("===== MULTIPLAYER SETUP COMPLETE =====\n")
            
            return True
        except Exception as e:
            print(f"Error in multiplayer setup: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def network_receive_loop(self):
        """Continuous loop for receiving network messages"""
        import select  # Import here to avoid global import issues
        
        while True:
            try:
                # Only try to receive if the node is connected
                if self.network_node and self.network_node.is_connected:
                    self.network_node.receive_messages()
                    
                    # Process messages if plugin_manager exists
                    if self.plugin_manager:
                        self.network_node.process_messages(self.plugin_manager)
                
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
    
    def register_menu_actions(self, ui=None, menu=None):
        """
        Register menu actions for the Multiplayer plugin
        
        Args:
            ui: Optional user interface 
            menu: Optional menu to add actions to
        """
        try:
            # If no UI is provided, try to get it from tamagotchi_logic
            if ui is None and hasattr(self, 'tamagotchi_logic'):
                ui = self.tamagotchi_logic.user_interface
            
            # If no menu is provided, try to get the plugins menu
            if menu is None and ui and hasattr(ui, 'plugins_menu'):
                menu = ui.plugins_menu
            
            # If we still don't have a menu, print a warning and return
            if menu is None:
                print("No menu available for registering multiplayer actions")
                return
            
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
            
            print("Multiplayer menu actions registered successfully")
        
        except Exception as e:
            print(f"Error in register_menu_actions: {e}")
            import traceback
            traceback.print_exc()

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
        
        # Subscribe to hooks
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
        
        # Add this subscription for squid exit
        self.plugin_manager.subscribe_to_hook(
            "network_squid_exit",
            PLUGIN_NAME,
            self.handle_squid_exit_message
        )
        
        # Subscribe to pre-update hook for processing network messages
        self.plugin_manager.subscribe_to_hook(
            "pre_update",
            PLUGIN_NAME,
            self.pre_update
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
        """
        Start periodic synchronization of game state
        """
        def sync_state():
            while True:
                try:
                    if self.network_node and self.network_node.is_connected:
                        self.sync_game_state()
                except Exception as e:
                    if self.debug_mode:
                        print(f"Error in sync_state: {e}")
                time.sleep(SYNC_INTERVAL)
        
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
            
            # Send synchronization message
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
            
            # Send heartbeat less frequently
            current_time = time.time()
            if current_time - self.last_message_times.get('heartbeat', 0) > 3.0:  # Every 3 seconds
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
        
        except Exception as e:
            if self.debug_mode:
                print(f"Error in sync_game_state: {e}")
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
    
    def update_remote_squid(self, node_id, squid_data):
        """Update the visual representation of a remote squid"""
        if not squid_data or not all(k in squid_data for k in ['x', 'y']):
            return

        ui = self.tamagotchi_logic.user_interface
        
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
                if 'view_cone' in remote_squid and remote_squid['view_cone'] in ui.scene.items():
                    ui.scene.removeItem(remote_squid['view_cone'])
                    remote_squid['view_cone'] = None
            
            # Update status text
            if 'status_text' in remote_squid:
                status = squid_data.get('status', 'unknown')
                remote_squid['status_text'].setPlainText(f"{status}")
                remote_squid['status_text'].setPos(
                    squid_data['x'], 
                    squid_data['y'] - 30
                )
        else:
            # Create new remote squid representation
            try:
                # Create colored ellipse for remote squid
                color = squid_data.get('color', (150, 150, 255))
                remote_visual = QtWidgets.QGraphicsEllipseItem(0, 0, 60, 40)
                remote_visual.setBrush(QtGui.QBrush(QtGui.QColor(*color, 180)))
                remote_visual.setPen(QtGui.QPen(QtGui.QColor(0, 0, 0)))
                remote_visual.setPos(squid_data['x'], squid_data['y'])
                remote_visual.setZValue(-1)  # Behind local squid
                remote_visual.setOpacity(REMOTE_SQUID_OPACITY)
                
                # Add ID text
                id_text = ui.scene.addText(f"Remote Squid ({node_id[-4:]})")
                id_text.setDefaultTextColor(QtGui.QColor(*color))
                id_text.setPos(squid_data['x'], squid_data['y'] - 45)
                id_text.setScale(0.8)
                id_text.setZValue(-1)
                id_text.setVisible(SHOW_REMOTE_LABELS)
                
                # Add status text
                status_text = ui.scene.addText(f"{squid_data.get('status', 'unknown')}")
                status_text.setDefaultTextColor(QtGui.QColor(200, 200, 200))
                status_text.setPos(squid_data['x'], squid_data['y'] - 30)
                status_text.setScale(0.7)
                status_text.setZValue(-1)
                status_text.setVisible(SHOW_REMOTE_LABELS)
                
                # Add to scene
                ui.scene.addItem(remote_visual)
                
                # Store in our tracking dict
                self.remote_squids[node_id] = {
                    'visual': remote_visual,
                    'id_text': id_text,
                    'status_text': status_text,
                    'view_cone': None,
                    'last_update': time.time(),
                    'data': squid_data
                }
                
                # Show notification message
                if hasattr(self.tamagotchi_logic, 'show_message'):
                    self.tamagotchi_logic.show_message(f"Remote squid {node_id[-4:]} connected!")
                
                # Add view cone if needed
                if 'view_cone_visible' in squid_data and squid_data['view_cone_visible']:
                    self.update_remote_view_cone(node_id, squid_data)
                    
                # Create connection line
                self.update_connection_lines()
            
            except Exception as e:
                if self.debug_mode:
                    print(f"Error creating remote squid: {e}")
                    traceback.print_exc()
        
        # Update last seen time
        if node_id in self.remote_squids:
            self.remote_squids[node_id]['last_update'] = time.time()
            self.remote_squids[node_id]['data'] = squid_data
    
    def update_remote_view_cone(self, node_id, squid_data):
        """Update or create the view cone for a remote squid"""
        if node_id not in self.remote_squids:
            return
            
        ui = self.tamagotchi_logic.user_interface
        remote_squid = self.remote_squids[node_id]
        
        # Remove existing view cone if it exists
        if 'view_cone' in remote_squid and remote_squid['view_cone'] in ui.scene.items():
            ui.scene.removeItem(remote_squid['view_cone'])
        
        # Get view cone parameters
        squid_x = squid_data['x']
        squid_y = squid_data['y']
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
        print("Initializing multiplayer plugin (with no dependency checks)")
        
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
        
        print(f"Successfully initialized Multiplayer plugin (disabled by default)")
        return True
    except Exception as e:
        print(f"Error initializing Multiplayer plugin: {e}")
        import traceback
        traceback.print_exc()
        return False