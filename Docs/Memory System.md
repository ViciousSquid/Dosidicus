# Memory System Technical Overview

The `MemoryManager` class handles both short-term and long-term memories. This system allows the squid to store, retrieve, and utilize past experiences to influence his decision-making process.
* The `_memory` folder holds `ShortTerm.json` and `LongTerm.json`

## Key Components

1. `MemoryManager` class
2. Short-term memory storage
3. Long-term memory storage
4. Memory persistence (JSON files)
5. Memory transfer mechanism
6. Integration with decision-making

## Detailed Breakdown

### 1. MemoryManager Class

The `MemoryManager` class is the core of the memory system. It handles:

- Initialization of memory storages
- Loading and saving memories to/from files
- Adding new memories
- Retrieving memories
- Transferring memories from short-term to long-term storage
- Periodic memory management

```python
class MemoryManager:
    def __init__(self):
        self.memory_dir = '_memory'
        self.short_term_file = os.path.join(self.memory_dir, 'ShortTerm.json')
        self.long_term_file = os.path.join(self.memory_dir, 'LongTerm.json')
        self.short_term_memory = self.load_memory(self.short_term_file) or []
        self.long_term_memory = self.load_memory(self.long_term_file) or []
        self.short_term_limit = 50  # Maximum number of short-term memories
        self.short_term_duration = timedelta(minutes=5)  # Duration of short-term memory
```

### 2. Short-term Memory

Short-term memories are recent experiences or observations. They have a limited capacity and duration.

- Stored in `self.short_term_memory` list
- Limited to `self.short_term_limit` items
- Expire after `self.short_term_duration`

```python
def add_short_term_memory(self, category, key, value, importance=1):
    memory = {
        'category': category,
        'key': key,
        'value': value,
        'timestamp': datetime.now().isoformat(),
        'importance': importance,
        'access_count': 1
    }
    self.short_term_memory.append(memory)
```

### 3. Long-term Memory

Long-term memories are persistent and don't expire. They represent important or frequently accessed information.

- Stored in `self.long_term_memory` list
- No limit on the number of items
- Do not expire

```python
def add_long_term_memory(self, category, key, value):
    memory = {
        'category': category,
        'key': key,
        'value': value,
        'timestamp': datetime.now().isoformat()
    }
    self.long_term_memory.append(memory)
```

### 4. Memory Persistence

Memories are saved to and loaded from JSON files for persistence across sessions.

```python
def save_memory(self, memory, file_path):
    with open(file_path, 'w') as file:
        json.dump(memory, file, indent=4, default=str)

def load_memory(self, file_path):
    if os.path.exists(file_path):
        with open(file_path, 'r') as file:
            memory = json.loads(file.read())
            for item in memory:
                if 'timestamp' in item:
                    item['timestamp'] = datetime.fromisoformat(item['timestamp'])
            return memory
    return []
```

### 5. Memory Transfer Mechanism

Short-term memories can be transferred to long-term memory based on importance and access frequency.

```python
def should_transfer_to_long_term(self, memory):
    return (
        memory['importance'] >= 7 or
        memory['access_count'] >= 3 or
        (memory['importance'] >= 5 and memory['access_count'] >= 2)
    )

def review_and_transfer_memories(self):
    for memory in list(self.short_term_memory):
        if self.should_transfer_to_long_term(memory):
            self.transfer_to_long_term_memory(memory['category'], memory['key'])
        elif (datetime.now() - memory['timestamp']) > self.short_term_duration:
            self.short_term_memory.remove(memory)
```

### 6. Integration with Decision-making

The memory system is integrated into the squid's decision-making process in the `make_decision` method:

```python
def make_decision(self):
    # ... (other code)
    short_term_memories = self.memory_manager.get_all_short_term_memories('experiences')
    long_term_memories = self.memory_manager.get_all_long_term_memories('experiences')

    combined_state = current_state.copy()
    combined_state.update(short_term_memories)
    combined_state.update(long_term_memories)

    decision = self.tamagotchi_logic.squid_brain_window.make_decision(combined_state)
    # ... (rest of the decision-making process)
```

## Key Features

1. **Dual Storage**: Separate short-term and long-term memory systems allow for different treatment of recent vs. important memories.

2. **Automatic Transfer**: Important or frequently accessed short-term memories are automatically transferred to long-term storage.

3. **Expiration**: Short-term memories expire after a set duration, preventing information overload.

4. **Persistence**: Memories are saved to disk, allowing for continuity across sessions.

5. **Categorization**: Memories are categorized (e.g., 'experiences', 'decorations'), allowing for targeted retrieval and use.

6. **Integration**: The memory system is tightly integrated with the decision-making process, allowing past experiences to influence behavior.

7. **Importance and Access Tracking**: Memories have importance levels and access counts, which influence their likelihood of being transferred to long-term storage.

This memory system provides the squid with a sophisticated ability to learn from and adapt to his experiences, contributing to more complex and realistic behavior over time.
