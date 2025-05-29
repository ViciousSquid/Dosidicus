import os
import importlib.util
import inspect # Retained as it was in the original file
import logging
import sys # For sys.stdout and potentially sys.modules if discover_plugins uses it
from typing import Dict, List, Callable, Any

# ANSI escape codes for colors
class ANSI:
    BLUE = "\x1b[34m"
    RED = "\x1b[31m"
    YELLOW = "\x1b[33m" # For warnings
    CYAN = "\x1b[36m"   # For debug
    RESET = "\x1b[0m"

class ColoredFormatter(logging.Formatter):
    """
    A custom logging formatter that colors only the 'LEVEL:NAME:' prefix
    for messages from the 'PluginManager' logger.
    """
    
    COLORS = {
        logging.DEBUG: ANSI.CYAN,
        logging.INFO: ANSI.BLUE,
        logging.WARNING: ANSI.YELLOW,
        logging.ERROR: ANSI.RED,
        logging.CRITICAL: ANSI.RED, # Can use BOLD_RED if needed
    }

    def __init__(self, fmt="%(levelname)s:%(name)s:%(message)s", datefmt=None, style='%'):
        # We call super().__init__ but will override format completely
        super().__init__(fmt, datefmt, style)

    def format(self, record):
        # Check if the log is from our target logger
        if record.name == "PluginManager":
            # Get the appropriate color for the log level
            color = self.COLORS.get(record.levelno, ANSI.RESET) # Default to RESET if no color found
            
            # Create the prefix string (e.g., "INFO:PluginManager:")
            prefix = f"{record.levelname}:{record.name}:"
            
            # Get the actual log message
            message = record.getMessage()
            
            # Append exception information if present
            if record.exc_info:
                if not record.exc_text:
                    record.exc_text = self.formatException(record.exc_info)
                if record.exc_text:
                    message = message + "\n" + record.exc_text
            
            # Construct the final colored log string
            # Only the prefix is colored; the message remains default (white/black) until RESET
            return f"{color}{prefix}{ANSI.RESET} {message}"
        else:
            # For any other logger, use the default formatter behavior (uncolored)
            # You might want to define a specific format here if needed,
            # but super().format(record) uses the 'fmt' passed during __init__.
            return super().format(record)

