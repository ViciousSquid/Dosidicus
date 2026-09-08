`MemoryManager` is designed to simulate a simple cognitive memory system with two main components:

#### Data Persistence and Initialization
* File Storage: Memory is persisted in two JSON files within a _memory directory: `ShortTerm.json` and `LongTerm.json`.

* `__init__` Method: Initializes memory paths, loads existing memory using _load_and_convert_timestamps, and sets operational limits:

* `self.short_term_limit` = 50: Maximum number of items in short-term memory (STM).

* `self.short_term_duration` = 300 (5 minutes): The lifespan for a short-term memory item before it's considered for cleanup or transfer.

* `_load_and_convert_timestamps`: A crucial helper method that handles loading memory from JSON. It's robust, attempting to convert string-based _ISO 8601_ timestamps (used for storage) into floating-point Unix timestamps (used for internal operations) to enable easy time-based comparisons.
* `save_memory`: The counterpart to the loading function. It takes the in-memory list and converts the internal float timestamps back to _ISO 8601_ strings before saving to the JSON file with indentation (indent=4).

-------------------------------

#### Short-Term Memory (STM) Management
STM is dynamic, time-limited, and its items have calculated metrics to determine their longevity.

`add_short_term_memory`: Adds a new memory item. If an item with the same category and key already exists, it reinforces the memory by increasing its importance by 0.5 and updating its timestamp.

It checks for immediate promotion: if importance reaches 3.0, it calls `transfer_to_long_term_memory`.

It enforces the `self.short_term_limit` by dropping the oldest memory (`pop(0)`) when the limit is exceeded (FIFO - First In, First Out).

`get_short_term_memory`: Retrieves a memory by category and key. It verifies the memory is still within the `self.short_term_duration`. A successful access increases the memory's `access_count`.

`cleanup_short_term_memory`: Removes expired memories (older than `self.short_term_duration`). If the list is still over the limit, it prunes based on a combined score of importance and access_count.

`get_active_memories_data`: Retrieves and formats memories that are still valid, sorting them by a combination of importance and access_count in descending order.

---------------------

#### Long-Term Memory (LTM) Management
LTM is for permanent or reinforced memories and is primarily concerned with deduplication.

`add_long_term_memory`: Adds a memory. It checks for duplicates based on category and key. If a memory already exists, it is not duplicated; instead, its timestamp is updated to reflect the reinforcement.

`get_all_long_term_memories`: Retrieves all LTM items, with an optional filter by category.

---------------


#### Transfer and Review Logic
This section defines the "learning" or "consolidation" process where temporary memories become permanent.

* `review_and_transfer_memories`: The core decay and promotion loop. It iterates through expired STM items.

* If an expired item meets the criteria in `should_transfer_to_long_term`, it's promoted using `transfer_to_long_term_memory`.

* Otherwise, the expired memory is simply removed from the STM.

* `periodic_memory_management`: A simple rate limiter that calls review_and_transfer_memories only if 30 seconds have passed since the last cleanup.

* `should_transfer_to_long_term`: Defines the promotion criteria:

1. importance >= 7 OR

1. access_count >= 3 OR

1. (importance >= 5 AND access_count >= 2)

* `transfer_to_long_term_memory`: Moves a memory from STM to LTM (using `add_long_term_memory` to handle LTM deduplication) and then removes it from the STM.


-------------------

#### Utility and Formatting
* `clear_short_term_memory` / `clear_all_memories`: Provides methods to reset one or both memory stores.

* `update_memory_importance`: Allows external logic to manually adjust the importance of an STM item.

* `format_memory`: A presentation method that takes a memory dictionary and returns an HTML-formatted string, color-coding the memory's interaction type (Positive/Negative/Neutral) based on its raw_value or category/key.