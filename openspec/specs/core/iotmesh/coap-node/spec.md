# CoAP Node Specification

## Purpose

Provides a CoAP server that responds to CoRE Link Format discovery requests and serves sensor data formatted as SenML JSON.

## Requirements

### Requirement: CoAP UDP Binding
The system SHALL bind a UDP socket on port 5683 to listen for CoAP messages, including unicast, broadcast (`255.255.255.255`), and IPv4 multicast (`224.0.1.187`) destinations.

#### Scenario: Bind successfully
- **WHEN** the system initializes network services
- **THEN** it successfully starts listening on UDP port 5683

### Requirement: CoAP IPv4 Multicast Group Membership
The system SHALL join the CoAP all-nodes IPv4 multicast group `224.0.1.187` (RFC 7252 §12.8) after binding the UDP socket, so that it receives multicast discovery requests from other nodes on the local network.

The join SHALL be attempted using `IP_ADD_MEMBERSHIP` with `INADDR_ANY` as the interface address. If the underlying network stack does not support this socket option (e.g. some MicroPython builds), the join SHALL fail gracefully with a log message and the server SHALL continue operating on unicast and broadcast only.

#### Scenario: Multicast join succeeds
- **WHEN** the CoAP server starts and `IP_ADD_MEMBERSHIP` is available
- **THEN** the board joins `224.0.1.187` and logs `[coap] Joined multicast group 224.0.1.187`
- **AND** the board responds to `GET coap://224.0.1.187/.well-known/core` requests

#### Scenario: Multicast join not supported
- **WHEN** the CoAP server starts and `IP_ADD_MEMBERSHIP` is not available on the platform
- **THEN** the board logs `[coap] Multicast join skipped (not supported): <reason>`
- **AND** the server continues listening on unicast and broadcast

### Requirement: CoRE Link Discovery
The system SHALL respond to `GET /.well-known/core` requests with a CoRE Link Format payload enumerating its identity, sensor endpoints (including `</sensors/light>;rt="light";if="sensor"` on boards equipped with a light sensor), and actuator endpoints.

#### Scenario: Discovery request received
- **WHEN** a CoAP `GET` is received on `/.well-known/core`
- **THEN** the system returns `2.05 Content` with the CoRE Link Format string, including `</sensors/light>;rt="light";if="sensor"` on boards with an active light sensor, or omitting it on boards without a light sensor

### Requirement: Identity Endpoint
The system SHALL expose device identity at `GET /id` returning a JSON object with `id` and `type` fields.

#### Scenario: Identity queried
- **WHEN** a CoAP `GET` is received on `/id`
- **THEN** the system returns `2.05 Content` with the identity JSON

### Requirement: Individual Sensor Endpoints
The system SHALL expose `GET /sensors/temperature` and `GET /sensors/humidity`, and on boards with a light sensor SHALL expose `GET /sensors/light`, returning SenML JSON payloads. On boards where a sensor is not connected or unsupported, the corresponding SenML `v` field SHALL be `null` or the endpoint SHALL return `4.04 Not Found`.

#### Scenario: Sensor queried with hardware present
- **WHEN** a CoAP `GET` is received on `/sensors/temperature`, `/sensors/humidity`, or `/sensors/light` and the sensor is connected
- **THEN** the system returns `2.05 Content` with SenML JSON containing the numeric reading (`Cel` for temperature, `%RH` for humidity, `%` for light)

#### Scenario: Sensor queried with no hardware
- **WHEN** a CoAP `GET` is received on `/sensors/temperature`, `/sensors/humidity`, or `/sensors/light` and no corresponding sensor is connected
- **THEN** the system returns `2.05 Content` with SenML JSON where `v` is `null`

### Requirement: Sensor Collection Endpoint
The system SHALL expose `GET /sensors` returning a SenML Pack (JSON array) containing all sensor readings. On boards where sensors are not connected, readings SHALL have `null` values. On boards with a light sensor (Pico 2 W), the array SHALL include `{"n": "light", "u": "%", "v": <pct>}`.

#### Scenario: Collection queried
- **WHEN** a CoAP `GET` is received on `/sensors`
- **THEN** the system returns `2.05 Content` with a SenML Pack JSON array containing all supported sensor metrics (including temperature, humidity, and light on supported boards)

### Requirement: Node Discovery Cache and Caller Resolution
The system SHALL maintain a cache of known network node identities discovered via CoRE Link Format probes. Upon receiving a `POST /display` request from a caller IP, the system SHALL check the cache, trigger a discovery probe if the caller IP is absent, and resolve the caller's device ID or fall back to the last IP octet.

