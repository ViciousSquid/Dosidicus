import json
import os
from datetime import datetime, timedelta

class MemoryManager:
    def __init__(self):
        self.memory_dir = '_memory'
        self.short_term_file = os.path.join(self.memory_dir, 'ShortTerm.json')
        self.long_term_file = os.path.join(self.memory_dir, 'LongTerm.json')
        self.short_term_memory = self.load_memory(self.short_term_file) or []
        self.long_term_memory = self.load_memory(self.long_term_file) or []
        self.short_term_limit = 50  # Maximum number of short-term memories
        self.short_term_duration = timedelta(minutes=5)  # Duration of short-term memory
        self.last_cleanup_time = datetime.now()

        # Ensure memories are lists
        if not isinstance(self.short_term_memory, list):
            self.short_term_memory = []
        if not isinstance(self.long_term_memory, list):
            self.long_term_memory = []

    def load_memory(self, file_path):
        if os.path.exists(file_path):
            try:
                with open(file_path, 'r') as file:
                    content = file.read()
                    if not content.strip():  # File is empty
                        print(f"Warning: {file_path} is empty. Initializing with an empty list.")
                        return []
                    memory = json.loads(content)
                    for item in memory:
                        if 'timestamp' in item:
                            item['timestamp'] = datetime.fromisoformat(item['timestamp'])
                    return memory
            except json.JSONDecodeError as e:
                print(f"Error decoding JSON from {file_path}: {e}")
                print("Initializing with an empty list.")
                return []
            except Exception as e:
                print(f"Unexpected error loading memory from {file_path}: {e}")
                print("Initializing with an empty list.")
                return []
        else:
            print(f"Memory file {file_path} does not exist. Initializing with an empty list.")
        return []

    def save_memory(self, memory, file_path):
        if not memory:
            print(f"Warning: Attempting to save empty memory to {file_path}. Skipping save.")
            return
        
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        try:
            with open(file_path, 'w') as file:
                json.dump(memory, file, indent=4, default=str)  # Use default=str to handle datetime
        except Exception as e:
            print(f"Error saving memory to {file_path}: {e}")

    def add_short_term_memory(self, category, key, value):
        timestamp = datetime.now()

        memory = {
            'category': category,
            'key': key,
            'value': value,
            'timestamp': timestamp.isoformat(),
            'importance': 1,
            'access_count': 1
        }
        self.short_term_memory.append(memory)

        if len(self.short_term_memory) > self.short_term_limit:
            self.cleanup_short_term_memory()

        self.save_memory(self.short_term_memory, self.short_term_file)


    def cleanup_short_term_memory(self):
        current_time = datetime.now()

        def is_valid_memory(memory):
            timestamp = memory['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            return (current_time - timestamp) <= self.short_term_duration

        # Remove expired memories
        self.short_term_memory = [memory for memory in self.short_term_memory if is_valid_memory(memory)]

        # If still over limit, remove least important and least accessed memories
        if len(self.short_term_memory) > self.short_term_limit:
            self.short_term_memory.sort(key=lambda x: (x['importance'], x['access_count']), reverse=True)
            self.short_term_memory = self.short_term_memory[:self.short_term_limit]


    def add_long_term_memory(self, category, key, value):
        memory = {
            'category': category,
            'key': key,
            'value': value,
            'timestamp': datetime.now().isoformat()
        }
        self.long_term_memory.append(memory)
        self.save_memory(self.long_term_memory, self.long_term_file)

    def get_short_term_memory(self, category, key, default=None):
        for memory in self.short_term_memory:
            if memory['category'] == category and memory['key'] == key:
                current_time = datetime.now()
                memory_time = datetime.fromisoformat(memory['timestamp'])
                
                if (current_time - memory_time) <= self.short_term_duration:
                    memory['access_count'] += 1
                    return memory['value']
                else:
                    # Memory has expired, remove it
                    self.short_term_memory.remove(memory)
                    self.save_memory(self.short_term_memory, self.short_term_file)
                    break
        return default

    def get_long_term_memory(self, category, key, default=None):
        for memory in self.long_term_memory:
            if memory['category'] == category and memory['key'] == key:
                return memory['value']
        return default

    def get_all_short_term_memories(self, category=None):
        current_time = datetime.now()

        def is_valid_memory(memory):
            timestamp = memory['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            return (current_time - timestamp) <= self.short_term_duration

        if category:
            return [memory for memory in self.short_term_memory
                    if memory.get('category') == category and is_valid_memory(memory)]
        return [memory for memory in self.short_term_memory if is_valid_memory(memory)]


    def get_all_long_term_memories(self, category=None):
        if category:
            return [memory for memory in self.long_term_memory if memory.get('category') == category]
        return self.long_term_memory

    def clear_short_term_memory(self):
        self.short_term_memory = []
        self.save_memory(self.short_term_memory, self.short_term_file)

    def transfer_to_long_term_memory(self, category, key):
        memory = next((m for m in self.short_term_memory if m['category'] == category and m['key'] == key), None)
        if memory:
            self.long_term_memory.append(memory)
            self.short_term_memory.remove(memory)
            self.save_memory(self.short_term_memory, self.short_term_file)
            self.save_memory(self.long_term_memory, self.long_term_file)

    def periodic_memory_management(self):
        current_time = datetime.now()
        if (current_time - self.last_cleanup_time) > timedelta(seconds=30):
            self.last_cleanup_time = current_time
            self.review_and_transfer_memories()

    def review_and_transfer_memories(self):
        current_time = datetime.now()
        for memory in list(self.short_term_memory):
            timestamp = memory['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            memory_time = timestamp

            if (current_time - memory_time) > self.short_term_duration:
                if self.should_transfer_to_long_term(memory):
                    self.transfer_to_long_term_memory(memory['category'], memory['key'])
                else:
                    self.short_term_memory.remove(memory)

        # After transfers, clean up any remaining excess short-term memories
        self.cleanup_short_term_memory()


    def should_transfer_to_long_term(self, memory):
        # Criteria for transfer:
        # 1. Memory has high importance (>= 7)
        # 2. Memory has been accessed frequently (>= 3 times)
        # 3. Memory is moderately important (>= 5) and has been accessed at least twice
        return (
            memory['importance'] >= 7 or
            memory['access_count'] >= 3 or
            (memory['importance'] >= 5 and memory['access_count'] >= 2)
        )

    def update_memory_importance(self, category, key, importance_change):
        for memory in self.short_term_memory:
            if memory['category'] == category and memory['key'] == key:
                memory['importance'] += importance_change
                memory['importance'] = max(1, min(10, memory['importance']))
                self.save_memory(self.short_term_memory, self.short_term_file)
                break

    def clear_all_memories(self):
        # Clear short-term memory
        self.short_term_memory = []
        self.save_memory(self.short_term_memory, self.short_term_file)

        # Clear long-term memory
        self.long_term_memory = []
        self.save_memory(self.long_term_memory, self.long_term_file)

        print("All memory files have been cleared.")

    def format_value(self, val):
        if isinstance(val, (int, float)):
            return f"{val:.2f}"
        return str(val)

    def format_memory(self, memory):
        timestamp = memory['timestamp']
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        timestamp = timestamp.strftime("%H:%M:%S")

        formatted_memory = f"[{timestamp}] "
        interaction_type = "<b>Neutral</b>"
        total_effect = 0

        if 'value' in memory and isinstance(memory['value'], dict):
            if 'decoration' in memory['value'] and 'effects' in memory['value']:
                decoration = memory['value']['decoration']
                effects = memory['value']['effects']
                formatted_effects = ', '.join(f"{attr.capitalize()} {'Decreased' if attr == 'anxiety' and val < 0 else '+' if val >= 0 else ''}{abs(val):.2f}" for attr, val in effects.items())
                formatted_memory += f"Interaction with {decoration}: {formatted_effects}"
                total_effect = sum(float(val) if attr != 'anxiety' else -float(val) for attr, val in effects.items())
            else:
                formatted_memory += str(memory['value'])
        else:
            formatted_memory += str(memory.get('value', 'No value'))

        # Determine if the memory is positive, negative, or neutral
        if total_effect > 0:
            interaction_type = "<font color='green'><b>Positive</b></font>"
        elif total_effect < 0:
            interaction_type = "<font color='red'><b>Negative</b></font>"

        # Add background color based on interaction type
        if "Negative" in interaction_type:
            background_color = "#FFD1DC"  # Pastel red
        elif "Positive" in interaction_type:
            background_color = "#D1FFD1"  # Pastel green
        else:
            background_color = "#FFFACD"  # Pastel yellow

        return f"<div style='background-color: {background_color}; padding: 5px; margin: 5px; border-radius: 5px;'>{formatted_memory}<br>{interaction_type}<hr></div>"