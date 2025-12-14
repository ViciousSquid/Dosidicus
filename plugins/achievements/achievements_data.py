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
    name: str # Now stores the localisation KEY
    description: str # Now stores the localisation KEY
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
        name="ach_first_feeding_name",
        description="ach_first_feeding_desc",
        icon="🍽️", category="feeding", points=10, tier=1,
    ),
    "fed_10_times": Achievement(
        id="fed_10_times", 
        name="ach_fed_10_times_name",
        description="ach_fed_10_times_desc",
        icon="🥄", category="feeding", points=15, tier=1, target_count=10,
    ),
    "fed_50_times": Achievement(
        id="fed_50_times", 
        name="ach_fed_50_times_name",
        description="ach_fed_50_times_desc",
        icon="🍴", category="feeding", points=25, tier=2, target_count=50,
    ),
    "fed_100_times": Achievement(
        id="fed_100_times", 
        name="ach_fed_100_times_name",
        description="ach_fed_100_times_desc",
        icon="👨‍🍳", category="feeding", points=50, tier=3, target_count=100,
    ),
    "fed_500_times": Achievement(
        id="fed_500_times", 
        name="ach_fed_500_times_name",
        description="ach_fed_500_times_desc",
        icon="🌟", category="feeding", points=100, tier=4, target_count=500, hidden=True,
    ),

    # =========================================================================
    # NEUROGENESIS CATEGORY (6)
    # =========================================================================
    "first_neuron": Achievement(
        id="first_neuron", 
        name="ach_first_neuron_name",
        description="ach_first_neuron_desc",
        icon="🧠", category="neurogenesis", points=20, tier=1,
    ),
    "neurons_10": Achievement(
        id="neurons_10", 
        name="ach_neurons_10_name",
        description="ach_neurons_10_desc",
        icon="🔮", category="neurogenesis", points=30, tier=2, target_count=10,
    ),
    "neurons_50": Achievement(
        id="neurons_50", 
        name="ach_neurons_50_name",
        description="ach_neurons_50_desc",
        icon="💫", category="neurogenesis", points=50, tier=3, target_count=50,
    ),
    "neurons_100": Achievement(
        id="neurons_100", 
        name="ach_neurons_100_name",
        description="ach_neurons_100_desc",
        icon="🌌", category="neurogenesis", points=75, tier=4, target_count=100, hidden=True,
    ),
    "first_neuron_levelup": Achievement(
        id="first_neuron_levelup", 
        name="ach_first_neuron_levelup_name",
        description="ach_first_neuron_levelup_desc",
        icon="⚡", category="neurogenesis", points=15, tier=1,
    ),
    "neuron_max_level": Achievement(
        id="neuron_max_level", 
        name="ach_neuron_max_level_name",
        description="ach_neuron_max_level_desc",
        icon="🌠", category="neurogenesis", points=40, tier=3,
    ),

    # =========================================================================
    # SLEEP CATEGORY (3)
    # =========================================================================
    "first_sleep": Achievement(
        id="first_sleep", 
        name="ach_first_sleep_name",
        description="ach_first_sleep_desc",
        icon="😴", category="sleep", points=10, tier=1,
    ),
    "slept_10_times": Achievement(
        id="slept_10_times", 
        name="ach_slept_10_times_name",
        description="ach_slept_10_times_desc",
        icon="🛏️", category="sleep", points=20, tier=2, target_count=10,
    ),
    "dream_state": Achievement(
        id="dream_state", 
        name="ach_dream_state_name",
        description="ach_dream_state_desc",
        icon="💭", category="sleep", points=25, tier=2, hidden=True,
    ),

    # =========================================================================
    # MILESTONES CATEGORY (6)
    # =========================================================================
    "age_1_hour": Achievement(
        id="age_1_hour", 
        name="ach_age_1_hour_name",
        description="ach_age_1_hour_desc",
        icon="⏰", category="milestones", points=15, tier=1,
    ),
    "age_10_hours": Achievement(
        id="age_10_hours", 
        name="ach_age_10_hours_name",
        description="ach_age_10_hours_desc",
        icon="📅", category="milestones", points=30, tier=2,
    ),
    "age_24_hours": Achievement(
        id="age_24_hours", 
        name="ach_age_24_hours_name",
        description="ach_age_24_hours_desc",
        icon="🎂", category="milestones", points=50, tier=3,
    ),
    "age_1_week": Achievement(
        id="age_1_week", 
        name="ach_age_1_week_name",
        description="ach_age_1_week_desc",
        icon="🏅", category="milestones", points=100, tier=4, hidden=True,
    ),
    "age_1_month": Achievement(
        id="age_1_month", 
        name="ach_age_1_month_name",
        description="ach_age_1_month_desc",
        icon="🎖️", category="milestones", points=150, tier=5, hidden=True,
    ),
    "happiness_100": Achievement(
        id="happiness_100", 
        name="ach_happiness_100_name",
        description="ach_happiness_100_desc",
        icon="😄", category="milestones", points=20, tier=2,
    ),
    "all_stats_high": Achievement(
        id="all_stats_high", 
        name="ach_all_stats_high_name",
        description="ach_all_stats_high_desc",
        icon="⚖️", category="milestones", points=40, tier=3,
    ),

    # =========================================================================
    # CLEANING CATEGORY (3)
    # =========================================================================
    "first_clean": Achievement(
        id="first_clean", 
        name="ach_first_clean_name",
        description="ach_first_clean_desc",
        icon="🧼", category="cleaning", points=10, tier=1,
    ),
    "cleaned_25_times": Achievement(
        id="cleaned_25_times", 
        name="ach_cleaned_25_times_name",
        description="ach_cleaned_25_times_desc",
        icon="✨", category="cleaning", points=25, tier=2, target_count=25,
    ),
    "germaphobe": Achievement(
        id="germaphobe", 
        name="ach_germaphobe_name",
        description="ach_germaphobe_desc",
        icon="🧹", category="cleaning", points=30, tier=2,
    ),

    # =========================================================================
    # HEALTH CATEGORY (3)
    # =========================================================================
    "first_medicine": Achievement(
        id="first_medicine", 
        name="ach_first_medicine_name",
        description="ach_first_medicine_desc",
        icon="💊", category="health", points=10, tier=1,
    ),
    "medicine_10_times": Achievement(
        id="medicine_10_times", 
        name="ach_medicine_10_times_name",
        description="ach_medicine_10_times_desc",
        icon="🩺", category="health", points=20, tier=2, target_count=10,
    ),
    "comeback_kid": Achievement(
        id="comeback_kid", 
        name="ach_comeback_kid_name",
        description="ach_comeback_kid_desc",
        icon="💪", category="health", points=40, tier=3, hidden=True,
    ),

    # =========================================================================
    # INTERACTION - ROCKS (6)
    # =========================================================================
    "first_rock_pickup": Achievement(
        id="first_rock_pickup", 
        name="ach_first_rock_pickup_name",
        description="ach_first_rock_pickup_desc",
        icon="🪨", category="interaction", points=10, tier=1,
    ),
    "rocks_picked_10": Achievement(
        id="rocks_picked_10", 
        name="ach_rocks_picked_10_name",
        description="ach_rocks_picked_10_desc",
        icon="⛰️", category="interaction", points=15, tier=1, target_count=10,
    ),
    "rocks_picked_50": Achievement(
        id="rocks_picked_50", 
        name="ach_rocks_picked_50_name",
        description="ach_rocks_picked_50_desc",
        icon="🏔️", category="interaction", points=30, tier=2, target_count=50,
    ),
    "first_rock_throw": Achievement(
        id="first_rock_throw", 
        name="ach_first_rock_throw_name",
        description="ach_first_rock_throw_desc",
        icon="🎯", category="interaction", points=10, tier=1,
    ),
    "rocks_thrown_25": Achievement(
        id="rocks_thrown_25", 
        name="ach_rocks_thrown_25_name",
        description="ach_rocks_thrown_25_desc",
        icon="🚀", category="interaction", points=20, tier=2, target_count=25,
    ),
    "rocks_thrown_100": Achievement(
        id="rocks_thrown_100", 
        name="ach_rocks_thrown_100_name",
        description="ach_rocks_thrown_100_desc",
        icon="💨", category="interaction", points=40, tier=3, target_count=100, hidden=True,
    ),

    # =========================================================================
    # INTERACTION - PLANTS & DECORATIONS (8)
    # =========================================================================
    "first_decoration_push": Achievement(
        id="first_decoration_push", 
        name="ach_first_decoration_push_name",
        description="ach_first_decoration_push_desc",
        icon="🪴", category="interaction", points=10, tier=1,
    ),
    "decorations_pushed_10": Achievement(
        id="decorations_pushed_10", 
        name="ach_decorations_pushed_10_name",
        description="ach_decorations_pushed_10_desc",
        icon="🏠", category="interaction", points=15, tier=1, target_count=10,
    ),
    "decorations_pushed_50": Achievement(
        id="decorations_pushed_50", 
        name="ach_decorations_pushed_50_name",
        description="ach_decorations_pushed_50_desc",
        icon="🎨", category="interaction", points=30, tier=2, target_count=50,
    ),
    "first_plant_interact": Achievement(
        id="first_plant_interact", 
        name="ach_first_plant_interact_name",
        description="ach_first_plant_interact_desc",
        icon="🌱", category="interaction", points=10, tier=1,
    ),
    "plants_interacted_10": Achievement(
        id="plants_interacted_10", 
        name="ach_plants_interacted_10_name",
        description="ach_plants_interacted_10_desc",
        icon="🌿", category="interaction", points=15, tier=1, target_count=10,
    ),
    "plants_interacted_50": Achievement(
        id="plants_interacted_50", 
        name="ach_plants_interacted_50_name",
        description="ach_plants_interacted_50_desc",
        icon="🌳", category="interaction", points=30, tier=2, target_count=50,
    ),
    "objects_investigated_25": Achievement(
        id="objects_investigated_25", 
        name="ach_objects_investigated_25_name",
        description="ach_objects_investigated_25_desc",
        icon="🔍", category="interaction", points=25, tier=2, target_count=25,
    ),
    "objects_investigated_100": Achievement(
        id="objects_investigated_100", 
        name="ach_objects_investigated_100_name",
        description="ach_objects_investigated_100_desc",
        icon="🕵️", category="interaction", points=50, tier=3, target_count=100,
    ),

    # =========================================================================
    # EXPLORATION - POOP (1)
    # =========================================================================
    "first_poop_throw": Achievement(
        id="first_poop_throw", 
        name="ach_first_poop_throw_name",
        description="ach_first_poop_throw_desc",
        icon="💩", category="exploration", points=10, tier=1,
    ),

    # =========================================================================
    # INK CATEGORY (2)
    # =========================================================================
    "first_ink_cloud": Achievement(
        id="first_ink_cloud", 
        name="ach_first_ink_cloud_name",
        description="ach_first_ink_cloud_desc",
        icon="🖤", category="ink", points=15, tier=1,
    ),
    "ink_clouds_20": Achievement(
        id="ink_clouds_20", 
        name="ach_ink_clouds_20_name",
        description="ach_ink_clouds_20_desc",
        icon="🌫️", category="ink", points=25, tier=2, target_count=20,
    ),

    # =========================================================================
    # MEMORY CATEGORY (3)
    # =========================================================================
    "first_memory": Achievement(
        id="first_memory", 
        name="ach_first_memory_name",
        description="ach_first_memory_desc",
        icon="💾", category="memory", points=15, tier=1,
    ),
    "memory_long_term": Achievement(
        id="memory_long_term", 
        name="ach_memory_long_term_name",
        description="ach_memory_long_term_desc",
        icon="🗄️", category="memory", points=25, tier=2,
    ),
    "memories_50": Achievement(
        id="memories_50", 
        name="ach_memories_50_name",
        description="ach_memories_50_desc",
        icon="📚", category="memory", points=40, tier=3, target_count=50,
    ),

    # =========================================================================
    # EMOTIONAL CATEGORY (4)
    # =========================================================================
    "curiosity_100": Achievement(
        id="curiosity_100", 
        name="ach_curiosity_100_name",
        description="ach_curiosity_100_desc",
        icon="🤔", category="emotional", points=15, tier=1,
    ),
    "zen_master": Achievement(
        id="zen_master", 
        name="ach_zen_master_name",
        description="ach_zen_master_desc",
        icon="🧘", category="emotional", points=30, tier=2,
    ),
    "first_startle": Achievement(
        id="first_startle", 
        name="ach_first_startle_name",
        description="ach_first_startle_desc",
        icon="😱", category="emotional", points=10, tier=1,
    ),
    "nervous_wreck": Achievement(
        id="nervous_wreck", 
        name="ach_nervous_wreck_name",
        description="ach_nervous_wreck_desc",
        icon="😰", category="emotional", points=15, tier=2, hidden=True,
    ),

    # =========================================================================
    # SECRET CATEGORY (3)
    # =========================================================================
    "night_owl": Achievement(
        id="night_owl", 
        name="ach_night_owl_name",
        description="ach_night_owl_desc",
        icon="🦉", category="secret", points=15, tier=2, hidden=True,
    ),
    "early_bird": Achievement(
        id="early_bird", 
        name="ach_early_bird_name",
        description="ach_early_bird_desc",
        icon="🐦", category="secret", points=15, tier=2, hidden=True,
    ),
    "weekend_warrior": Achievement(
        id="weekend_warrior", 
        name="ach_weekend_warrior_name",
        description="ach_weekend_warrior_desc",
        icon="🗓️", category="secret", points=20, tier=2, hidden=True,
    ),

    # =========================================================================
    # META CATEGORY (2)
    # =========================================================================
    "brain_surgeon": Achievement(
        id="brain_surgeon", 
        name="ach_brain_surgeon_name",
        description="ach_brain_surgeon_desc",
        icon="🔬", category="meta", points=10, tier=1,
    ),
    "speed_demon": Achievement(
        id="speed_demon", 
        name="ach_speed_demon_name",
        description="ach_speed_demon_desc",
        icon="⏩", category="meta", points=15, tier=2,
    ),
    "completionist": Achievement(
        id="completionist", 
        name="ach_completionist_name",
        description="ach_completionist_desc",
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