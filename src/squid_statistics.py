import time

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
        self.other_squids_encountered = 0
        self.total_rocks_thrown = 0
        self.total_poops_thrown = 0
        self.total_env_interactions = 0
        self.time_spent_asleep = 0
        self.peak_novelty = 0
        self.peak_stress = 0
        self.peak_reward = 0

    def get_total_age_seconds(self):
        """Calculates the total persistent age in seconds."""
        current_session_age = time.time() - self.start_time
        return self.total_age_seconds + current_session_age

    def get_squid_age(self):
        """Returns the total age formatted as a string."""
        age_seconds = self.get_total_age_seconds()
        hours = int(age_seconds // 3600)
        minutes = int((age_seconds % 3600) // 60)
        return f"{hours}h {minutes}m"

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
            if brain_widget and hasattr(brain_widget, 'neurogenesis_data'):
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

    def get_sleep_time(self):
        hours = int(self.time_spent_asleep // 3600)
        minutes = int((self.time_spent_asleep % 3600) // 60)
        return f"{hours}h {minutes}m"