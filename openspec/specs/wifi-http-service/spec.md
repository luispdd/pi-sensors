# WiFi HTTP Service Specification

## Purpose

Connects the Raspberry Pi Pico W to a local WiFi network, tracks cumulative API query volume, and hosts an asynchronous HTTP server to serve sensor telemetry as structured JSON over the network.

## Requirements

### Requirement: WiFi network connection and external secrets configuration
The system SHALL obtain local 2.4GHz WiFi network credentials (SSID and password) from an external `secrets.py` configuration file ignored by Git.

#### Scenario: Successful network connection
- **WHEN** the device boots up with a valid `secrets.py` containing non-empty `WIFI_SSID` and `WIFI_PASSWORD` within network range
- **THEN** it joins the WiFi network, obtains an IP via DHCP, and starts the HTTP server

#### Scenario: Missing or invalid secrets file
- **WHEN** `secrets.py` does not exist or does not contain valid, non-empty `WIFI_SSID` and `WIFI_PASSWORD` credentials
- **THEN** the system SHALL record a configuration error status and prevent WiFi connection attempts without blocking sensor reading and display loops

#### Scenario: Network disconnection and automatic retry
- **WHEN** WiFi connection drops or fails during runtime
- **THEN** the system SHALL attempt background reconnection without freezing the sensor reading and OLED display loops

### Requirement: JSON HTTP endpoint /sensors and request tracking
The system SHALL serve an HTTP GET endpoint at `/sensors` responding with valid JSON containing the latest environmental measurements, and maintain a cumulative counter of successful requests.

#### Scenario: Successful GET /sensors request and counter increment
- **WHEN** a client performs an HTTP `GET /sensors` request (e.g. `http://<ip>/sensors`)
- **THEN** the system increments the request counter by 1, and returns HTTP 200 with header `Content-Type: application/json` and a JSON body containing temperature, humidity, light status, request count, uptime, and status

#### Scenario: Unrecognized route request
- **WHEN** a client requests a path other than `/sensors`
- **THEN** the system returns HTTP 404 Not Found without incrementing the `/sensors` request counter
