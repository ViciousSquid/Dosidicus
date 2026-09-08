### Hooks


The application can be extended via **HOOKS** which are made available by the simulation engine when certain events occur
* Available hooks are documented here: ../engine/Plugin-Hooks.md

Plugins can subscribe to these hooks by calling the following methods in `src/plugin_manager.py` :

### `register_hook`, `subscribe_to_hook`, `trigger_hook`
<details>
<summary>Show full methods</summary>

```python

def register_hook(self, hook_name: str) -> None:
        """
        Register a new hook that plugins can subscribe to.
        """
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
            self.logger.debug(f"Registered hook: {hook_name}")

```

-----------------

```python

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

```

--------------------

```python

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

```


</details>

--------------------------

### A Quick Guide to Creating a Plugin

#### A really good starting place would be to look at [multiplayer main.py](https://github.com/ViciousSquid/Dosidicus/blob/2.4.5.1_latest_release/plugins/multiplayer/main.py) and [achievements main.py](https://github.com/ViciousSquid/Dosidicus/blob/2.4.5.1_latest_release/plugins/achievements/main.py) and then refer back to this guide

This guide will walk you through the essential steps to create a basic plugin that correctly initializes and registers with the system's `PluginManager` _(src/plugin_manager.py)_

```
The plugin manager expects:
* A folder in plugins/ directory (e.g., plugins/pluginname/)
* A main.py file inside that folder
* Module-level constants: PLUGIN_NAME, PLUGIN_VERSION, PLUGIN_AUTHOR, PLUGIN_DESCRIPTION, PLUGIN_REQUIRES
* An initialize(plugin_manager) function that:

1. Creates the plugin instance
1. Registers it with the plugin manager via plugin_manager.plugins[name] = {..., 'instance': instance}
1. Returns `True` on success
```

### Step 1: Create the Plugin Folder Structure
First, create a new folder for your plugin inside the plugins/ directory. The name of this folder will be your plugin's unique identifier (its key), so choose a simple, lowercase name.

```
Dosidicus/
├── plugins/
│   ├── my_new_plugin/        <-- Your new plugin folder
│   │   └── main.py           <-- Your plugin's entry point
│   ├── auto_care/
│   └── multiplayer/
└── src/
    └── ...
```

### Step 2: Define Plugin Metadata
You must define Module-level constants that the PluginManager uses to identify and load your plugin.

* `PLUGIN_NAME`: (Required) The display name of your plugin.    ### **MUST **BE LOWERCASE!

* `PLUGIN_DESCRIPTION`: A brief description of what your plugin does.

* `PLUGIN_AUTHOR`: Your name or alias.

* `PLUGIN_VERSION`: The version of your plugin.

```python
# plugins/my_new_plugin/main.py

# --- Plugin Metadata --- # PLUGIN_NAME must be lowercase
PLUGIN_NAME = "my new plugin"
PLUGIN_DESCRIPTION = "A simple plugin that demonstrates the basics."
PLUGIN_AUTHOR = "Seymour Butts"
PLUGIN_VERSION = "1.0"
```

### Step 3: Create the Main Plugin Class
It's best practice to encapsulate your plugin's logic within a class. This class will hold the state and functionality of your plugin, such as methods for enabling, disabling, and handling events (hooks).

```python
# plugins/my_new_plugin/main.py

class MyPlugin:
    def __init__(self, plugin_manager, plugin_key):
        self.plugin_manager = plugin_manager
        self.plugin_key = plugin_key # e.g., "my_new_plugin"
        self.is_enabled = False

        # Subscribe to a system event (hook)
        self.plugin_manager.subscribe_to_hook(
            "on_startup",
            self.plugin_key,
            self.on_app_startup
        )

    def enable(self):
        """Called when the user enables the plugin."""
        print(f"[{self.plugin_key}] Plugin Enabled!")
        self.is_enabled = True
        return True # Return True on success

    def disable(self):
        """Called when the user disables the plugin."""
        print(f"[{self.plugin_key}] Plugin Disabled!")
        self.is_enabled = False
        return True # Return True on success

    def on_app_startup(self, **kwargs):
        """Callback for the on_startup hook."""
        if self.is_enabled:
            print(f"[{self.plugin_key}] Application has started up!")
```

### Step 4: Implement the initialize Function
The PluginManager requires a global function named initialize in your main.py. This function's job is to:

1. Get the plugin's unique key (the folder name).

2. Create an instance of your main plugin class.

3. Register the instance with the PluginManager.

This is the crucial step that connects your plugin to the main application.

```python
# plugins/my_new_plugin/main.py
import os

# (Metadata and Class definition from above)
# ...

def initialize(plugin_manager_instance):
    """
    This function is called by the PluginManager to initialize the plugin.
    """
    # Get the plugin's unique key from its directory name
    # os.path.basename(os.path.dirname(__file__)) will return "my_new_plugin"
    plugin_key = os.path.basename(os.path.dirname(__file__))

    try:
        # Create an instance of your main plugin class
        plugin_instance = MyPlugin(plugin_manager_instance, plugin_key)

        # Register the plugin instance with the manager
        # This makes the manager aware of the plugin and its instance
        plugin_manager_instance.plugins[plugin_key] = {
            'instance': plugin_instance,
            'is_enabled_by_default': False # ALWAYS FALSE NEVER CHANGE THIS
        }

        print(f"[{plugin_key}] Plugin initialized successfully.")
        return True # IMPORTANT: Return True on successful initialization

    except Exception as e:
        print(f"[{plugin_key}] Failed to initialize: {e}")
        return False # Return False on failure
```

With these steps, you have a complete, well-structured plugin that the system can discover, load, and run. The user can then enable and disable it manually through the application's plugin management UI.