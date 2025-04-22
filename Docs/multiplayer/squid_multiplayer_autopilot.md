### Remote Squid Control

(`squid_multiplayer_autopilot.py`)

When your squid visits another instance, it's not directly controlled by the other player. Instead, the `RemoteSquidController` class in `squid_multiplayer_autopilot.py` takes over.
This is an AI autopilot that simulates your squid's behavior according to predefined patterns (exploring, seeking food, interacting with objects, etc.). The controller makes decisions based on:

The initial state of your squid when it crossed the boundary
A random "personality" for the visit
The environment of the other tank (available food, rocks, etc.)

The flow works like this:

Your squid hits a boundary and sends a squid_exit message
The other instance receives this message and:

Creates a visual representation of your squid
Creates a RemoteSquidController to manage its behavior


The autopilot controls your squid in the other tank
After a random amount of time (or when the controller decides it's met its goals like stealing rocks), it initiates a return
When your squid returns, any experiences or stolen items are synchronized back

This autopilot system allows for autonomous interaction between instances without requiring direct player control. Your squid effectively has a "life of its own" while visiting other tanks.
