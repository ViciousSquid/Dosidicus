"""Shared desktop achievement definitions with a mobile event adapter.

Definitions, localization keys and targets come from the actual desktop data.
Mobile lifecycle events update the same achievement IDs for save interchange.
"""

from __future__ import annotations

import time
from datetime import datetime

# Tier -> display colour (hex, used in the [color=] markup on cards).
TIER_COLORS = {1: "cd7f32", 2: "c0c0c0", 3: "ffd700", 4: "e5e4e2", 5: "b9f2ff"}
TIER_NAMES = {1: "Bronze", 2: "Silver", 3: "Gold", 4: "Platinum", 5: "Diamond"}

CATEGORY_ORDER = [
    "feeding", "neurogenesis", "sleep", "milestones", "cleaning", "health",
    "interaction", "exploration", "ink", "memory", "emotional", "secret", "meta",
]
CATEGORY_LABELS = {
    "feeding": "Feeding", "neurogenesis": "Neurogenesis", "sleep": "Sleep",
    "milestones": "Milestones", "cleaning": "Cleaning", "health": "Health",
    "interaction": "Interaction", "exploration": "Exploration", "ink": "Ink",
    "memory": "Memory", "emotional": "Emotional", "secret": "Secret", "meta": "Meta",
}

# Share the actual desktop definitions, including future additions and targets.
from . import shared
from plugins.achievements.achievements_data import ACHIEVEMENT_DEFINITIONS, Achievement
from src.localisation import loc

ACHIEVEMENTS = {key: Achievement(**dict(definition.to_dict(),
    name=loc(definition.name, default=definition.name),
    description=loc(definition.description, default=definition.description)))
    for key, definition in ACHIEVEMENT_DEFINITIONS.items()}
TOTAL_ACHIEVEMENTS = len(ACHIEVEMENTS)
TOTAL_VISIBLE = sum(1 for a in ACHIEVEMENTS.values() if not a.hidden)
MAX_POINTS = sum(a.points for a in ACHIEVEMENTS.values())


