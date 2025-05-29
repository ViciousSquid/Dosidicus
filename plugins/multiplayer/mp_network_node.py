# File: mp_network_node.py

import uuid
import time
import socket
import queue
import zlib
import json
import traceback

# Import constants from the new constants file
from .mp_constants import MULTICAST_GROUP, MULTICAST_PORT, MAX_PACKET_SIZE


class NetworkNode:
    def __init__(self, node_id=None):
        """
        Represents a networked node in the multiplayer system.

        Args:
            node_id (str, optional): Unique identifier for this node.
                                     Generated if not provided.
        """
        # Attempt to use NetworkUtilities if available, otherwise fallback
        try:
            from plugins.multiplayer.network_utilities import NetworkUtilities
            self.node_id = node_id or NetworkUtilities.generate_node_id()
            self.utils = NetworkUtilities # For potential compression/decompression utilities
        except ImportError:
            self.node_id = node_id or f"squid_{uuid.uuid4().hex[:8]}"
            self.utils = None

        self.local_ip = self._get_local_ip()
        self.socket = None
        self.initialized = False
        self.is_connected = False
        self.last_connection_attempt = 0
        self.connection_retry_interval = 5.0  # Seconds between reconnection attempts
        self.auto_reconnect = True            # Attempt to reconnect if connection drops
        self.use_compression = True           # Use zlib compression for messages

        self.incoming_queue = queue.Queue()   # Queue for messages received from the network
        self.outgoing_queue = queue.Queue()   # (Not currently used, but good for future outgoing message management)

        self.known_nodes = {}                 # Tracks other nodes: {node_id: (ip, last_seen, squid_data)}
        self.last_sync_time = 0               # Timestamp of the last sync operation
        self.debug_mode = False               # Enable/disable debug logging

        try:
            self.initialize_socket()
        except Exception as e:
            print(f"NetworkNode: Error initializing socket (will operate in limited mode): {e}")
            self.is_connected = False

    def initialize_socket(self):
        """Initializes or re-initializes the network socket with error handling."""
        try:
            if self.socket: # If socket exists, close it before reinitializing
                try:
                    self.socket.close()
                except Exception: # Ignore errors on close
                    pass

            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Multicast Time-To-Live (TTL) setup
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2) # 2 hops for local network

            # Binding to port with retries for flexibility
            max_bind_attempts = 3
            current_attempt = 0
            bind_port = MULTICAST_PORT
            bind_success = False
            while current_attempt < max_bind_attempts:
                try:
                    self.socket.bind(('', bind_port)) # Bind to all interfaces on the specified port
                    bind_success = True
                    break
                except OSError as bind_error:
                    current_attempt += 1
                    if current_attempt >= max_bind_attempts:
                        raise bind_error # Re-raise if all attempts fail
                    print(f"NetworkNode: Port {bind_port} in use, trying {bind_port + current_attempt}...")
                    bind_port += current_attempt # Try next port

            if not bind_success: # Should have been raised by now, but as a safeguard
                 print(f"NetworkNode: Critical error - could not bind socket after multiple attempts.")
                 self.is_connected = False
                 return False

            # Join the multicast group
            # Request membership for the multicast group on the local IP interface
            mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(self.local_ip)
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)

            self.socket.settimeout(0.05) # Non-blocking timeout for recvfrom

            self.is_connected = True
            self.initialized = True
            self.last_connection_attempt = time.time()
            if self.debug_mode:
                print(f"NetworkNode: Successfully initialized socket on {self.local_ip}:{bind_port} for multicast group {MULTICAST_GROUP}")

        except ImportError: # socket module itself might be missing in some restricted envs
            print("NetworkNode: Socket module not available. Network functionality disabled.")
            self.is_connected = False
        except Exception as e:
            print(f"NetworkNode: Error creating or configuring socket: {e}")
            self.socket = None
            self.is_connected = False

        self.last_connection_attempt = time.time() # Record time of this attempt
        return self.is_connected

    def try_reconnect(self):
        """Attempts to reconnect if auto-reconnect is enabled."""
        if not self.auto_reconnect:
            return False
        current_time = time.time()
        if current_time - self.last_connection_attempt < self.connection_retry_interval:
            return False # Too soon to retry

        if self.debug_mode:
            print("NetworkNode: Attempting to reconnect...")
        success = self.initialize_socket() # This will set self.is_connected

        # Optional: Notify status widget if one is linked
        # This part is more for UI, usually handled by the main plugin class
        # if hasattr(self, 'status_widget_callback') and self.status_widget_callback:
        #     self.status_widget_callback(success)
        return success

    def _get_local_ip(self):
        """Determines the local IP address. Falls back to localhost if unable."""
        try:
            # Connect to an external server (doesn't actually send data) to find preferred outbound IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.1) # Prevent long block
                s.connect(("8.8.8.8", 80)) # Google's public DNS
                local_ip = s.getsockname()[0]
            return local_ip
        except Exception as e: # Covers socket errors, timeouts, import errors if socket was conditional
            print(f"NetworkNode: Error getting local IP: {e}. Defaulting to 127.0.0.1.")
            return '127.0.0.1'

    def send_message_batch(self, messages: list):
        """
        Sends multiple messages as a single batch packet.
        Args:
            messages: A list of (message_type, payload_dict) tuples.
        """
        if not self.is_connected and self.auto_reconnect: self.try_reconnect()
        if not self.is_connected or not self.socket:
            if self.debug_mode: print("NetworkNode: Cannot send batch, socket not connected.")
            return False

        batch_data = {
            'node_id': self.node_id,
            'timestamp': time.time(),
            'batch': True,
            'messages': [{'type': msg_type, 'payload': payload} for msg_type, payload in messages]
        }

        try:
            serialized_batch = json.dumps(batch_data).encode('utf-8')
            if self.utils and self.use_compression and hasattr(self.utils, 'compress_message'):
                data_to_send = self.utils.compress_message(serialized_batch) # Assuming compress_message takes bytes
            elif self.use_compression: # Fallback zlib compression
                data_to_send = zlib.compress(serialized_batch)
            else: # No compression
                data_to_send = serialized_batch

            if len(data_to_send) > MAX_PACKET_SIZE:
                print(f"NetworkNode Warning: Batch message size ({len(data_to_send)}) exceeds MAX_PACKET_SIZE. Transmission may fail.")

            self.socket.sendto(data_to_send, (MULTICAST_GROUP, MULTICAST_PORT))
            return True
        except Exception as e:
            print(f"NetworkNode: Error sending message batch: {e}")
            self.is_connected = False # Potentially flag as disconnected on send error
            return False

    def send_message(self, message_type: str, payload: dict):
        """Sends a single message to the multicast group."""
        if not self.is_connected and self.auto_reconnect: self.try_reconnect()
        if not self.is_connected or not self.socket:
            if self.debug_mode: print(f"NetworkNode: Cannot send '{message_type}', socket not connected.")
            return False

        message_data = {
            'node_id': self.node_id,
            'timestamp': time.time(),
            'type': message_type,
            'payload': payload
        }

        try:
            serialized_message = json.dumps(message_data).encode('utf-8')
            data_to_send = serialized_message
            if self.utils and self.use_compression and hasattr(self.utils, 'compress_message'):
                # Assuming compress_message takes the dict and handles json.dumps itself
                # Or, if it takes bytes: data_to_send = self.utils.compress_message(serialized_message)
                data_to_send = self.utils.compress_message(message_data) # Pass dict if util handles serialization
            elif self.use_compression: # Fallback zlib compression
                data_to_send = zlib.compress(serialized_message)
            # else: data_to_send remains serialized_message

            if len(data_to_send) > MAX_PACKET_SIZE:
                print(f"NetworkNode Warning: Message '{message_type}' size ({len(data_to_send)}) exceeds MAX_PACKET_SIZE. May fail.")

            self.socket.sendto(data_to_send, (MULTICAST_GROUP, MULTICAST_PORT))
            if self.debug_mode and message_type not in ['object_sync', 'squid_move']: # Avoid spam for frequent messages
                print(f"NetworkNode: Sent '{message_type}' ({len(data_to_send)} bytes).")
            return True
        except Exception as e:
            print(f"NetworkNode: Error sending message '{message_type}': {e}")
            self.is_connected = False # Connection might be compromised
            return False

    def receive_messages(self):
        """
        Receives and processes incoming messages, putting them onto self.incoming_queue.
        Returns a list of (message_dict, address_tuple) for immediate processing if needed,
        but primary handling should be via pulling from the queue.
        """
        if not self.is_connected and self.auto_reconnect: self.try_reconnect()
        if not self.is_connected or not self.socket:
            return [] # No messages if not connected

        received_messages_list = []
        try:
            # Loop to process multiple messages if available, up to a limit per call
            for _ in range(10): # Process up to 10 datagrams per call to avoid blocking too long
                try:
                    raw_data, addr = self.socket.recvfrom(MAX_PACKET_SIZE)
                    if not raw_data: continue # Skip empty datagrams

                    message_dict = None
                    # Attempt decompression and deserialization
                    if self.utils and self.use_compression and hasattr(self.utils, 'decompress_message'):
                        message_dict = self.utils.decompress_message(raw_data) # Assumes this returns a dict
                    else: # Fallback or no specific utility
                        try:
                            if self.use_compression: # Try zlib decompress first
                                decompressed_data_bytes = zlib.decompress(raw_data)
                            else: # Assume not compressed
                                decompressed_data_bytes = raw_data
                            message_dict = json.loads(decompressed_data_bytes.decode('utf-8'))
                        except (zlib.error, json.JSONDecodeError, UnicodeDecodeError) as e:
                            # If zlib fails or json fails, try direct json load (if not compressed but looks like it)
                            if isinstance(e, zlib.error) and not self.use_compression: pass # Expected if not compressed
                            else:
                                try:
                                    message_dict = json.loads(raw_data.decode('utf-8'))
                                except Exception as e2:
                                    if self.debug_mode: print(f"NetworkNode: Error decoding message from {addr}: {e}, then {e2}. Data: {raw_data[:60]}...")
                                    continue # Skip malformed message

                    if not message_dict or not isinstance(message_dict, dict):
                        if self.debug_mode: print(f"NetworkNode: Invalid message structure from {addr}.")
                        continue

                    # Ignore messages from self
                    if message_dict.get('node_id') == self.node_id:
                        continue

                    # Update known nodes list (basic presence tracking)
                    self.known_nodes[message_dict['node_id']] = (addr[0], time.time(), message_dict.get('payload', {}).get('squid', {}))

                    self.incoming_queue.put((message_dict, addr))
                    received_messages_list.append((message_dict, addr))

                except socket.timeout: # Expected when no data is available on non-blocking socket
                    break # No more data for now
                except socket.error as sock_err: # More serious socket errors
                    # Specific error codes can be checked here (e.g., conection reset for TCP)
                    print(f"NetworkNode: Socket error during receive: {sock_err}")
                    self.is_connected = False # Assume connection is lost
                    break # Stop trying to receive
        except Exception as e:
            print(f"NetworkNode: General error in receive_messages loop: {e}")
            # traceback.print_exc() # For detailed debugging

        return received_messages_list

    def process_messages(self, plugin_manager_ref):
        """
        Processes messages from self.incoming_queue.
        Called by the main plugin logic (e.g., in its update loop or via a timer).
        Args:
            plugin_manager_ref: Reference to the plugin manager to trigger hooks.
        """
        messages_processed_count = 0
        # Process a limited number of messages per call to avoid blocking the main thread for too long.
        for _ in range(20): # Max 20 messages per call
            try:
                message_data, addr = self.incoming_queue.get_nowait() # Non-blocking

                # Basic validation
                if not isinstance(message_data, dict) or 'type' not in message_data or 'node_id' not in message_data:
                    if self.debug_mode: print(f"NetworkNode: Discarding malformed message from queue: {message_data}")
                    continue

                if message_data['node_id'] == self.node_id: # Should have been filtered, but double check
                    continue

                message_type = message_data.get('type', 'unknown_message')
                # Construct hook name, e.g., "network_squid_move"
                hook_name = f"network_{message_type}"

                if hasattr(plugin_manager_ref, 'trigger_hook'):
                    plugin_manager_ref.trigger_hook(
                        hook_name,
                        node=self, # Pass this NetworkNode instance
                        message=message_data, # The full message dictionary
                        addr=addr             # Sender's address (ip, port)
                    )
                messages_processed_count += 1
            except queue.Empty: # No more messages in the queue
                break
            except Exception as e:
                print(f"NetworkNode: Error processing message from queue: {e}")
                traceback.print_exc() # For debugging
        return messages_processed_count