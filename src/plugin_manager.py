import os
import importlib.util
import inspect
import logging
import sys
from typing import Dict, List, Callable, Any

# ANSI escape codes for console colours
class ANSI:
    BLUE = "\x1b[34m"
    RED = "\x1b[31m"
    YELLOW = "\x1b[33m"
    CYAN = "\x1b[36m"
    RESET = "\x1b[0m"

class ColoredFormatter(logging.Formatter):
    """
    A custom logging formatter that colors only the 'LEVEL:NAME:' prefix
    for messages from the 'PluginManager' logger.
    """
    
    COLORS = {
        logging.DEBUG: ANSI.CYAN,
        logging.INFO: ANSI.CYAN,
        logging.WARNING: ANSI.YELLOW,
        logging.ERROR: ANSI.RED,
        logging.CRITICAL: ANSI.RED,
    }

    def __init__(self, fmt="%(levelname)s:%(name)s:%(message)s", datefmt=None, style='%'):
        # We call super().__init__ but will override format completely
        super().__init__(fmt, datefmt, style)

    def format(self, record):
        # Check if the log is from our target logger
        if record.name == "PluginManager":
            # Get the appropriate color for the log level
            color = self.COLORS.get(record.levelno, ANSI.RESET) # Default to RESET if no colour found
            
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
            
            # Construct the final coloured log string
            # Only the prefix is coloured; the message remains default (white/black) until RESET
            return f"{color}{prefix}{ANSI.RESET} {message}"
        else:
            # For any other logger, use the default formatter behavior (uncoloured)
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
        self.auto_load_blacklist: set[str] = {"multiplayer"}  ### FIX: Stop Multiplayer plugin freaking out at startup  ** ESSENTIAL **
                                                                ## This is actually important. All plugins start austomatically unless
                                                                ## specifically blacklisted here... DO NOT LET MULTIPLAYER AUTO START!!. 
        
        # Custom neuron handlers registered by plugins
        # Maps neuron_name -> {'handler': callable, 'plugin': plugin_name, 'metadata': dict}
        self._neuron_handlers: Dict[str, Dict] = {}
        
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
        self.register_hook("on_brain_state_update")
        self.register_hook("on_neurogenesis")
        self.register_hook("on_memory_created")
        self.register_hook("on_memory_to_long_term")
        
        # UI hooks
        self.register_hook("on_menu_creation")
        self.register_hook("on_message_display")
        
        # Custom menu action hooks
        self.register_hook("register_menu_actions")
        
        # Custom neuron hooks - allows plugins to register input neuron handlers
        self.register_hook("register_neuron_handlers")
        
        # Neuron output hooks - triggered when neurons fire above threshold
        # Movement behaviors
        self.register_hook("neuron_output_flee")
        self.register_hook("neuron_output_seek_food")
        self.register_hook("neuron_output_seek_plant")
        self.register_hook("neuron_output_approach_rock")
        self.register_hook("neuron_output_wander")
        
        # Action behaviors
        self.register_hook("neuron_output_throw_rock")
        self.register_hook("neuron_output_pick_up_rock")
        self.register_hook("neuron_output_ink_cloud")
        self.register_hook("neuron_output_eat")
        self.register_hook("neuron_output_change_color")
        
        # State changes
        self.register_hook("neuron_output_sleep")
        self.register_hook("neuron_output_wake")
        self.register_hook("neuron_output_startle")
        self.register_hook("neuron_output_calm")
        
        # Stat modifications
        self.register_hook("neuron_output_boost_happiness")
        self.register_hook("neuron_output_boost_curiosity")
        self.register_hook("neuron_output_reduce_anxiety")
        
        # Custom/plugin-defined outputs
        self.register_hook("neuron_output_custom")



    def register_all_sensors(self, tamagotchi_logic):
        """
        Register all available sensors (built-in and plugin) with the plugin manager.
        
        This creates a unified registry by registering built-in sensors that normally 
        live in BrainNeuronHooks, making them discoverable through the plugin manager's API.
        
        Args:
            tamagotchi_logic: TamagotchiLogic instance needed for sensor handlers
            
        Returns:
            int: Number of built-in sensors registered
        """
        # Lazy imports to avoid circular dependencies
        from .designer_sensor_discovery import get_builtin_sensors
        from .brain_neuron_hooks import BrainNeuronHooks
        
        brain_hooks = BrainNeuronHooks(tamagotchi_logic)
        builtin_sensors = get_builtin_sensors()
        
        count = 0
        for name, info in builtin_sensors.items():
            # Skip if already registered by a plugin
            if name in self._neuron_handlers:
                existing = self._neuron_handlers[name]
                if existing.get('plugin') != 'system':
                    self.logger.debug(
                        f"Skipping built-in sensor '{name}' - "
                        f"overridden by plugin '{existing.get('plugin')}'"
                    )
                continue
            
            # Register if handler exists
            if name in brain_hooks.handlers:
                handler = brain_hooks.handlers[name]
                
                metadata = {
                    'description': info.get('description', ''),
                    'is_binary': info.get('is_binary', False),
                    'category': info.get('category', 'built-in'),
                    'default_connections': info.get('default_connections', []),
                    'source': 'built-in'
                }
                
                self.register_neuron_handler(
                    neuron_name=name,
                    handler=handler,
                    plugin_name='system',
                    metadata=metadata
                )
                count += 1
        
        if count > 0:
            self.logger.info(f"Registered {count} built-in sensors with PluginManager")
        return count
    
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
                #self.logger.info(f"Discovered plugin:   {metadata['original_name']} v{metadata['version']} (key: {plugin_name})")
                
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

        #self.logger.info(f"Attempting to load plugin '{original_plugin_name_display}' (key: '{plugin_name}')")
        #self.logger.info(f"Plugin '{plugin_name}': Module '{module.__name__}' found.")

        required_plugins = plugin_data.get("requires", [])
        if required_plugins:
            missing_plugins = []
            for required_name_lower in required_plugins:
                if required_name_lower not in self.plugins:
                    missing_plugins.append(required_name_lower)
            if missing_plugins:
                #self.logger.error(f"Plugin '{plugin_name}' requires missing plugin(s): {', '.join(missing_plugins)}.")
                #self.logger.error(f"Plugin '{plugin_name}': Dependency check failed.")
                return False
        #self.logger.info(f"Plugin '{plugin_name}': Dependencies satisfied.")

        if not hasattr(module, "initialize"):
            self.logger.error(f"Plugin '{plugin_name}' has no 'initialize' function.")
            return False
        #self.logger.info(f"Plugin '{plugin_name}': Found 'initialize' function. Attempting to call.")

        try:
            initialize_func = getattr(module, "initialize")
            success = initialize_func(self)  # Call initialize

            if success:
                #self.logger.info(f"Plugin '{plugin_name}': 'initialize' function executed successfully.")
                
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
                     self.logger.info(f"Success")

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
        Load all discovered plugins except those in auto_load_blacklist.
        """
        self.logger.info("  Discovering plugins...")
        self.plugins.clear()
        self.enabled_plugins.clear()
        
        self._discovered_plugins = self.discover_plugins() 
        if not self._discovered_plugins:
            return {}
            
        results = {}
        # Skip plugins in auto_load_blacklist
        plugins_to_load_ordered = [
            name for name in self._discovered_plugins.keys() 
            if name not in self.auto_load_blacklist
        ]

        for plugin_name_key in plugins_to_load_ordered:
            result = self.load_plugin(plugin_name_key) 
            results[plugin_name_key] = result

        # Log skipped plugins
        blacklisted_found = [name for name in self._discovered_plugins.keys() if name in self.auto_load_blacklist]
        if blacklisted_found:
            self.logger.info(f"Skipped auto-loading of {blacklisted_found}")
        
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

    def reload_all_plugins(self) -> Dict[str, bool]:
        """
        Reload all plugins by unloading and then loading them again.
        This is useful when starting a new game to ensure plugins start fresh.
        
        Returns:
            Dict[str, bool]: Dictionary mapping plugin names to their load success status
        """
        self.logger.info("Reloading all plugins...")
        
        # First unload all plugins
        self.unload_all_plugins()
        
        # Then load them all again
        results = self.load_all_plugins()
        
        self.logger.info("All plugins have been reloaded.")
        return results

    def enable_plugin(self, plugin_key: str) -> bool:
        plugin_key_lower = plugin_key.lower()  # Normalize to lowercase

        if plugin_key_lower in self.enabled_plugins:
            self.logger.info(f"Plugin '{plugin_key_lower}' is already enabled.")
            return True

        # NEW: If plugin is not loaded but is discovered, load it first
        if plugin_key_lower not in self.plugins:
            if self._discovered_plugins is None:
                self.logger.info("Plugin discovery not yet run. Discovering plugins...")
                self.discover_plugins()
            
            if plugin_key_lower in self._discovered_plugins:
                self.logger.info(f"Plugin '{plugin_key_lower}' is discovered but not loaded. Loading it first...")
                if not self.load_plugin(plugin_key_lower):
                    self.logger.error(f"Failed to load plugin '{plugin_key_lower}' before enabling.")
                    return False
            else:
                self.logger.error(f"Plugin '{plugin_key_lower}' not found in discovered plugins.")
                return False

        # Now proceed with the original enabling logic...
        plugin_data = self.plugins.get(plugin_key_lower)
        if not plugin_data or 'instance' not in plugin_data:
            self.logger.error(f"ERROR:PluginManager: Plugin '{plugin_key_lower}' not found or has no instance for enabling.")
            return False

        instance = plugin_data['instance']
        if not instance:
            self.logger.error(f"ERROR:PluginManager: Instance for plugin '{plugin_key_lower}' is None.")
            return False

        # --- Call setup() if it hasn't been run ---
        if hasattr(instance, 'setup') and callable(instance.setup):
            if not plugin_data.get('is_setup', False): 
                try:
                    self.logger.info(f"INFO:PluginManager: Calling setup() for plugin '{plugin_key_lower}'.")
                    tamagotchi_logic_ref = getattr(self, 'tamagotchi_logic', None)
                    if tamagotchi_logic_ref:
                        instance.setup(self, tamagotchi_logic_ref)
                    else:
                        self.logger.warning(f"WARNING:PluginManager: tamagotchi_logic not available in PluginManager when setting up '{plugin_key_lower}'. Passing None.")
                        instance.setup(self, None)

                    plugin_data['is_setup'] = True
                    self.logger.info(f"INFO:PluginManager: setup() for plugin '{plugin_key_lower}' completed.")
                except Exception as e:
                    self.logger.error(f"ERROR:PluginManager: Exception during setup of plugin '{plugin_key_lower}': {e}", exc_info=True)
                    return False
            else:
                self.logger.info(f"INFO:PluginManager: Plugin '{plugin_key_lower}' already marked as setup by PluginManager. Skipping setup() call.")

        # --- Now, call the plugin's own enable method ---
        if hasattr(instance, 'enable') and callable(instance.enable):
            try:
                self.logger.info(f"INFO:PluginManager: Calling enable() method on plugin instance '{plugin_key_lower}'.")
                if instance.enable():
                    self.enabled_plugins.add(plugin_key_lower)
                    self.logger.info(f"INFO:PluginManager: Plugin '{plugin_key_lower}' successfully enabled and added to enabled set.")
                    self.trigger_hook("on_plugin_enabled", plugin_key=plugin_key_lower)
                    return True
                else:
                    self.logger.error(f"ERROR:PluginManager: Plugin '{plugin_key_lower}' enable() method returned False.")
                    return False
            except Exception as e:
                self.logger.error(f"ERROR:PluginManager: Exception during enable() of plugin '{plugin_key_lower}': {e}", exc_info=True)
                return False
        else:
            # If the plugin has no specific enable method, just mark it as enabled in the manager
            self.enabled_plugins.add(plugin_key_lower)
            self.logger.info(f"INFO:PluginManager: Plugin '{plugin_key_lower}' has no custom enable() method, marked as enabled in manager.")
            self.trigger_hook("on_plugin_enabled", plugin_key=plugin_key_lower)
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

    # =========================================================================
    # CUSTOM NEURON HANDLER REGISTRATION
    # =========================================================================
    
    def register_neuron_handler(
        self, 
        neuron_name: str, 
        handler: Callable, 
        plugin_name: str,
        metadata: Dict = None
    ) -> bool:
        """
        Register a custom handler for a brain input neuron.
        
        This allows plugins to add new sensor neurons that can be wired into
        the squid's neural network via the brain designer.
        
        Args:
            neuron_name: Unique name for the neuron (e.g., 'music_beat_detector')
            handler: A callable that returns a float (0-100) activation value.
                     Should take no arguments and return the current activation.
            plugin_name: Name of the plugin registering this handler
            metadata: Optional dict with additional info:
                - 'description': Human-readable description
                - 'is_binary': True if neuron only outputs 0 or 100
                - 'category': Category for grouping (e.g., 'environmental', 'social')
                - 'default_connections': List of neurons to auto-connect to
                
        Returns:
            True if registered successfully, False if neuron name already exists
            
        Example:
            def my_beat_handler():
                # Return 100 when beat detected, 0 otherwise
                return 100.0 if detect_beat() else 0.0
            
            plugin_manager.register_neuron_handler(
                'music_beat', 
                my_beat_handler, 
                'MusicPlugin',
                metadata={
                    'description': 'Detects music beats',
                    'is_binary': True,
                    'category': 'audio'
                }
            )
        """
        plugin_name_lower = plugin_name.lower()
        
        if neuron_name in self._neuron_handlers:
            existing = self._neuron_handlers[neuron_name]
            self.logger.warning(
                f"Neuron handler '{neuron_name}' already registered by "
                f"'{existing.get('plugin', 'unknown')}'. Overwriting with '{plugin_name}'."
            )
        
        self._neuron_handlers[neuron_name] = {
            'handler': handler,
            'plugin': plugin_name_lower,
            'metadata': metadata or {}
        }
        
        self.logger.info(f"Registered neuron handler: '{neuron_name}' from plugin '{plugin_name}'")
        return True
    
    def unregister_neuron_handler(self, neuron_name: str, plugin_name: str) -> bool:
        """
        Unregister a neuron handler.
        
        Args:
            neuron_name: Name of the neuron to unregister
            plugin_name: Name of the plugin that registered it (for verification)
            
        Returns:
            True if unregistered successfully, False otherwise
        """
        plugin_name_lower = plugin_name.lower()
        
        if neuron_name not in self._neuron_handlers:
            self.logger.warning(f"Cannot unregister '{neuron_name}': not found")
            return False
        
        existing = self._neuron_handlers[neuron_name]
        if existing.get('plugin') != plugin_name_lower:
            self.logger.warning(
                f"Cannot unregister '{neuron_name}': registered by "
                f"'{existing.get('plugin')}', not '{plugin_name}'"
            )
            return False
        
        del self._neuron_handlers[neuron_name]
        self.logger.info(f"Unregistered neuron handler: '{neuron_name}'")
        return True
    
    def get_neuron_handlers(self) -> Dict[str, Callable]:
        """
        Get all registered neuron handlers as a dict of name -> callable.
        
        This is called by BrainNeuronHooks to merge plugin handlers with
        built-in handlers.
        
        Returns:
            Dict mapping neuron names to their handler callables
        """
        return {
            name: data['handler'] 
            for name, data in self._neuron_handlers.items()
        }
    
    def get_neuron_handler_info(self, neuron_name: str) -> Dict | None:
        """
        Get full info about a registered neuron handler.
        
        Returns:
            Dict with 'handler', 'plugin', and 'metadata' keys, or None if not found
        """
        return self._neuron_handlers.get(neuron_name)
    
    def get_all_neuron_handler_info(self) -> Dict[str, Dict]:
        """
        Get info about all registered neuron handlers.
        
        Returns:
            Dict mapping neuron names to their full registration info
        """
        return dict(self._neuron_handlers)
    
    def get_plugin_neuron_handlers(self, plugin_name: str) -> List[str]:
        """
        Get list of neuron handlers registered by a specific plugin.
        
        Args:
            plugin_name: Name of the plugin
            
        Returns:
            List of neuron names registered by that plugin
        """
        plugin_name_lower = plugin_name.lower()
        return [
            name for name, data in self._neuron_handlers.items()
            if data.get('plugin') == plugin_name_lower
        ]
