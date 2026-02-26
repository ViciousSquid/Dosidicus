
The Experience Buffer is a core component in the system's learning and [neurogenesis](../neural-network/Neurogenesis.md) (neuron creation) module that functions as a memory for recent, significant events. It maintains a time-ordered log of the squid's context and uses this data to identify recurring patterns, which helps the system decide when and how to create new, functionally specialized neurons.

#### How the Experience Buffer Works
The experience buffer is technically implemented as the `ExperienceBuffer` class, which operates in two main ways: maintaining a rolling log and tracking pattern recurrence.

1. Rolling Log (deque): The buffer uses a deque (double-ended queue) to store a fixed, limited number of recent experiences (default maximum is 50 experiences). When a new experience is added, the oldest one is automatically discarded, ensuring the buffer only contains the latest, most relevant context.

2. Pattern Tracking: When an experience is added, it is processed to generate three levels of **pattern signatures**, which are counted to track how often similar events occur:

*  **Specific Pattern**: The most detailed signature, identifying a precise combination of `trigger`, `outcome`, and primary motivational neuron state.

*  **Parent Pattern**: A broader pattern used for hierarchical grouping.

*  **Core Pattern**: A minimal pattern used for "fuzzy matching" or identifying basic event categories.

The system analyses these counts to determine if a situation is a novel event or a recurring pattern, which heavily influences whether a new neuron is created, or if an existing neuron is strengthened.



----------------

#### Example Experiences (ExperienceContext)

<img src="https://github.com/user-attachments/assets/ecd998a9-e4b9-44d2-8f37-9a04df58515c" width="300">

Each recorded experience is captured as an ExperienceContext object, which is a snapshot of the squid's state and environment at the moment a significant event (the trigger) occurs.

* `trigger_type` - The general category of the event: `novelty`, `stress`, or `reward`.
* `outcome`	- The result of the experience: `positive`, `negative`, or `neutral`.
* `active_neurons`	A dictionary of all current neuron activations (e.g., {`hunger`: 20, `anxiety`: 85}).
* `recent_actions`	A list of recent actions taken by the squid (e.g., [`approach_plant`, `hide`]).
* `environmental_state`	Key external facts at the time (e.g., {`food_count`: 0, `has_rock`: True}).


