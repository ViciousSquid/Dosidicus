"""Counting what happens in a squid's life: the lifetime statistics.

Every `track_*` call the rest of the game makes ends up here, and from here
in SquidStatistics (src/squid_statistics.py) and the Statistics tab.
"""
import random


class StatisticsTrackingMixin:
    """Part of TamagotchiLogic (see tamagotchi_logic.py); not used on its own."""

    def _refresh_statistics_tab(self):
        """Refresh the optional statistics projection without owning data."""
        brain_window = getattr(self, 'brain_window', None)
        statistics_tab = getattr(brain_window, 'statistics_tab', None)
        if statistics_tab:
            statistics_tab.update_statistics()

    def record_statistic_event(self, event_name, amount=1):
        """Record one discrete event on the model, then refresh the view."""
        statistics = getattr(getattr(self, 'squid', None), 'statistics', None)
        if not statistics or not statistics.increment(event_name, amount):
            return False

        self._refresh_statistics_tab()
        return True

    def track_distance(self, distance):
        """Record movement on the model, then refresh the optional view."""
        statistics = getattr(getattr(self, 'squid', None), 'statistics', None)
        if not statistics:
            return

        statistics.add_distance(distance)
        self._refresh_statistics_tab()

    def track_poop_thrown(self):
        self.record_statistic_event('poops_thrown')

    def update_highest_anxiety(self, value):
        statistics = getattr(getattr(self, 'squid', None), 'statistics', None)
        if statistics:
            statistics.highest_anxiety = max(
                statistics.highest_anxiety,
                value,
            )
            self._refresh_statistics_tab()

    def update_lowest_happiness(self, value):
        statistics = getattr(getattr(self, 'squid', None), 'statistics', None)
        if statistics:
            statistics.lowest_happiness = min(
                statistics.lowest_happiness,
                value,
            )
            self._refresh_statistics_tab()

    def update_max_memories(self):
        statistics = getattr(getattr(self, 'squid', None), 'statistics', None)
        memory_manager = getattr(getattr(self, 'squid', None), 'memory_manager', None)
        if statistics and memory_manager:
            statistics.observe_memory_counts(
                len(memory_manager.short_term_memory),
                len(memory_manager.long_term_memory),
            )
            self._refresh_statistics_tab()

    def track_food_consumed(self, food_item):
        """Track when food is consumed"""
        event_name = (
            'sushi_eaten'
            if getattr(food_item, 'is_sushi', False)
            else 'cheese_eaten'
        )
        self.record_statistic_event(event_name)

    def track_poop_created(self):
        """Track when poop is created"""
        statistics = getattr(getattr(self, 'squid', None), 'statistics', None)
        if not statistics:
            return

        statistics.increment('poops_created')
        statistics.observe_poop_count(len(self.poop_items))
        self._refresh_statistics_tab()

    def track_rock_thrown(self):
        """Track when rock is thrown"""
        self.record_statistic_event('rocks_thrown')

    def track_plant_interaction(self):
        """Track when squid interacts with plants"""
        self.record_statistic_event('plants_interacted')

    def track_colour_changed(self):
        """Track a completed squid colour change."""
        self.record_statistic_event('times_colour_changed')

    def track_startle(self):
        """Track when squid is startled"""
        self.record_statistic_event('startles_experienced')

    def track_neuron_creation(self, neuron_type, current_count=None):
        """Record one completed neurogenesis event on the canonical model."""
        statistics = getattr(self.squid, 'statistics', None)
        if statistics:
            statistics.record_neuron_birth(
                neuron_type,
                current_count=current_count,
            )

        statistics_window = getattr(self, 'statistics_window', None)
        if statistics_window:
            statistics_window.add_score_for_neuron_creation()

        statistics_tab = getattr(self.brain_window, 'statistics_tab', None)
        if statistics_tab:
            statistics_tab.update_statistics()

    def _statistics_elapsed_seconds(self):
        """Return wall-clock seconds represented by one simulation callback."""
        return self.simulation_timer.interval() / 1000.0

    def _live_neuron_count(self):
        """Count positioned network neurons, excluding only matching keys."""
        brain_widget = getattr(self.brain_window, 'brain_widget', None)
        if not brain_widget:
            return 0

        positions = getattr(brain_widget, 'neuron_positions', {})
        excluded = set(getattr(brain_widget, 'excluded_neurons', ()) or ())
        return sum(name not in excluded for name in positions)

    def refresh_neuron_count(self):
        """Record the live count after any post-birth pruning has settled."""
        brain_widget = getattr(self.brain_window, 'brain_widget', None)
        statistics = getattr(self.squid, 'statistics', None)
        if not brain_widget or not statistics:
            return

        statistics.observe_neuron_count(self._live_neuron_count())
        statistics_tab = getattr(self.brain_window, 'statistics_tab', None)
        if statistics_tab:
            statistics_tab.update_statistics()

    def track_neurogenesis_triggers(self):
        """Update counters for neurogenesis triggers"""
        # Novelty tracking
        if self.new_object_encountered:
            self.neurogenesis_triggers['novel_objects'] = min(
                self.neurogenesis_triggers['novel_objects'] + 1,
                10  # Max cap
            )
            # Add thought about novelty
            self.add_thought("Encountered something new!")
        else:
            # Gradual decay when no novelty
            self.neurogenesis_triggers['novel_objects'] *= 0.95
        
        # Stress tracking
        if self.squid.anxiety > 70:
            self.neurogenesis_triggers['high_stress_cycles'] += 1
            # Add thought about stress if threshold crossed
            if self.neurogenesis_triggers['high_stress_cycles'] > 5:
                self.add_thought("Feeling stressed for a while...")
        else:
            self.neurogenesis_triggers['high_stress_cycles'] = max(
                0,
                self.neurogenesis_triggers['high_stress_cycles'] - 0.5
            )
        
        # Reward tracking (positive outcomes like eating, playing)
        if self.recent_positive_outcome:
            self.neurogenesis_triggers['positive_outcomes'] = min(
                self.neurogenesis_triggers['positive_outcomes'] + 1,
                5  # Max cap
            )
            # Add thought about positive experience
            if random.random() < 0.3:  # 30% chance to comment
                self.add_thought("That was enjoyable!")
        else:
            # Gradual decay when no rewards
            self.neurogenesis_triggers['positive_outcomes'] = max(
                0,
                self.neurogenesis_triggers['positive_outcomes'] - 0.2
            )

        statistics = getattr(self.squid, 'statistics', None)
        if statistics:
            statistics.observe_neurogenesis_peaks(
                self.neurogenesis_triggers['novel_objects'],
                self.neurogenesis_triggers['high_stress_cycles'] / 10.0,
                self.neurogenesis_triggers['positive_outcomes'],
            )
        
        # Debug output if in debug mode
        if self.debug_mode:
            print(f"Neurogenesis triggers: {self.neurogenesis_triggers}")

    def track_action(self, action_name):
        """Track what the squid is doing"""
        self.recent_actions.append(action_name)
        if len(self.recent_actions) > 10:
            self.recent_actions.pop(0)
