import time
import math

# Distance tracking constants
DISTANCE_ROLLOVER_LIMIT = 999_999_999  # ~1 billion pixels before rollover
DEFAULT_NEURON_COUNT = 8


class SquidStatistics:
    """Canonical lifetime statistics for a squid.

    Simulation code records elapsed time and discrete domain events here. UI
    components may mirror these values, but they must not derive or persist
    their own competing counters.
    """

    _PERSISTENCE_KEYS = {
        'distance_swam': 'distance_swam',
        'distance_swam_multiplier': 'distance_swam_multiplier',
        'sushi_eaten': 'sushi_consumed',
        'cheese_eaten': 'cheese_consumed',
        'total_memories_formed': 'total_memories_formed',
        'max_short_term_memories': 'max_short_term_memories',
        'max_long_term_memories': 'max_long_term_memories',
        'highest_anxiety': 'highest_anxiety',
        'lowest_happiness': 'lowest_happiness',
        'highest_satisfaction': 'highest_satisfaction',
        'other_squids_encountered': 'other_squids_encountered',
        'rocks_thrown': 'total_rocks_thrown',
        'poops_thrown': 'total_poops_thrown',
        'total_env_interactions': 'total_env_interactions',
        'ink_clouds_created': 'ink_clouds_created',
        'plants_interacted': 'plants_interacted',
        'total_sleep_time': 'time_spent_asleep',
        'peak_novelty': 'peak_novelty',
        'peak_stress': 'peak_stress',
        'peak_reward': 'peak_reward',
        'novelty_neurons_created': 'novelty_neurons_created',
        'stress_neurons_created': 'stress_neurons_created',
        'reward_neurons_created': 'reward_neurons_created',
        'poops_created': 'poops_created',
        'max_poops_cleaned': 'max_poops_cleaned',
        'startles_experienced': 'startles_experienced',
        'times_colour_changed': 'times_colour_changed',
        'sickness_episodes': 'sickness_episodes',
    }

    _EVENT_KEYS = {
        'cheese_eaten': 'cheese_consumed',
        'sushi_eaten': 'sushi_consumed',
        'poops_created': 'poops_created',
        'poops_thrown': 'total_poops_thrown',
        'startles_experienced': 'startles_experienced',
        'ink_clouds_created': 'ink_clouds_created',
        'times_colour_changed': 'times_colour_changed',
        'rocks_thrown': 'total_rocks_thrown',
        'plants_interacted': 'plants_interacted',
    }

    _NEURON_BIRTH_KEYS = {
        'novelty': 'novelty_neurons_created',
        'stress': 'stress_neurons_created',
        'reward': 'reward_neurons_created',
    }

    def __init__(self, squid):
        self.squid = squid
        self.start_time = time.time()
        self.total_age_seconds = 0
        self.sushi_consumed = 0
        self.cheese_consumed = 0
        self.total_memories_formed = 0
        self.max_short_term_memories = 0
        self.max_long_term_memories = 0
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
        self.max_neurons_reached = DEFAULT_NEURON_COUNT
        self.current_neurons = DEFAULT_NEURON_COUNT
        self._last_sickness_state = bool(getattr(squid, 'is_sick', False))

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

    def add_distance(self, distance):
        """Track an already calculated distance without making a view own it."""
        distance = float(distance)
        if distance < 0 or not math.isfinite(distance):
            raise ValueError("distance must be a finite non-negative number")

        self.distance_swam += distance
        if self.distance_swam >= DISTANCE_ROLLOVER_LIMIT:
            rollovers, self.distance_swam = divmod(
                self.distance_swam, DISTANCE_ROLLOVER_LIMIT
            )
            self.distance_swam_multiplier += int(rollovers)
    
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
        """Load canonical statistics from a desktop ``statistics.json`` dict."""
        if data:
            self.total_age_seconds = data.get('total_age_seconds', 0)
            self.start_time = time.time()

            for persisted_key, attribute_name in self._PERSISTENCE_KEYS.items():
                if persisted_key in data:
                    setattr(self, attribute_name, data[persisted_key])

            current_neurons = max(
                0, int(data.get('current_neurons', self.current_neurons))
            )
            saved_maximum = data.get('max_neurons_reached', current_neurons)
            if saved_maximum is None:
                saved_maximum = current_neurons

            self.current_neurons = current_neurons
            self.max_neurons_reached = max(
                current_neurons, max(0, int(saved_maximum))
            )

        # Loading an already-sick squid resumes the same episode. It must not
        # manufacture a fresh false -> true transition on the next tick.
        self._last_sickness_state = bool(getattr(self.squid, 'is_sick', False))

    def to_dict(self):
        """Return the canonical desktop persistence representation."""
        total_age_seconds = self.get_total_age_seconds()
        data = {
            persisted_key: getattr(self, attribute_name)
            for persisted_key, attribute_name in self._PERSISTENCE_KEYS.items()
        }
        data.update({
            'total_age_seconds': total_age_seconds,
            'squid_age_minutes': int(total_age_seconds // 60),
            'max_neurons_reached': self.max_neurons_reached,
            'current_neurons': self.current_neurons,
        })
        return data

    def increment(self, event_name, amount=1):
        """Increment a legacy gameplay event on the canonical model."""
        attribute_name = self._EVENT_KEYS.get(event_name)
        if not attribute_name:
            return False

        setattr(self, attribute_name, getattr(self, attribute_name) + amount)
        return True

    def record_sickness_state(self, is_sick):
        """Record one sickness episode for each false -> true transition."""
        is_sick = bool(is_sick)
        if is_sick and not self._last_sickness_state:
            self.sickness_episodes += 1
        self._last_sickness_state = is_sick

    def record_neuron_birth(self, neuron_type, current_count=None):
        """Record a completed neurogenesis event exactly once at its source."""
        counter_name = self._NEURON_BIRTH_KEYS.get(neuron_type)
        if counter_name:
            setattr(self, counter_name, getattr(self, counter_name) + 1)

        if current_count is None:
            current_count = self.current_neurons + 1
        self.observe_neuron_count(current_count)

    def observe_neuron_count(self, current_count):
        """Update the live count while preserving the lifetime maximum."""
        current_count = int(current_count)
        if current_count < 0:
            raise ValueError("current neuron count cannot be negative")

        self.current_neurons = current_count
        self.max_neurons_reached = max(
            self.max_neurons_reached, current_count
        )

    def observe_poop_count(self, current_count):
        """Preserve the largest number of simultaneous poop items."""
        current_count = int(current_count)
        if current_count < 0:
            raise ValueError("current poop count cannot be negative")

        self.max_poops_cleaned = max(
            self.max_poops_cleaned,
            current_count,
        )

    def observe_memory_counts(self, short_term_count, long_term_count):
        """Preserve lifetime maxima for both memory stores."""
        short_term_count = int(short_term_count)
        long_term_count = int(long_term_count)
        if short_term_count < 0 or long_term_count < 0:
            raise ValueError("memory counts cannot be negative")

        self.max_short_term_memories = max(
            self.max_short_term_memories,
            short_term_count,
        )
        self.max_long_term_memories = max(
            self.max_long_term_memories,
            long_term_count,
        )

    def reset(self):
        """Reset the canonical statistics model."""
        self.__init__(self.squid)

    def update(self, elapsed_seconds):
        """Advance continuous statistics by an explicit elapsed duration."""
        elapsed_seconds = float(elapsed_seconds)
        if elapsed_seconds < 0 or not math.isfinite(elapsed_seconds):
            raise ValueError("elapsed_seconds must be a finite non-negative number")

        # Update peak mental states
        if self.squid.anxiety > self.highest_anxiety:
            self.highest_anxiety = self.squid.anxiety
        if self.squid.happiness < self.lowest_happiness:
            self.lowest_happiness = self.squid.happiness
        if self.squid.satisfaction > self.highest_satisfaction:
            self.highest_satisfaction = self.squid.satisfaction

        if self.squid.is_sleeping:
            self.time_spent_asleep += elapsed_seconds

    def get_sleep_time(self):
        hours = int(self.time_spent_asleep // 3600)
        minutes = int((self.time_spent_asleep % 3600) // 60)
        return f"{hours}h {minutes}m"
