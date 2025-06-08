import json
import os
from datetime import datetime
import time

class MemoryManager:
    def __init__(self):
        self.memory_dir = '_memory'
        self.short_term_file = os.path.join(self.memory_dir, 'ShortTerm.json')
        self.long_term_file = os.path.join(self.memory_dir, 'LongTerm.json')
        
        # Load memory and ensure all timestamps are converted to floats
        self.short_term_memory = self._load_and_convert_timestamps(self.short_term_file)
        self.long_term_memory = self._load_and_convert_timestamps(self.long_term_file)
        
        self.short_term_limit = 50
        self.short_term_duration = 300  # 5 minutes in seconds
        self.last_cleanup_time = time.time()

    def _load_and_convert_timestamps(self, file_path):
        """Loads memory from JSON and converts all timestamps to floats."""
        if not os.path.exists(file_path):
            return []
        try:
            with open(file_path, 'r') as file:
                content = file.read()
                if not content.strip():
                    return []
                memory_list = json.loads(content)
                if not isinstance(memory_list, list):
                    return []

                for item in memory_list:
                    if 'timestamp' in item:
                        ts = item['timestamp']
                        if isinstance(ts, str):
                            try:
                                # Convert ISO string to float timestamp
                                item['timestamp'] = datetime.fromisoformat(ts).timestamp()
                            except (ValueError, TypeError):
                                # If conversion fails, set a default invalid timestamp
                                item['timestamp'] = 0
                        elif not isinstance(ts, (int, float)):
                            item['timestamp'] = 0 # Mark other invalid types
                return memory_list
        except (json.JSONDecodeError, Exception) as e:
            print(f"Error processing memory file {file_path}: {e}")
            return []

    def save_memory(self, memory, file_path):
        """Saves memory to JSON, converting float timestamps to ISO strings."""
        if not memory:
            # To clear a file, we can write an empty list
            memory_to_save = []
        else:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            serializable_memory = []
            for item in memory:
                new_item = item.copy()
                if 'timestamp' in new_item and isinstance(new_item['timestamp'], float):
                    new_item['timestamp'] = datetime.fromtimestamp(new_item['timestamp']).isoformat()
                serializable_memory.append(new_item)
            memory_to_save = serializable_memory

        try:
            with open(file_path, 'w') as file:
                json.dump(memory_to_save, file, indent=4)
        except Exception as e:
            print(f"Error saving memory to {file_path}: {e}")


    def add_short_term_memory(self, category, key, value, importance=1.0, related_neurons=None):
        """Adds a memory, using float timestamps."""
        for memory in self.short_term_memory:
            if memory.get('key') == key and memory.get('category') == category:
                memory['importance'] = memory.get('importance', 1.0) + 0.5
                memory['timestamp'] = time.time()
                if memory['importance'] >= 3.0:
                    self.transfer_to_long_term_memory(category, key)
                return

        memory_item = {
            "timestamp": time.time(),
            "category": category,
            "key": key,
            "value": value,
            "importance": importance,
            "related_neurons": related_neurons or [],
            "access_count": 1
        }
        self.short_term_memory.append(memory_item)
        if len(self.short_term_memory) > self.short_term_limit:
            self.short_term_memory.pop(0)
        self.save_memory(self.short_term_memory, self.short_term_file)

    def cleanup_short_term_memory(self):
        current_time = time.time()
        self.short_term_memory = [m for m in self.short_term_memory if isinstance(m.get('timestamp'), (int, float)) and (current_time - m.get('timestamp', 0)) <= self.short_term_duration]
        if len(self.short_term_memory) > self.short_term_limit:
            self.short_term_memory.sort(key=lambda x: (x.get('importance', 1), x.get('access_count', 0)), reverse=True)
            self.short_term_memory = self.short_term_memory[:self.short_term_limit]

    def add_long_term_memory(self, category, key, value):
        memory = {'category': category, 'key': key, 'value': value, 'timestamp': time.time()}
        self.long_term_memory.append(memory)
        self.save_memory(self.long_term_memory, self.long_term_file)

    def get_short_term_memory(self, category, key, default=None):
        current_time = time.time()
        for memory in self.short_term_memory:
            if memory.get('category') == category and memory.get('key') == key:
                ts = memory.get('timestamp', 0)
                if isinstance(ts, (int, float)) and (current_time - ts) <= self.short_term_duration:
                    memory['access_count'] = memory.get('access_count', 0) + 1
                    return memory.get('value')
        return default

    def get_all_short_term_memories(self, raw=False):
        """Retrieves all valid short-term memories."""
        current_time = time.time()
        valid_memories = [
            m for m in self.short_term_memory
            if isinstance(m.get('timestamp'), (int, float)) and (current_time - m.get('timestamp', 0)) <= self.short_term_duration
        ]
        sorted_memories = sorted(valid_memories, key=lambda x: x.get('timestamp', 0), reverse=True)
        return sorted_memories if raw else [self._format_memory_for_display(mem) for mem in sorted_memories]

    def get_all_long_term_memories(self, category=None):
        filtered = [m for m in self.long_term_memory if not (isinstance(m.get('key'), str) and m['key'].isdigit())]
        if category:
            return [m for m in filtered if m.get('category') == category]
        return filtered

    def get_active_memories_data(self, count=None):
        """Gets active memories, ensuring timestamps are floats before use."""
        current_time = time.time()
        active_memories = []
        for memory in self.short_term_memory:
            timestamp = memory.get('timestamp')
            # Now we can reliably expect a float
            if isinstance(timestamp, (int, float)) and (current_time - timestamp) <= self.short_term_duration:
                formatted_memory = {
                    'category': memory.get('category'),
                    'key': memory.get('key'),
                    'formatted_value': memory.get('value'),
                    'raw_value': memory.get('value'),
                    'timestamp': datetime.fromtimestamp(timestamp),
                    'importance': memory.get('importance', 1),
                    'access_count': memory.get('access_count', 0)
                }
                active_memories.append(formatted_memory)
        
        active_memories.sort(key=lambda x: (x.get('importance', 1), x.get('access_count', 0)), reverse=True)
        return active_memories[:count] if count is not None else active_memories

    def review_and_transfer_memories(self):
        current_time = time.time()
        # Iterate over a copy as we may modify the list
        for memory in list(self.short_term_memory):
            timestamp = memory.get('timestamp', 0)
            if isinstance(timestamp, (int, float)) and (current_time - timestamp) > self.short_term_duration:
                if self.should_transfer_to_long_term(memory):
                    self.transfer_to_long_term_memory(memory['category'], memory['key'])
                else:
                    self.short_term_memory.remove(memory)
        self.cleanup_short_term_memory()
        
    def periodic_memory_management(self):
        if (time.time() - self.last_cleanup_time) > 30:
            self.last_cleanup_time = time.time()
            self.review_and_transfer_memories()

    def transfer_to_long_term_memory(self, category, key):
        memory_to_transfer = None
        for mem in self.short_term_memory:
             if mem.get('category') == category and mem.get('key') == key:
                  memory_to_transfer = mem
                  break
        if memory_to_transfer:
            self.long_term_memory.append(memory_to_transfer)
            self.short_term_memory.remove(memory_to_transfer)
            self.save_memory(self.short_term_memory, self.short_term_file)
            self.save_memory(self.long_term_memory, self.long_term_file)

    def should_transfer_to_long_term(self, memory):
        return (memory.get('importance', 1) >= 7 or
                memory.get('access_count', 0) >= 3 or
                (memory.get('importance', 1) >= 5 and memory.get('access_count', 0) >= 2))
                
    # Other methods (clear_all_memories, etc.) remain largely the same but benefit from consistent data
    def clear_short_term_memory(self):
        self.short_term_memory = []
        self.save_memory(self.short_term_memory, self.short_term_file)

    def update_memory_importance(self, category, key, importance_change):
        for memory in self.short_term_memory:
            if memory.get('category') == category and memory.get('key') == key:
                memory['importance'] = max(1, min(10, memory.get('importance', 1) + importance_change))
                self.save_memory(self.short_term_memory, self.short_term_file)
                break

    def clear_all_memories(self):
        self.short_term_memory = []
        self.save_memory([], self.short_term_file)
        self.long_term_memory = []
        self.save_memory([], self.long_term_file)
        print("All memory files have been cleared.")

    def _format_memory_for_display(self, memory):
        return memory

    def format_memory(self, memory):
        timestamp = memory.get('timestamp', 0)
        timestamp_str = datetime.fromtimestamp(timestamp).strftime("%H:%M:%S") if isinstance(timestamp, (int,float)) and timestamp > 0 else "N/A"
        formatted_memory = f"[{timestamp_str}] {memory.get('value', '')}"

        interaction_type = "<b>Neutral</b>"
        background_color = "#FFFACD"  # Pastel yellow

        raw_value = memory.get('raw_value')
        if isinstance(raw_value, dict):
            total_effect = sum(float(val) for val in raw_value.values() if isinstance(val, (int, float)))
            if total_effect > 0:
                interaction_type = "<font color='green'><b>Positive</b></font>"
                background_color = "#D1FFD1"
            elif total_effect < 0:
                interaction_type = "<font color='red'><b>Negative</b></font>"
                background_color = "#FFD1DC"
        elif memory.get('category') == 'mental_state' and memory.get('key') == 'startled':
            interaction_type = "<font color='red'><b>Negative</b></font>"
            background_color = "#FFD1DC"

        return f"<div style='background-color: {background_color}; padding: 5px; margin: 5px; border-radius: 5px;'>{formatted_memory}<br>{interaction_type}<hr></div>"