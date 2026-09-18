## MODIFIED Requirements

### Requirement: Display Operation Modes
The system SHALL support three mutually exclusive display modes, identified by named constants:
- `MODE_SENSOR_DISPLAY` (0): Display on, continuously refreshed with sensor metrics and network status.
- `MODE_SEMI_SLEEP` (1): Display off; sensor metrics refresh suspended.
- `MODE_MESSAGE` (2): Display shows a remotely posted override message; alert LED is on.

The active mode SHALL be stored in `AppState` as a single `mode` field initialised to `MODE_SENSOR_DISPLAY` at startup.

#### Scenario: Startup display state
- **WHEN** the node powers on
- **THEN** the display mode SHALL be `MODE_SENSOR_DISPLAY` and the display SHALL begin showing sensor metrics (or placeholders if sensors are not yet available)

#### Scenario: Display refresh in SENSOR_DISPLAY mode
- **WHEN** the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the display SHALL refresh at `DISPLAY_REFRESH_INTERVAL_S` with the latest temperature, humidity (or placeholder values), IP, request count, and last caller

#### Scenario: Display blanked on entering SEMI_SLEEP
- **WHEN** the mode transitions to `MODE_SEMI_SLEEP`
- **THEN** the display SHALL be cleared and powered off immediately, and SHALL NOT refresh again until the mode changes

#### Scenario: Display resume after SEMI_SLEEP
- **WHEN** the mode transitions out of `MODE_SEMI_SLEEP` to `MODE_SENSOR_DISPLAY`
- **THEN** the display SHALL resume normal sensor-metrics refresh

### Requirement: Real-time sensor metrics display
The system SHALL update the connected display with the latest temperature, humidity readings and network status. On boards where sensors are not yet connected, the display SHALL render placeholder values (e.g., `--.-C`, `--%`).

#### Scenario: Displaying current values
- **WHEN** new sensor measurements are read from the sensors and the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the display SHALL show formatted temperature in °C and relative humidity in %

#### Scenario: Displaying placeholder values when sensors unavailable
- **WHEN** the mode is `MODE_SENSOR_DISPLAY` and sensor readings are `null`
- **THEN** the display SHALL render `--.-C` for temperature and `--%` for humidity

### Requirement: Network connectivity, remote URL, and request count display
The system SHALL present the device's assigned local IP address, the remote HTTP route `/info`, and the cumulative count of requests served over WiFi on the display when in `MODE_SENSOR_DISPLAY`.

#### Scenario: WiFi connected with remote route and hit count
- **WHEN** the node connects to WiFi, starts the HTTP server, and the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the display SHALL show the assigned IPv4 address, the route `/info`, and the total count of requests served

#### Scenario: WiFi request received
- **WHEN** an HTTP client requests `/info` and the counter increments
- **THEN** the display SHALL reflect the updated request counter on its next refresh cycle while in `MODE_SENSOR_DISPLAY`

#### Scenario: WiFi connecting or disconnected
- **WHEN** the node is attempting connection or loses connection
- **THEN** the display SHALL show a connecting or offline indicator while in `MODE_SENSOR_DISPLAY`

#### Scenario: Missing or invalid WiFi configuration error
- **WHEN** the WiFi secrets file does not exist or lacks valid SSID/password credentials
- **THEN** the display SHALL show an error message reporting the missing or invalid WiFi configuration

### Requirement: Display hardware driver dependency
The system SHALL use the appropriate display driver for the board's hardware:
- On boards with an SSD1306 OLED (I2C): use the `stlehmann/micropython-ssd1306` driver from `boards/<board-name>/lib/ssd1306.py`.
- On boards with an ST7735 TFT (SPI): use the `boochow/MicroPython-ST7735` driver from `boards/<board-name>/lib/ST7735.py`.

#### Scenario: Driver loading from lib directory
- **WHEN** the display service initializes
- **THEN** it SHALL import the appropriate display driver class from `lib/` and instantiate the display with the board's configured interface
