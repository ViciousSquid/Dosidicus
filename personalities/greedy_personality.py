from personality_traits import register_personality

def greedy_decision(squid):
    if squid.hunger > 30:
        squid.status = "hunting for food"
        squid.search_for_food()
    elif squid.satisfaction < 50:
        squid.status = "seeking more resources"
        squid.explore_environment()
    else:
        squid.status = "guarding resources"
        squid.move_slowly()

def eat_greedily(squid, food_item):
    squid.status = "Eating greedily"
    food_type = "sushi" if getattr(food_item, 'is_sushi', False) else "cheese"
    
    squid.hunger = max(0, squid.hunger - 25)
    squid.happiness = min(100, squid.happiness + 15)
    squid.satisfaction = min(100, squid.satisfaction + 20)
    squid.anxiety = min(100, squid.anxiety + 5)
    
    squid.tamagotchi_logic.remove_food(food_item)
    print(f"The greedy squid enthusiastically ate the {food_type}")
    squid.show_eating_effect()
    squid.start_poop_timer()
    squid.pursuing_food = False
    squid.target_food = None

GREEDY = register_personality(
    "GREEDY",
    greedy_decision,
    {"hunger": 1.3, "satisfaction": 0.7}
)