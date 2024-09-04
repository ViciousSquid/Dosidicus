import json
import os
from datetime import datetime

class MemoryManager:
    def __init__(self):
        self.memory_dir = '_memory'
        self.short_term_file = os.path.join(self.memory_dir, 'ShortTerm.json')
        self.long_term_file = os.path.join(self.memory_dir, 'LongTerm.json')
        self.short_term_memory = self.load_memory(self.short_term_file)
        self.long_term_memory = self.load_memory(self.long_term_file)

    def load_memory(self, file_path):
        if os.path.exists(file_path):
            with open(file_path, 'r') as f:
                return json.load(f)
        return {}

    def save_memory(self, memory, file_path):
        os.makedirs(os.path.dirname(file_path), exist_ok=True)
        with open(file_path, 'w') as f:
            json.dump(memory, f, indent=4)

    def add_short_term_memory(self, category, key, value):
        if isinstance(self.short_term_memory, dict):
            if category not in self.short_term_memory:
                self.short_term_memory[category] = {}
            self.short_term_memory[category][key] = value
        elif isinstance(self.short_term_memory, list):
            self.short_term_memory.append({
                'category': category,
                'key': key,
                'value': value
            })
        else:
            self.short_term_memory = [{
                'category': category,
                'key': key,
                'value': value
            }]
        
        self.save_memory(self.short_term_memory, self.short_term_file)

    def add_long_term_memory(self, category, key, value):
        if category not in self.long_term_memory:
            self.long_term_memory[category] = {}
        self.long_term_memory[category][key] = value
        self.save_memory(self.long_term_memory, self.long_term_file)

    def get_short_term_memory(self, category, key, default=None):
        if isinstance(self.short_term_memory, dict):
            return self.short_term_memory.get(category, {}).get(key, default)
        elif isinstance(self.short_term_memory, list):
            for memory in self.short_term_memory:
                if memory.get('category') == category and memory.get('key') == key:
                    return memory.get('value', default)
        return default

    def get_long_term_memory(self, category, key, default=None):
        return self.long_term_memory.get(category, {}).get(key, default)

    def get_all_short_term_memories(self, category):
        if isinstance(self.short_term_memory, dict):
            return self.short_term_memory.get(category, {})
        elif isinstance(self.short_term_memory, list):
            return [item for item in self.short_term_memory if item.get('category') == category]
        else:
            return {}

    def get_all_long_term_memories(self, category):
        return self.long_term_memory.get(category, {})

    def clear_short_term_memory(self):
        self.short_term_memory = {} if isinstance(self.short_term_memory, dict) else []
        self.save_memory(self.short_term_memory, self.short_term_file)

    def transfer_to_long_term_memory(self, category, key):
        if isinstance(self.short_term_memory, dict):
            if category in self.short_term_memory and key in self.short_term_memory[category]:
                value = self.short_term_memory[category][key]
                self.add_long_term_memory(category, key, value)
                del self.short_term_memory[category][key]
                self.save_memory(self.short_term_memory, self.short_term_file)
        elif isinstance(self.short_term_memory, list):
            for i, memory in enumerate(self.short_term_memory):
                if memory.get('category') == category and memory.get('key') == key:
                    value = memory.get('value')
                    self.add_long_term_memory(category, key, value)
                    del self.short_term_memory[i]
                    self.save_memory(self.short_term_memory, self.short_term_file)
                    break

    def update_short_term_memory(self, category, key, value):
        if isinstance(self.short_term_memory, dict):
            if category not in self.short_term_memory:
                self.short_term_memory[category] = {}
            self.short_term_memory[category][key] = value
        elif isinstance(self.short_term_memory, list):
            for memory in self.short_term_memory:
                if memory.get('category') == category and memory.get('key') == key:
                    memory['value'] = value
                    break
            else:
                self.short_term_memory.append({
                    'category': category,
                    'key': key,
                    'value': value
                })
        else:
            self.short_term_memory = [{
                'category': category,
                'key': key,
                'value': value
            }]
        
        self.save_memory(self.short_term_memory, self.short_term_file)

    def update_long_term_memory(self, category, key, value):
        if category not in self.long_term_memory:
            self.long_term_memory[category] = {}
        self.long_term_memory[category][key] = value
        self.save_memory(self.long_term_memory, self.long_term_file)