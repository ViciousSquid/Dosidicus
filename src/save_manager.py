import json
import os
import zipfile
from datetime import datetime
import shutil

class SaveManager:
    def __init__(self, save_directory="saves"):
        self.save_directory = save_directory
        if not os.path.exists(save_directory):
            os.makedirs(save_directory)
        self.autosave_path = os.path.join(save_directory, "autosave.zip")
        self.manual_save_path = os.path.join(save_directory, "save_data.zip")

    def save_exists(self):
        """Check if any save file exists."""
        return os.path.exists(self.autosave_path) or os.path.exists(self.manual_save_path)
    
    def extract_memories(self, zip_path, memory_dir):
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            # Remove existing memory files
            if os.path.exists(memory_dir):
                shutil.rmtree(memory_dir)
            os.makedirs(memory_dir)

            # Extract new memory files
            for filename in ['ShortTerm.json', 'LongTerm.json']:
                if filename in zipf.namelist():
                    zipf.extract(filename, memory_dir)

    def get_latest_save(self):
        """Get the path of the most recent save file."""
        if os.path.exists(self.autosave_path):
            return self.autosave_path
        elif os.path.exists(self.manual_save_path):
            return self.manual_save_path
        return None

    def save_game(self, save_data, is_autosave=False):
        filepath = self.autosave_path if is_autosave else self.manual_save_path
        try:
            with zipfile.ZipFile(filepath, 'w') as zipf:
                for key, data in save_data.items():
                    zipf.writestr(f"{key}.json", json.dumps(data, indent=4))
            return filepath
        except Exception as e:
            print(f"Error saving game: {str(e)}")
            import traceback
            traceback.print_exc()
            return None

    def load_game(self):
        latest_save = self.get_latest_save()
        if latest_save:
            save_data = {}
            with zipfile.ZipFile(latest_save, 'r') as zipf:
                for filename in zipf.namelist():
                    with zipf.open(filename) as f:
                        key = os.path.splitext(filename)[0]
                        save_data[key] = json.loads(f.read().decode('utf-8'))
            
            # Extract memory files one directory level above
                extract_path = os.path.join(os.path.dirname(os.path.dirname(latest_save)), '_memory')
                self.extract_memories(latest_save, extract_path)
            
            return save_data
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