# File: mp_network_node.py

import uuid
import time
import socket
import queue
import zlib
import json
import traceback
import threading

# Import constants
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
            self.utils = NetworkUtilities
        except ImportError:
            self.node_id = node_id or f"squid_{uuid.uuid4().hex[:8]}"
            self.utils = None

        self.local_ip = self._get_local_ip()
        self.socket = None
        self.initialized = False # Socket structure initialized
        self.is_connected = False # Socket bound and ready for I/O
        
        self._is_listening_active = False # Flag to control the listening loop
        self.listener_thread = None      # Thread object for the listening loop

        self.last_connection_attempt = 0
        self.connection_retry_interval = 5.0
        self.auto_reconnect = True
        self.use_compression = True

        self.incoming_queue = queue.Queue()
        self.outgoing_queue = queue.Queue() # Currently unused

        self.known_nodes = {}
        self.last_sync_time = 0
        self.debug_mode = False # Set this to True for verbose logging

        # Logger setup
        self.logger = getattr(self, 'logger', None)
        if self.logger is None:
            import logging
            self.logger = logging.getLogger(f"{__name__}.NetworkNode.{self.node_id[:4]}")
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
        
        # Initialize socket structure but do not start listening yet.
        # Listening is started by calling start_listening()
        self.initialize_socket_structure()

    def _get_local_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.1) # Non-blocking
                s.connect(("8.8.8.8", 80)) # Connect to a known address (doesn't send data)
                local_ip = s.getsockname()[0]
            return local_ip
        except Exception as e:
            self.logger.warning(f"Error getting local IP: {e}. Defaulting to 127.0.0.1.")
            return '127.0.0.1'

    def initialize_socket_structure(self):
        """Initializes the socket for network communication but does not start listening."""
        if self.is_connected and self.socket:
            self.logger.info("Socket structure already initialized and connected.")
            return True
            
        try:
            if self.socket: # Close existing socket if any
                try:
                    self.socket.close()
                except Exception: pass # Ignore errors on close
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2) # Configure TTL for multicast

            max_bind_attempts = 3
            current_attempt = 0
            bind_port = MULTICAST_PORT
            bind_success = False

            while current_attempt < max_bind_attempts:
                try:
                    self.socket.bind(('', bind_port)) # Bind to all interfaces on the chosen port
                    bind_success = True
                    self.logger.info(f"Socket bound successfully to port {bind_port}.")
                    break
                except OSError as bind_error:
                    current_attempt += 1
                    self.logger.warning(f"Port {bind_port} in use (Attempt {current_attempt}/{max_bind_attempts}). Error: {bind_error}")
                    if current_attempt >= max_bind_attempts:
                        self.logger.error(f"Critical error: Could not bind socket after {max_bind_attempts} attempts.")
                        self.is_connected = False
                        self.initialized = False
                        return False
                    bind_port += 1 # Try next port

            if not bind_success:
                self.is_connected = False
                self.initialized = False
                return False
            
            # Join the multicast group
            mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(self.local_ip)
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            self.socket.settimeout(0.1) # Non-blocking timeout for recvfrom, adjust as needed

            self.is_connected = True  # Socket is now ready for I/O
            self.initialized = True   # Basic initialization is complete
            self.last_connection_attempt = time.time()
            self.logger.info(f"Socket structure initialized on {self.local_ip}:{bind_port} for multicast group {MULTICAST_GROUP}.")
            return True

        except Exception as e:
            self.logger.error(f"Error initializing socket structure: {e}", exc_info=self.debug_mode)
            if self.socket:
                try: self.socket.close()
                except: pass
            self.socket = None
            self.is_connected = False
            self.initialized = False
            return False

    def _listen_for_multicast(self):
        """The actual listening loop run by the listener_thread."""
        self.logger.info(f"Listener thread started for node {self.node_id} on IP {self.local_ip}.")
        while self._is_listening_active:
            if not self.is_connected or not self.socket:
                self.logger.warning("Listening loop: Socket not connected. Attempting to reconnect...")
                if not self.try_reconnect(): # try_reconnect will attempt to re-init socket and restart listening (which includes this thread)
                    self.logger.error("Listening loop: Reconnect failed. Pausing before retry.")
                    time.sleep(self.connection_retry_interval) # Wait before retrying connection
                    continue # Re-check _is_listening_active and socket status

            # Call receive_messages to get data and put it on the queue
            # receive_messages handles its own socket.timeout for non-blocking reads
            messages = self.receive_messages() 
            if not messages and not self._is_listening_active: # if receive_messages returns empty and we should stop
                 break
            
            # Small sleep to prevent high CPU usage if queue is empty and no timeout in receive_messages
            # Adjust if receive_messages has a good timeout. If receive_messages is blocking, this isn't strictly needed.
            # Since self.socket.settimeout(0.1) is set, receive_messages will timeout, so this sleep is less critical
            # but can still be useful to yield control.
            time.sleep(0.001) # Minimal sleep

        self.logger.info(f"Listener thread stopped for node {self.node_id}.")

    def is_listening(self):
        """Checks if the node is actively listening for network traffic."""
        return self._is_listening_active and self.listener_thread is not None and self.listener_thread.is_alive()

    def start_listening(self):
        """Starts the network listening process if not already active."""
        if self.is_listening():
            self.logger.info("Attempted to start listening, but already listening.")
            return True

        if not self.initialized or not self.is_connected:
            self.logger.warning("Socket not initialized or connected. Attempting to initialize before listening.")
            if not self.initialize_socket_structure():
                self.logger.error("Failed to initialize socket structure. Cannot start listening.")
                return False
        
        self.logger.info("Starting network listener thread...")
        try:
            self._is_listening_active = True # Set flag before starting thread
            self.listener_thread = threading.Thread(target=self._listen_for_multicast, daemon=True)
            self.listener_thread.setName(f"MPNodeListener-{self.node_id[:4]}")
            self.listener_thread.start()
            self.logger.info("Listener thread started successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start listener thread: {e}", exc_info=self.debug_mode)
            self._is_listening_active = False # Reset flag on failure
            return False

    def stop_listening(self):
        """Stops the network listening thread."""
        if not self._is_listening_active and (self.listener_thread is None or not self.listener_thread.is_alive()):
            self.logger.info("Listener already stopped or was never started.")
            return

        self.logger.info("Stopping listener thread...")
        self._is_listening_active = False # Signal the thread's loop to terminate
        
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2.0) # Wait for the thread to finish
            if self.listener_thread.is_alive():
                self.logger.warning("Listener thread did not stop in time (join timeout).")
            else:
                self.logger.info("Listener thread joined successfully.")
        else:
            self.logger.info("Listener thread was not active or did not exist.")
            
        self.listener_thread = None
        # Do not set self.is_connected = False here, as the socket might still be valid for sending.

    def try_reconnect(self):
        """Attempts to re-establish the socket connection and restart listening."""
        if self.is_listening(): # If already listening, assume connected.
            return True

        current_time = time.time()
        if current_time - self.last_connection_attempt < self.connection_retry_interval:
            return False # Too soon to retry

        self.logger.info("Attempting to reconnect...")
        self.last_connection_attempt = current_time
        
        # Stop any existing (potentially broken) listening attempts first
        self.stop_listening() 

        if self.initialize_socket_structure(): # Re-initialize socket
            return self.start_listening()      # Start listening again
        else:
            self.logger.error("Reconnect failed: Could not re-initialize socket structure.")
            return False

    def send_message(self, message_type: str, payload: dict):
        if not self.is_connected:
            self.logger.warning(f"Cannot send '{message_type}', socket not connected.")
            if self.auto_reconnect and not self.try_reconnect():
                self.logger.error(f"Send failed for '{message_type}': Reconnect attempt failed.")
                return False
            elif not self.is_connected:
                 self.logger.error(f"Send failed for '{message_type}': Still not connected after reconnect check.")
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
            
            if self.use_compression:
                if self.utils and hasattr(self.utils, 'compress_message'):
                    # Assuming compress_message takes the dict and handles json.dumps itself or expects bytes
                    # For safety, pass bytes if that's what zlib.compress expects
                    data_to_send = self.utils.compress_message(serialized_message) # Pass bytes to align with zlib
                else:
                    data_to_send = zlib.compress(serialized_message)

            if len(data_to_send) > MAX_PACKET_SIZE:
                self.logger.warning(f"Message '{message_type}' size ({len(data_to_send)}) exceeds MAX_PACKET_SIZE. May fail.")

            self.socket.sendto(data_to_send, (MULTICAST_GROUP, MULTICAST_PORT))
            if self.debug_mode and message_type not in ['object_sync', 'squid_move', 'heartbeat']: # Reduce log spam
                self.logger.debug(f"Sent '{message_type}' ({len(data_to_send)} bytes).")
            return True
        except socket.error as sock_err:
            self.logger.error(f"Socket error sending message '{message_type}': {sock_err}")
            self.is_connected = False # Socket error likely means connection is broken
            self.stop_listening() # Stop listening as connection is unreliable
        except Exception as e:
            self.logger.error(f"Error sending message '{message_type}': {e}", exc_info=self.debug_mode)
        return False

    def send_message_batch(self, messages: list):
        if not self.is_connected:
            self.logger.warning("Cannot send batch, socket not connected.")
            if self.auto_reconnect and not self.try_reconnect():
                self.logger.error("Send batch failed: Reconnect attempt failed.")
                return False
            elif not self.is_connected:
                 self.logger.error("Send batch failed: Still not connected after reconnect check.")
                 return False

        batch_data = {
            'node_id': self.node_id,
            'timestamp': time.time(),
            'batch': True,
            'messages': [{'type': msg_type, 'payload': payload} for msg_type, payload in messages]
        }

        try:
            serialized_batch = json.dumps(batch_data).encode('utf-8')
            data_to_send = serialized_batch

            if self.use_compression:
                if self.utils and hasattr(self.utils, 'compress_message'):
                    data_to_send = self.utils.compress_message(serialized_batch)
                else:
                    data_to_send = zlib.compress(serialized_batch)

            if len(data_to_send) > MAX_PACKET_SIZE:
                self.logger.warning(f"Batch message size ({len(data_to_send)}) exceeds MAX_PACKET_SIZE. Transmission may fail.")

            self.socket.sendto(data_to_send, (MULTICAST_GROUP, MULTICAST_PORT))
            return True
        except socket.error as sock_err:
            self.logger.error(f"Socket error sending message batch: {sock_err}")
            self.is_connected = False
            self.stop_listening()
        except Exception as e:
            self.logger.error(f"Error sending message batch: {e}", exc_info=self.debug_mode)
        return False

    def receive_messages(self):
        """Receives and processes incoming datagrams, putting decoded messages onto self.incoming_queue."""
        if not self.is_connected or not self.socket:
            # This state should ideally be caught by the _listen_for_multicast loop's reconnect logic
            return [] 

        received_messages_this_call = []
        try:
            # Try to read multiple datagrams if available, but don't block indefinitely here.
            # The _listen_for_multicast loop provides the continuous listening.
            # The socket timeout handles the non-blocking nature.
            for _ in range(10): # Process up to N datagrams to avoid starving other operations if traffic is heavy
                try:
                    raw_data, addr = self.socket.recvfrom(MAX_PACKET_SIZE)
                    if not raw_data:
                        continue # Should not happen with UDP, but good check

                    message_dict = None
                    decoded_successfully = False

                    # Attempt decompression if enabled
                    if self.use_compression:
                        try:
                            if self.utils and hasattr(self.utils, 'decompress_message'):
                                # Assuming decompress_message returns a dict or raises error
                                message_dict = self.utils.decompress_message(raw_data)
                            else:
                                decompressed_data_bytes = zlib.decompress(raw_data)
                                message_dict = json.loads(decompressed_data_bytes.decode('utf-8'))
                            decoded_successfully = True
                        except (zlib.error, json.JSONDecodeError, UnicodeDecodeError) as e:
                            if self.debug_mode:
                                self.logger.debug(f"Failed compressed decoding from {addr}: {e}. Trying uncompressed.")
                            # Fall through to try uncompressed if primary method fails
                    
                    # If not using compression, or if compression failed, try direct JSON load
                    if not decoded_successfully:
                        try:
                            message_dict = json.loads(raw_data.decode('utf-8'))
                            decoded_successfully = True
                        except (json.JSONDecodeError, UnicodeDecodeError) as e:
                            if self.debug_mode:
                                self.logger.debug(f"Failed uncompressed JSON decoding from {addr}: {e}. Data: {raw_data[:80]}...")
                            # If all decoding fails, skip this datagram
                            continue 
                    
                    if not message_dict or not isinstance(message_dict, dict) or 'node_id' not in message_dict:
                        if self.debug_mode: self.logger.debug(f"Invalid or incomplete message structure from {addr}.")
                        continue
                    
                    # Filter out messages from self
                    if message_dict.get('node_id') == self.node_id:
                        continue

                    # Update known nodes (basic presence)
                    self.known_nodes[message_dict['node_id']] = (addr[0], time.time(), message_dict.get('payload', {}).get('squid', {}))
                    
                    self.incoming_queue.put((message_dict, addr))
                    received_messages_this_call.append((message_dict, addr))

                except socket.timeout:
                    # This is expected if no data is available due to socket.settimeout()
                    break 
                except socket.error as sock_err:
                    # Serious socket error, connection might be lost
                    self.logger.error(f"Socket error during receive: {sock_err}")
                    self.is_connected = False  # Mark as not connected
                    self._is_listening_active = False # Signal listening loop to stop/reconnect
                    # The _listen_for_multicast loop should handle this state.
                    break # Exit receive loop for this call
                except Exception as e:
                    self.logger.error(f"Unexpected error processing datagram: {e}", exc_info=self.debug_mode)
                    # Continue to try next datagram if possible
                    continue
            
        except Exception as e:
            # Catch-all for errors in the outer loop of receive_messages (less likely)
            self.logger.error(f"General error in receive_messages: {e}", exc_info=self.debug_mode)

        return received_messages_this_call

    def process_messages(self, plugin_manager_ref):
        messages_processed_count = 0
        for _ in range(self.incoming_queue.qsize() + 5): # Process current queue + a few more
            try:
                message_data, addr = self.incoming_queue.get_nowait()

                if not isinstance(message_data, dict) or 'type' not in message_data or 'node_id' not in message_data:
                    if self.debug_mode: self.logger.debug(f"Discarding malformed message from queue: {message_data}")
                    continue

                if message_data['node_id'] == self.node_id:
                    continue

                message_type = message_data.get('type', 'unknown_message')
                hook_name = f"network_{message_type}"

                if hasattr(plugin_manager_ref, 'trigger_hook'):
                    plugin_manager_ref.trigger_hook(
                        hook_name,
                        node=self,
                        message=message_data,
                        addr=addr
                    )
                messages_processed_count += 1
            except queue.Empty:
                break
            except Exception as e:
                self.logger.error(f"Error processing message from queue: {e}", exc_info=self.debug_mode)
        return messages_processed_count

    def close(self):
        """Gracefully closes the network node, stops listening, and releases resources."""
        self.logger.info(f"Closing network node {self.node_id}...")
        
        self.auto_reconnect = False # Prevent reconnection attempts during close
        self.stop_listening()       # Stop the listening thread first

        if self.socket:
            socket_was_connected = self.is_connected # Check before modifying
            self.is_connected = False # Mark as not connected immediately
            self.initialized = False

            if socket_was_connected and self.local_ip:
                try:
                    # Attempt to leave the multicast group
                    mreq_leave = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(self.local_ip)
                    self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq_leave)
                    self.logger.info("Left multicast group.")
                except Exception as e_mcast_leave:
                    if self.debug_mode: self.logger.debug(f"Error leaving multicast group: {e_mcast_leave}")
            
            try:
                self.socket.close()
                self.logger.info("Socket closed.")
            except Exception as e_sock_close:
                if self.debug_mode: self.logger.debug(f"Error closing socket: {e_sock_close}")
            self.socket = None
        
        self.logger.info(f"Network node {self.node_id} closed.")