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