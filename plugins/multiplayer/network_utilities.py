# In plugins/multiplayer/network_utilities.py

import json
import zlib
import socket # Make sure socket is imported if get_local_ip uses it
import time   # Make sure time is imported if is_node_active uses it
import uuid   # Make sure uuid is imported if generate_node_id uses it
from typing import Dict, Any, Union, List, Tuple # Ensure all used types are imported

# It's good practice to have a logger for utilities if they are complex
# import logging
# logger = logging.getLogger(__name__)


class NetworkUtilities:
    """
    A collection of static utility methods for network operations
    including message compression, decompression, and node ID generation.
    """

    @staticmethod
    def get_local_ip() -> str:
        """
        Attempts to discover the local IP address of the machine.
        Fallback to '127.0.0.1' if discovery fails.
        """
        try:
            # Create a temporary socket to connect to an external server (doesn't send data)
            temp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            temp_socket.settimeout(0.5) # Prevent long blocking
            # Google's public DNS server is a common choice for this
            temp_socket.connect(('8.8.8.8', 80))
            local_ip = temp_socket.getsockname()[0]
            temp_socket.close()
            return local_ip
        except socket.error: # Catch socket-specific errors
            # Fallback if the above method fails (e.g., no network, firewall)
            try:
                # Get hostname and resolve it
                hostname = socket.gethostname()
                local_ip = socket.gethostbyname(hostname)
                return local_ip
            except socket.gaierror: # getaddrinfo error
                return '127.0.0.1' # Ultimate fallback
        except Exception:
            # Catch any other unexpected errors
            return '127.0.0.1'


    @staticmethod
    def compress_message(message: Dict[str, Any]) -> bytes:
        """Compress a message dictionary to bytes using JSON and zlib."""
        is_squid_exit_message = message.get('type') == 'squid_exit'
        
        # Optional: More detailed logging for all messages for debugging structure
        # print("--- Debug: Attempting to compress message (NetworkUtilities) ---")
        # for key, value in message.items():
        #     print(f"  Key: {key}, Type: {type(value)}")
        #     if isinstance(value, dict):
        #         for sub_key, sub_value in value.items():
        #             print(f"    SubKey: {sub_key}, SubType: {type(sub_value)}")
        # print("--- End of debug statements for message content (NetworkUtilities) ---")

        if is_squid_exit_message:
            # Using json.dumps for pretty printing complex nested structures for the log
            try:
                message_for_log = json.dumps(message, indent=2)
            except TypeError: # Handle non-serializable items if any for logging
                message_for_log = str(message) # Fallback to string representation
            print(f"DEBUG_COMPRESS: Compressing SQUID_EXIT. Full message data: {message_for_log}")

        serialized_msg = None # Initialize to handle potential early error
        try:
            serialized_msg = json.dumps(message).encode('utf-8')
            if is_squid_exit_message:
                print(f"DEBUG_COMPRESS: SQUID_EXIT serialized size: {len(serialized_msg)}")
            
            compressed_msg = zlib.compress(serialized_msg)
            if is_squid_exit_message:
                compression_ratio = len(compressed_msg) / len(serialized_msg) if len(serialized_msg) > 0 else 0
                print(f"DEBUG_COMPRESS: SQUID_EXIT compressed size: {len(compressed_msg)}. Compression ratio: {compression_ratio:.2f}")
            return compressed_msg

        except TypeError as te:
            error_detail = f"TypeError during JSON serialization for SQUID_EXIT: {te}. Message keys: {list(message.keys())}" if is_squid_exit_message else f"TypeError during JSON serialization: {te}. Message keys: {list(message.keys())}"
            print(f"DEBUG_COMPRESS_ERROR: {error_detail}")
            # Fallback: return an error message, still as bytes
            return json.dumps({"error": "json_type_error", "details": str(te), "original_type": message.get('type')}).encode('utf-8')
        except zlib.error as ze:
            error_detail = f"zlib compression error for SQUID_EXIT: {ze}. Sending uncompressed." if is_squid_exit_message else f"zlib compression error: {ze}. Sending uncompressed."
            print(f"DEBUG_COMPRESS_ERROR: {error_detail}")
            if serialized_msg: # If serialization succeeded before zlib error
                return serialized_msg 
            else: # Should not happen if TypeError is caught, but as a safeguard
                return json.dumps({"error": "zlib_error_and_serialization_failed", "details": str(ze), "original_type": message.get('type')}).encode('utf-8')
        except Exception as e:
            error_detail = f"General error compressing SQUID_EXIT: {e}" if is_squid_exit_message else f"General error compressing message: {e}"
            print(f"DEBUG_COMPRESS_ERROR: {error_detail}")
            return json.dumps({"error": "compression_failure", "details": str(e), "original_type": message.get('type')}).encode('utf-8')

    @staticmethod
    def decompress_message(compressed_msg: bytes) -> Union[Dict[str, Any], None]:
        """Decompress bytes to a message dictionary using zlib and JSON."""
        if not compressed_msg:
            print("DEBUG_DECOMPRESS_ERROR: Received empty message for decompression.")
            return None

        # Crude check on raw/compressed bytes to see if it *might* be a squid_exit message for targeted logging
        # This check is heuristic and might not always be accurate before decompression.
        is_potentially_squid_exit = b'"type": "squid_exit"' in compressed_msg or \
                                    b'squid_exit' in compressed_msg # More generic check
        
        if is_potentially_squid_exit:
            print(f"DEBUG_DECOMPRESS: Potential SQUID_EXIT raw data received (first 100 bytes): {compressed_msg[:100]}")

        decompressed_data_str = None
        message_dict = None

        try:
            # Attempt zlib decompression first
            try:
                decompressed_bytes = zlib.decompress(compressed_msg)
                if is_potentially_squid_exit:
                     print(f"DEBUG_DECOMPRESS: SQUID_EXIT (potential) successfully zlib decompressed. Decompressed size: {len(decompressed_bytes)}")
                decompressed_data_str = decompressed_bytes.decode('utf-8')
                message_dict = json.loads(decompressed_data_str)
            except zlib.error as ze_decompress:
                # If zlib fails, assume it's uncompressed JSON
                if is_potentially_squid_exit:
                    print(f"DEBUG_DECOMPRESS: zlib.error for SQUID_EXIT (potential) ('{ze_decompress}'). Assuming uncompressed JSON.")
                decompressed_data_str = compressed_msg.decode('utf-8') # Use original msg as string
                message_dict = json.loads(decompressed_data_str)
            except UnicodeDecodeError as ude: # Catch if decode after zlib fails
                print(f"DEBUG_DECOMPRESS_ERROR: UnicodeDecodeError after zlib success (or if it was uncompressed non-UTF8). Details: {ude}. Data (first 100 bytes of error source): {decompressed_bytes[:100] if 'decompressed_bytes' in locals() else compressed_msg[:100]}")
                return {"error": "unicode_decode_error_post_zlib", "details": str(ude)}

            # After successful JSON load, confirm and log if it's a squid_exit
            if isinstance(message_dict, dict) and message_dict.get('type') == 'squid_exit':
                # Using json.dumps for pretty printing complex nested structures for the log
                try:
                    message_for_log = json.dumps(message_dict, indent=2)
                except TypeError:
                    message_for_log = str(message_dict) # Fallback
                print(f"DEBUG_DECOMPRESS: Successfully decoded SQUID_EXIT message: {message_for_log}")
            
            return message_dict

        except UnicodeDecodeError as ude_uncompressed: # If decode of presumed uncompressed fails
            print(f"DEBUG_DECOMPRESS_ERROR: UnicodeDecodeError (assuming uncompressed). Details: {ude_uncompressed}. Raw data (first 100 bytes): {compressed_msg[:100]}")
            return {"error": "unicode_decode_error_uncompressed", "details": str(ude_uncompressed)}
        except json.JSONDecodeError as jde:
            # The data fed to json.loads here is `decompressed_data_str`
            print(f"DEBUG_DECOMPRESS_ERROR: JSONDecodeError. Details: {jde}. Data fed to json.loads (first 100 chars): {decompressed_data_str[:100] if decompressed_data_str else 'N/A'}")
            return {"error": "json_decode_error", "details": str(jde)}
        except Exception as e: # Catch-all for other unexpected errors
            print(f"DEBUG_DECOMPRESS_ERROR: General Exception during decompression. Details: {e}. Raw data (first 100 bytes): {compressed_msg[:100]}")
            return {"error": "general_decompression_failure", "details": str(e)}

    @staticmethod
    def generate_node_id(prefix: str = "squid") -> str:
        """Generate a unique node identifier with a given prefix."""
        # Generate a UUID and take a portion of its hex representation for brevity
        return f"{prefix}_{uuid.uuid4().hex[:8]}"

    @staticmethod
    def is_node_active(last_seen_time: float, threshold: float = 30.0) -> bool: # Increased threshold
        """
        Check if a node is considered active based on its last seen time.
        Args:
            last_seen_time: The timestamp (unix epoch float) when the node was last heard from.
            threshold: The number of seconds without contact after which a node is considered inactive.
        Returns:
            True if the node is active, False otherwise.
        """
        if last_seen_time is None:
            return False # Never seen
        return (time.time() - last_seen_time) < threshold

# Example of a BinaryProtocol class if it were part of this file:
# class BinaryProtocol:
#     @staticmethod
#     def pack_data(*args) -> bytes:
#         # Example: Implement packing logic using struct or similar
#         # This is a placeholder and would need a proper specification
#         packed_bytes = b''
#         for arg in args:
#             if isinstance(arg, int):
#                 packed_bytes += arg.to_bytes(4, 'big', signed=True)
#             elif isinstance(arg, float):
#                 # A more robust solution would use struct.pack
#                 packed_bytes += str(arg).encode('utf-8').ljust(16, b'\0') # Simplistic
#             elif isinstance(arg, str):
#                 packed_bytes += arg.encode('utf-8').ljust(32, b'\0') # Simplistic
#         return packed_bytes

#     @staticmethod
#     def unpack_data(data: bytes) -> tuple:
#         # Example: Implement unpacking logic
#         # This is a placeholder
#         # Assuming a fixed format like: int (4B), float_str (16B), str (32B)
#         num = int.from_bytes(data[0:4], 'big', signed=True)
#         float_val_str = data[4:20].decode('utf-8').strip('\0')
#         str_val = data[20:52].decode('utf-8').strip('\0')
#         return num, float(float_val_str), str_val