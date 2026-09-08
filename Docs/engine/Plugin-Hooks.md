The following hooks are available for [plugins](../engine/Plugin-System.md) to subscribe to:

  ### Lifecycle hooks
`on_startup`
-called when the application launches

`on_shutdown`
-called when the application shuts down

`on_new_game`
-called when a new game is started

`on_save_game`
-called when a game is saved
 
`on_load_game`
-called when a game is loaded
        
  ### Simulation hooks
`pre_update`
-called immediately BEFORE the update of a frame (once per 1000 milliseconds)  

`post_update`
-called immediately AFTER the update of a frame  

`on_speed_change`
-called when the game speed is changed 
        
  ### Squid state hooks
`on_squid_state_change`
-called when any of the squid's states change 

`on_hunger_change`
-called every time the value of HUNGER changes 

`on_happiness_change`
-called every time the value of HAPPINESS changes 

`on_cleanliness_change`
-called every time the value of CLEANLINESS changes
  
`on_sleepiness_change`
-called every time the value of SLEEPINESS changes 
 
`on_satisfaction_change`
-called every time the value of SATISFACTION changes 

`on_anxiety_change`
-called every time the value of ANXIETY changes  

`on_curiosity_change`
-called every time the value of ANXIETY changes  
        
  ### Action hooks
`on_feed`
-called when the squid is fed via Actions>Feed

`on_clean`
-called when the tank is cleaned via Actions>Clean

`on_medicine`
-called when squid is administered medicine via Actions>Medicine

`on_sleep`
-squid calls this when going to sleep
 
`on_wake`
-squid calls this when waking up

`on_startle`
-squid calls this upon being startled  
        
 ### Interaction hooks
`on_rock_pickup`
-called when squid picks up a rock
 
`on_rock_throw`
-called when squid throws a rock
 
`on_decoration_interaction`
-called when squid interacts with a decoration item such as rock or plant
  
`on_ink_cloud`
-squid calls this if he is sufficiently startled to produce an ink cloud (rare)  
        
 ### Neural/memory hooks
`on_neurogenesis`
-called when a new neuron is created via neurogenesis
  
`on_memory_created`
-called when a new memory is created  

`on_memory_to_long_term`
-called when a short term memory is transferred to long term memory  
        
 ### UI hooks
`on_menu_creation`
-custom mod submenu (used with `register_menu_actions` [see below])  
`on_message_display`
-Displays a UI message 
        
### Custom menu action hooks
`register_menu_actions`
-Creates a submenu underneath the 'Plugins' menu  

### Designer Hooks

register_neuron_handler(name, handler, plugin_name, metadata) - plugins call this to register custom neurons