#### Scenario: Caller found in cache
- **WHEN** a `POST /display` arrives from an IP already recorded in the discovery cache
- **THEN** the system resolves and records the caller's device ID for display

#### Scenario: Caller missing from cache but responds to probe
- **WHEN** a `POST /display` arrives from an unknown IP and the discovery probe receives a response
- **THEN** the system updates the cache and records the discovered device ID for display

#### Scenario: Caller missing from cache and does not respond to probe
- **WHEN** a `POST /display` arrives from an unknown IP and discovery probe does not find a device ID
- **THEN** the system records the last octet of the caller's IP address for display

### Requirement: Logger capability advertisement in CoRE Link Format
The system SHALL include a `/logger` resource entry in the `.well-known/core` CoRE Link Format response when the logger capability is present, allowing other nodes to discover that this board can record sensor data.

#### Scenario: Logger resource present in discovery response
- **WHEN** any CoAP client sends `GET /.well-known/core`
- **THEN** the response SHALL include `</logger>;rt="data-logger";if="logger"` in the CoRE Link Format payload

### Requirement: GET /logger endpoint
The system SHALL expose a `GET /logger` CoAP endpoint that returns the current logger session status as a JSON object. The response SHALL include at minimum: `active` (boolean), `buffered` (integer count of total buffered readings), and `last_ntp` (UTC time string or `null`).

#### Scenario: Logger status queried while session active
- **WHEN** a CoAP `GET` is received on `/logger` and a logging session is active
- **THEN** the system SHALL return `2.05 Content` with JSON `{"active": true, "buffered": <n>, "last_ntp": "<HH:MM UTC>"}`

#### Scenario: Logger status queried while idle
- **WHEN** a CoAP `GET` is received on `/logger` and no session is active
- **THEN** the system SHALL return `2.05 Content` with JSON `{"active": false, "buffered": 0, "last_ntp": null}` (or the last known NTP time if available)

### Requirement: CoAP discovery filters by resource type
When the system performs its own outbound CoAP multicast discovery during staging, it SHALL filter responses to include only boards that advertise at least one resource with `rt="temperature"` or `rt="humidity"` in their CoRE Link Format payload.

#### Scenario: Remote board with sensor resources discovered
- **WHEN** the staging discovery receives a `.well-known/core` response containing `rt="temperature"` or `rt="humidity"`
- **THEN** the responding board's IP and device ID SHALL be added to `AppState.log_active_nodes`

#### Scenario: Remote board without sensor resources ignored
- **WHEN** the staging discovery receives a `.well-known/core` response with no temperature or humidity resource types
- **THEN** the responding board SHALL NOT be added to `AppState.log_active_nodes`

### Requirement: GET /log endpoint for data synchronization
The system SHALL expose a `GET /log` CoAP endpoint to allow external controllers to download the persistently stored sensor data from the SD card. The endpoint SHALL accept an optional `cursor` query parameter (in the format `filename:line_number`) and a mandatory `size` query parameter specifying the maximum number of lines to return. If `cursor` is omitted, it SHALL default to the beginning of the oldest available log file (e.g. `YYYY-MM-DD.csv:0`).

The response SHALL be a JSON object containing:
- `data`: A JSON array of the requested CSV lines, formatted as objects `{"ts": "...", "device_id": "...", "temp": ..., "hum": ...}`
- `next_cursor`: The cursor string representing the position immediately after the last returned line, to be used in the subsequent request. If the end of all available files is reached, `next_cursor` SHALL reflect the EOF of the newest file.

#### Scenario: First sync request without cursor
- **WHEN** a CoAP `GET` is received on `/log?size=50`
- **THEN** the system SHALL return `2.05 Content` with up to 50 lines from the oldest available SD card log file and a `next_cursor` indicating the new position

#### Scenario: Sync request with cursor
- **WHEN** a CoAP `GET` is received on `/log?cursor=2026-09-22:50&size=50`
- **THEN** the system SHALL open `2026-09-22.csv`, skip 50 lines, read up to 50 subsequent lines, and return them along with the new `next_cursor`

#### Scenario: Sync request crosses file boundary
- **WHEN** a CoAP `GET` is received on `/log?cursor=2026-09-22:100&size=50` and the file only has 10 remaining lines
- **THEN** the system SHALL return the 10 remaining lines, locate the next chronological file (e.g., `2026-09-23.csv`), read up to 40 lines from it, and return all 50 lines with a `next_cursor` pointing into the new file

#### Scenario: Sync request at EOF of newest file
- **WHEN** a CoAP `GET` is received with a cursor pointing to the exact EOF of the newest file
- **THEN** the system SHALL return `2.05 Content` with an empty `data` array and the same cursor as `next_cursor`

