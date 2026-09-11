## Purpose

Connects the Raspberry Pi Pico W to a local WiFi network and hosts an asynchronous HTTP server to serve sensor telemetry as structured JSON over the network.

## ADDED Requirements

### Requirement: WiFi network connection
The system SHALL connect to the configured local 2.4GHz WiFi network (SSID and password) upon boot and maintain network connectivity.

#### Scenario: Successful network connection
- **WHEN** the device boots up with valid network credentials in range
- **THEN** it joins the WiFi network, obtains an IP via DHCP, and starts the HTTP server

#### Scenario: Network disconnection and automatic retry
- **WHEN** WiFi connection drops or fails during runtime
- **THEN** the system SHALL attempt background reconnection without freezing the sensor reading and OLED display loops

### Requirement: JSON HTTP endpoint /sensors
The system SHALL serve an HTTP GET endpoint at `/sensors` responding with valid JSON containing the latest environmental measurements.

#### Scenario: Successful GET /sensors request
- **WHEN** a client performs an HTTP `GET /sensors` request (e.g. `http://<ip>/sensors`)
- **THEN** the system returns HTTP 200 with header `Content-Type: application/json` and a JSON body containing temperature, humidity, light status, timestamp or uptime, and status

#### Scenario: Unrecognized route request
- **WHEN** a client requests a path other than `/sensors`
- **THEN** the system returns HTTP 404 Not Found with a JSON error payload or plain text
