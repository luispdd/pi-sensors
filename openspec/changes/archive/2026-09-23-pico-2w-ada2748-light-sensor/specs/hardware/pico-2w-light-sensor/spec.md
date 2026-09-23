## Purpose

Defines the hardware interface, ADC pin assignment, and voltage sampling for the Adafruit ALS-PT19 (ADA2748) analog ambient light sensor connected to the Raspberry Pi Pico 2 W board.

## ADDED Requirements

### Requirement: Pico 2 W ALS-PT19 Hardware Pin Assignment and ADC Sampling
The system SHALL configure GPIO 26 (Pin 31, ADC0) on the Raspberry Pi Pico 2 W board as the analog input channel for the Adafruit ALS-PT19 (ADA2748) ambient light sensor breakout.

#### Scenario: ADC hardware initialization on Pico 2 W
- **WHEN** the `SensorReader` initializes on the Pico 2 W board
- **THEN** it SHALL configure `PIN_LIGHT_ADC = 26` and `LIGHT_SCALE_FACTOR` in `settings/config.py`, instantiate `machine.ADC(Pin(26))`, and configure the scaling multiplier from `LIGHT_SCALE_FACTOR`

#### Scenario: ADC oversampling and noise filtering
- **WHEN** reading the ALS-PT19 sensor during a sampling cycle
- **THEN** the system SHALL perform oversampling by averaging 32 successive 16-bit ADC samples (`read_u16()`) to filter out electrical noise, LED PWM, and 100Hz/120Hz AC artificial lighting ripple before calculating percentage values

#### Scenario: Ambient light percentage calculation and upper ceiling
- **WHEN** `read_sensors()` computes the final light percentage from the averaged ADC reading
- **THEN** the system SHALL compute `raw_pct = (raw_u16 / 65535.0) * 100.0`, scale it by `LIGHT_SCALE_FACTOR`, round to 1 decimal place, and cap the result at `100.0%` via `light_pct = min(100.0, round(raw_pct * LIGHT_SCALE_FACTOR, 1))`

#### Scenario: Sensor failure or ADC disconnected
- **WHEN** reading the ADC fails due to hardware faults or uninitialized ADC
- **THEN** the system SHALL retain the last known valid light reading or return `null` without throwing an unhandled exception or halting the sensor task
