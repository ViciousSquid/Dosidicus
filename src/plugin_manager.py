import os
import importlib.util
import inspect
import logging
from typing import Dict, List, Callable, Any

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
        self.plugins = {}        # Stores loaded plugins' metadata and instances
        self.hooks = {}          # Registered hooks and their subscribers
        self.enabled_plugins = set()  # Names of enabled plugins
        self.logger = logging.getLogger("PluginManager")
        self._discovered_plugins = None  # Cache for discovered plugins
        
        # Create plugins directory if it doesn't exist
        os.makedirs(plugin_directory, exist_ok=True)
        
        # Initialize standard hooks
        self._initialize_hooks()
        self._initialized = True  # Mark as initialized
    
    def _initialize_hooks(self):
        """Initialize standard hooks that plugins can register for"""
        # Lifecycle hooks
        self.register_hook("on_startup")           # Application startup
        self.register_hook("on_shutdown")          # Application shutdown
        self.register_hook("on_new_game")          # New game created
        self.register_hook("on_save_game")         # Game being saved
        self.register_hook("on_load_game")         # Game being loaded
        
        # Simulation hooks
        self.register_hook("pre_update")           # Before simulation update
        self.register_hook("post_update")          # After simulation update
        self.register_hook("on_speed_change")      # Simulation speed changed
        
        # Squid state hooks
        self.register_hook("on_squid_state_change") # Squid state changed
        self.register_hook("on_hunger_change")     # Hunger value changed
        self.register_hook("on_happiness_change")  # Happiness value changed
        self.register_hook("on_cleanliness_change") # Cleanliness value changed
        self.register_hook("on_sleepiness_change") # Sleepiness value changed
        self.register_hook("on_satisfaction_change") # Satisfaction value changed
        self.register_hook("on_anxiety_change")    # Anxiety value changed
        self.register_hook("on_curiosity_change")  # Curiosity value changed
        
        # Action hooks
        self.register_hook("on_feed")              # Squid fed
        self.register_hook("on_clean")             # Environment cleaned
        self.register_hook("on_medicine")         # Medicine given
        self.register_hook("on_sleep")             # Squid falling asleep
        self.register_hook("on_wake")              # Squid waking up
        self.register_hook("on_startle")           # Squid startled
        
        # Interaction hooks
        self.register_hook("on_rock_pickup")       # Rock picked up
        self.register_hook("on_rock_throw")        # Rock thrown
        self.register_hook("on_decoration_interaction") # Decoration interaction
        self.register_hook("on_ink_cloud")         # Ink cloud created
        
        # Neural/memory hooks
        self.register_hook("on_neurogenesis")      # New neuron created
        self.register_hook("on_memory_created")    # New memory created
        self.register_hook("on_memory_to_long_term") # Memory moved to long term
        
        # UI hooks
        self.register_hook("on_menu_creation")     # UI menus being created
        self.register_hook("on_message_display")   # Message being displayed
        
        # Custom menu action hooks
        self.register_hook("register_menu_actions") # Register custom menu actions
    
    def register_hook(self, hook_name: str) -> None:
        """
        Register a new hook that plugins can subscribe to.
        
        Args:
            hook_name: Name of the hook
        """
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
            self.logger.debug(f"Registered hook: {hook_name}")
    
    def subscribe_to_hook(self, hook_name: str, plugin_name: str, callback: Callable) -> bool:
        """
        Subscribe a plugin's callback to a specific hook.
        
        Args:
            hook_name: Name of the hook to subscribe to
            plugin_name: Name of the plugin subscribing
            callback: Function to call when the hook is triggered
            
        Returns:
            bool: True if subscription was successful, False otherwise
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
        
        Args:
            hook_name: Name of the hook to unsubscribe from
            plugin_name: Name of the plugin unsubscribing
            
        Returns:
            bool: True if unsubscription was successful, False otherwise
        """
        if hook_name not in self.hooks:
            return False
        
        self.hooks[hook_name] = [
            h for h in self.hooks[hook_name] 
            if h["plugin"] != plugin_name
        ]
        return True
    
    def trigger_hook(self, hook_name, **kwargs):
        print(f"Attempting to trigger hook: {hook_name}")
        """
        Trigger a hook, calling all subscribed plugin callbacks.
        
        Args:
            hook_name: Name of the hook to trigger
            **kwargs: Arguments to pass to plugin callbacks
            
        Returns:
            List of results from plugin callbacks
        """
        if hook_name not in self.hooks:
            self.logger.warning(f"Attempted to trigger non-existent hook: {hook_name}")
            return []
        
        results = []
        for subscriber in self.hooks[hook_name]:
            plugin_name = subscriber["plugin"]
            if plugin_name not in self.enabled_plugins:
                continue
                
            try:
                callback = subscriber["callback"]
                result = callback(**kwargs)
                results.append(result)
            except Exception as e:
                self.logger.error(f"Error in plugin {plugin_name} for hook {hook_name}: {str(e)}")
        
        return results
    
    def discover_plugins(self) -> Dict[str, Dict]:
        """
        Discover available plugins from the plugin directory.
        Only loads plugins that have a main.py file in their directory.
        
        Returns:
            Dictionary mapping plugin names to metadata
        """
        # Store current enabled plugins before discovery
        current_enabled = set(self.enabled_plugins)
        
        plugin_info = {}
        
        # Skip if directory doesn't exist
        if not os.path.exists(self.plugin_directory):
            print(f"WARNING: Plugin directory does not exist: {self.plugin_directory}")
            return plugin_info
        
        print(f"+++ Scanning for plugins...")
        #print(f"Directory contents: {os.listdir(self.plugin_directory)}")

        
        # Iterate through plugin directories
        for plugin_dir in os.listdir(self.plugin_directory):
            plugin_path = os.path.join(self.plugin_directory, plugin_dir)
            
            # Only consider directories
            if not os.path.isdir(plugin_path):
                #print(f"Skipping non-directory: {plugin_path}")
                continue
                
            # Look for main.py in the plugin directory
            main_py = os.path.join(plugin_path, "main.py")
            #print(f"Checking for main.py in: {main_py}")
            
            if not os.path.exists(main_py):
                print(f"No main.py found in {plugin_path}")
                continue
                
            try:
                # Load the plugin module
                spec = importlib.util.spec_from_file_location(f"plugins.{plugin_dir}.main", main_py)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                
                # Get plugin metadata
                plugin_name = getattr(module, "PLUGIN_NAME", plugin_dir).lower()
                metadata = {
                    "name": plugin_name,
                    "version": getattr(module, "PLUGIN_VERSION", "1.0.0"),
                    "author": getattr(module, "PLUGIN_AUTHOR", "Unknown"),
                    "description": getattr(module, "PLUGIN_DESCRIPTION", ""),
                    "requires": getattr(module, "PLUGIN_REQUIRES", []),
                    "path": main_py,
                    "directory": plugin_path,
                    "module": module
                }
                
                # Add plugin to discovered plugins
                plugin_info[plugin_name] = metadata
                self.logger.info(f"Discovered plugin: {metadata['name']} v{metadata['version']} by {metadata['author']}")
                
                print(f"++ Found plugin: {plugin_name}")
                #print(f"Plugin metadata: {metadata}")
                
            except Exception as e:
                print(f"\034[31mError loading plugin {plugin_dir}: {str(e)}\033[m")
                import traceback
                traceback.print_exc()
        
        print(f"\034[31mTotal plugins discovered: {len(plugin_info)}\033[m")
        
        # Restore previously enabled plugins
        self.enabled_plugins.update(current_enabled)
        print(f"Restored enabled plugins: {list(self.enabled_plugins)}")
        
        return plugin_info
    
    # In plugin_manager.py, modify the load_all_plugins method

    def load_all_plugins(self) -> Dict[str, bool]:
        """
        Load all discovered plugins.
        
        Returns:
            Dictionary mapping plugin names to load success status
        """
        # Clear any existing plugin tracking
        self.plugins.clear()
        self.enabled_plugins.clear()
        
        # Discover plugins
        self._discovered_plugins = self.discover_plugins()
        results = {}
        
        print(f"Attempting to load {len(self._discovered_plugins)} discovered plugins")
        
        # Load multiplayer plugin first, but DON'T automatically enable it
        if 'multiplayer' in self._discovered_plugins:
            print("Attempting to load multiplayer plugin (ignoring dependencies)...")
            result = self.load_plugin('multiplayer')
            results['multiplayer'] = result
            
            if result:
                print("Successfully loaded multiplayer plugin!")
                # Remove this line so it doesn't auto-enable
                # self.enabled_plugins.add('multiplayer')
            else:
                print("Failed to load multiplayer plugin despite ignoring dependencies")
        
        # Now load other plugins
        for plugin_name in self._discovered_plugins:
            if plugin_name != 'multiplayer':  # Skip multiplayer as we already tried to load it
                print(f"Loading plugin: {plugin_name}")
                result = self.load_plugin(plugin_name)
                results[plugin_name] = result
                
                # Ensure successful plugins are added to enabled set
                if result:
                    self.enabled_plugins.add(plugin_name.lower())
        
        # Print debug information
        print(f"Loaded Plugins: {list(self.plugins.keys())}")
        print(f"Enabled Plugins: {list(self.enabled_plugins)}")
        
        return results
    
    def unload_plugin(self, plugin_name):
        """Unload a plugin"""
        success = self.plugin_manager.unload_plugin(plugin_name)
        if success:
            self.show_message(f"Plugin {plugin_name} unloaded")
        else:
            self.show_message(f"Failed to unload plugin {plugin_name}")
        
        # Refresh the list
        self.load_plugins()
    
    def unload_all_plugins(self) -> None:
        """Unload all active plugins"""
        for plugin_name in list(self.plugins.keys()):
            self.unload_plugin(plugin_name)
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a loaded plugin."""
        plugin_name = plugin_name.lower()
        
        if plugin_name not in self.plugins:
            return False
            
        # Get plugin instance
        plugin_data = self.plugins[plugin_name]
        plugin_instance = plugin_data.get('instance')
        
        # If plugin has an enable method, call it
        if plugin_instance and hasattr(plugin_instance, 'enable'):
            success = plugin_instance.enable()
            if not success:
                return False
        
        # Add to enabled set
        self.enabled_plugins.add(plugin_name)
        self.logger.info(f"Enabled plugin: {plugin_name}")
        return True

    def disable_plugin(self, plugin_name: str) -> bool:
        """Disable a loaded plugin."""
        plugin_name = plugin_name.lower()
        
        if plugin_name not in self.plugins:
            return False
            
        # Get plugin instance
        plugin_data = self.plugins[plugin_name]
        plugin_instance = plugin_data.get('instance')
        
        # If plugin has a disable method, call it
        if plugin_instance and hasattr(plugin_instance, 'disable'):
            plugin_instance.disable()
        
        # Remove from enabled set
        if plugin_name in self.enabled_plugins:
            self.enabled_plugins.remove(plugin_name)
            self.logger.info(f"Disabled plugin: {plugin_name}")
        return True
    
    def disable_plugin(self, plugin_name: str) -> bool:
        """
        Disable a loaded plugin without unloading it.
        
        Args:
            plugin_name: Name of the plugin to disable
            
        Returns:
            bool: True if plugin was disabled successfully, False otherwise
        """
        # Normalize plugin name to lowercase
        plugin_name = plugin_name.lower()
        
        if plugin_name not in self.plugins:
            return False
            
        if plugin_name in self.enabled_plugins:
            self.enabled_plugins.remove(plugin_name)
            self.logger.info(f"Disabled plugin: {plugin_name}")
            
        return True
    
    def get_plugin_info(self, plugin_name: str) -> Dict:
        """
        Get information about a loaded plugin.
        
        Args:
            plugin_name: Name of the plugin to get info for
            
        Returns:
            Dict containing plugin metadata
        """
        if plugin_name not in self.plugins:
            return {}
            
        return self.plugins[plugin_name]
    
    def get_loaded_plugins(self) -> List[str]:
        """
        Get names of all loaded plugins.
        
        Returns:
            List of plugin names
        """
        return list(self.plugins.keys())
    
    def get_enabled_plugins(self) -> List[str]:
        print(f"Current enabled_plugins: {self.enabled_plugins}")
        return list(set(plugin.lower() for plugin in self.enabled_plugins))
    
    def check_dependencies(self, plugin_name):
        """
        Check if all dependencies for a plugin are satisfied.
        
        Args:
            plugin_name: Name of the plugin to check dependencies for
            
        Returns:
            bool: True if all dependencies are satisfied, False otherwise
        """
        if plugin_name not in self._discovered_plugins:
            self.logger.error(f"Plugin not found: {plugin_name}")
            return False
            
        plugin_data = self._discovered_plugins[plugin_name]
        required_plugins = plugin_data.get("requires", [])
        
        if not required_plugins:
            return True  # No dependencies
            
        # Check if all required plugins are loaded
        for required in required_plugins:
            if required not in self.plugins:
                self.logger.error(f"Plugin {plugin_name} requires {required} which is not loaded")
                return False
        
        return True

    def load_plugin(self, plugin_name):
        """
        Load and initialize a plugin by name.

        Args:
            plugin_name: Name of the plugin to load

        Returns:
            bool: True if plugin was loaded successfully, False otherwise
        """
        # Normalize plugin name to lowercase
        plugin_name = plugin_name.lower()

        # Skip if already loaded
        if plugin_name in self.plugins:
            self.logger.info(f"Plugin already loaded: {plugin_name}")

            # Ensure it's in enabled plugins, but not for multiplayer
            if plugin_name != "multiplayer" and plugin_name not in self.enabled_plugins:
                self.enabled_plugins.add(plugin_name)

            return True

        # Discover plugins if needed
        if not hasattr(self, '_discovered_plugins') or not self._discovered_plugins:
            self._discovered_plugins = self.discover_plugins()

        # Check if plugin exists
        if plugin_name not in self._discovered_plugins:
            self.logger.error(f"Plugin not found: {plugin_name}")
            return False

        plugin_data = self._discovered_plugins[plugin_name]
        module = plugin_data["module"]

        # Check for required plugins (skip for multiplayer)
        if plugin_name.lower() != "multiplayer":
            required_plugins = plugin_data.get("requires", [])
            if required_plugins:
                missing_plugins = []
                for required in required_plugins:
                    if required not in self.plugins:
                        missing_plugins.append(required)

                if missing_plugins:
                    self.logger.error(f"Plugin {plugin_name} requires {missing_plugins} which are not loaded")
                    return False

        # Check for initialize function
        if not hasattr(module, "initialize"):
            self.logger.error(f"Plugin {plugin_name} has no initialize function")
            return False

        try:
            # Initialize the plugin
            print(f"Attempting to initialize plugin: {plugin_name}")
            initialize_func = getattr(module, "initialize")

            # Special handling for multiplayer plugin
            if plugin_name.lower() == "multiplayer":
                print("Using special initialization for multiplayer plugin")
                # Create the plugin instance
                if hasattr(module, "MultiplayerPlugin"):
                    plugin_instance = module.MultiplayerPlugin()
                    # Store the instance in plugin_data
                    plugin_data['instance'] = plugin_instance
                    
                    # Pass plugin manager and tamagotchi_logic references
                    plugin_instance.plugin_manager = self
                    if hasattr(self, 'tamagotchi_logic'):
                        plugin_instance.tamagotchi_logic = self.tamagotchi_logic
                    
                    # Pass plugin manager to initialize
                    success = initialize_func(self)
                else:
                    print(f"ERROR: Could not find MultiplayerPlugin class in {plugin_name}")
                    success = False
            else:
                # Normal initialization for other plugins
                success = initialize_func(self)

            if success:
                # Store plugin instance for future reference
                self.plugins[plugin_name] = plugin_data

                # Add to enabled plugins, but not the multiplayer plugin
                if plugin_name != "multiplayer":
                    self.enabled_plugins.add(plugin_name)

                self.logger.info(f"Loaded plugin: {plugin_name}")
                print(f"Successfully loaded plugin: {plugin_name}")
                return True
            else:
                self.logger.error(f"Plugin {plugin_name} initialization returned False")
                print(f"Plugin {plugin_name} initialization returned False")
                return False

        except Exception as e:
            self.logger.error(f"Error initializing plugin {plugin_name}: {str(e)}")
            print(f"Error initializing plugin {plugin_name}: {str(e)}")
            import traceback
            traceback.print_exc()
            return False
    
    def enable_plugin(self, plugin_name: str) -> bool:
        """Enable a loaded plugin with improved error handling."""
        plugin_name = plugin_name.lower()
        
        if plugin_name not in self.plugins:
            print(f"Cannot enable plugin {plugin_name}: not loaded")
            return False
            
        # Get plugin instance
        plugin_data = self.plugins[plugin_name]
        plugin_instance = plugin_data.get('instance')
        
        # Make sure the plugin has references it needs
        if plugin_instance:
            # Set plugin_manager reference if needed
            if not hasattr(plugin_instance, 'plugin_manager') or plugin_instance.plugin_manager is None:
                plugin_instance.plugin_manager = self
                print(f"Set plugin_manager reference for {plugin_name}")
                
            # Set tamagotchi_logic reference if available
            if hasattr(self, 'tamagotchi_logic') and self.tamagotchi_logic:
                plugin_instance.tamagotchi_logic = self.tamagotchi_logic
                print(f"Set tamagotchi_logic reference for {plugin_name}")
        
        # If plugin has an enable method, call it
        try:
            if plugin_instance and hasattr(plugin_instance, 'enable'):
                print(f"Calling enable() method for {plugin_name}")
                success = plugin_instance.enable()
                if not success:
                    print(f"Plugin {plugin_name}.enable() returned False")
                    return False
        except Exception as e:
            print(f"Error enabling plugin {plugin_name}: {e}")
            import traceback
            traceback.print_exc()
            return False
        
        # Add to enabled set
        self.enabled_plugins.add(plugin_name)
        self.logger.info(f"Enabled plugin: {plugin_name}")
        print(f"Successfully enabled plugin: {plugin_name}")
        return True