# Display Service Specification

## Purpose

Renders real-time environmental metrics, system status, WiFi network connection parameters, remote access endpoint URL, and API request count onto a connected SSD1306 OLED display.

## Requirements

### Requirement: Real-time sensor metrics display
The system SHALL update the SSD1306 OLED screen (I2C SDA on GP0, SCL on GP1) with the latest temperature, humidity, and light readings.

#### Scenario: Displaying current values
- **WHEN** new sensor measurements are read from the sensors
- **THEN** the OLED screen displays formatted temperature in °C, relative humidity in %, and light state

### Requirement: Network connectivity, remote URL, and request count display
The system SHALL present the device's assigned local IP address, the complete remote HTTP route to query the data, and the cumulative count of requests served over WiFi on the OLED display.

#### Scenario: WiFi connected with remote route and hit count
- **WHEN** the Pico W connects to WiFi and starts the HTTP server
- **THEN** the OLED screen displays the assigned IPv4 address, the remote route `http://<ip>/sensors`, and the total count of WiFi requests served (e.g., `Hits: 12`)

#### Scenario: WiFi request received
- **WHEN** an HTTP client requests `/sensors` and the counter increments
- **THEN** the OLED screen reflects the updated request counter on its next screen refresh cycle

#### Scenario: WiFi connecting or disconnected
- **WHEN** the Pico W is attempting connection or loses connection
- **THEN** the OLED screen displays a connecting or offline indicator while attempting reconnect

#### Scenario: Missing or invalid WiFi configuration error
- **WHEN** the WiFi secrets file does not exist or lacks valid SSID/password credentials
- **THEN** the OLED screen displays an error message reporting the missing or invalid WiFi configuration

### Requirement: OLED display hardware driver dependency
The system SHALL use the `stlehmann/micropython-ssd1306` driver located at `src/lib/ssd1306.py` (accessible in the `lib/` directory) for I2C communication with the SSD1306 OLED controller.

#### Scenario: Driver loading from lib directory
- **WHEN** the display service initializes
- **THEN** it SHALL import the `SSD1306_I2C` class from the `ssd1306` module located in `lib/` (within `src/`) and instantiate the display driver with the configured I2C interface
