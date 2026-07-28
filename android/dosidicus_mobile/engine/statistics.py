"""Lifetime statistics, mirroring the desktop ``statistics.json`` fields.

The Simulation feeds this per-tick (distance, sleep time, live neuron counts)
and on discrete events (eating, pooping, throwing, plant interactions, sickness,
neurogenesis). ``display_items`` returns the same labelled, ordered list the
desktop Statistics tab shows.
"""

from __future__ import annotations

# (key, human label) in the desktop's order.
DISPLAY = [
    ("squid_age_minutes", "Squid Age (min)"),
    ("distance_swam", "Distance Swam (pixels)"),
    ("cheese_eaten", "Cheese Eaten"),
    ("sushi_eaten", "Sushi Eaten"),
    ("poops_created", "Poops Created"),
    ("max_poops_cleaned", "Max Poops in Tank"),
    ("startles_experienced", "Times Startled"),
    ("ink_clouds_created", "Ink Clouds Created"),
    ("times_colour_changed", "Times Colour Changed"),
    ("rocks_thrown", "Rocks Thrown"),
    ("plants_interacted", "Plant Interactions"),
    ("total_sleep_time", "Total Sleep Time (s)"),
    ("sickness_episodes", "Sickness Episodes"),
    ("novelty_neurons_created", "Novelty Neurons Created"),
    ("stress_neurons_created", "Stress Neurons Created"),
    ("reward_neurons_created", "Reward Neurons Created"),
    ("max_neurons_reached", "Max Neurons Reached"),
    ("current_neurons", "Current Neurons"),
]

_FIELDS = [k for k, _ in DISPLAY] + ["squid_age_seconds"]


class Statistics:
    def __init__(self):
        for f in _FIELDS:
            setattr(self, f, 0)

    # -------------------------------------------------- per-tick accumulation
    def tick(self, dt, squid, brain, moved):
        self.squid_age_seconds = squid.age_seconds
        self.squid_age_minutes = int(squid.age_seconds // 60)
        self.distance_swam += moved
        if squid.is_sleeping:
            self.total_sleep_time += dt
        n = len(brain.neuron_names)
        self.current_neurons = n
        self.max_neurons_reached = max(self.max_neurons_reached, n)

    # -------------------------------------------------- discrete events
    def on_eat(self, food_type):
        if food_type == "cheese":
            self.cheese_eaten += 1
        else:
            self.sushi_eaten += 1

    def on_poop(self, poops_in_tank):
        self.poops_created += 1
        self.max_poops_cleaned = max(self.max_poops_cleaned, poops_in_tank)

    def on_rock_thrown(self):
        self.rocks_thrown += 1

    def on_plant_interaction(self):
        self.plants_interacted += 1

    def on_startle(self):
        self.startles_experienced += 1

    def on_ink_cloud(self):
        self.ink_clouds_created += 1

    def on_sickness(self):
        self.sickness_episodes += 1

    def on_neuron_born(self, kind):
        key = {"novelty": "novelty_neurons_created", "stress": "stress_neurons_created",
               "reward": "reward_neurons_created"}.get(kind)
        if key:
            setattr(self, key, getattr(self, key) + 1)

    # -------------------------------------------------- views / persistence
    def display_items(self):
        out = []
        for key, label in DISPLAY:
            val = getattr(self, key, 0)
            if key == "distance_swam":
                out.append((label, f"{int(val):,}"))
            elif key in ("total_sleep_time",):
                out.append((label, f"{val:.0f}"))
            else:
                out.append((label, str(int(val))))
        return out

    def to_dict(self):
        d = {k: getattr(self, k, 0) for k in _FIELDS}
        # desktop compatibility: it uses total_age_seconds
        d["total_age_seconds"] = self.squid_age_seconds
        return d

    @classmethod
    def from_dict(cls, data):
        s = cls()
        if data:
            for k in _FIELDS:
                if k in data:
                    setattr(s, k, data[k])
            if "total_age_seconds" in data and not data.get("squid_age_seconds"):
                s.squid_age_seconds = data["total_age_seconds"]
        return s
