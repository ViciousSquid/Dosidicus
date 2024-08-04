from personality_traits import register_personality
import random

def timid_decision(squid):
    # Update brain inputs
    brain_inputs = {
        'hunger': squid.hunger,
        'happiness': squid.happiness,
        'cleanliness': squid.cleanliness,
        'sleepiness': squid.sleepiness,
        'satisfaction': squid.satisfaction,
        'anxiety': squid.anxiety,
        'curiosity': squid.curiosity,
        'is_sick': squid.is_sick,
        'is_eating': squid.status == "eating",
        'is_sleeping': squid.is_sleeping,
        'pursuing_food': squid.pursuing_food,
        'direction': squid.squid_direction
    }
    
    # Update the brain
    squid.brain.update(brain_inputs)
    
    # Check for visible plants
    visible_plants = squid.get_visible_plants()
    
    if visible_plants:
        # Reduce anxiety and increase happiness when plants are visible
        squid.anxiety = max(0, squid.anxiety - 2)
        squid.happiness = min(100, squid.happiness + 1)
        
        if squid.anxiety > 50 or squid.curiosity > 50:
            squid.status = "seeking safety near plants"
            closest_plant = min(visible_plants, key=lambda plant: squid.distance_to(plant.pos().x(), plant.pos().y()))
            squid.move_towards(closest_plant.pos().x(), closest_plant.pos().y())
        else:
            squid.status = "feeling safe near plants"
            squid.move_randomly()
    else:
        # Increase anxiety when no plants are visible
        squid.anxiety = min(100, squid.anxiety + 1)
        squid.happiness = max(0, squid.happiness - 1)
        
        if squid.anxiety > 70:
            squid.status = "anxiously searching for plants"
            squid.explore_environment()
        elif squid.curiosity > 60:
            squid.status = "cautiously exploring"
            squid.explore_environment()
        else:
            squid.status = "timidly roaming"
            squid.move_slowly()

    # Apply effects of nearby plants
    for plant in visible_plants:
        if squid.distance_to(plant.pos().x(), plant.pos().y()) < 50:  # Close enough to benefit
            squid.apply_decoration_effects(plant)

    # Handle other needs
    if squid.hunger > 70 and not squid.pursuing_food:
        squid.status = "hesitantly looking for food"
        food_position = squid.get_food_position()
        if food_position != (-1, -1):
            squid.move_towards(food_position[0], food_position[1])
    elif squid.sleepiness > 80 and not squid.is_sleeping:
        squid.status = "sleepily seeking a quiet spot"
        squid.go_to_sleep()

    # Timid squids are more easily startled
    if random.random() < 0.1:  # 10% chance each decision
        squid.status = "startled!"
        squid.move_erratically()

    # Update brain with the final decision
    brain_inputs['status'] = squid.status
    squid.brain.update(brain_inputs)

    # Show a message about the squid's state occasionally
    if random.random() < 0.05:  # 5% chance each decision
        squid.tamagotchi_logic.show_message(f"Timid squid is {squid.status}")

TIMID = register_personality(
    "TIMID",
    timid_decision,
    {"curiosity": 0.5, "anxiety": 1.5}
)