`Personality.py` defines a base `PersonalityType` class with empty methods for `configure()`, `make_decision()`, `eat()`, `go_to_sleep()`,` wake_up()`, and `play()`. These methods will be overridden by specific personality classes.
We create separate classes for each personality type (`ShyPersonality`, `InquisitivePersonality`, `GreedyPersonality`, `StubbornPersonality`, `PlayfulPersonality`, `IntrovertPersonality`) that inherit from `PersonalityType`.
Each personality class overrides the relevant methods to implement its specific behaviors. For example, ShyPersonality implements the `make_decision()` method to hide among plants or rocks, GreedyPersonality modifies the `eat()` method to increase hunger and decrease satisfaction, and so on.
We define a `create_personality()` function that takes a `personality_type` string and a `squid` object, and returns an instance of the corresponding personality class.

