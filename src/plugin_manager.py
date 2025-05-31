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


    def _initialize_hooks(self):
        """Initialize standard hooks that plugins can register for"""
        # Lifecycle hooks
        self.register_hook("on_startup")
        self.register_hook("on_shutdown")
        self.register_hook("on_new_game")
        self.register_hook("on_save_game")
        self.register_hook("on_load_game")
        self.register_hook("on_plugin_enabled")
        
        # Simulation hooks
        self.register_hook("pre_update")
        self.register_hook("post_update")
        self.register_hook("on_speed_change")
        self.register_hook("on_update")
        
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
        self.register_hook("on_spawn_food")
        self.register_hook("on_spawn_poop")
        
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
        Plugins loaded this way will NOT be enabled by default. They must be explicitly enabled.
        """
        plugin_name = plugin_name.lower()

        if plugin_name in self.plugins:
            # This check is if the plugin's metadata (including potentially an instance) is already in self.plugins.
            # It doesn't mean it's enabled.
            self.logger.info(f"Plugin '{plugin_name}' metadata already present. Checking if it needs full loading/initialization or just enabling.")
            # If it's already fully loaded and has an instance, this method might not need to re-initialize.
            # However, the current flow re-initializes if called again.
            # For simplicity in this revision, we'll proceed as if it might need initialization if not properly instanced.
            # A more robust system might differentiate between "known plugin metadata" and "fully loaded and instanced plugin".

        if self._discovered_plugins is None:
            self.logger.error("Plugin discovery must be run before loading.")
            # Attempt to discover plugins if not done, though ideally discovery is a separate explicit step.
            self._discovered_plugins = self.discover_plugins()

        if plugin_name not in self._discovered_plugins:
            self.logger.error(f"Plugin '{plugin_name}' not found in discovered plugins.")
            return False

        plugin_data_discovered = self._discovered_plugins[plugin_name] # Use a different name to avoid confusion
        module = plugin_data_discovered["module"]
        original_plugin_name_display = plugin_data_discovered.get("original_name", plugin_name) # For logging

        self.logger.info(f"Attempting to load plugin '{original_plugin_name_display}' (key: '{plugin_name}')")
        # self.logger.info(f"Plugin '{plugin_name}': Module '{module.__name__}' found.") # This log might be redundant with the one above

        required_plugins = plugin_data_discovered.get("requires", [])
        if required_plugins:
            missing_plugins = []
            for required_name_lower in required_plugins:
                # Check if the required plugin's metadata and instance are loaded
                if required_name_lower not in self.plugins or not self.plugins[required_name_lower].get('instance'):
                    missing_plugins.append(required_name_lower)
            if missing_plugins:
                self.logger.error(f"Plugin '{original_plugin_name_display}' requires missing or not fully loaded plugin(s): {', '.join(missing_plugins)}.")
                self.logger.error(f"Plugin '{original_plugin_name_display}': Dependency check failed.")
                return False
        self.logger.info(f"Plugin '{original_plugin_name_display}': Dependencies satisfied.")

        if not hasattr(module, "initialize"):
            self.logger.error(f"Plugin '{original_plugin_name_display}' has no 'initialize' function.")
            return False
        self.logger.info(f"Plugin '{original_plugin_name_display}': Found 'initialize' function. Attempting to call.")

        try:
            initialize_func = getattr(module, "initialize")
            # The initialize function is expected to populate self.plugins[plugin_name]
            # with the instance and other metadata like 'is_enabled_by_default'.
            success = initialize_func(self) # `self` here is the PluginManager instance

            if success:
                self.logger.info(f"Plugin '{original_plugin_name_display}': 'initialize' function executed successfully.")
                
                # Verify that the plugin's initialize function registered the plugin's details in self.plugins
                if plugin_name not in self.plugins:
                     # This case should ideally not happen if initialize is well-behaved and populates self.plugins[plugin_name]
                     self.logger.warning(f"Plugin '{original_plugin_name_display}' did not fully register itself in self.plugins via its initialize function. Using discovered data as fallback.")
                     # This line below is problematic if initialize is meant to be the sole source of self.plugins entry
                     # self.plugins[plugin_name] = plugin_data_discovered # Fallback, might lack instance or correct 'is_enabled_by_default'
                     # Instead, rely on initialize to do its job. If it doesn't, it's an error in the plugin's initialize.
                     self.logger.error(f"CRITICAL: Plugin '{original_plugin_name_display}' initialize() ran but did not populate self.plugins entry.")
                     return False


                # Check if an instance is now present in the plugin's record within self.plugins
                current_plugin_record = self.plugins.get(plugin_name, {})
                if 'instance' not in current_plugin_record or current_plugin_record.get('instance') is None:
                     self.logger.warning(f"Plugin '{original_plugin_name_display}': Instance was not set in PluginManager's records by its 'initialize' function.")
                     # This might be okay if initialize is only for metadata, but typically it creates the instance.
                else:
                     self.logger.info(f"Plugin '{original_plugin_name_display}': Instance found/set in PluginManager's records.")

                # Plugins are loaded but NOT automatically enabled.
                
                #self.logger.info(f"Plugin '{original_plugin_name_display}' (key: {plugin_name}) is loaded. It must be enabled manually if needed.")
                
                return True
            else:
                self.logger.error(f"Plugin '{original_plugin_name_display}' 'initialize' function returned False or indicated failure.")
                # Clean up if initialize failed but partially registered?
                if plugin_name in self.plugins and (not self.plugins[plugin_name].get('instance') or not success): # if success is false, even if entry exists
                    self.logger.debug(f"Removing partially registered data for failed plugin '{plugin_name}'.")
                    del self.plugins[plugin_name]
                return False

        except Exception as e:
            self.logger.error(f"Error during initialization of plugin '{original_plugin_name_display}': {str(e)}", exc_info=True)
            # Clean up if initialize failed due to exception
            if plugin_name in self.plugins and not self.plugins[plugin_name].get('instance'): # if entry exists but no instance
                self.logger.debug(f"Removing partially registered data for exception in plugin '{plugin_name}'.")
                del self.plugins[plugin_name]
            return False

    def load_all_plugins(self) -> Dict[str, bool]:
        """
        Load all discovered plugins. (This will call initialize() on each plugin module)
        """
        self.logger.info("Loading all discovered plugins (calling initialize() on each)...")
        # self.plugins.clear() # Clearing here would lose any plugins already loaded individually.
        # self.enabled_plugins.clear() # Usually, enabling is a separate step.
        
        if self._discovered_plugins is None: # Ensure discovery has happened
            self.logger.info("No plugins discovered yet. Running discovery first.")
            self.discover_plugins() 
        
        if not self._discovered_plugins:
            self.logger.info("No plugins found by discovery to load.")
            return {}
            
        results = {}
        # Create a list of keys to avoid issues if self.plugins is modified during iteration (though load_plugin modifies self.plugins)
        plugins_to_load_ordered = list(self._discovered_plugins.keys()) 

        for plugin_name_key in plugins_to_load_ordered:
            if plugin_name_key not in self.plugins: # Only load if not already loaded
                result = self.load_plugin(plugin_name_key) 
                results[plugin_name_key] = result
            else:
                self.logger.info(f"Plugin '{plugin_name_key}' already in self.plugins, skipping re-load in load_all_plugins.")
                results[plugin_name_key] = True # Consider it successfully "loaded" in this context

        self.logger.info(f"Finished loading all plugins. Results: {results}")
        self.logger.info(f"Currently loaded plugins in self.plugins: {list(self.plugins.keys())}")
        # self.logger.info(f"Currently enabled plugins: {list(self.enabled_plugins)}") # Enabling is separate
        
        return results
    
    def unload_plugin(self, plugin_name: str) -> bool:
        """Unload a plugin by name."""
        plugin_name_lower = plugin_name.lower()
        if plugin_name_lower not in self.plugins:
            self.logger.warning(f"Plugin '{plugin_name_lower}' not found for unloading.")
            return False

        # Disable it first if it's enabled
        if plugin_name_lower in self.enabled_plugins:
            self.disable_plugin(plugin_name_lower) # This will call the plugin's disable if it exists
        
        plugin_data = self.plugins.get(plugin_name_lower)
        if plugin_data:
            instance = plugin_data.get('instance')
            # A more comprehensive shutdown might involve a 'cleanup' or 'shutdown' method in the plugin
            if instance and hasattr(instance, 'cleanup'): # Assuming 'cleanup' is more thorough than 'disable'
                try:
                    self.logger.info(f"Calling cleanup() on plugin '{plugin_name_lower}' instance before unloading.")
                    instance.cleanup()
                except Exception as e:
                    self.logger.error(f"Error during plugin '{plugin_name_lower}' cleanup: {e}", exc_info=True)
            elif instance and hasattr(instance, 'shutdown'): # Fallback to shutdown if cleanup not present
                try:
                    self.logger.info(f"Calling shutdown() on plugin '{plugin_name_lower}' instance before unloading.")
                    instance.shutdown()
                except Exception as e:
                    self.logger.error(f"Error during plugin '{plugin_name_lower}' shutdown: {e}", exc_info=True)

        # Unsubscribe from all hooks
        for hook_name in list(self.hooks.keys()): # Iterate over a copy of keys
            # List comprehension to rebuild the subscriber list without the target plugin
            self.hooks[hook_name] = [
                sub for sub in self.hooks[hook_name] if sub['plugin'].lower() != plugin_name_lower
            ]

        # Remove from PluginManager's tracking
        if plugin_name_lower in self.plugins:
            del self.plugins[plugin_name_lower]
        
        # It should already be removed from enabled_plugins by disable_plugin call
        if plugin_name_lower in self.enabled_plugins: 
             self.enabled_plugins.remove(plugin_name_lower)


        # Remove from discovered_plugins as well if we want to fully "forget" it until next discovery
        # Or keep it in _discovered_plugins if we want to allow re-loading without re-discovery.
        # For now, let's assume _discovered_plugins persists until a new explicit discovery.
        # if self._discovered_plugins and plugin_name_lower in self._discovered_plugins:
        #     del self._discovered_plugins[plugin_name_lower]

        self.logger.info(f"Plugin '{plugin_name_lower}' unloaded successfully.")
        return True

    def unload_all_plugins(self) -> None:
        """Unload all active plugins."""
        self.logger.info("Unloading all plugins...")
        # Iterate over a copy of the keys, as unload_plugin modifies self.plugins
        for plugin_name_key in list(self.plugins.keys()): 
            self.unload_plugin(plugin_name_key)
        self.logger.info("All plugins have been unloaded.")


    def enable_plugin(self, plugin_key: str) -> bool:
        plugin_key_lower = plugin_key.lower() # Normalize to lowercase

        if plugin_key_lower in self.enabled_plugins:
            self.logger.info(f"INFO:PluginManager: Plugin '{plugin_key_lower}' is already enabled.")
            return True

        # Step 1: Ensure plugin is discovered
        if self._discovered_plugins is None:
            self.logger.info("INFO:PluginManager: Plugins not yet discovered. Running discovery first for enable_plugin.")
            self.discover_plugins()

        if plugin_key_lower not in self._discovered_plugins:
            self.logger.error(f"ERROR:PluginManager: Plugin '{plugin_key_lower}' not found in discovered plugins. Cannot enable.")
            return False

        # Step 2: Ensure plugin is loaded (its initialize() has run and an instance exists in self.plugins)
        if plugin_key_lower not in self.plugins:
            self.logger.info(f"INFO:PluginManager: Plugin '{plugin_key_lower}' is not loaded. Loading now as part of enable process...")
            if not self.load_plugin(plugin_key_lower): # load_plugin calls the plugin's initialize()
                self.logger.error(f"ERROR:PluginManager: Failed to load plugin '{plugin_key_lower}' during enable process.")
                return False
        
        plugin_data = self.plugins.get(plugin_key_lower)
        if not plugin_data or 'instance' not in plugin_data or plugin_data['instance'] is None:
            self.logger.error(f"ERROR:PluginManager: Plugin '{plugin_key_lower}' failed to load correctly (instance or metadata missing after load_plugin).")
            return False

        instance = plugin_data['instance']

        # Step 3: Call plugin's setup() method if it hasn't been run yet for this loaded instance.
        # The 'is_setup' flag in plugin_data is set by the plugin's initialize() (e.g., to False)
        # and should only be set to True by this PluginManager after setup() succeeds.
        
        # Check plugin's internal 'is_setup' as a pre-condition if it helps avoid re-setup issues.
        plugin_instance_reports_setup = hasattr(instance, 'is_setup') and getattr(instance, 'is_setup')
        
        if plugin_instance_reports_setup and not plugin_data.get('is_setup', False):
            self.logger.info(f"INFO:PluginManager: Plugin '{plugin_key_lower}' instance reports internal 'is_setup' is True. Updating PluginManager's record.")
            plugin_data['is_setup'] = True # Sync PluginManager's flag based on instance's state

        if hasattr(instance, 'setup') and callable(instance.setup):
            if not plugin_data.get('is_setup', False):
                try:
                    self.logger.info(f"INFO:PluginManager: Calling setup() for plugin '{plugin_key_lower}'.")
                    tamagotchi_logic_ref = getattr(self, 'tamagotchi_logic', None)
                    instance.setup(self, tamagotchi_logic_ref) # Pass PluginManager (self) and tamagotchi_logic
                    
                    plugin_data['is_setup'] = True # Mark that setup has been run in PluginManager's records
                    if hasattr(instance, 'is_setup'): # Also ensure instance knows it's setup
                         setattr(instance, 'is_setup', True)
                    self.logger.info(f"INFO:PluginManager: setup() for plugin '{plugin_key_lower}' completed and marked in PluginManager.")
                except Exception as e:
                    self.logger.error(f"ERROR:PluginManager: Exception during setup of plugin '{plugin_key_lower}': {e}", exc_info=True)
                    return False 
            else:
                self.logger.info(f"INFO:PluginManager: Plugin '{plugin_key_lower}' already marked as setup by PluginManager or instance. Skipping setup() call.")
        
        # Step 4: Call the plugin's own enable() method
        if hasattr(instance, 'enable') and callable(instance.enable):
            try:
                self.logger.info(f"INFO:PluginManager: Calling plugin's own enable() method for '{plugin_key_lower}'.")
                if instance.enable(): 
                    self.enabled_plugins.add(plugin_key_lower)
                    self.logger.info(f"INFO:PluginManager: Plugin '{plugin_key_lower}' successfully enabled and added to enabled set.")
                    self.trigger_hook("on_plugin_enabled", plugin_key=plugin_key_lower)
                    return True
                else:
                    self.logger.error(f"ERROR:PluginManager: Plugin '{plugin_key_lower}' enable() method returned False.")
                    # If plugin's own enable fails, it's not added to enabled_plugins.
                    # The setup state remains True.
                    return False
            except AttributeError as ae: # Catch if 'is_setup' was missing inside plugin's enable
                self.logger.error(f"ERROR:PluginManager: AttributeError during enable() of plugin '{plugin_key_lower}': {ae}. This might indicate an issue within the plugin's enable logic (e.g., relying on an uninitialized attribute).", exc_info=True)
                return False
            except Exception as e:
                self.logger.error(f"ERROR:PluginManager: Exception during enable() of plugin '{plugin_key_lower}': {e}", exc_info=True)
                return False
        else:
            # If the plugin has no specific enable method, but loading and setup (if applicable) were successful,
            # simply add it to the set of enabled plugins.
            self.enabled_plugins.add(plugin_key_lower)
            self.logger.info(f"INFO:PluginManager: Plugin '{plugin_key_lower}' has no custom enable() method; marked as enabled in manager after load/setup.")
            self.trigger_hook("on_plugin_enabled", plugin_key=plugin_key_lower)
            return True

    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable an enabled plugin."""
        plugin_name_lower = plugin_name.lower()
        
        if plugin_name_lower not in self.enabled_plugins:
            self.logger.warning(f"Plugin '{plugin_name_lower}' is not currently enabled.")
            return False # Or True, if "not enabled" means "successfully disabled state"
            
        plugin_data = self.plugins.get(plugin_name_lower)
        if plugin_data:
            plugin_instance = plugin_data.get('instance')
            if plugin_instance and hasattr(plugin_instance, 'disable'):
                try:
                    self.logger.info(f"INFO:PluginManager: Calling plugin's own disable() method for '{plugin_name_lower}'.")
                    plugin_instance.disable() # Call the plugin's own disable method
                except Exception as e:
                    self.logger.error(f"ERROR:PluginManager: Error calling .disable() on plugin '{plugin_name_lower}': {e}", exc_info=True)
                    # Even if plugin's disable fails, proceed to mark as disabled in manager.
        
        self.enabled_plugins.remove(plugin_name_lower)
        self.logger.info(f"INFO:PluginManager: Plugin '{plugin_name_lower}' disabled in PluginManager.")
        return True
    
    def get_plugin_info(self, plugin_name: str) -> Dict | None:
        """Get information about a loaded plugin."""
        plugin_name_lower = plugin_name.lower()
        return self.plugins.get(plugin_name_lower) # Returns from self.plugins (loaded plugins)
    
    def get_discovered_plugin_data(self, plugin_name: str) -> Dict | None:
        """Get metadata for a discovered plugin (even if not loaded)."""
        if self._discovered_plugins:
            return self._discovered_plugins.get(plugin_name.lower())
        return None

    def get_loaded_plugins(self) -> List[str]:
        """Get original names of all loaded (instantiated) plugins."""
        # Returns original_name for plugins that are in self.plugins (meaning initialize() has run)
        return [data.get('original_name', key) for key, data in self.plugins.items()]
    
    def get_enabled_plugins(self) -> List[str]:
        """Get original names of all enabled plugins."""
        enabled_original_names = []
        for name_lower in self.enabled_plugins: # self.enabled_plugins contains lowercase keys
            if name_lower in self.plugins: # Check if the enabled plugin is also in loaded plugins
                enabled_original_names.append(self.plugins[name_lower].get('original_name', name_lower))
            else:
                # This case (enabled but not in self.plugins) should ideally not happen
                # if logic is consistent. For robustness, add the key itself.
                enabled_original_names.append(name_lower) 
        return enabled_original_names

    def check_dependencies(self, plugin_name_to_check: str) -> bool:
        """Check if dependencies for a plugin are met (checks against loaded plugins)."""
        plugin_name_to_check_lower = plugin_name_to_check.lower()
        
        # Dependency data comes from _discovered_plugins metadata
        plugin_discovery_data = None
        if self._discovered_plugins:
            plugin_discovery_data = self._discovered_plugins.get(plugin_name_to_check_lower)

        if not plugin_discovery_data:
            self.logger.error(f"Plugin '{plugin_name_to_check_lower}' not found in discovered plugins for dependency check.")
            return False
            
        required_plugin_keys_lower = plugin_discovery_data.get("requires", []) 
        
        if not required_plugin_keys_lower:
            return True # No dependencies
            
        for required_key_lower in required_plugin_keys_lower:
            # Dependencies must be loaded (i.e., in self.plugins and have an instance)
            if required_key_lower not in self.plugins or not self.plugins[required_key_lower].get('instance'):
                self.logger.error(f"Plugin '{plugin_name_to_check_lower}' requires '{required_key_lower}' which is not loaded (no instance).")
                return False
            # Optionally, also check if dependencies are enabled:
            # if required_key_lower not in self.enabled_plugins:
            #     self.logger.error(f"Plugin '{plugin_name_to_check_lower}' requires '{required_key_lower}' which is loaded but not enabled.")
            #     return False
        return True

    def set_tamagotchi_logic(self, tamagotchi_logic_instance):
        """Allows setting a reference to the main TamagotchiLogic instance."""
        setattr(self, 'tamagotchi_logic', tamagotchi_logic_instance)
        # This reference is used when calling plugin's setup method.
        self.logger.info("TamagotchiLogic instance has been linked to PluginManager.")