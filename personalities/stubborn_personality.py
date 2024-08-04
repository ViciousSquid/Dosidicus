from personality_traits import register_personality

def stubborn_decision(squid):
    if squid.hunger > 70 and squid.target_food is None:
        squid.status = "reluctantly seeking food"
        squid.search_for_favorite_food()
    elif squid.sleepiness > 90:
        squid.status = "Stubbornly resisting sleep"
        squid.move_slowly()
    else:
        squid.status = "Doing my own thing"
        squid.move_randomly()

def search_for_favorite_food(squid):
    visible_food = squid.get_visible_food()
    if visible_food:
        for food_x, food_y in visible_food:
            if squid.is_favorite_food(squid.tamagotchi_logic.get_food_item_at(food_x, food_y)):
                squid.move_towards(food_x, food_y)
                return
        squid.tamagotchi_logic.show_message("Stubborn squid does not like that type of food!")
        squid.move_randomly()
    else:
        squid.move_randomly()

def investigate_food(squid, food_item):
    squid.status = "Investigating food"
    squid.tamagotchi_logic.show_message("Squid investigates the food...")
    
    food_pos = food_item.pos()
    squid.move_towards_position(food_pos)
    
    squid.tamagotchi_logic.show_message("Stubborn squid ignored the food")
    squid.status = "I don't like that food"

STUBBORN = register_personality(
    "STUBBORN",
    stubborn_decision,
    {"happiness": 0.9, "anxiety": 1.1}
)