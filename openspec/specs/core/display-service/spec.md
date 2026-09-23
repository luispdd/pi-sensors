# Display Service Specification

## Purpose

Renders real-time environmental metrics, system status, WiFi network connection parameters, remote access endpoint URL, and API request count onto a connected display (SSD1306 OLED or ST7735 TFT).

## Requirements

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
The system SHALL update the connected display with the latest temperature, humidity readings, and on boards equipped with a light sensor (Pico 2 W with ADA2748), ambient light percentage, alongside network status. On boards where sensors are not yet connected or values are unavailable, the display SHALL render placeholder values (e.g., `--.-C`, `--%`, `L:--%`).

#### Scenario: Displaying current values
- **WHEN** new sensor measurements are read from the sensors and the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the display SHALL show formatted temperature in °C, relative humidity in %, and on supported boards (Pico 2 W) light percentage formatted as `L:<val>%` (e.g., `L:50%`) on the telemetry line without clipping within the screen boundaries

#### Scenario: Displaying placeholder values when sensors unavailable
- **WHEN** the mode is `MODE_SENSOR_DISPLAY` and sensor readings are `null`
- **THEN** the display SHALL render `--.-C` for temperature, `--%` for humidity, and `L:--%` for light percentage when supported

### Requirement: Network connectivity, remote URL, and request count display
The system SHALL present the device's assigned local IP address (without `http://` prefix), the remote HTTP route `/info`, the cumulative count of requests served over WiFi, and the last request caller on the display when in `MODE_SENSOR_DISPLAY`.

#### Scenario: WiFi connected with remote route and hit count
- **WHEN** the node connects to WiFi, starts the network services, and the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the display SHALL show the assigned IPv4 address without protocol prefix, the route `/info`, the total count of requests served, and the last request caller identifier

#### Scenario: WiFi request received
- **WHEN** an HTTP or CoAP client sends a request and the counter increments
- **THEN** the display SHALL reflect the updated request counter and update the last caller indicator on its next refresh cycle while in `MODE_SENSOR_DISPLAY`

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

### Requirement: Logging status section on TFT during active session
When `AppState.logging_active` is `True`, the system SHALL render a logging status section in the lower area of the TFT display below the standard telemetry content. The section SHALL show: a horizontal divider, active board IDs (truncated to up to 7 characters each, prefixed with `LOG`, wrapping across up to two lines if needed to fit the 20-character screen width, allowing multiple board IDs such as `LOG pico-2w pico-1w` to render on a single line), the total buffered reading count, and the last NTP sync time.

#### Scenario: Logging status section rendered during active session
- **WHEN** `AppState.logging_active` is `True` and the display refreshes in `MODE_SENSOR_DISPLAY`
- **THEN** the lower area of the TFT SHALL show: a divider line, the board-list line(s) (prefixed with `LOG`, fitting on one line when total length <= 20 characters, wrapping to a second line only if needed), a buffered-count line (e.g. `Buf: 12 reads`), and the last NTP time line (e.g. `NTP: 10:04 UTC`)

#### Scenario: Logging status section absent when session inactive
- **WHEN** `AppState.logging_active` is `False`
- **THEN** the TFT SHALL render the standard layout without any logging section

### Requirement: Removal of title header to maximize screen space
The telemetry display SHALL omit the static title header (`Pico 2 W IoTMesh`) and its separator line, starting telemetry and network metrics directly from the top of the display to maximize vertical space and cleanly fit telemetry, requests, caller information, and the logging status section without overflow.

#### Scenario: Screen space optimized
- **WHEN** the standard status screen is displayed
- **THEN** telemetry data starts near y=8, followed by network status, requests served, and last caller, allowing the logging status section to fit within the 160-pixel display height without requiring a separate compact layout mode

### Requirement: LOGGER_CONFIRM screen takes over the TFT
When `AppState.logger_state` is `LOGGER_CONFIRM`, the system SHALL replace the standard sensor display with a full-screen confirmation layout showing: the page title `LOGGER SETUP`, the current UTC date and time from NTP, the list of discovered boards (one per line, prefixed with `*`), and the available user options (`[click] START` and `[hold] CANCEL`). If an error is present in `AppState.log_error`, the error SHALL replace the board list and only the cancel option SHALL be shown.

#### Scenario: Confirm screen rendered — no errors
- **WHEN** `AppState.logger_state` is `LOGGER_CONFIRM` and `AppState.log_error` is `None`
- **THEN** the TFT SHALL show the LOGGER SETUP title, the NTP date/time, discovered board names, and both START and CANCEL options

#### Scenario: Confirm screen rendered — with errors
- **WHEN** `AppState.logger_state` is `LOGGER_CONFIRM` and `AppState.log_error` is set
- **THEN** the TFT SHALL show the LOGGER SETUP title, the error message in red, and only the CANCEL option

### Requirement: LOGGER_STAGING transitional display
When `AppState.logger_state` is `LOGGER_STAGING`, the system SHALL display a transitional status on the TFT indicating that NTP sync and discovery are in progress.

#### Scenario: Staging progress shown
- **WHEN** `AppState.logger_state` is `LOGGER_STAGING`
- **THEN** the TFT SHALL show a message such as `"Preparing..."` or `"Scanning..."` replacing the standard content

### Requirement: Log error display on normal screen
When `AppState.log_error` is set during an active session (e.g. SD card failure), the error string SHALL appear in the logging status section in place of the NTP time line, rendered in red.

#### Scenario: SD error shown in logging section
- **WHEN** `AppState.logging_active` is `True` and `AppState.log_error` is set
- **THEN** the error string SHALL be shown in the logging status section on the TFT in red, replacing the NTP time line

