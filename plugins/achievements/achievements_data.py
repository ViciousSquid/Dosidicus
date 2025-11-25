# File: achievements_data.py
# All achievement definitions for the Achievements Plugin
# Separated from main.py for cleaner organization

from dataclasses import dataclass, asdict
from typing import Dict
from enum import Enum


# =============================================================================
# ENUMS AND DATA CLASSES
# =============================================================================

class AchievementCategory(Enum):
    FEEDING = "feeding"
    NEUROGENESIS = "neurogenesis"
    SLEEP = "sleep"
    MILESTONES = "milestones"
    EXPLORATION = "exploration"
    CLEANING = "cleaning"
    HEALTH = "health"
    INTERACTION = "interaction"
    INK = "ink"
    MEMORY = "memory"
    EMOTIONAL = "emotional"
    SECRET = "secret"
    META = "meta"


@dataclass
class Achievement:
    id: str
    name: str
    description: str
    icon: str = "🏆"
    category: str = "milestones"
    hidden: bool = False
    points: int = 10
    tier: int = 1
    target_count: int = 1

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class UnlockedAchievement:
    achievement_id: str
    unlocked_at: str
    progress: int = 0
    notified: bool = False

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> 'UnlockedAchievement':
        return cls(**data)


# Tier colors for UI
TIER_COLORS = {
    1: "#CD7F32",  # Bronze
    2: "#C0C0C0",  # Silver
    3: "#FFD700",  # Gold
    4: "#E5E4E2",  # Platinum
    5: "#B9F2FF",  # Diamond
}


# =============================================================================
# ALL ACHIEVEMENT DEFINITIONS (50+ achievements)
# =============================================================================

