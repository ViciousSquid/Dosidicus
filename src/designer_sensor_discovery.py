# designer_sensor_discovery.py
"""
Utility module for discovering available input sensors.

This module provides functions to merge built-in sensors from designer_constants
with plugin-registered custom sensors from the plugin manager.
"""

from typing import Dict, Any, Optional

# Try to import designer constants
try:
    from designer_constants import INPUT_SENSORS, REQUIRED_NEURONS, BINARY_NEURONS
except ImportError:
    # Fallbacks if constants file is missing or structure is different
    INPUT_SENSORS = {}
    REQUIRED_NEURONS = {}
    BINARY_NEURONS = set()

# Localization helper
try:
    from localization import tr
except ImportError:
    def tr(key, **kwargs):
        return key


def get_plugin_manager() -> Optional[Any]:
    """
    Try to get the PluginManager singleton instance.
    
    Returns:
        PluginManager instance or None if not available
    """
    try:
        from plugin_manager import PluginManager
        pm = PluginManager()
        if hasattr(pm, '_initialized') and pm._initialized:
            return pm
    except ImportError:
        pass
    except Exception:
        pass
    return None


def get_builtin_sensors() -> Dict[str, Dict]:
    """
    Get all built-in sensors from designer_constants.
    
    Returns:
        Dict mapping sensor names to their info dicts
    """
    sensors = {}
    
    # Add INPUT_SENSORS
    # NOTE: In brain_constants, values are (x, y) tuples, not dicts.
    for name, info in INPUT_SENSORS.items():
        # Default values
        description = tr("desc_builtin_sensor").format(name=name.replace('_', ' ').title())
        is_binary = name in BINARY_NEURONS
        category = tr("desc_builtin")
        default_connections = []
        
        # Handle case where info is a dict (future compatibility) vs tuple (current)
        if isinstance(info, dict):
            description = info.get('description', description)
            is_binary = info.get('is_binary', is_binary)
            category = info.get('category', category)
            default_connections = info.get('default_connections', default_connections)
        
        sensors[name] = {
            'description': description,
            'is_binary': is_binary,
            'category': category,
            'plugin': None,  # Built-in, not from a plugin
            'default_connections': default_connections
        }
    
    # Add can_see_food from REQUIRED_NEURONS if not already present
    if 'can_see_food' not in sensors and 'can_see_food' in REQUIRED_NEURONS:
        # Check if REQUIRED_NEURONS uses dicts or tuples
        info = REQUIRED_NEURONS['can_see_food']
        
        description = tr("desc_vision_food")
        default_connections = []
        
        if isinstance(info, dict):
             description = info.get('description', description)
             default_connections = info.get('default_connections', default_connections)

        sensors['can_see_food'] = {
            'description': description,
            'is_binary': True,
            'category': tr("desc_vision"),
            'plugin': None,
            'default_connections': default_connections
        }
    
    return sensors


def get_plugin_sensors() -> Dict[str, Dict]:
    """
    Get all custom sensors registered by plugins.
    
    Returns:
        Dict mapping sensor names to their info dicts
    """
    pm = get_plugin_manager()
    if not pm or not hasattr(pm, 'get_all_neuron_handler_info'):
        return {}
    
    sensors = {}
    try:
        for name, data in pm.get_all_neuron_handler_info().items():
            metadata = data.get('metadata', {})
            plugin_name = data.get("plugin", "unknown")
            default_desc = tr("desc_custom_sensor").format(plugin=plugin_name)
            
            sensors[name] = {
                'description': metadata.get('description', default_desc),
                'is_binary': metadata.get('is_binary', False),
                'category': metadata.get('category', tr("desc_plugin")),
                'plugin': data.get('plugin'),
                'default_connections': metadata.get('default_connections', [])
            }
    except Exception as e:
        print(f"[Designer] Error getting plugin sensors: {e}")
        return {}
    
    return sensors


def get_all_available_sensors() -> Dict[str, Dict]:
    """
    Get all available sensors (built-in + plugin-registered).
    
    Returns:
        Dict mapping sensor names to their info dicts.
        Each info dict contains:
        - description: Human-readable description
        - is_binary: Whether the sensor outputs only 0 or 100
        - category: Category for grouping
        - plugin: Plugin name if custom, None if built-in
        - default_connections: Suggested default connections
    """
    sensors = get_builtin_sensors()
    
    # Merge plugin sensors (plugin sensors can override built-ins)
    plugin_sensors = get_plugin_sensors()
    for name, info in plugin_sensors.items():
        if name in sensors:
            # Plugin is overriding a built-in sensor
            info['_overrides_builtin'] = True
        sensors[name] = info
    
    return sensors


def get_sensors_by_category() -> Dict[str, Dict[str, Dict]]:
    """
    Get all sensors organized by category.
    
    Returns:
        Dict mapping category names to dicts of sensors in that category
    """
    sensors = get_all_available_sensors()
    by_category = {}
    
    for name, info in sensors.items():
        category = info.get('category', tr("desc_other"))
        if category not in by_category:
            by_category[category] = {}
        by_category[category][name] = info
    
    return by_category


def refresh_plugin_sensors():
    """
    Force refresh of plugin sensors.
    
    Call this after plugins are loaded/enabled to update the available sensors.
    """
    # Currently a no-op since we query the plugin manager dynamically,
    # but could be used for caching in the future
    pass


# Convenience function for checking if a sensor is from a plugin
def is_plugin_sensor(sensor_name: str) -> bool:
    """Check if a sensor is from a plugin rather than built-in."""
    sensors = get_all_available_sensors()
    if sensor_name in sensors:
        return sensors[sensor_name].get('plugin') is not None
    return False