# File: mp_constants.py

# --- Plugin Metadata ---
# These constants describe the plugin to the system and users.
PLUGIN_NAME = "Multiplayer"
PLUGIN_VERSION = "1.0.0"
PLUGIN_AUTHOR = "ViciousSquid"
PLUGIN_DESCRIPTION = "Enables network sync for squids and objects (Experimental)"
PLUGIN_REQUIRES = [] # Names of other plugins this one depends on

# --- Network Configuration ---
# These define the network parameters for multicast communication.
MULTICAST_GROUP = '224.3.29.71'   # IP address for the multicast group
MULTICAST_PORT = 10000            # Port number for multicast communication
SYNC_INTERVAL = 1.0               # Default seconds between game state sync broadcasts
MAX_PACKET_SIZE = 65507           # Maximum UDP packet size, to prevent fragmentation

# --- Visual Settings (Defaults) ---
# These are default visual parameters. The MultiplayerPlugin instance may override these
# based on runtime configuration (e.g., from a settings dialog).
REMOTE_SQUID_OPACITY = 0.8        # Default opacity for remote squids (0.0 to 1.0)
SHOW_REMOTE_LABELS = True         # Default setting for showing labels on remote entities
SHOW_CONNECTION_LINES = True      # Default setting for showing lines connecting to remote squids