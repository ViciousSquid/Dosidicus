import time
import math

# Distance tracking constants
DISTANCE_ROLLOVER_LIMIT = 999_999_999  # ~1 billion pixels before rollover

class SquidStatistics:
    def __init__(self, squid):

        self.squid = squid
        self.start_time = time.time()
        self.total_age_seconds = 0
        self.sushi_consumed = 0
        self.cheese_consumed = 0
        self.total_memories_formed = 0
        self.highest_anxiety = 0
        self.lowest_happiness = 100
        self.highest_satisfaction = 0
        self.distance_swam = 0
        self.distance_swam_multiplier = 1
        self.other_squids_encountered = 0
        self.total_rocks_thrown = 0
        self.total_poops_thrown = 0
        self.total_env_interactions = 0
        self.ink_clouds_created = 0
        self.plants_interacted = 0
        self.time_spent_asleep = 0
        self.peak_novelty = 0
        self.peak_stress = 0
        self.peak_reward = 0
        self.novelty_neurons_created = 0
        self.stress_neurons_created = 0
        self.reward_neurons_created = 0
        self.poops_created = 0
        self.max_poops_cleaned = 0
        self.startles_experienced = 0
        self.times_colour_changed = 0
        self.sickness_episodes = 0
        self.max_neurons_reached = 7
        self.current_neurons = 7

    def get_total_age_seconds(self):
        """Calculates the total persistent age in seconds."""
        current_session_age = time.time() - self.start_time
        return self.total_age_seconds + current_session_age
    
    def update_distance(self, dx, dy):
        '''Track distance traveled by squid with rollover protection'''
        distance = math.sqrt(dx*dx + dy*dy)
        self.distance_swam += distance
        
        # Check for rollover and reset with multiplier
        if self.distance_swam >= DISTANCE_ROLLOVER_LIMIT:
            self.distance_swam = self.distance_swam - DISTANCE_ROLLOVER_LIMIT
            self.distance_swam_multiplier += 1
            
            # Log the rollover event
            if hasattr(self.squid, 'tamagotchi_logic'):
                self.squid.tamagotchi_logic.show_message(
                    f"🌊 Distance counter rolled over! Now at {self.distance_swam_multiplier}x"
                )
    
    def get_distance_display(self):
        '''Get formatted distance string with multiplier if needed'''
        if self.distance_swam_multiplier > 1:
            return f"{self.distance_swam_multiplier}x {int(self.distance_swam):,}"
        return f"{int(self.distance_swam):,}"

    def get_squid_age(self):
        """
        Return the squid’s age as a readable string:
            1 min  – 59 min   → “<n> min”
            60 min – 89 min   → “1 hr”
            90 min – 119 min  → “1.5 hrs”
            120 min – 149 min → “2 hrs”
            150 min – 179 min → “2.5 hrs”
            …and so on, stepping in 30-minute blocks.
        """
        total_minutes = int(self.get_total_age_seconds() // 60)

        if total_minutes < 60:                      # still in minutes
            return f"{total_minutes} min" + ("s" if total_minutes != 1 else "")

        # 60 min and above → switch to hours, 30-min steps
        whole_hours = total_minutes // 60
        half_hour   = (total_minutes % 60) // 30   # 0 or 1

        hours_str = f"{whole_hours}" if half_hour == 0 else f"{whole_hours}.5"
        return f"{hours_str} hr" + ("s" if whole_hours + half_hour != 1 else "")
    
    def load_statistics(self, data):
        """Load statistics from saved data dictionary"""
        if not data:
            return
            
        # Core stats
        self.total_age_seconds = data.get('total_age_seconds', 0)
        self.distance_swam = data.get('distance_swam', 0)
        self.distance_swam_multiplier = data.get('distance_swam_multiplier', 1)
        
        # Food consumption
        self.sushi_consumed = data.get('sushi_eaten', 0)
        self.cheese_consumed = data.get('cheese_eaten', 0)
        
        # Mental states
        self.highest_anxiety = data.get('highest_anxiety', 0)
        self.lowest_happiness = data.get('lowest_happiness', 100)
        
        # Object interactions
        self.total_rocks_thrown = data.get('rocks_thrown', 0)
        self.total_poops_thrown = data.get('poops_thrown', 0)
        self.ink_clouds_created = data.get('ink_clouds_created', 0)
        self.plants_interacted = data.get('plants_interacted', 0)
        
        # Other tracked stats
        self.times_colour_changed = data.get('times_colour_changed', 0)
        self.poops_created = data.get('poops_created', 0)
        self.max_poops_cleaned = data.get('max_poops_cleaned', 0)
        self.startles_experienced = data.get('startles_experienced', 0)
        
        # Time and health
        self.time_spent_asleep = data.get('total_sleep_time', 0)
        self.sickness_episodes = data.get('sickness_episodes', 0)
        
        # Neurogenesis
        self.novelty_neurons_created = data.get('novelty_neurons_created', 0)
        self.stress_neurons_created = data.get('stress_neurons_created', 0)
        self.reward_neurons_created = data.get('reward_neurons_created', 0)
        
        # --- FIX: Ensure these are loaded correctly, defaulting to 7 ---
        self.max_neurons_reached = data.get('max_neurons_reached', 7)
        self.current_neurons = data.get('current_neurons', 7)

    def update(self):
        # Update peak mental states
        if self.squid.anxiety > self.highest_anxiety:
            self.highest_anxiety = self.squid.anxiety
        if self.squid.happiness < self.lowest_happiness:
            self.lowest_happiness = self.squid.happiness
        if self.squid.satisfaction > self.highest_satisfaction:
            self.highest_satisfaction = self.squid.satisfaction
            
        if self.squid.is_sleeping:
            self.time_spent_asleep += 1 # update is called every second

        # --- Check and update peak neurogenesis values ---
        if self.squid.tamagotchi_logic and self.squid.tamagotchi_logic.brain_window:
            brain_widget = self.squid.tamagotchi_logic.brain_window.brain_widget
            if brain_widget:
                # 1. Update Neurogenesis Stats
                if hasattr(brain_widget, 'neurogenesis_data'):
                    neuro_data = brain_widget.neurogenesis_data
                    current_novelty = neuro_data.get('novelty_counter', 0)
                    current_stress = neuro_data.get('stress_counter', 0)
                    current_reward = neuro_data.get('reward_counter', 0)

                    if current_novelty > self.peak_novelty:
                        self.peak_novelty = current_novelty
                    if current_stress > self.peak_stress:
                        self.peak_stress = current_stress
                    if current_reward > self.peak_reward:
                        self.peak_reward = current_reward
                
                # 2. Update Max Neurons Reached (FIX)
                if hasattr(brain_widget, 'neuron_positions'):
                    actual_count = len(brain_widget.neuron_positions)
                    if actual_count > self.max_neurons_reached:
                        self.max_neurons_reached = actual_count
                    self.current_neurons = actual_count

    def get_sleep_time(self):
        hours = int(self.time_spent_asleep // 3600)
        minutes = int((self.time_spent_asleep % 3600) // 60)
        return f"{hours}h {minutes}m"