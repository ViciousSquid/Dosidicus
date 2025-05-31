# File: mp_network_node.py

import uuid
import time
import socket
import queue # Retaining import
import zlib
import json
import traceback # Retaining import
import threading
import logging # Ensure logging is imported

# Import constants
from .mp_constants import MULTICAST_GROUP, MULTICAST_PORT, MAX_PACKET_SIZE


class NetworkNode:
    def __init__(self, node_id=None, logger=None):
        """
        Represents a networked node in the multiplayer system.

        Args:
            node_id (str, optional): Unique identifier for this node.
                                     Generated if not provided.
            logger (logging.Logger, optional): Logger instance to use.
                                               A default one is created if not provided.
        """
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
        # self.outgoing_queue is not used in the provided send logic for this file.
        # If it were used by a separate sending thread, its usage would be different.
        # Based on the provided file, messages are sent directly.

        self.known_nodes = {}
        self.last_sync_time = 0
        self.debug_mode = False 

        if logger is not None:
            self.logger = logger
        else:
            _logger_name = f"{__name__}.NetworkNode.{self.node_id[:4]}"
            self.logger = logging.getLogger(_logger_name)
            if not self.logger.handlers:
                handler = logging.StreamHandler()
                formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
                handler.setFormatter(formatter)
                self.logger.addHandler(handler)
                # Initial level, can be updated by MultiplayerPlugin if debug_mode changes
                self.logger.setLevel(logging.DEBUG if self.debug_mode else logging.INFO)
        
        self.initialize_socket_structure()

    def _get_local_ip(self):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.settimeout(0.1) 
                s.connect(("8.8.8.8", 80)) 
                local_ip = s.getsockname()[0]
            return local_ip
        except Exception as e:
            self.logger.warning(f"Error getting local IP: {e}. Defaulting to 127.0.0.1.")
            return '127.0.0.1'

    def initialize_socket_structure(self):
        if self.is_connected and self.socket:
            self.logger.info("Socket structure already initialized and connected.")
            return True
            
        try:
            if self.socket: 
                try:
                    self.socket.close()
                except Exception: pass 
            
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)

            max_bind_attempts = 3
            current_attempt = 0
            bind_port = MULTICAST_PORT
            bind_success = False

            while current_attempt < max_bind_attempts:
                try:
                    self.socket.bind(('', bind_port)) 
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
                    bind_port += 1 

            if not bind_success:
                self.is_connected = False
                self.initialized = False
                return False
            
            mreq = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(self.local_ip)
            self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            self.socket.settimeout(0.1) 

            self.is_connected = True
            self.initialized = True
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
        self.logger.info(f"Listener thread started for node {self.node_id} on IP {self.local_ip}.")
        while self._is_listening_active:
            if not self.is_connected or not self.socket:
                self.logger.warning("Listening loop: Socket not connected. Attempting to reconnect...")
                if not self.try_reconnect(): 
                    self.logger.error("Listening loop: Reconnect failed. Pausing before retry.")
                    time.sleep(self.connection_retry_interval) 
                    continue 

            messages = self.receive_messages() 
            if not messages and not self._is_listening_active:
                 break
            
            time.sleep(0.001) 

        self.logger.info(f"Listener thread stopped for node {self.node_id}.")

    def is_listening(self):
        return self._is_listening_active and self.listener_thread is not None and self.listener_thread.is_alive()

    def start_listening(self):
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
            self._is_listening_active = True 
            self.listener_thread = threading.Thread(target=self._listen_for_multicast, daemon=True)
            self.listener_thread.setName(f"MPNodeListener-{self.node_id[:4]}")
            self.listener_thread.start()
            self.logger.info("Listener thread started successfully.")
            return True
        except Exception as e:
            self.logger.error(f"Failed to start listener thread: {e}", exc_info=self.debug_mode)
            self._is_listening_active = False 
            return False

    def stop_listening(self):
        if not self._is_listening_active and (self.listener_thread is None or not self.listener_thread.is_alive()):
            self.logger.info("Listener already stopped or was never started.")
            return

        self.logger.info("Stopping listener thread...")
        self._is_listening_active = False 
        
        if self.listener_thread and self.listener_thread.is_alive():
            self.listener_thread.join(timeout=2.0) 
            if self.listener_thread.is_alive():
                self.logger.warning("Listener thread did not stop in time (join timeout).")
            else:
                self.logger.info("Listener thread joined successfully.")
        else:
            self.logger.info("Listener thread was not active or did not exist.")
            
        self.listener_thread = None

    def try_reconnect(self):
        if self.is_listening(): 
            return True

        current_time = time.time()
        if current_time - self.last_connection_attempt < self.connection_retry_interval:
            return False 

        self.logger.info("Attempting to reconnect...")
        self.last_connection_attempt = current_time
        
        self.stop_listening() 

        if self.initialize_socket_structure(): 
            return self.start_listening()      
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
            data_to_send: bytes

            if self.use_compression:
                if self.utils and hasattr(self.utils, 'compress_message'):
                    # ** THE FIX IS HERE: Pass the dictionary `message_data` **
                    self.logger.debug(f"MPNetworkNode.send_message: Passing to self.utils.compress_message. Type: {type(message_data)}")
                    if isinstance(message_data, dict):
                        self.logger.debug(f"MPNetworkNode.send_message: Keys in message_data for compress_message: {list(message_data.keys())}")
                    data_to_send = self.utils.compress_message(message_data)
                else:
                    # Fallback to direct zlib if NetworkUtilities.compress_message is not available
                    self.logger.debug(f"MPNetworkNode.send_message: Serializing for zlib. Type of message_data: {type(message_data)}")
                    serialized_message_for_zlib = json.dumps(message_data).encode('utf-8')
                    self.logger.debug(f"MPNetworkNode.send_message: Type of serialized_message_for_zlib for zlib.compress: {type(serialized_message_for_zlib)}")
                    data_to_send = zlib.compress(serialized_message_for_zlib)
            else: # Not using compression
                self.logger.debug(f"MPNetworkNode.send_message: Not using compression. Serializing message_data. Type: {type(message_data)}")
                data_to_send = json.dumps(message_data).encode('utf-8')


            if len(data_to_send) > MAX_PACKET_SIZE:
                self.logger.warning(f"Message '{message_type}' size ({len(data_to_send)}) exceeds MAX_PACKET_SIZE. May fail.")

            self.socket.sendto(data_to_send, (MULTICAST_GROUP, MULTICAST_PORT))
            if self.debug_mode and message_type not in ['object_sync', 'squid_move', 'heartbeat']: 
                self.logger.debug(f"Sent '{message_type}' ({len(data_to_send)} bytes).")
            return True
        except socket.error as sock_err:
            self.logger.error(f"Socket error sending message '{message_type}': {sock_err}")
            self.is_connected = False 
            self.stop_listening() 
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

        batch_data = { # This is a dictionary
            'node_id': self.node_id,
            'timestamp': time.time(),
            'batch': True,
            'messages': [{'type': msg_type, 'payload': payload} for msg_type, payload in messages]
        }

        try:
            data_to_send: bytes

            if self.use_compression:
                if self.utils and hasattr(self.utils, 'compress_message'):
                    # ** THE FIX IS HERE: Pass the dictionary `batch_data` **
                    self.logger.debug(f"MPNetworkNode.send_message_batch: Passing to self.utils.compress_message. Type: {type(batch_data)}")
                    if isinstance(batch_data, dict):
                        self.logger.debug(f"MPNetworkNode.send_message_batch: Keys in batch_data for compress_message: {list(batch_data.keys())}")
                    data_to_send = self.utils.compress_message(batch_data)
                else:
                    self.logger.debug(f"MPNetworkNode.send_message_batch: Serializing for zlib. Type of batch_data: {type(batch_data)}")
                    serialized_batch_for_zlib = json.dumps(batch_data).encode('utf-8')
                    self.logger.debug(f"MPNetworkNode.send_message_batch: Type of serialized_batch_for_zlib for zlib.compress: {type(serialized_batch_for_zlib)}")
                    data_to_send = zlib.compress(serialized_batch_for_zlib)
            else: # Not using compression
                self.logger.debug(f"MPNetworkNode.send_message_batch: Not using compression. Serializing batch_data. Type: {type(batch_data)}")
                data_to_send = json.dumps(batch_data).encode('utf-8')


            if len(data_to_send) > MAX_PACKET_SIZE:
                self.logger.warning(f"Batch message size ({len(data_to_send)}) exceeds MAX_PACKET_SIZE. Transmission may fail.")

            self.socket.sendto(data_to_send, (MULTICAST_GROUP, MULTICAST_PORT))
            if self.debug_mode:
                self.logger.debug(f"Sent batch message ({len(data_to_send)} bytes).")
            return True
        except socket.error as sock_err:
            self.logger.error(f"Socket error sending message batch: {sock_err}")
            self.is_connected = False
            self.stop_listening()
        except Exception as e:
            self.logger.error(f"Error sending message batch: {e}", exc_info=self.debug_mode)
        return False


    # In plugins/multiplayer/mp_network_node.py (inside NetworkNode class)

    def receive_messages(self):
        if not self.is_connected or not self.socket:
            return [] 

        received_messages_this_call = []
        try:
            for _ in range(10): # Process up to 10 messages per call to avoid blocking
                try:
                    raw_data, addr = self.socket.recvfrom(MAX_PACKET_SIZE)
                    if not raw_data:
                        continue 

                    # =============== NEW PRINT STATEMENT (1/3) ===============
                    # Log raw data reception from OTHERS (before filtering self)
                    # We want to see if the squid_exit packet arrives here at all.
                    # To avoid confusion with self-messages, let's initially peek at a potential node_id
                    # This is a bit hacky for a peek, but helps for this specific debug.
                    temp_node_id_peek = "unknown_at_raw_recv"
                    try:
                        # Attempt a quick, optimistic partial decode just for sender ID logging
                        # This is VERY simplified and might fail often, but good enough for a hint
                        if self.use_compression:
                            try:
                                d_peek = zlib.decompress(raw_data)
                                j_peek = json.loads(d_peek.decode('utf-8', errors='ignore'))
                                temp_node_id_peek = j_peek.get('node_id', 'peek_decode_fail')
                            except: # Broad except as this is just for a debug hint
                                temp_node_id_peek = 'peek_zlib_fail'
                        else:
                            try:
                                j_peek = json.loads(raw_data.decode('utf-8', errors='ignore'))
                                temp_node_id_peek = j_peek.get('node_id', 'peek_json_fail')
                            except:
                                 temp_node_id_peek = 'peek_raw_json_fail'
                    except:
                        pass # Ignore errors in this peek

                    if temp_node_id_peek != self.node_id : # Only log if it's potentially from another node
                        print(f"DEBUG_RAW_RECEIVE: Node {self.node_id} RAW_RECV from {addr} (potential sender: {temp_node_id_peek}). Size: {len(raw_data)}. Data[:60]: {raw_data[:60]}")
                    # ========================================================

                    message_dict = None
                    decoded_successfully = False
                    decompression_attempted = False
                    decompression_error_details = "No decompression error."

                    if self.use_compression:
                        decompression_attempted = True
                        try:
                            if self.utils and hasattr(self.utils, 'decompress_message'):
                                message_dict = self.utils.decompress_message(raw_data)
                            else: # Fallback to direct zlib
                                decompressed_data_bytes = zlib.decompress(raw_data)
                                message_dict = json.loads(decompressed_data_bytes.decode('utf-8'))
                            
                            if isinstance(message_dict, dict):
                                decoded_successfully = True
                            elif message_dict is None: # Decompress_message might return None on error
                                decompression_error_details = "utils.decompress_message returned None."
                            elif isinstance(message_dict, dict) and "error" in message_dict:
                                decompression_error_details = f"utils.decompress_message error: {message_dict.get('details')}"
                        
                        except (zlib.error, json.JSONDecodeError, UnicodeDecodeError) as e_comp: 
                            decompression_error_details = f"Compressed decoding (zlib/json direct) failed: {e_comp}"
                            # Will fall through to uncompressed
                    
                    if not decoded_successfully: # Try as uncompressed if compression failed or wasn't used
                        try:
                            message_dict = json.loads(raw_data.decode('utf-8'))
                            decoded_successfully = True
                            if decompression_attempted: # Log if we fell back from compression
                                if self.debug_mode: self.logger.debug(f"Successfully decoded as uncompressed JSON after failed compression attempt from {addr}. Original error: {decompression_error_details}")
                        except (json.JSONDecodeError, UnicodeDecodeError) as e_json:
                            if self.debug_mode: self.logger.debug(f"Failed all decoding attempts from {addr}: CompError='{decompression_error_details}', UncompJSONError='{e_json}'. Data: {raw_data[:80]}...")
                            continue # Skip this datagram if all decoding fails
                    
                    # =============== MODIFIED PRINT STATEMENT (2/3) ===============
                    # This is the old DEBUG_RECEIVE, now more informative
                    log_this_decoded_message = False
                    final_sender_node_id = "unknown_after_decode"

                    if not message_dict or not isinstance(message_dict, dict) or 'node_id' not in message_dict:
                        if self.debug_mode: self.logger.debug(f"Invalid or incomplete message structure AFTER DECODE from {addr}: {message_dict}")
                        continue # Skip if still malformed
                    
                    final_sender_node_id = message_dict.get('node_id')
                    if final_sender_node_id != self.node_id: # Only log messages from OTHERS
                        log_this_decoded_message = True
                    
                    if log_this_decoded_message:
                        payload_keys_str = list(message_dict.get('payload', {}).keys()) if isinstance(message_dict.get('payload'), dict) else 'N/A_or_NotDict'
                        print(f"DEBUG_DECODED: Node {self.node_id} DECODED message from {addr}: Type '{message_dict.get('type')}', From Node '{final_sender_node_id}', PayloadKeys: {payload_keys_str}")
                        if message_dict.get('type') == 'squid_exit': # More detail for squid_exit
                            print(f"DEBUG_SQUID_EXIT_PAYLOAD: {message_dict.get('payload')}")
                    # ==============================================================
                    
                    if final_sender_node_id == self.node_id: # Filter out own messages AFTER logging if needed for loopback test
                        continue

                    # Update known nodes (basic presence)
                    self.known_nodes[message_dict['node_id']] = (addr[0], time.time(), message_dict.get('payload', {}).get('squid', {}))
                    
                    # Put successfully decoded message from other nodes onto the queue
                    self.incoming_queue.put((message_dict, addr))
                    received_messages_this_call.append((message_dict, addr))

                except socket.timeout:
                    break 
                except socket.error as sock_err:
                    self.logger.error(f"Socket error during specific recvfrom: {sock_err}")
                    self.is_connected = False
                    self._is_listening_active = False
                    break 
                except Exception as e:
                    self.logger.error(f"Unexpected error processing one datagram: {e}", exc_info=self.debug_mode)
                    continue
            
        except Exception as e_outer:
            self.logger.error(f"General error in receive_messages outer loop: {e_outer}", exc_info=self.debug_mode)

        return received_messages_this_call

    def process_messages(self, plugin_manager_ref): # Assuming plugin_manager_ref is the MultiplayerPlugin instance
        messages_processed_count = 0
        # Process a limited number of messages per call to avoid blocking the main thread for too long
        for _ in range(self.incoming_queue.qsize() + 5): # Process current queue + a few more to be safe
            try:
                message_data, addr = self.incoming_queue.get_nowait()

                if not isinstance(message_data, dict) or 'type' not in message_data or 'node_id' not in message_data:
                    if self.debug_mode: self.logger.debug(f"Discarding malformed message from queue: {message_data}")
                    continue

                # Messages from self should have been filtered during receive_messages, but double check.
                if message_data['node_id'] == self.node_id:
                    continue # Skip own messages

                message_type = message_data.get('type', 'unknown_message')

                # Construct hook name, e.g., "on_network_squid_state", "on_network_boundary_exit"
                # This assumes the plugin registers handlers like "on_network_squid_state"
                hook_name = f"on_network_{message_type}" 

                # =============== ADD THIS LINE EXACTLY AS SHOWN BELOW ===============
                print(f"DEBUG_STEP_2A: NetworkNode {self.node_id} is attempting to trigger hook: '{hook_name}' for message type '{message_type}' from node {message_data['node_id']}")
                # =====================================================================

                if hasattr(plugin_manager_ref, 'trigger_hook'): 
                     plugin_manager_ref.trigger_hook(
                         hook_name, 
                         node=self, 
                         message=message_data, 
                         addr=addr
                     )
                elif hasattr(plugin_manager_ref, '_process_network_message'): # Fallback for direct processing
                   plugin_manager_ref._process_network_message(message_data, addr)
                else:
                    if self.debug_mode: self.logger.warning(f"Plugin manager reference has no trigger_hook or _process_network_message method for hook {hook_name}")


                messages_processed_count += 1
            except queue.Empty:
                break # No more messages in the queue
            except Exception as e:
                self.logger.error(f"Error processing message from queue: {e}", exc_info=self.debug_mode)
        return messages_processed_count

    def close(self):
        self.logger.info(f"Closing network node {self.node_id}...")
        
        self.auto_reconnect = False 
        self.stop_listening()       

        if self.socket:
            socket_was_connected = self.is_connected 
            self.is_connected = False 
            self.initialized = False

            if socket_was_connected and self.local_ip: # Only try to leave if was connected & IP known
                try:
                    mreq_leave = socket.inet_aton(MULTICAST_GROUP) + socket.inet_aton(self.local_ip)
                    self.socket.setsockopt(socket.IPPROTO_IP, socket.IP_DROP_MEMBERSHIP, mreq_leave)
                    self.logger.info("Left multicast group.")
                except Exception as e_mcast_leave: # Catch any error during setsockopt
                    if self.debug_mode: self.logger.debug(f"Error leaving multicast group: {e_mcast_leave}")
            
            try:
                self.socket.close()
                self.logger.info("Socket closed.")
            except Exception as e_sock_close:
                if self.debug_mode: self.logger.debug(f"Error closing socket: {e_sock_close}")
            self.socket = None
        
        self.logger.info(f"Network node {self.node_id} closed.")