class AchievementManager:
    def __init__(self, on_unlock=None):
        self.on_unlock = on_unlock         # callback(Achievement) for a toast
        self.unlocked = {}                  # id -> ISO timestamp
        self.progress = {}                  # id -> current count
        self.counters = {}                  # raw event tallies
        # time-window tracking (wall-clock seconds)
        self._clean_high_since = None
        self._anxiety_low_since = None
        self._was_critical = False
        self._weekend_sat = False
        self._weekend_sun = False
        # memory-count baselines so evaluate() can spot new/promoted memories
        self._prev_mem_total = 0
        self._prev_long = 0

    # ------------------------------------------------------------- unlocking
    def _unlock(self, aid, silent=False):
        if aid in self.unlocked or aid not in ACHIEVEMENTS:
            return
        ach = ACHIEVEMENTS[aid]
        if ach.target_count > 1 and self.progress.get(aid, 0) < ach.target_count:
            return
        self.unlocked[aid] = datetime.now().isoformat(timespec="seconds")
        self.progress.setdefault(aid, ach.target_count)
        if not silent and self.on_unlock:
            try:
                self.on_unlock(ach)
            except Exception:
                pass

    def _count(self, name):
        self.counters[name] = self.counters.get(name, 0) + 1
        return self.counters[name]

    def _tiered(self, count, tiers):
        """tiers = [(threshold, achievement_id), ...] with threshold 1 for firsts."""
        for threshold, aid in tiers:
            if threshold > 1:
                self.progress[aid] = count
            if count >= threshold:
                self._unlock(aid)

    # --------------------------------------------------------------- events
    def on_feed(self):
        self._tiered(self._count("times_fed"), [
            (1, "first_feeding"), (10, "fed_10_times"), (50, "fed_50_times"),
            (100, "fed_100_times"), (500, "fed_500_times")])

    def on_medicine(self):
        self._tiered(self._count('times_medicine'), [(1, 'first_medicine'), (10, 'medicine_10_times')])

    def on_neuron_levelled(self, strength):
        self._unlock('first_neuron_levelup')
        if strength >= 4:
            self._unlock('neuron_max_level')

    def on_clean(self):
        self._tiered(self._count("times_cleaned"),
                     [(1, "first_clean"), (25, "cleaned_25_times")])

    def on_wake(self):
        self._tiered(self._count("times_slept"),
                     [(1, "first_sleep"), (10, "slept_10_times")])

    def on_sleep_consolidated(self):
        self._unlock("dream_state")     # REM analogue: memory replay on sleep

    def on_neuron_born(self):
        self._tiered(self._count("neurons_created"), [
            (1, "first_neuron"), (10, "neurons_10"), (50, "neurons_50"),
            (100, "neurons_100")])

    def on_rock_pickup(self):
        self._tiered(self._count("rocks_picked"), [
            (1, "first_rock_pickup"), (10, "rocks_picked_10"), (50, "rocks_picked_50")])
        self._investigate()

    def on_rock_throw(self):
        self._tiered(self._count("rocks_thrown"), [
            (1, "first_rock_throw"), (25, "rocks_thrown_25"), (100, "rocks_thrown_100")])

    def on_decoration_added(self):
        self._tiered(self._count("decorations_pushed"), [
            (1, "first_decoration_push"), (10, "decorations_pushed_10"),
            (50, "decorations_pushed_50")])
        self._investigate()

    def on_plant_interaction(self):
        self._tiered(self._count("plants_interacted"), [
            (1, "first_plant_interact"), (10, "plants_interacted_10"),
            (50, "plants_interacted_50")])
        self._investigate()

    def _investigate(self):
        self._tiered(self._count("objects_investigated"),
                     [(25, "objects_investigated_25"), (100, "objects_investigated_100")])

    def on_ink_cloud(self):
        self._tiered(self._count("ink_clouds"),
                     [(1, "first_ink_cloud"), (20, "ink_clouds_20")])

    def on_startle(self):
        self._tiered(self._count("times_startled"), [(1, "first_startle")])

    def on_fight(self):
        """A fight with a visitor was decided, won or lost."""
        self._tiered(self._count("fights"), [
            (1, "first_fight"), (5, "fights_5"), (20, "fights_20"), (50, "fights_50")])

    def on_brain_opened(self):
        self._unlock("brain_surgeon")

    # ------------------------------------------------------------ periodic
    def evaluate(self, squid, stats, now=None):
        """Threshold/time/age checks. Called ~once a second by the Simulation."""
        now = now or time.time()

        # Memories: infer forming/promotion from the running counts.
        short = len(squid.memory.short_term)
        long = len(squid.memory.long_term)
        total = short + long
        if total > self._prev_mem_total:
            self.counters["memories_formed"] = (
                self.counters.get("memories_formed", 0) + (total - self._prev_mem_total))
        self._prev_mem_total = total
        formed = self.counters.get("memories_formed", 0)
        self.progress["memories_50"] = formed
        if formed >= 1:
            self._unlock("first_memory")
        if formed >= 50:
            self._unlock("memories_50")
        if long > self._prev_long:
            self._unlock("memory_long_term")
        self._prev_long = long

        # Age milestones (age accrues while the squid is alive & playing).
        h = squid.age_seconds / 3600.0
        for thr, aid in [(1, "age_1_hour"), (10, "age_10_hours"), (24, "age_24_hours"),
                         (168, "age_1_week"), (720, "age_1_month")]:
            if h >= thr:
                self._unlock(aid)

        # Live stat peaks.
        if squid.happiness >= 100:
            self._unlock("happiness_100")
        if squid.curiosity >= 100:
            self._unlock("curiosity_100")
        if squid.anxiety >= 100:
            self._unlock("nervous_wreck")
        good = (squid.happiness >= 80 and squid.satisfaction >= 80
                and squid.cleanliness >= 80 and squid.curiosity >= 80
                and squid.hunger <= 30 and squid.anxiety <= 30 and squid.sleepiness <= 30)
        if good:
            self._unlock("all_stats_high")

        # Sickness recovery (mobile analogue of low-health -> full).
        if squid.is_sick:
            self._was_critical = True
        elif self._was_critical and squid.happiness >= 80 and squid.cleanliness >= 80:
            self._unlock("comeback_kid")
            self._was_critical = False

        # Sustained-cleanliness / sustained-calm windows.
        self._clean_high_since = self._window(
            self._clean_high_since, squid.cleanliness >= 90, now, 3600, "germaphobe")
        self._anxiety_low_since = self._window(
            self._anxiety_low_since, squid.anxiety < 10, now, 1800, "zen_master")

        # Time-of-day / weekend (real clock, like the desktop).
        hour = datetime.now().hour
        if 0 <= hour < 4:
            self._unlock("night_owl")
        if 5 <= hour < 7:
            self._unlock("early_bird")
        weekday = datetime.now().weekday()
        if weekday == 5:
            self._weekend_sat = True
        elif weekday == 6:
            self._weekend_sun = True
        if self._weekend_sat and self._weekend_sun:
            self._unlock("weekend_warrior")

        # Completionist: 30 others unlocked.
        if "completionist" not in self.unlocked and len(self.unlocked) >= 30:
            self._unlock("completionist")

    def _window(self, since, condition, now, duration, aid):
        if condition:
            if since is None:
                return now
            if now - since >= duration:
                self._unlock(aid)
            return since
        return None

    # --------------------------------------------------------------- views
    def total_points(self):
        return sum(ACHIEVEMENTS[a].points for a in self.unlocked if a in ACHIEVEMENTS)

    def summary(self):
        return (self.total_points(), len(self.unlocked), TOTAL_VISIBLE, MAX_POINTS)

    def items(self, category=None):
        """Ordered list of {ach, unlocked, progress} for the UI (hidden+locked
        achievements are omitted, matching the desktop)."""
        out = []
        for aid, ach in ACHIEVEMENTS.items():
            if category and ach.category != category:
                continue
            unlocked = aid in self.unlocked
            if ach.hidden and not unlocked:
                continue
            out.append({"ach": ach, "unlocked": unlocked,
                        "progress": min(self.progress.get(aid, 0), ach.target_count)})
        # Unlocked first, then by category order, then by tier.
        out.sort(key=lambda x: (not x["unlocked"],
                                CATEGORY_ORDER.index(x["ach"].category),
                                x["ach"].tier))
        return out

    # ------------------------------------------------------------ persistence
    def to_dict(self):
        return {
            "unlocked": dict(self.unlocked),
            "progress": dict(self.progress),
            "counters": dict(self.counters),
            "tracking": {"weekend_saturday": self._weekend_sat,
                         "weekend_sunday": self._weekend_sun},
        }

    @classmethod
    def from_dict(cls, data, on_unlock=None):
        m = cls(on_unlock=on_unlock)
        if not data:
            return m
        # Accept both our shape and a desktop achievements.json ("statistics").
        m.unlocked = {k: (v.get("unlocked_at") if isinstance(v, dict) else v)
                      for k, v in data.get("unlocked", {}).items()}
        m.progress = dict(data.get("progress", {}))
        m.counters = dict(data.get("counters", data.get("statistics", {})))
        tracking = data.get("tracking", {})
        m._weekend_sat = tracking.get("weekend_saturday", False)
        m._weekend_sun = tracking.get("weekend_sunday", False)
        return m
