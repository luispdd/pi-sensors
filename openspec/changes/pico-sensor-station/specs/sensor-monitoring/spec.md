## Purpose

Provides periodic environmental telemetry by acquiring ambient temperature, relative humidity, and digital light presence measurements from connected sensors.

## ADDED Requirements

### Requirement: Periodic DHT22 sensor readings
The system SHALL sample temperature (in Celsius) and relative humidity (percentage) from the DHT22 sensor on GP15 at regular intervals of at least 1 second.

#### Scenario: Successful measurement reading
- **WHEN** the sampling timer triggers and the DHT22 signal is intact
- **THEN** valid numeric values for temperature and humidity SHALL be cached for display and HTTP serving

#### Scenario: Sensor read failure handling
- **WHEN** reading the DHT22 fails due to checksum errors or timing timeout
- **THEN** the system SHALL retain the last known valid values and increment a read error counter without crashing the execution loop

### Requirement: Ambient light detection
The system SHALL monitor digital output state from the LM393 photoresistor light sensor module on GP14 to determine whether the environment is currently illuminated or dark.

#### Scenario: Light detected
- **WHEN** the light level exceeds the LM393 potentiometer threshold (digital signal active)
- **THEN** the system SHALL record the light status as "light" (or boolean true)

#### Scenario: Darkness detected
- **WHEN** the light level falls below the LM393 threshold
- **THEN** the system SHALL record the light status as "dark" (or boolean false)
