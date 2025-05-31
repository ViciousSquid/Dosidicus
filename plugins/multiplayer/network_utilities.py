import socket
import time
import uuid
import json
import zlib
import os
from typing import Dict, Any, Tuple, Optional, Union

class NetworkUtilities:
    @staticmethod
    def get_local_ip() -> str:
        """Get local IP address with fallback to localhost"""
        try:
            temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_socket.connect(('8.8.8.8', 80))
            local_ip = temp_socket.getsockname()[0]
            temp_socket.close()
            return local_ip
        except Exception:
            return '127.0.0.1'
    
    @staticmethod
    def compress_message(message: Dict[str, Any]) -> bytes:
        """Compress a message with efficient error handling"""
        try:
            # --- Start of added debug statements ---
            print("--- Debug: Attempting to compress message ---")
            for key, value in message.items():
                print(f"  Key: {key}, Type: {type(value)}")
                if isinstance(value, dict):
                    for sub_key, sub_value in value.items():
                        print(f"    SubKey: {sub_key}, SubType: {type(sub_value)}")
                        # You can add more levels of nested checks if your dictionaries are deeper
                        # For example:
                        # if isinstance(sub_value, dict):
                        #     for s_sub_key, s_sub_value in sub_value.items():
                        #         print(f"      SSubKey: {s_sub_key}, SSubType: {type(s_sub_value)}")
                elif isinstance(value, list):
                    print(f"    List items for key '{key}':")
                    for i, item in enumerate(value):
                        print(f"      Item {i}, Type: {type(item)}")
                        if isinstance(item, dict): # If list contains dictionaries
                            for list_dict_key, list_dict_value in item.items():
                                print(f"        DictInList - Key: {list_dict_key}, Type: {type(list_dict_value)}")
            print("--- End of debug statements for message content ---")
            # --- End of added debug statements ---

            serialized_msg = json.dumps(message).encode('utf-8')
            try:
                # Attempt compression, fallback to uncompressed if zlib is not available or fails
                compressed_msg = zlib.compress(serialized_msg)
                return compressed_msg
            except ImportError:
                # zlib not available on this system, return uncompressed
                # This case might be less likely in standard Python environments
                print("Warning: zlib not available, sending uncompressed message.")
                return serialized_msg
            except zlib.error as ze:
                # Handle potential zlib compression errors
                print(f"Error during zlib compression: {ze}. Sending uncompressed.")
                return serialized_msg

        except TypeError as te: # Specifically catch TypeError from json.dumps
            print(f"Error compressing message (TypeError): {te}")
            # Log the problematic message structure for further analysis if in debug mode
            # Be cautious about logging potentially large or sensitive data in production
            # print(f"Problematic message structure: {message}") # Uncomment if needed for deep debug
            return json.dumps({"error": "json_type_error", "details": str(te)}).encode('utf-8')
        except Exception as e:
            # Catch any other unexpected errors during serialization or compression
            print(f"Error compressing message (General Exception): {e}")
            return json.dumps({"error": "compression_failure", "details": str(e)}).encode('utf-8')
    
    @staticmethod
    def decompress_message(compressed_msg: bytes) -> Union[Dict[str, Any], None]:
        """Decompress a message with efficient error handling"""
        if not compressed_msg:
            return None
        try:
            # Attempt decompression, assume it might be uncompressed if zlib fails
            try:
                decompressed_msg = zlib.decompress(compressed_msg)
            except zlib.error:
                # If zlib decompression fails, it might be an uncompressed JSON string
                decompressed_msg = compressed_msg # Treat as potentially uncompressed

            # Now, try to load the JSON
            message = json.loads(decompressed_msg.decode('utf-8'))
            return message
        except UnicodeDecodeError as ude:
            print(f"Error decompressing message (UnicodeDecodeError): {ude}. Original data (first 50 bytes): {compressed_msg[:50]}")
            return {"error": "unicode_decode_error", "details": str(ude)}
        except json.JSONDecodeError as jde:
            print(f"Error decompressing message (JSONDecodeError): {jde}. Data (first 50 bytes): {decompressed_msg[:50] if 'decompressed_msg' in locals() else compressed_msg[:50]}")
            return {"error": "json_decode_error", "details": str(jde)}
        except Exception as e:
            print(f"Error decompressing message (General Exception): {e}")
            return {"error": "decompression_failure", "details": str(e)}
    
    @staticmethod
    def generate_node_id(prefix: str = "squid") -> str:
        """Generate a unique node identifier"""
        return f"{prefix}_{uuid.uuid4().hex[:8]}"
    
    @staticmethod
    def is_node_active(last_seen_time: float, threshold: float = 10.0) -> bool:
        """Check if a node is considered active based on last seen time"""
        return time.time() - last_seen_time < threshold
    
import struct

class BinaryProtocol:
    """Efficient binary protocol for network messages"""
    
    # Message type constants
    MSG_HEARTBEAT = 1
    MSG_SQUID_MOVE = 2
    MSG_OBJECT_SYNC = 3
    MSG_PLAYER_JOIN = 4
    
    @staticmethod
    def encode_squid_move(node_id, x, y, direction, timestamp):
        """Encode squid movement into compact binary format"""
        # Convert direction to numeric value
        dir_map = {'right': 0, 'left': 1, 'up': 2, 'down': 3}
        dir_value = dir_map.get(direction, 0)
        
        # Pack into binary: message type(1) + node_id(16) + x(4) + y(4) + direction(1) + timestamp(8)
        return struct.pack('!B16sffBd', 
                          BinaryProtocol.MSG_SQUID_MOVE,
                          node_id.encode()[:16].ljust(16, b'\0'),
                          float(x), 
                          float(y),
                          dir_value,
                          timestamp)
    
    @staticmethod
    def decode_message(binary_data):
        """Decode binary message into appropriate type"""
        if not binary_data or len(binary_data) < 2:
            return None
            
        msg_type = struct.unpack('!B', binary_data[0:1])[0]
        
        if msg_type == BinaryProtocol.MSG_SQUID_MOVE:
            # Unpack squid move message
            msg_type, node_id, x, y, dir_value, timestamp = struct.unpack('!B16sffBd', binary_data)
            
            # Convert back to string and direction
            node_id = node_id.rstrip(b'\0').decode()
            dir_map = {0: 'right', 1: 'left', 2: 'up', 3: 'down'}
            direction = dir_map.get(dir_value, 'right')
            
            return {
                'type': 'squid_move',
                'node_id': node_id,
                'x': x,
                'y': y,
                'direction': direction,
                'timestamp': timestamp
            }