ACHIEVEMENT_DEFINITIONS: Dict[str, Achievement] = {
    
    # =========================================================================
    # FEEDING CATEGORY (5)
    # =========================================================================
    "first_feeding": Achievement(
        id="first_feeding", 
        name="First Bite",
        description="Feed the squid for the first time",
        icon="🍽️", category="feeding", points=10, tier=1,
    ),
    "fed_10_times": Achievement(
        id="fed_10_times", 
        name="Regular Meals",
        description="Feed the squid 10 times",
        icon="🥄", category="feeding", points=15, tier=1, target_count=10,
    ),
    "fed_50_times": Achievement(
        id="fed_50_times", 
        name="Dedicated Caretaker",
        description="Feed the squid 50 times",
        icon="🍴", category="feeding", points=25, tier=2, target_count=50,
    ),
    "fed_100_times": Achievement(
        id="fed_100_times", 
        name="Master Chef",
        description="Feed the squid 100 times",
        icon="👨‍🍳", category="feeding", points=50, tier=3, target_count=100,
    ),
    "fed_500_times": Achievement(
        id="fed_500_times", 
        name="Culinary Legend",
        description="Feed the squid 500 times",
        icon="🌟", category="feeding", points=100, tier=4, target_count=500, hidden=True,
    ),

    # =========================================================================
    # NEUROGENESIS CATEGORY (6)
    # =========================================================================
    "first_neuron": Achievement(
        id="first_neuron", 
        name="Brain Spark",
        description="Create the first neurogenesis neuron",
        icon="🧠", category="neurogenesis", points=20, tier=1,
    ),
    "neurons_10": Achievement(
        id="neurons_10", 
        name="Neural Network",
        description="Create 10 neurons through neurogenesis",
        icon="🔮", category="neurogenesis", points=30, tier=2, target_count=10,
    ),
    "neurons_50": Achievement(
        id="neurons_50", 
        name="Expanding Mind",
        description="Create 50 neurons through neurogenesis",
        icon="💫", category="neurogenesis", points=50, tier=3, target_count=50,
    ),
    "neurons_100": Achievement(
        id="neurons_100", 
        name="Cerebral Powerhouse",
        description="Create 100 neurons through neurogenesis",
        icon="🌌", category="neurogenesis", points=75, tier=4, target_count=100, hidden=True,
    ),
    "first_neuron_levelup": Achievement(
        id="first_neuron_levelup", 
        name="Strengthened Synapse",
        description="Level up a neuron for the first time",
        icon="⚡", category="neurogenesis", points=15, tier=1,
    ),
    "neuron_max_level": Achievement(
        id="neuron_max_level", 
        name="Peak Performance",
        description="Level a neuron to maximum strength",
        icon="🌠", category="neurogenesis", points=40, tier=3,
    ),

    # =========================================================================
    # SLEEP CATEGORY (3)
    # =========================================================================
    "first_sleep": Achievement(
        id="first_sleep", 
        name="Sweet Dreams",
        description="The squid wakes from its first sleep",
        icon="😴", category="sleep", points=10, tier=1,
    ),
    "slept_10_times": Achievement(
        id="slept_10_times", 
        name="Well Rested",
        description="The squid has slept 10 times",
        icon="🛏️", category="sleep", points=20, tier=2, target_count=10,
    ),
    "dream_state": Achievement(
        id="dream_state", 
        name="Deep Dreamer",
        description="Squid entered REM sleep",
        icon="💭", category="sleep", points=25, tier=2, hidden=True,
    ),

    # =========================================================================
    # MILESTONES CATEGORY (6)
    # =========================================================================
    "age_1_hour": Achievement(
        id="age_1_hour", 
        name="One Hour Old",
        description="Squid reached 1 hour old",
        icon="⏰", category="milestones", points=15, tier=1,
    ),
    "age_10_hours": Achievement(
        id="age_10_hours", 
        name="Growing Up",
        description="Squid reached 10 hours old",
        icon="📅", category="milestones", points=30, tier=2,
    ),
    "age_24_hours": Achievement(
        id="age_24_hours", 
        name="One Day Wonder",
        description="Squid survived for 24 hours",
        icon="🎂", category="milestones", points=50, tier=3,
    ),
    "age_1_week": Achievement(
        id="age_1_week", 
        name="Week Veteran",
        description="Squid has lived for one week",
        icon="🏅", category="milestones", points=100, tier=4, hidden=True,
    ),
    "age_1_month": Achievement(
        id="age_1_month", 
        name="Month Veteran",
        description="Squid has lived for one month",
        icon="🎖️", category="milestones", points=150, tier=5, hidden=True,
    ),
    "happiness_100": Achievement(
        id="happiness_100", 
        name="Pure Bliss",
        description="Reach 100% happiness",
        icon="😄", category="milestones", points=20, tier=2,
    ),
    "all_stats_high": Achievement(
        id="all_stats_high", 
        name="Perfect Balance",
        description="All stats above 80% simultaneously",
        icon="⚖️", category="milestones", points=40, tier=3,
    ),

    # =========================================================================
    # CLEANING CATEGORY (3) - NEW
    # =========================================================================
    "first_clean": Achievement(
        id="first_clean", 
        name="First Scrub",
        description="Clean the tank for the first time",
        icon="🧼", category="cleaning", points=10, tier=1,
    ),
    "cleaned_25_times": Achievement(
        id="cleaned_25_times", 
        name="Spotless Environment",
        description="Clean the tank 25 times",
        icon="✨", category="cleaning", points=25, tier=2, target_count=25,
    ),
    "germaphobe": Achievement(
        id="germaphobe", 
        name="Germaphobe",
        description="Keep cleanliness above 90% for 1 hour straight",
        icon="🧹", category="cleaning", points=30, tier=2,
    ),

    # =========================================================================
    # HEALTH CATEGORY (3) - NEW
    # =========================================================================
    "first_medicine": Achievement(
        id="first_medicine", 
        name="First Aid",
        description="Give medicine for the first time",
        icon="💊", category="health", points=10, tier=1,
    ),
    "medicine_10_times": Achievement(
        id="medicine_10_times", 
        name="Doctor Squid",
        description="Give medicine 10 times",
        icon="🩺", category="health", points=20, tier=2, target_count=10,
    ),
    "comeback_kid": Achievement(
        id="comeback_kid", 
        name="Comeback Kid",
        description="Recover from critically low health (<20%) to full",
        icon="💪", category="health", points=40, tier=3, hidden=True,
    ),

    # =========================================================================
    # INTERACTION - ROCKS (6) - EXPANDED
    # =========================================================================
    "first_rock_pickup": Achievement(
        id="first_rock_pickup", 
        name="Rock Collector",
        description="Pick up a rock for the first time",
        icon="🪨", category="interaction", points=10, tier=1,
    ),
    "rocks_picked_10": Achievement(
        id="rocks_picked_10", 
        name="Stone Gatherer",
        description="Pick up 10 rocks",
        icon="⛰️", category="interaction", points=15, tier=1, target_count=10,
    ),
    "rocks_picked_50": Achievement(
        id="rocks_picked_50", 
        name="Boulder Hoarder",
        description="Pick up 50 rocks",
        icon="🏔️", category="interaction", points=30, tier=2, target_count=50,
    ),
    "first_rock_throw": Achievement(
        id="first_rock_throw", 
        name="Skipping Stones",
        description="Throw a rock for the first time",
        icon="🎯", category="interaction", points=10, tier=1,
    ),
    "rocks_thrown_25": Achievement(
        id="rocks_thrown_25", 
        name="Rock Launcher",
        description="Throw 25 rocks",
        icon="🚀", category="interaction", points=20, tier=2, target_count=25,
    ),
    "rocks_thrown_100": Achievement(
        id="rocks_thrown_100", 
        name="Catapult Master",
        description="Throw 100 rocks",
        icon="💨", category="interaction", points=40, tier=3, target_count=100, hidden=True,
    ),

    # =========================================================================
    # INTERACTION - PLANTS & DECORATIONS (8) - EXPANDED
    # =========================================================================
    "first_decoration_push": Achievement(
        id="first_decoration_push", 
        name="Interior Decorator",
        description="Push a decoration for the first time",
        icon="🪴", category="interaction", points=10, tier=1,
    ),
    "decorations_pushed_10": Achievement(
        id="decorations_pushed_10", 
        name="Furniture Mover",
        description="Push decorations 10 times",
        icon="🏠", category="interaction", points=15, tier=1, target_count=10,
    ),
    "decorations_pushed_50": Achievement(
        id="decorations_pushed_50", 
        name="Feng Shui Master",
        description="Push decorations 50 times",
        icon="🎨", category="interaction", points=30, tier=2, target_count=50,
    ),
    "first_plant_interact": Achievement(
        id="first_plant_interact", 
        name="Green Thumb",
        description="Interact with a plant for the first time",
        icon="🌱", category="interaction", points=10, tier=1,
    ),
    "plants_interacted_10": Achievement(
        id="plants_interacted_10", 
        name="Garden Explorer",
        description="Interact with plants 10 times",
        icon="🌿", category="interaction", points=15, tier=1, target_count=10,
    ),
    "plants_interacted_50": Achievement(
        id="plants_interacted_50", 
        name="Botanist",
        description="Interact with plants 50 times",
        icon="🌳", category="interaction", points=30, tier=2, target_count=50,
    ),
    "objects_investigated_25": Achievement(
        id="objects_investigated_25", 
        name="Curious Inspector",
        description="Investigate 25 different objects",
        icon="🔍", category="interaction", points=25, tier=2, target_count=25,
    ),
    "objects_investigated_100": Achievement(
        id="objects_investigated_100", 
        name="Master Detective",
        description="Investigate 100 different objects",
        icon="🕵️", category="interaction", points=50, tier=3, target_count=100,
    ),

    # =========================================================================
    # EXPLORATION - POOP (1)
    # =========================================================================
    "first_poop_throw": Achievement(
        id="first_poop_throw", 
        name="Mischief Maker",
        description="Squid threw a poop for the first time",
        icon="💩", category="exploration", points=10, tier=1,
    ),

    # =========================================================================
    # INK CATEGORY (2) - NEW
    # =========================================================================
    "first_ink_cloud": Achievement(
        id="first_ink_cloud", 
        name="Smoke Screen",
        description="Squid releases ink cloud for the first time",
        icon="🖤", category="ink", points=15, tier=1,
    ),
    "ink_clouds_20": Achievement(
        id="ink_clouds_20", 
        name="Ink Master",
        description="Release 20 ink clouds",
        icon="🌫️", category="ink", points=25, tier=2, target_count=20,
    ),

    # =========================================================================
    # MEMORY CATEGORY (3) - NEW
    # =========================================================================
    "first_memory": Achievement(
        id="first_memory", 
        name="First Memory",
        description="Form the first memory",
        icon="💾", category="memory", points=15, tier=1,
    ),
    "memory_long_term": Achievement(
        id="memory_long_term", 
        name="Long Term Thinking",
        description="Promote a memory to long-term storage",
        icon="🗄️", category="memory", points=25, tier=2,
    ),
    "memories_50": Achievement(
        id="memories_50", 
        name="Photographic Memory",
        description="Have 50 memories stored",
        icon="📚", category="memory", points=40, tier=3, target_count=50,
    ),

    # =========================================================================
    # EMOTIONAL CATEGORY (4) - NEW
    # =========================================================================
    "curiosity_100": Achievement(
        id="curiosity_100", 
        name="Curious George",
        description="Curiosity reaches 100%",
        icon="🤔", category="emotional", points=15, tier=1,
    ),
    "zen_master": Achievement(
        id="zen_master", 
        name="Zen Master",
        description="Keep anxiety below 10% for 30 minutes",
        icon="🧘", category="emotional", points=30, tier=2,
    ),
    "first_startle": Achievement(
        id="first_startle", 
        name="Startled!",
        description="Startle the squid for the first time",
        icon="😱", category="emotional", points=10, tier=1,
    ),
    "nervous_wreck": Achievement(
        id="nervous_wreck", 
        name="Nervous Wreck",
        description="Anxiety reaches 100%",
        icon="😰", category="emotional", points=15, tier=2, hidden=True,
    ),

    # =========================================================================
    # SECRET CATEGORY (3)
    # =========================================================================
    "night_owl": Achievement(
        id="night_owl", 
        name="Night Owl",
        description="Play between midnight and 4 AM",
        icon="🦉", category="secret", points=15, tier=2, hidden=True,
    ),
    "early_bird": Achievement(
        id="early_bird", 
        name="Early Bird",
        description="Play between 5 AM and 7 AM",
        icon="🐦", category="secret", points=15, tier=2, hidden=True,
    ),
    "weekend_warrior": Achievement(
        id="weekend_warrior", 
        name="Weekend Warrior",
        description="Play on both Saturday and Sunday",
        icon="🗓️", category="secret", points=20, tier=2, hidden=True,
    ),

    # =========================================================================
    # META CATEGORY (2) - NEW
    # =========================================================================
    "brain_surgeon": Achievement(
        id="brain_surgeon", 
        name="Brain Surgeon",
        description="Open the brain visualization tool",
        icon="🔬", category="meta", points=10, tier=1,
    ),
    "speed_demon": Achievement(
        id="speed_demon", 
        name="Speed Demon",
        description="Run simulation at max speed for 10 minutes",
        icon="⏩", category="meta", points=15, tier=2,
    ),
    "completionist": Achievement(
        id="completionist", 
        name="Completionist",
        description="Unlock 30 other achievements",
        icon="🏆", category="meta", points=100, tier=4, hidden=True,
    ),
}


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_achievement(achievement_id: str) -> Achievement | None:
    """Get an achievement by ID"""
    return ACHIEVEMENT_DEFINITIONS.get(achievement_id)


def get_achievements_by_category(category: str) -> Dict[str, Achievement]:
    """Get all achievements in a specific category"""
    return {
        aid: ach for aid, ach in ACHIEVEMENT_DEFINITIONS.items()
        if ach.category == category
    }


def get_visible_achievements() -> Dict[str, Achievement]:
    """Get all non-hidden achievements"""
    return {
        aid: ach for aid, ach in ACHIEVEMENT_DEFINITIONS.items()
        if not ach.hidden
    }


def get_total_points() -> int:
    """Get total possible points from all achievements"""
    return sum(ach.points for ach in ACHIEVEMENT_DEFINITIONS.values())


def get_achievement_count() -> int:
    """Get total number of achievements"""
    return len(ACHIEVEMENT_DEFINITIONS)
