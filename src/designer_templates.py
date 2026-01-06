from designer_core import BrainDesign, DesignerLayer, DesignerNeuron
from designer_constants import NeuronType, REQUIRED_NEURONS, CORE_NEURONS, INPUT_SENSORS, DEFAULT_LAYER_SPACING
import random

class TemplateManager:
    @staticmethod
    def get_templates() -> dict:
        return {
            'core_only': {'name': '🟡 Required Only', 'description': '8 required neurons'},
            'dosidicus_default': {'name': '🟡 Dosidicus Default', 'description': 'Standard layout'},
            'full_sensors': {'name': '🟡 Full Sensor Suite', 'description': 'All sensors'},
            'insomniac': {'name': '🔴 The Insomniac', 'description': 'Anxiety & Curiosity block sleep'},
            'hyperactive': {'name': '🔴 The Hyperactive', 'description': 'Noise neurons overwhelm sleepiness'},
            'hangry': {'name': '🔴 The Hangry', 'description': 'Hunger causes extreme rage'},
            'depressive': {'name': '🔴 The Depressive', 'description': 'Resistant to happiness'},
            'obsessive': {'name': '🔴 The Obsessive', 'description': 'Anxiety/Curiosity feedback loop'},
        }
    
    @staticmethod
    def create_template(key: str) -> BrainDesign:
        design = BrainDesign()
        
        # ==========================================
        # STANDARD TEMPLATES
        # ==========================================
        if key == 'core_only':
            design.layers = [DesignerLayer("Sensors", NeuronType.INPUT, 100), DesignerLayer("Core", NeuronType.HIDDEN, 250)]
            design.add_missing_required_neurons()
            
        elif key == 'full_sensors':
            design.layers = [DesignerLayer("Input", NeuronType.INPUT, 50), DesignerLayer("Core", NeuronType.HIDDEN, 200), DesignerLayer("Out", NeuronType.OUTPUT, 350)]
            design.add_missing_required_neurons()
            design.add_all_sensors()

        # ==========================================
        # PATHOLOGICAL / SPECIFIC BEHAVIORS
        # ==========================================
        elif key == 'insomniac':
            # A brain where active states aggressively inhibit sleep
            design.layers = [DesignerLayer("Sensors", NeuronType.INPUT, 150), DesignerLayer("Racing Mind", NeuronType.HIDDEN, 200), DesignerLayer("State", NeuronType.OUTPUT, 350)]
            design.add_missing_required_neurons()
            
            # The Insomniac Logic:
            # Any active emotion makes it impossible to sleep (Strong Inhibition)
            design.add_connection("anxiety", "sleepiness", -0.95)
            design.add_connection("curiosity", "sleepiness", -0.80)
            design.add_connection("hunger", "sleepiness", -0.50)
            design.add_connection("can_see_food", "sleepiness", -0.50)
            
            # Weak positive feedback means once awake, they stay awake
            design.add_connection("sleepiness", "anxiety", 0.2) # Being tired makes them anxious

        elif key == 'hyperactive':
            # A brain with a "Noise" layer that floods the system
            design.layers = [
                DesignerLayer("Vision", NeuronType.INPUT, 150), 
                DesignerLayer("Core", NeuronType.HIDDEN, 200), 
                DesignerLayer("Noise", NeuronType.HIDDEN, 300), # Extra space for noise neurons
                DesignerLayer("Output", NeuronType.OUTPUT, 400)
            ]
            design.add_missing_required_neurons()

            # Create 12 "Noise" neurons that act as a distraction generator
            noise_neurons = [f"noise_{i}" for i in range(12)]
            for n in noise_neurons:
                design.add_neuron(n, "Noise")
                
                # The "Overwhelm" Logic:
                # These neurons excite sleepiness (crash) and curiosity (distraction)
                # Randomize weights slightly so they aren't identical
                w_sleep = random.uniform(0.6, 0.9)
                w_curiosity = random.uniform(0.5, 0.8)
                
                design.add_connection(n, "sleepiness", w_sleep)   # Floods sleep buffer
                design.add_connection(n, "curiosity", w_curiosity) # Forces erratic attention
                
                # Connect noise to itself for chaotic sustainability
                if random.random() > 0.5:
                    target = random.choice(noise_neurons)
                    design.add_connection(n, target, 0.4)

        elif key == 'hangry':
            # Metabolic mood disorder
            design.layers = [DesignerLayer("Sensors", NeuronType.INPUT, 100), DesignerLayer("Gut-Brain", NeuronType.HIDDEN, 200)]
            design.add_missing_required_neurons()
            
            # Hunger overrides all positive emotions and triggers anxiety/stress
            design.add_connection("hunger", "happiness", -1.0) # Cannot be happy if hungry
            design.add_connection("hunger", "satisfaction", -1.0)
            design.add_connection("hunger", "anxiety", 0.9) # Extreme stress when hungry
            design.add_connection("can_see_food", "anxiety", 0.5) # Seeing food but not eating it is stressful

        elif key == 'depressive':
            # Anhedonia model: High resistance to positive weights
            design.layers = [DesignerLayer("Input", NeuronType.INPUT, 150), DesignerLayer("Gray", NeuronType.HIDDEN, 200)]
            design.add_missing_required_neurons()
            
            # Hard to get happy, easy to get sad
            design.add_connection("satisfaction", "happiness", 0.1) # Drastically reduced reward
            design.add_connection("curiosity", "happiness", 0.0) # No joy from exploration
            design.add_connection("anxiety", "happiness", -0.8) # Anxiety kills happiness easily
            design.add_connection("sleepiness", "happiness", -0.6)

        elif key == 'obsessive':
            # Feedback loop central
            design.layers = [DesignerLayer("Input", NeuronType.INPUT, 150), DesignerLayer("Loop", NeuronType.HIDDEN, 200)]
            design.add_missing_required_neurons()
            
            # Tight feedback loop between anxiety and curiosity (Worrying/Checking)
            design.add_connection("anxiety", "curiosity", 0.7) # Worry makes you check things
            design.add_connection("curiosity", "anxiety", 0.5) # Checking things makes you worry
            design.add_connection("sleepiness", "anxiety", 0.4) # Being tired makes the loops worse

        else: # Default Dosidicus
            design.layers = [DesignerLayer("Vision", NeuronType.INPUT, 200), DesignerLayer("Stats", NeuronType.HIDDEN, 81), DesignerLayer("Emotions", NeuronType.OUTPUT, 385)]
            design.add_missing_required_neurons()
            # Default connections
            design.add_connection("can_see_food", "hunger", 0.3)
            design.add_connection("can_see_food", "happiness", 0.2)
            design.add_connection("hunger", "satisfaction", -0.5)
            

        return design