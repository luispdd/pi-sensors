# Pico 2 W DHT22 Sensor Specification

## Purpose

Defines the hardware interface and pin assignment for the DHT22 temperature and humidity sensor connected to the Pico 2 W board.

## Requirements

### Requirement: Pico 2 W DHT22 Hardware Interface
The system SHALL configure GPIO 15 (Pin 20) on the Raspberry Pi Pico 2 W board as the dedicated data line for the DHT22 temperature and humidity sensor using MicroPython's `dht.DHT22` hardware class.

#### Scenario: DHT22 pin configuration on Pico 2 W
- **WHEN** the `SensorReader` initializes on the Pico 2 W board
- **THEN** it SHALL configure `PIN_DHT22 = 15` in `config.py` and instantiate `dht.DHT22(Pin(15))`

#### Scenario: Sensor telemetry sampling
- **WHEN** `read_sensors()` is invoked on Pico 2 W
- **THEN** it SHALL sample `temperature_c` and `humidity_pct` rounded to 1 decimal place, returning `{"temperature_c": float, "humidity_pct": float, "read_errors": int}`
