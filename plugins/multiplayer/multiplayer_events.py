from PyQt5 import QtCore
from typing import Dict, Any, List, Optional, Callable

class MultiplayerEventDispatcher(QtCore.QObject):
    """Dispatches multiplayer events to registered handlers"""
    
    # Define signals for various event types
    squid_joined = QtCore.pyqtSignal(str, dict)  # node_id, squid_data
    squid_left = QtCore.pyqtSignal(str, str)  # node_id, reason
    squid_moved = QtCore.pyqtSignal(str, dict)  # node_id, position_data
    squid_action = QtCore.pyqtSignal(str, str, dict)  # node_id, action_type, action_data
    object_synced = QtCore.pyqtSignal(str, list)  # node_id, objects_data
    rock_thrown = QtCore.pyqtSignal(str, dict)  # node_id, rock_data
    squid_exited = QtCore.pyqtSignal(str, str, dict)  # node_id, direction, exit_data
    squid_arrived = QtCore.pyqtSignal(str, dict)  # node_id, arrival_data
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.handlers = {}
        self.debug_mode = False
    
    def register_handler(self, event_type: str, handler: Callable):
        """Register a handler for a specific event type"""
        if event_type not in self.handlers:
            self.handlers[event_type] = []
        self.handlers[event_type].append(handler)
        
        # Connect to corresponding signal if it exists
        signal_map = {
            'squid_joined': self.squid_joined,
            'squid_left': self.squid_left,
            'squid_moved': self.squid_moved,
            'squid_action': self.squid_action,
            'object_synced': self.object_synced,
            'rock_thrown': self.rock_thrown,
            'squid_exited': self.squid_exited,
            'squid_arrived': self.squid_arrived
        }
        
        if event_type in signal_map:
            signal_map[event_type].connect(handler)
    
    def dispatch_event(self, event_type: str, *args, **kwargs):
        """Dispatch an event to all registered handlers"""
        if self.debug_mode:
            print(f"Dispatching event: {event_type}")
        
        # Emit the corresponding signal if it exists
        signal_map = {
            'squid_joined': self.squid_joined,
            'squid_left': self.squid_left,
            'squid_moved': self.squid_moved,
            'squid_action': self.squid_action,
            'object_synced': self.object_synced,
            'rock_thrown': self.rock_thrown,
            'squid_exited': self.squid_exited,
            'squid_arrived': self.squid_arrived
        }
        
        if event_type in signal_map:
            signal = signal_map[event_type]
            signal.emit(*args)
        
        # Call direct handlers
        if event_type in self.handlers:
            for handler in self.handlers[event_type]:
                try:
                    handler(*args, **kwargs)
                except Exception as e:
                    print(f"Error in event handler for {event_type}: {e}")