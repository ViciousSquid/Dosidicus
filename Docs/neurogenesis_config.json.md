# Neurogenesis Configuration Reference

## File Purpose

This JSON configuration file controls how new neurons are created in the squid's neural network, simulating the biological process of neurogenesis.

## General Settings

### Global Neurogenesis Parameters

*   enabled: Turns neurogenesis on/off completely (default: true)
*   cooldown: Minimum seconds between neuron creation (default: 300.0 = 5 minutes)
*   max\_neurons: Maximum number of neurons the network can grow to (default: 20)
*   initial\_neuron\_count: Starting number of neurons (default: 7)

## Trigger Settings

### Novelty Trigger

Creates neurons when encountering new experiences

*   enabled: Turns this trigger on/off (default: true)
*   threshold: Minimum novelty score needed (default: 0.7)
*   decay\_rate: How quickly novelty wears off (0-1) (default: 0.95)
*   max\_counter: Maximum novelty accumulation (default: 10.0)
*   min\_curiosity: Minimum curiosity level required (default: 0.3)
*   personality\_modifiers:
    *   adventurous: 1.2 (20% more likely)
    *   timid: 0.8 (20% less likely)

### Stress Trigger

Creates neurons in response to stressful situations

*   enabled: Turns this trigger on/off (default: true)
*   threshold: Minimum stress score needed (default: 0.8)
*   decay\_rate: How quickly stress diminishes (default: 0.9)
*   max\_counter: Maximum stress accumulation (default: 10.0)
*   min\_anxiety: Minimum anxiety level required (default: 0.4)
*   personality\_modifiers:
    *   timid: 1.5 (50% more likely)
    *   energetic: 0.7 (30% less likely)

### Reward Trigger

Creates neurons in response to positive experiences

*   enabled: Turns this trigger on/off (default: true)
*   threshold: Minimum reward score needed (default: 0.6)
*   decay\_rate: How quickly reward memory fades (default: 0.85)
*   max\_counter: Maximum reward accumulation (default: 10.0)
*   min\_satisfaction: Minimum satisfaction level required (default: 0.5)
*   boost\_multiplier: How much rewards amplify learning (default: 1.1)

## Neuron Properties

*   base\_activation: Starting activation level (0-1) (default: 0.5)
*   position\_variance: Pixel range for random neuron placement (default: 50)
*   default\_connections: Whether to auto-connect new neurons (default: true)
*   connection\_strength: Initial connection weight (default: 0.3)
*   reciprocal\_strength: Strength of return connections (default: 0.15)

## Visual Appearance

### Colors

*   novelty: RGB values for novelty neurons (default: \[255, 255, 150\] - pale yellow)
*   stress: RGB values for stress neurons (default: \[255, 150, 150\] - light red)
*   reward: RGB values for reward neurons (default: \[150, 255, 150\] - light green)

### Shapes

*   novelty: Shape for novelty neurons (default: "triangle")
*   stress: Shape for stress neurons (default: "square")
*   reward: Shape for reward neurons (default: "circle")

## Visual Effects

*   highlight\_duration: Seconds to highlight new neurons (default: 5.0)
*   highlight\_radius: Size of highlight effect in pixels (default: 40)
*   pulse\_effect: Whether neurons pulse when active (default: true)
*   pulse\_speed: Speed of pulsing animation (cycles/sec) (default: 0.5)

### Implementation Notes

All threshold values range from 0.0 to 1.0, representing percentages of maximum possible values.

Decay rates are multipliers applied per second (0.95 means 5% reduction per second).

Personality modifiers multiply the base threshold values (1.2 = 20% easier to trigger).
