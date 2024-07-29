import json
import os

class SaveManager:
    def __init__(self, save_directory="saves"):
        self.save_directory = save_directory
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        self.autosave_path = os.path.join(save_directory, "autosave.json")
        self.manual_save_path = os.path.join(save_directory, "save_data.json")

    def save_exists(self):
        """Check if any save file exists."""
        return os.path.exists(self.autosave_path) or os.path.exists(self.manual_save_path)

    def get_latest_save(self):
        """Get the path of the most recent save file."""
        if os.path.exists(self.autosave_path):
            return self.autosave_path
        elif os.path.exists(self.manual_save_path):
            return self.manual_save_path
        return None

    def save_game(self, save_data, is_autosave=False):
        """Save the game data to a file."""
        filepath = self.autosave_path if is_autosave else self.manual_save_path
        with open(filepath, 'w') as file:
            json.dump(save_data, file, indent=4)
        return filepath

    def load_game(self):
        """Load the game data from the most recent save file."""
        latest_save = self.get_latest_save()
        if latest_save:
            with open(latest_save, 'r') as file:
                return json.load(file)
        return None

    def delete_save(self, is_autosave=False):
        """Delete a save file."""
        filepath = self.autosave_path if is_autosave else self.manual_save_path
        if os.path.exists(filepath):
            os.remove(filepath)
            return True
        return False

    def get_save_timestamp(self, is_autosave=False):
        """Get the timestamp of a save file."""
        filepath = self.autosave_path if is_autosave else self.manual_save_path
        if os.path.exists(filepath):
            return os.path.getmtime(filepath)
        return None

    def get_save_size(self, is_autosave=False):
        """Get the size of a save file in bytes."""
        filepath = self.autosave_path if is_autosave else self.manual_save_path
        if os.path.exists(filepath):
            return os.path.getsize(filepath)
        return None