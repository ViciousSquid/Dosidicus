"""Achievements - a faithful mobile port of the desktop achievements plugin.

The definitions (id, name, description, icon, category, tier, points,
target_count, hidden) mirror ``plugins/achievements/achievements_data.py`` so a
mobile squid earns the same 56 trophies a desktop one does. The
``AchievementManager`` is the GUI-free analogue of ``AchievementsPlugin``: the
Simulation calls event methods (feed, clean, neuron_born, rock_throw, ...) and a
periodic ``evaluate`` inspects the squid's live stats and age for the
threshold/time-based ones. State is JSON-serialisable and rides along in the
save (and the exported achievements.json).

A few desktop achievements depend on mechanics the mobile MVP doesn't have
(medicine, neuron level-ups, poop-throwing, a variable simulation speed); those
stay locked, exactly as they would on desktop with those hooks absent.
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

# (id, name, description, icon, category, points, tier, target_count, hidden)
_DEFS = [
    # Feeding
    ("first_feeding", "First Bite", "Feed the squid for the first time", "🍽️", "feeding", 10, 1, 1, False),
    ("fed_10_times", "Regular Meals", "Feed the squid 10 times", "🥄", "feeding", 15, 1, 10, False),
    ("fed_50_times", "Dedicated Caretaker", "Feed the squid 50 times", "🍴", "feeding", 25, 2, 50, False),
    ("fed_100_times", "Master Chef", "Feed the squid 100 times", "👨‍🍳", "feeding", 50, 3, 100, False),
    ("fed_500_times", "Culinary Legend", "Feed the squid 500 times", "🌟", "feeding", 100, 4, 500, True),
    # Neurogenesis
    ("first_neuron", "Brain Spark", "Create the first neurogenesis neuron", "🧠", "neurogenesis", 20, 1, 1, False),
    ("neurons_10", "Neural Network", "Create 10 neurons through neurogenesis", "🔮", "neurogenesis", 30, 2, 10, False),
    ("neurons_50", "Expanding Mind", "Create 50 neurons through neurogenesis", "💫", "neurogenesis", 50, 3, 50, False),
    ("neurons_100", "Cerebral Powerhouse", "Create 100 neurons through neurogenesis", "🌌", "neurogenesis", 75, 4, 100, True),
    ("first_neuron_levelup", "Strengthened Synapse", "Level up a neuron for the first time", "⚡", "neurogenesis", 15, 1, 1, False),
    ("neuron_max_level", "Peak Performance", "Level a neuron to maximum strength", "🌠", "neurogenesis", 40, 3, 1, False),
    # Sleep
    ("first_sleep", "Sweet Dreams", "The squid wakes from its first sleep", "😴", "sleep", 10, 1, 1, False),
    ("slept_10_times", "Well Rested", "The squid has slept 10 times", "🛏️", "sleep", 20, 2, 10, False),
    ("dream_state", "Deep Dreamer", "Squid entered REM sleep", "💭", "sleep", 25, 2, 1, True),
    # Milestones
    ("age_1_hour", "One Hour Old", "Squid reached 1 hour old", "⏰", "milestones", 15, 1, 1, False),
    ("age_10_hours", "Growing Up", "Squid reached 10 hours old", "📅", "milestones", 30, 2, 1, False),
    ("age_24_hours", "One Day Wonder", "Squid survived for 24 hours", "🎂", "milestones", 50, 3, 1, False),
    ("age_1_week", "Week Veteran", "Squid has lived for one week", "🏅", "milestones", 100, 4, 1, True),
    ("age_1_month", "Month Veteran", "Squid has lived for one month", "🎖️", "milestones", 150, 5, 1, True),
    ("happiness_100", "Pure Bliss", "Reach 100% happiness", "😄", "milestones", 20, 2, 1, False),
    ("all_stats_high", "Perfect Balance", "All stats above 80% simultaneously", "⚖️", "milestones", 40, 3, 1, False),
    # Cleaning
    ("first_clean", "First Scrub", "Clean the tank for the first time", "🧼", "cleaning", 10, 1, 1, False),
    ("cleaned_25_times", "Spotless Environment", "Clean the tank 25 times", "✨", "cleaning", 25, 2, 25, False),
    ("germaphobe", "Germaphobe", "Keep cleanliness above 90% for 1 hour straight", "🧹", "cleaning", 30, 2, 1, False),
    # Health
    ("first_medicine", "First Aid", "Give medicine for the first time", "💊", "health", 10, 1, 1, False),
    ("medicine_10_times", "Doctor Squid", "Give medicine 10 times", "🩺", "health", 20, 2, 10, False),
    ("comeback_kid", "Comeback Kid", "Recover from critically low health (<20%) to full", "💪", "health", 40, 3, 1, True),
    # Interaction - rocks
    ("first_rock_pickup", "Rock Collector", "Pick up a rock for the first time", "🪨", "interaction", 10, 1, 1, False),
    ("rocks_picked_10", "Stone Gatherer", "Pick up 10 rocks", "⛰️", "interaction", 15, 1, 10, False),
    ("rocks_picked_50", "Boulder Hoarder", "Pick up 50 rocks", "🏔️", "interaction", 30, 2, 50, False),
    ("first_rock_throw", "Skipping Stones", "Throw a rock for the first time", "🎯", "interaction", 10, 1, 1, False),
    ("rocks_thrown_25", "Rock Launcher", "Throw 25 rocks", "🚀", "interaction", 20, 2, 25, False),
    ("rocks_thrown_100", "Catapult Master", "Throw 100 rocks", "💨", "interaction", 40, 3, 100, True),
    # Interaction - plants & decorations
    ("first_decoration_push", "Interior Decorator", "Push a decoration for the first time", "🪴", "interaction", 10, 1, 1, False),
    ("decorations_pushed_10", "Furniture Mover", "Push decorations 10 times", "🏠", "interaction", 15, 1, 10, False),
    ("decorations_pushed_50", "Feng Shui Master", "Push decorations 50 times", "🎨", "interaction", 30, 2, 50, False),
    ("first_plant_interact", "Green Thumb", "Interact with a plant for the first time", "🌱", "interaction", 10, 1, 1, False),
    ("plants_interacted_10", "Garden Explorer", "Interact with plants 10 times", "🌿", "interaction", 15, 1, 10, False),
    ("plants_interacted_50", "Botanist", "Interact with plants 50 times", "🌳", "interaction", 30, 2, 50, False),
    ("objects_investigated_25", "Curious Inspector", "Investigate 25 different objects", "🔍", "interaction", 25, 2, 25, False),
    ("objects_investigated_100", "Master Detective", "Investigate 100 different objects", "🕵️", "interaction", 50, 3, 100, False),
    # Exploration - poop
    ("first_poop_throw", "Mischief Maker", "Squid threw a poop for the first time", "💩", "exploration", 10, 1, 1, False),
    # Ink
    ("first_ink_cloud", "Smoke Screen", "Squid releases ink cloud for the first time", "🖤", "ink", 15, 1, 1, False),
    ("ink_clouds_20", "Ink Master", "Release 20 ink clouds", "🌫️", "ink", 25, 2, 20, False),
    # Memory
    ("first_memory", "First Memory", "Form the first memory", "💾", "memory", 15, 1, 1, False),
    ("memory_long_term", "Long Term Thinking", "Promote a memory to long-term storage", "🗄️", "memory", 25, 2, 1, False),
    ("memories_50", "Photographic Memory", "Have 50 memories stored", "📚", "memory", 40, 3, 50, False),
    # Emotional
    ("curiosity_100", "Curious George", "Curiosity reaches 100%", "🤔", "emotional", 15, 1, 1, False),
    ("zen_master", "Zen Master", "Keep anxiety below 10% for 30 minutes", "🧘", "emotional", 30, 2, 1, False),
    ("first_startle", "Startled!", "Startle the squid for the first time", "😱", "emotional", 10, 1, 1, False),
    ("nervous_wreck", "Nervous Wreck", "Anxiety reaches 100%", "😰", "emotional", 15, 2, 1, True),
    # Secret
    ("night_owl", "Night Owl", "Play between midnight and 4 AM", "🦉", "secret", 15, 2, 1, True),
    ("early_bird", "Early Bird", "Play between 5 AM and 7 AM", "🐦", "secret", 15, 2, 1, True),
    ("weekend_warrior", "Weekend Warrior", "Play on both Saturday and Sunday", "🗓️", "secret", 20, 2, 1, True),
    # Meta
    ("brain_surgeon", "Brain Surgeon", "Open the brain visualization tool", "🔬", "meta", 10, 1, 1, False),
    ("speed_demon", "Speed Demon", "Run simulation at max speed for 10 minutes", "⏩", "meta", 15, 2, 1, False),
    ("completionist", "Completionist", "Unlock 30 other achievements", "🏆", "meta", 100, 4, 1, True),
]


class Achievement:
    __slots__ = ("id", "name", "description", "icon", "category", "points",
                 "tier", "target_count", "hidden")

    def __init__(self, id, name, description, icon, category, points, tier,
                 target_count, hidden):
        self.id = id
        self.name = name
        self.description = description
        self.icon = icon
        self.category = category
        self.points = points
        self.tier = tier
        self.target_count = target_count
        self.hidden = hidden


ACHIEVEMENTS = {d[0]: Achievement(*d) for d in _DEFS}
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
