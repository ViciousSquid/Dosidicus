
Neurogenesis Technical Documentation
====================================

1\. Overview
------------

Neurogenesis enables the dynamic creation of new neurons in the squid's brain. This process, also known as brain plasticity, allows the squid to adapt and learn from his experiences and environment over time. Neurogenesis is triggered by three primary environmental and psychological factors: **Novelty**, **Stress**, and **Reward**. The entire system is highly configurable through the `config.ini` file, which allows for fine-tuning of the triggers, neuron properties, and visual effects associated with this process.

2\. Configuration (config.ini)
------------------------------

The behavior of the neurogenesis system is defined by the `[Neurogenesis]` section and its subsections in the `config.ini` file. This allows for easy modification of the system without altering the source code.

### 2.1. General Settings

![image](https://github.com/user-attachments/assets/f54fd9f0-e26d-49f0-a6a6-a4dd440196bf)


### 2.2. Neurogenesis Triggers

Neurogenesis is triggered when a counter for Novelty, Stress, or Reward exceeds its defined threshold.

#### 2.2.1. Novelty (\[Neurogenesis.Novelty\])

![image](https://github.com/user-attachments/assets/413375d3-e581-4154-bfec-3b4ac6802faf)


#### 2.2.2. Stress (\[Neurogenesis.Stress\])

![image](https://github.com/user-attachments/assets/4a003c06-5690-40c4-b47d-ffd46e6f8174)


#### 2.2.3. Reward (\[Neurogenesis.Reward\])

![image](https://github.com/user-attachments/assets/581362bd-d8bb-4cb7-bcc5-c6737c37592a)


### 2.3. Neuron Properties (\[Neurogenesis.NeuronProperties\])

![image](https://github.com/user-attachments/assets/9280a0a2-0395-4baa-9425-ac478fa0cfe9)



3\. Data Flow
-------------

The neurogenesis process follows a clear data flow through the application:

1.  **State Change:** The squid's internal state (e.g., hunger, happiness, anxiety) changes due to interactions with the environment or internal processes. This happens in src/tamagotchi\_logic.py.
2.  **Trigger Update:** The `update_simulation` method in `TamagotchiLogic` detects these state changes and updates the neurogenesis trigger counters (novelty, stress, reward) accordingly.
3.  **Brain Update:** The updated trigger counters are passed to the `BrainWidget` in src/brain\_widget.py via the `update_squid_brain` method.
4.  **Neurogenesis Check:** The `update_state` method in `BrainWidget` calls `check_neurogenesis` to determine if any of the trigger counters have exceeded their thresholds and if the cooldown period has passed.
5.  **Neuron Creation:** If the conditions are met, `_create_neuron_internal` is called to create a new neuron with the appropriate properties (color, shape, connections) based on the trigger type.
6.  **Visualization:** The new neuron and its associated visual effects are rendered in the brain visualization.
7.  **UI Update:** The `NeurogenesisTab` in src/brain\_neurogenesis\_tab.py is updated to reflect the new state of the counters, cooldown, and the recently created neuron.
8.  **Logging:** The neurogenesis event is logged to neurogenesis\_log.txt.

4\. Core Logic and Implementation
---------------------------------

### 4.1. Trigger Management (src/tamagotchi\_logic.py)

The `TamagotchiLogic` class in src/tamagotchi\_logic.py is responsible for managing the squid's state and updating the neurogenesis triggers. The `update_simulation` method continuously monitors the squid's needs and interactions, incrementing the novelty, stress, and reward counters based on the logic defined in this class and the parameters from `config.ini`.

### 4.2. Neuron Creation and Visualization (src/brain\_widget.py)

The `BrainWidget` class is the heart of the neurogenesis visualization. The key methods involved are:

#### `check_neurogenesis(state)`

This method is called by `update_state` and is responsible for checking if the conditions for neurogenesis are met. It compares the trigger counters in the provided \`state\` with the thresholds from the configuration and checks the cooldown timer.

#### `_create_neuron_internal(neuron_type, state)`

This method handles the actual creation of a new neuron. Here's a simplified code snippet illustrating its function:

    
    
    def _create_neuron_internal(self, neuron_type, state):
        # Generate a unique name for the new neuron
        base_name = {'novelty': 'novel', 'stress': 'defense', 'reward': 'reward'}[neuron_type]
        new_name = f"{base_name}_{len(self.neurogenesis_data['new_neurons'])}"
    
        # Determine the position of the new neuron based on active neurons
        # ... (logic to calculate position)
    
        # Set initial activation, color, and shape from config
        self.state[new_name] = self.neurogenesis_config['neuron_properties']['base_activation']
        self.state_colors[new_name] = self.neurogenesis_config['appearance']['colors'][neuron_type]
        self.neuron_shapes[new_name] = self.neurogenesis_config['appearance']['shapes'][neuron_type]
        
        # Create default connections to existing neurons
        if self.neurogenesis_config['neuron_properties']['default_connections']:
            # ... (logic to create connections)
        
        # Log the event and apply visual effects
        self.log_neurogenesis_event(new_name, "created", ...)
        self.neurogenesis_highlight = {'neuron': new_name, ...}
        
        return new_name

        
            

### 4.3. User Interface (src/brain\_neurogenesis\_tab.py)

The `NeurogenesisTab` class in src/brain\_neurogenesis\_tab.py provides a user-friendly interface for monitoring the neurogenesis process. It displays the following real-time information:

*   **Live Counters:** The current values of the novelty, stress, and reward counters.
*   **Thresholds:** The current thresholds for each trigger.
*   **Cooldown Status:** The time remaining before another neuron can be created.
*   **Next Neuron Prediction:** An educated guess about the type of neuron that will be created next.
*   **Recently Created Neurons:** A detailed table of the most recently created neurons, including their creation time, trigger, and associated state.

5\. Neurogenesis Log (neurogenesis\_log.txt)
--------------------------------------------

The system maintains a detailed log of all neurogenesis events in the `neurogenesis_log.txt` file. This log is invaluable for debugging, analysis, and understanding the long-term development of the squid's brain. Each entry provides a timestamp, the name of the new neuron, the trigger that caused its creation, and the value of the trigger counter at that time. For certain neuron types, like "stress" neurons, additional information such as the creation of inhibitory connections and permanent changes to the squid's stats are also logged.

Example log entries:

    
    02:42:35 - a STRESS neuron (stress_0) was created because stress counter was 1.21
    An inhibitory connection was made to ANXIETY
    Maximum anxiety value has been permanently reduced by 10
    
    -------------------------------
    
    02:45:35 - a STRESS neuron (stress_1) was created because stress counter was 51.17
    An inhibitory connection was made to ANXIETY
    Maximum anxiety value has been permanently reduced by 10
    
    -------------------------------
