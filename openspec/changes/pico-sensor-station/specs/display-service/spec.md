## Purpose

Renders real-time environmental metrics, system status, and WiFi network connection parameters onto a connected SSD1306 OLED display.

## ADDED Requirements

### Requirement: Real-time sensor metrics display
The system SHALL update the SSD1306 OLED screen (I2C SDA on GP0, SCL on GP1) with the latest temperature, humidity, and light readings.

#### Scenario: Displaying current values
- **WHEN** new sensor measurements are read from the sensors
- **THEN** the OLED screen displays formatted temperature in °C, relative humidity in %, and light state

### Requirement: Network connectivity and IP display
The system SHALL present network connection status and the device's assigned local IP address on the OLED screen.

#### Scenario: WiFi connected
- **WHEN** the Pico W establishes a connection to the local WiFi access point
- **THEN** the OLED screen displays the assigned IPv4 address and network indicator

#### Scenario: WiFi connecting or disconnected
- **WHEN** the Pico W is attempting connection or loses connection
- **THEN** the OLED screen displays a connecting or offline indicator while attempting reconnect
