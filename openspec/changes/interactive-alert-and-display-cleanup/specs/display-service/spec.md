## MODIFIED Requirements

### Requirement: Real-time sensor metrics display
The system SHALL update the SSD1306 OLED screen (I2C SDA on GP0, SCL on GP1) with the latest temperature and humidity readings, omitting light sensor readings.

#### Scenario: Displaying current values
- **WHEN** new sensor measurements are read from the sensors
- **THEN** the OLED screen displays formatted temperature in °C and relative humidity in % without light status

### Requirement: Network connectivity, remote URL, and request count display
The system SHALL present the device's assigned local IP address (without `http://` prefix), the remote endpoint route `/info`, the cumulative count of requests served, and the last request caller on the OLED display.

#### Scenario: WiFi connected with remote route and hit count
- **WHEN** the Pico W connects to WiFi and starts network services
- **THEN** the OLED screen displays the assigned IPv4 address without protocol prefix, the route `/info`, the total count of requests served, and the last request caller identifier

#### Scenario: WiFi request received
- **WHEN** an HTTP or CoAP client sends a request
- **THEN** the OLED screen reflects the updated request counter and updates the last caller indicator on its next screen refresh cycle

#### Scenario: WiFi connecting or disconnected
- **WHEN** the Pico W is attempting connection or loses connection
- **THEN** the OLED screen displays a connecting or offline indicator while attempting reconnect

#### Scenario: Missing or invalid WiFi configuration error
- **WHEN** the WiFi secrets file does not exist or lacks valid SSID/password credentials
- **THEN** the OLED screen displays an error message reporting the missing or invalid WiFi configuration
