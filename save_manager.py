import os
import json

# For Loading and Saving of the squid statistics in json format

class SaveManager:
    def __init__(self, save_file):
        self.save_file = save_file

    def save_game(self, squid, tamagotchi_logic):
        save_data = {
            "squid": {
                "hunger": squid.hunger,
                "sleepiness": squid.sleepiness,
                "happiness": squid.happiness,
                "cleanliness": squid.cleanliness,
                "health": squid.health,
                "is_sick": squid.is_sick,
                "squid_x": squid.squid_x,
                "squid_y": squid.squid_y
            },
            "tamagotchi_logic": {
                "cleanliness_threshold_time": tamagotchi_logic.cleanliness_threshold_time,
                "hunger_threshold_time": tamagotchi_logic.hunger_threshold_time,
                "last_clean_time": tamagotchi_logic.last_clean_time
            }
        }

        with open(self.save_file, "w") as file:
            json.dump(save_data, file)

    def load_game(self):
        if os.path.exists(self.save_file):
            with open(self.save_file, "r") as file:
                save_data = json.load(file)
                return save_data
        else:
            return None