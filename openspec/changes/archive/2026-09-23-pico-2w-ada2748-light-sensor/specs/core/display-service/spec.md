## MODIFIED Requirements

### Requirement: Real-time sensor metrics display
The system SHALL update the connected display with the latest temperature, humidity readings, and on boards equipped with a light sensor (Pico 2 W with ADA2748), ambient light percentage, alongside network status. On boards where sensors are not yet connected or values are unavailable, the display SHALL render placeholder values (e.g., `--.-C`, `--%`, `L:--%`).

#### Scenario: Displaying current values
- **WHEN** new sensor measurements are read from the sensors and the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the display SHALL show formatted temperature in °C, relative humidity in %, and on supported boards (Pico 2 W) light percentage formatted as `L:<val>%` (e.g., `L:50%`) on the telemetry line without clipping within the screen boundaries

#### Scenario: Displaying placeholder values when sensors unavailable
- **WHEN** the mode is `MODE_SENSOR_DISPLAY` and sensor readings are `null`
- **THEN** the display SHALL render `--.-C` for temperature, `--%` for humidity, and `L:--%` for light percentage when supported