class PluginManager:
    _instance = None  # Singleton instance reference
    
    def __new__(cls, *args, **kwargs):
        """Singleton pattern implementation"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False  # Mark as uninitialized
        return cls._instance
    
    def __init__(self, plugin_directory="plugins"):
        """Initialize the plugin manager (only once due to singleton)"""
        if self._initialized:
            return
            
        self.plugin_directory = plugin_directory
        self.plugins: Dict[str, Dict] = {}        # Stores loaded plugins' metadata and instances
        self.hooks: Dict[str, List[Dict]] = {}    # Registered hooks and their subscribers
        self.enabled_plugins: set[str] = set()    # Names of enabled plugins (use lowercase)
        
        # Configure the logger for PluginManager
        self.logger = logging.getLogger("PluginManager")
        
        if not self.logger.handlers: # Avoid adding multiple handlers
            self.logger.setLevel(logging.INFO) # Set the minimum level

            ch = logging.StreamHandler(sys.stdout) # Log to standard output
            
            # Use the NEW ColoredFormatter. 
            # The 'fmt' here is less critical since we override format(), 
            # but it acts as a fallback or for other loggers.
            formatter = ColoredFormatter() 
            ch.setFormatter(formatter)
            
            self.logger.addHandler(ch)
            self.logger.propagate = False # Prevent logs from going to root logger

        self._discovered_plugins: Dict[str, Dict] | None = None
        
        os.makedirs(plugin_directory, exist_ok=True)
        
        self._initialize_hooks()
        self._initialized = True

    # --- Start of Original PluginManager Methods ---
    # (These methods remain largely the same, only the logger setup in __init__ 
    # and the Formatter class definition are the core changes for coloring)

    def _initialize_hooks(self):
        """Initialize standard hooks that plugins can register for"""
        # Lifecycle hooks
        self.register_hook("on_startup")
        self.register_hook("on_shutdown")
        self.register_hook("on_new_game")
        self.register_hook("on_save_game")
        self.register_hook("on_load_game")
        
        # Simulation hooks
        self.register_hook("pre_update")
        self.register_hook("post_update")
        self.register_hook("on_speed_change")
        
        # Squid state hooks
        self.register_hook("on_squid_state_change")
        self.register_hook("on_hunger_change")
        self.register_hook("on_happiness_change")
        self.register_hook("on_cleanliness_change")
        self.register_hook("on_sleepiness_change")
        self.register_hook("on_satisfaction_change")
        self.register_hook("on_anxiety_change")
        self.register_hook("on_curiosity_change")
        
        # Action hooks
        self.register_hook("on_feed")
        self.register_hook("on_clean")
        self.register_hook("on_medicine")
        self.register_hook("on_sleep")
        self.register_hook("on_wake")
        self.register_hook("on_startle")
        
        # Interaction hooks
        self.register_hook("on_rock_pickup")
        self.register_hook("on_rock_throw")
        self.register_hook("on_decoration_interaction")
        self.register_hook("on_ink_cloud")
        
        # Neural/memory hooks
        self.register_hook("on_neurogenesis")
        self.register_hook("on_memory_created")
        self.register_hook("on_memory_to_long_term")
        
        # UI hooks
        self.register_hook("on_menu_creation")
        self.register_hook("on_message_display")
        
        # Custom menu action hooks
        self.register_hook("register_menu_actions")
    
    def register_hook(self, hook_name: str) -> None:
        """
        Register a new hook that plugins can subscribe to.
        """
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
            self.logger.debug(f"Registered hook: {hook_name}")
    
    def subscribe_to_hook(self, hook_name: str, plugin_name: str, callback: Callable) -> bool:
        """
        Subscribe a plugin's callback to a specific hook.
        """
        if hook_name not in self.hooks:
            self.logger.warning(f"Plugin {plugin_name} tried to subscribe to non-existent hook: {hook_name}")
            return False
        
        self.hooks[hook_name].append({
            "plugin": plugin_name,
            "callback": callback
        })
        self.logger.debug(f"Plugin {plugin_name} subscribed to hook: {hook_name}")
        return True
    
    def unsubscribe_from_hook(self, hook_name: str, plugin_name: str) -> bool:
        """
        Unsubscribe a plugin from a specific hook.
        """
        if hook_name not in self.hooks:
            return False
        
        self.hooks[hook_name] = [
            h for h in self.hooks[hook_name] 
            if h["plugin"] != plugin_name
        ]
        return True
    
    def trigger_hook(self, hook_name, **kwargs):
        """
        Trigger a hook, calling all subscribed plugin callbacks.
        """
        if hook_name not in self.hooks:
            self.logger.warning(f"Attempted to trigger non-existent hook: {hook_name}")
            return []
        
        results = []
        for subscriber in self.hooks[hook_name]:
            plugin_name = subscriber["plugin"]
            # Only trigger hooks for enabled plugins
            if plugin_name.lower() not in self.enabled_plugins:
                continue
                
            try:
                callback = subscriber["callback"]
                result = callback(**kwargs)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error in plugin {plugin_name} for hook {hook_name}: {str(e)}", exc_info=True)
        
        return results
    
    def discover_plugins(self) -> Dict[str, Dict]:
        """
        Discover available plugins from the plugin directory.
        Ensures plugin names (keys in the returned dict) are lowercase.
        """
        plugin_info: Dict[str, Dict] = {}
        
        if not os.path.exists(self.plugin_directory):
            self.logger.warning(f"Plugin directory does not exist: {self.plugin_directory}")
            return plugin_info
        
        self.logger.info(f"Discovering plugins in directory: '{self.plugin_directory}'")

        for plugin_dir in os.listdir(self.plugin_directory):
            plugin_path = os.path.join(self.plugin_directory, plugin_dir)
            
            if not os.path.isdir(plugin_path):
                continue
                
            main_py = os.path.join(plugin_path, "main.py")
            
            if not os.path.exists(main_py):
                self.logger.debug(f"No main.py found in {plugin_path}")
                continue
                
            try:
                module_name = f"plugins.{plugin_dir}.main"
                spec = importlib.util.spec_from_file_location(module_name, main_py)
                if spec is None or spec.loader is None:
                    self.logger.error(f"Could not create spec for plugin {plugin_dir} at {main_py}")
                    continue
                module = importlib.util.module_from_spec(spec)
                
                sys.modules[module_name] = module

                spec.loader.exec_module(module)
                
                plugin_name_attr = getattr(module, "PLUGIN_NAME", plugin_dir)
                plugin_name = plugin_name_attr.lower()
                
                metadata = {
                    "name": plugin_name,
                    "original_name": plugin_name_attr,
                    "version": getattr(module, "PLUGIN_VERSION", "1.0.0"),
                    "author": getattr(module, "PLUGIN_AUTHOR", "Unknown"),
                    "description": getattr(module, "PLUGIN_DESCRIPTION", ""),
                    "requires": [req.lower() for req in getattr(module, "PLUGIN_REQUIRES", [])],
                    "path": main_py,
                    "directory": plugin_path,
                    "module": module,
                    "main_class_name": getattr(module, "PLUGIN_MAIN_CLASS", None) 
                }
                
                plugin_info[plugin_name] = metadata
                self.logger.info(f"Discovered plugin: {metadata['original_name']} v{metadata['version']} (key: {plugin_name})")
                
            except Exception as e:
                self.logger.error(f"Error discovering plugin in '{plugin_dir}': {str(e)}", exc_info=True)
        
        self._discovered_plugins = plugin_info
        if not plugin_info:
            self.logger.info("No plugins discovered to load.")
        return plugin_info

    def load_plugin(self, plugin_name: str) -> bool:
        """
        Load and initialize a plugin by name. Assumes plugin_name is already lowercase.
        (Using the version from previous turns, without the 'instance' check that was causing issues)
        """
        plugin_name = plugin_name.lower()

        if plugin_name in self.plugins:
            self.logger.info(f"Plugin '{plugin_name}' already loaded.")
            return True

        if self._discovered_plugins is None:
            self.logger.error("Plugin discovery must be run before loading.")
            self._discovered_plugins = self.discover_plugins()

        if plugin_name not in self._discovered_plugins:
            self.logger.error(f"Plugin '{plugin_name}' not found.")
            return False

        plugin_data = self._discovered_plugins[plugin_name]
        module = plugin_data["module"]
        original_plugin_name_display = plugin_data.get("original_name", plugin_name)

        self.logger.info(f"Attempting to load plugin '{original_plugin_name_display}' (key: '{plugin_name}')")
        self.logger.info(f"Plugin '{plugin_name}': Module '{module.__name__}' found.")

        required_plugins = plugin_data.get("requires", [])
        if required_plugins:
            missing_plugins = []
            for required_name_lower in required_plugins:
                if required_name_lower not in self.plugins:
                    missing_plugins.append(required_name_lower)
            if missing_plugins:
                self.logger.error(f"Plugin '{plugin_name}' requires missing plugin(s): {', '.join(missing_plugins)}.")
                self.logger.error(f"Plugin '{plugin_name}': Dependency check failed.")
                return False
        self.logger.info(f"Plugin '{plugin_name}': Dependencies satisfied.")

        if not hasattr(module, "initialize"):
            self.logger.error(f"Plugin '{plugin_name}' has no 'initialize' function.")
            return False
        self.logger.info(f"Plugin '{plugin_name}': Found 'initialize' function. Attempting to call.")

        try:
            initialize_func = getattr(module, "initialize")
            success = initialize_func(self)  # Call initialize

            if success:
                self.logger.info(f"Plugin '{plugin_name}': 'initialize' function executed successfully.")
                
                # Check if plugin registered itself (especially important for multiplayer's pattern)
                if plugin_name not in self.plugins:
                     # If it didn't register itself, add the discovered data now.
                     # This might happen for simpler plugins. If it was *supposed* to register and didn't,
                     # it might cause issues later if an instance is expected.
                     self.logger.info(f"Plugin '{plugin_name}' did not self-register; adding discovered data.")
                     self.plugins[plugin_name] = plugin_data

                # Check if an instance *is* now present in the (potentially updated) record
                if plugin_name in self.plugins and ('instance' not in self.plugins[plugin_name] or self.plugins[plugin_name].get('instance') is None):
                     # This is the warning that replaces the previous hard error
                     self.logger.warning(f"Plugin '{plugin_name}': Instance was not explicitly set in manager's records by 'initialize'.")
                elif plugin_name in self.plugins:
                     self.logger.info(f"Plugin '{plugin_name}': Instance found/set in manager's records.")

                if plugin_name != "multiplayer":
                    self.enabled_plugins.add(plugin_name)
                
                return True
            else:
                self.logger.error(f"Plugin '{plugin_name}' 'initialize' function returned False or failed.")
                return False

        except Exception as e:
            self.logger.error(f"Error during initialization of plugin '{plugin_name}': {str(e)}", exc_info=True)
            return False

    def load_all_plugins(self) -> Dict[str, bool]:
        """
        Load all discovered plugins.
        """
        self.logger.info("Loading all discovered plugins...")
        self.plugins.clear()
        self.enabled_plugins.clear()
        
        self._discovered_plugins = self.discover_plugins() 
        if not self._discovered_plugins:
            return {}
            
        results = {}
        plugins_to_load_ordered = list(self._discovered_plugins.keys())

        for plugin_name_key in plugins_to_load_ordered:
            result = self.load_plugin(plugin_name_key) 
            results[plugin_name_key] = result

        self.logger.info(f"Finished loading all plugins. Results: {results}")
        self.logger.info(f"Currently loaded plugins in self.plugins: {list(self.plugins.keys())}")
        self.logger.info(f"Currently enabled plugins: {list(self.enabled_plugins)}")
        
        return results
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin by name."""
        plugin_name_lower = plugin_name.lower()
        if plugin_name_lower not in self.plugins:
            self.logger.warning(f"Plugin '{plugin_name_lower}' not found for unloading.")
            return False

        plugin_data = self.plugins.get(plugin_name_lower)
        if plugin_data:
            instance = plugin_data.get('instance')
            if instance and hasattr(instance, 'shutdown'):
                try:
                    instance.shutdown()
                    self.logger.info(f"Plugin '{plugin_name_lower}' shutdown method called.")
                except Exception as e:
                    self.logger.error(f"Error during plugin '{plugin_name_lower}' shutdown: {e}", exc_info=True)
        
        if plugin_name_lower in self.enabled_plugins:
            self.enabled_plugins.remove(plugin_name_lower)
            self.logger.info(f"Plugin '{plugin_name_lower}' disabled.")
        
        for hook_name in list(self.hooks.keys()):
            self.hooks[hook_name] = [
                sub for sub in self.hooks[hook_name] if sub['plugin'].lower() != plugin_name_lower
            ]

        del self.plugins[plugin_name_lower]
        self.logger.info(f"Plugin '{plugin_name_lower}' unloaded successfully.")
        return True

    def unload_all_plugins(self) -> None:
        """Unload all active plugins."""
        self.logger.info("Unloading all plugins...")
        for plugin_name_key in list(self.plugins.keys()):
            self.unload_plugin(plugin_name_key)
        self.logger.info("All plugins have been unloaded.")

    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a loaded plugin."""
        plugin_name_lower = plugin_name.lower()
        
        if plugin_name_lower not in self.plugins:
            self.logger.error(f"Cannot enable plugin '{plugin_name_lower}': not loaded.")
            return False
        
        if plugin_name_lower in self.enabled_plugins:
            self.logger.info(f"Plugin '{plugin_name_lower}' is already enabled.")
            return True
            
        plugin_data = self.plugins[plugin_name_lower]
        plugin_instance = plugin_data.get('instance')
        
        if plugin_instance and hasattr(plugin_instance, 'enable'):
            try:
                enable_success = plugin_instance.enable()
                if not enable_success:
                    self.logger.error(f"Plugin '{plugin_name_lower}'.enable() returned False.")
                    return False
                self.logger.info(f"Plugin '{plugin_name_lower}'.enable() method called successfully.")
            except Exception as e:
                self.logger.error(f"Error calling .enable() on plugin '{plugin_name_lower}': {e}", exc_info=True)
                return False
        elif plugin_instance is None:
             self.logger.warning(f"Plugin '{plugin_name_lower}' has no instance, cannot call .enable(). Enabling in manager only.")
        
        self.enabled_plugins.add(plugin_name_lower)
        self.logger.info(f"Plugin '{plugin_name_lower}' enabled.")
        return True

    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable an enabled plugin."""
        plugin_name_lower = plugin_name.lower()
        
        if plugin_name_lower not in self.enabled_plugins:
            self.logger.warning(f"Plugin '{plugin_name_lower}' is not currently enabled.")
            return False
            
        plugin_data = self.plugins.get(plugin_name_lower)
        if plugin_data:
            plugin_instance = plugin_data.get('instance')
            if plugin_instance and hasattr(plugin_instance, 'disable'):
                try:
                    plugin_instance.disable()
                    self.logger.info(f"Plugin '{plugin_name_lower}'.disable() method called.")
                except Exception as e:
                    self.logger.error(f"Error calling .disable() on plugin '{plugin_name_lower}': {e}", exc_info=True)
        
        self.enabled_plugins.remove(plugin_name_lower)
        self.logger.info(f"Plugin '{plugin_name_lower}' disabled.")
        return True
    
    def get_plugin_info(self, plugin_name: str) -> Dict | None:
        """Get information about a loaded plugin."""
        plugin_name_lower = plugin_name.lower()
        return self.plugins.get(plugin_name_lower)
    
    def get_loaded_plugins(self) -> List[str]:
        """Get original names of all loaded plugins."""
        return [data.get('original_name', key) for key, data in self.plugins.items()]
    
    def get_enabled_plugins(self) -> List[str]:
        """Get original names of all enabled plugins."""
        enabled_original_names = []
        for name_lower in self.enabled_plugins:
            if name_lower in self.plugins:
                enabled_original_names.append(self.plugins[name_lower].get('original_name', name_lower))
            else:
                enabled_original_names.append(name_lower) 
        return enabled_original_names

    def check_dependencies(self, plugin_name_to_check: str) -> bool:
        """Check if dependencies for a plugin are met."""
        plugin_name_to_check = plugin_name_to_check.lower()
        if self._discovered_plugins is None or plugin_name_to_check not in self._discovered_plugins:
            self.logger.error(f"Plugin '{plugin_name_to_check}' not found for dependency check.")
            return False
            
        plugin_data = self._discovered_plugins[plugin_name_to_check]
        required_plugin_keys = plugin_data.get("requires", []) 
        
        if not required_plugin_keys:
            return True
            
        for required_key in required_plugin_keys:
            if required_key not in self.plugins:
                self.logger.error(f"Plugin '{plugin_name_to_check}' requires '{required_key}' which is not loaded.")
                return False
        return True

    def set_tamagotchi_logic(self, tamagotchi_logic_instance):
        """Allows setting a reference to the main TamagotchiLogic instance."""
        setattr(self, 'tamagotchi_logic', tamagotchi_logic_instance)
        self.logger.info("TamagotchiLogic instance has been linked to PluginManager.")