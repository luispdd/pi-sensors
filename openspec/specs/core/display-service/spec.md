# Display Service Specification

## Purpose

Renders real-time environmental metrics, system status, WiFi network connection parameters, remote access endpoint URL, and API request count onto a connected SSD1306 OLED display.

## Requirements

### Requirement: Display Operation Modes
The system SHALL support three mutually exclusive display modes, identified by named constants:
- `MODE_SENSOR_DISPLAY` (0): OLED on, continuously refreshed with sensor metrics and network status.
- `MODE_SEMI_SLEEP` (1): OLED off; sensor metrics refresh suspended.
- `MODE_MESSAGE` (2): OLED shows a remotely posted override message; alert LED is on.

The active mode SHALL be stored in `AppState` as a single `mode` field initialised to `MODE_SENSOR_DISPLAY` at startup.

#### Scenario: Startup display state
- **WHEN** the node powers on
- **THEN** the display mode SHALL be `MODE_SENSOR_DISPLAY` and the OLED SHALL begin showing sensor metrics

#### Scenario: Display refresh in SENSOR_DISPLAY mode
- **WHEN** the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the OLED SHALL refresh at `DISPLAY_REFRESH_INTERVAL_S` with the latest temperature, humidity, IP, request count, and last caller

#### Scenario: Display blanked on entering SEMI_SLEEP
- **WHEN** the mode transitions to `MODE_SEMI_SLEEP`
- **THEN** the OLED SHALL be cleared and powered off immediately, and SHALL NOT refresh again until the mode changes

#### Scenario: Display resume after SEMI_SLEEP
- **WHEN** the mode transitions out of `MODE_SEMI_SLEEP` to `MODE_SENSOR_DISPLAY`
- **THEN** the OLED SHALL resume normal sensor-metrics refresh

### Requirement: Real-time sensor metrics display
The system SHALL update the SSD1306 OLED screen (I2C SDA on GP0, SCL on GP1) with the latest temperature, humidity readings and network status.

#### Scenario: Displaying current values
- **WHEN** new sensor measurements are read from the sensors and the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the OLED screen SHALL display formatted temperature in °C and relative humidity in %

### Requirement: Network connectivity, remote URL, and request count display
The system SHALL present the device's assigned local IP address, the remote HTTP route `/info`, and the cumulative count of requests served over WiFi on the OLED display when in `MODE_SENSOR_DISPLAY`.

#### Scenario: WiFi connected with remote route and hit count
- **WHEN** the Pico W connects to WiFi, starts the HTTP server, and the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the OLED screen SHALL display the assigned IPv4 address, the route `/info`, and the total count of requests served

#### Scenario: WiFi request received
- **WHEN** an HTTP client requests `/info` and the counter increments
- **THEN** the OLED screen SHALL reflect the updated request counter on its next refresh cycle while in `MODE_SENSOR_DISPLAY`

#### Scenario: WiFi connecting or disconnected
- **WHEN** the Pico W is attempting connection or loses connection
- **THEN** the OLED screen SHALL display a connecting or offline indicator while in `MODE_SENSOR_DISPLAY`

#### Scenario: Missing or invalid WiFi configuration error
- **WHEN** the WiFi secrets file does not exist or lacks valid SSID/password credentials
- **THEN** the OLED screen SHALL display an error message reporting the missing or invalid WiFi configuration

### Requirement: OLED display hardware driver dependency
The system SHALL use the `stlehmann/micropython-ssd1306` driver located at `boards/<board-name>/lib/ssd1306.py` (accessible in the `lib/` directory) for I2C communication with the SSD1306 OLED controller.

#### Scenario: Driver loading from lib directory
- **WHEN** the display service initializes
- **THEN** it SHALL import the `SSD1306_I2C` class from the `ssd1306` module located in `lib/` (within `boards/<board-name>/`) and instantiate the display driver with the configured I2C interface
