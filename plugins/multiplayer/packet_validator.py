import re
import json
import os
import time
from typing import Dict, Any, Optional, List, Tuple

class PacketValidator:
    """Utility class to validate network packets for security and integrity"""
    
    @staticmethod
    def validate_message(message: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """
        Validate a message for required fields and proper structure
        
        Args:
            message: The message to validate
            
        Returns:
            (is_valid, error_message)
        """
        # Check for required fields
        required_fields = ['node_id', 'timestamp', 'type', 'payload']
        for field in required_fields:
            if field not in message:
                return False, f"Missing required field: {field}"
        
        # Validate node_id format (alphanumeric)
        if not isinstance(message['node_id'], str) or not re.match(r'^[a-zA-Z0-9_-]+$', message['node_id']):
            return False, "Invalid node_id format"
        
        # Check timestamp (should be within 1 hour of current time to prevent replay attacks)
        current_time = time.time()
        msg_time = message['timestamp']
        if not isinstance(msg_time, (int, float)) or abs(current_time - msg_time) > 3600:
            return False, "Invalid timestamp"
        
        # Validate message type
        valid_types = [
            'heartbeat', 'squid_move', 'squid_action', 'object_sync', 
            'rock_throw', 'player_join', 'player_leave', 'state_update',
            'squid_exit', 'new_squid_arrival'
        ]
        if message['type'] not in valid_types:
            return False, f"Unknown message type: {message['type']}"
        
        # Validate payload is a dictionary
        if not isinstance(message['payload'], dict):
            return False, "Payload must be a dictionary"
        
        # Type-specific validation
        if message['type'] == 'squid_exit':
            return PacketValidator.validate_squid_exit(message['payload'])
        elif message['type'] == 'object_sync':
            return PacketValidator.validate_object_sync(message['payload'])
        
        # Default to valid for types without specific validation
        return True, None
    
    @staticmethod
    def validate_squid_exit(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate squid exit payload"""
        # Check for nested payload structure
        if 'payload' not in payload:
            return False, "Missing nested payload in squid_exit message"
        
        exit_data = payload['payload']
        
        # Check required fields
        required_fields = ['node_id', 'direction', 'position', 'color']
        for field in required_fields:
            if field not in exit_data:
                return False, f"Missing required field in squid_exit: {field}"
        
        # Validate direction
        valid_directions = ['left', 'right', 'up', 'down']
        if exit_data['direction'] not in valid_directions:
            return False, f"Invalid exit direction: {exit_data['direction']}"
        
        # Validate position is a dictionary with x,y
        if not isinstance(exit_data['position'], dict) or not all(k in exit_data['position'] for k in ['x', 'y']):
            return False, "Invalid position format"
        
        # Validate color is a tuple or list
        color = exit_data['color']
        if not isinstance(color, (list, tuple)) or len(color) < 3 or not all(isinstance(c, int) for c in color[:3]):
            return False, "Invalid color format"
        
        return True, None
    
    @staticmethod
    def validate_object_sync(payload: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
        """Validate object sync payload"""
        # Check for squid data
        if 'squid' not in payload:
            return False, "Missing squid data in object_sync"
        
        # Check for objects array
        if 'objects' not in payload:
            return False, "Missing objects array in object_sync"
        
        if not isinstance(payload['objects'], list):
            return False, "Objects must be an array"
        
        # Validate squid data has required fields
        squid = payload['squid']
        required_squid_fields = ['x', 'y', 'direction']
        for field in required_squid_fields:
            if field not in squid:
                return False, f"Missing required squid field: {field}"
        
        # Validate node_info if present
        if 'node_info' in payload:
            node_info = payload['node_info']
            if not isinstance(node_info, dict) or 'id' not in node_info:
                return False, "Invalid node_info format"
        
        return True, None
    
    @staticmethod
    def sanitize_object_data(objects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sanitize object data to ensure no malicious content"""
        sanitized = []
        
        for obj in objects:
            # Check if required fields exist
            if not all(k in obj for k in ['id', 'type', 'x', 'y']):
                continue
                
            # Sanitize filename to prevent directory traversal
            if 'filename' in obj:
                filename = obj['filename']
                # Remove any path navigation
                filename = re.sub(r'\.\./', '', filename)
                filename = re.sub(r'\.\.\\', '', filename)
                # Use only the basename
                import os
                filename = os.path.basename(filename)
                obj['filename'] = filename
            
            # Ensure numeric values are valid
            obj['x'] = float(obj['x']) if isinstance(obj['x'], (int, float)) else 0
            obj['y'] = float(obj['y']) if isinstance(obj['y'], (int, float)) else 0
            if 'scale' in obj:
                obj['scale'] = float(obj['scale']) if isinstance(obj['scale'], (int, float)) else 1.0
                
            # Limit to valid values
            obj['scale'] = max(0.1, min(5.0, obj['scale']))  # Reasonable scale limits
            
            sanitized.append(obj)
            
        return sanitized