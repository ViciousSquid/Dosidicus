import socket
import time
import uuid
import json
import zlib
from typing import Dict, Any, Tuple, Optional

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
            serialized_msg = json.dumps(message).encode('utf-8')
            try:
                return zlib.compress(serialized_msg)
            except ImportError:
                return serialized_msg
        except Exception as e:
            print(f"Error compressing message: {e}")
            # Return a minimal valid message
            return json.dumps({"error": "compression_failure"}).encode('utf-8')
    
    @staticmethod
    def decompress_message(data: bytes) -> Dict[str, Any]:
        """Decompress a message with efficient error handling"""
        try:
            try:
                decompressed_data = zlib.decompress(data).decode('utf-8')
            except (ImportError, zlib.error):
                decompressed_data = data.decode('utf-8')
            
            return json.loads(decompressed_data)
        except Exception as e:
            print(f"Error decompressing message: {e}")
            return {"error": "decompression_failure"}
    
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