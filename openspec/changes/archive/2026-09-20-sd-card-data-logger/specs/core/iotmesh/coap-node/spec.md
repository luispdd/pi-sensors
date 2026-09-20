## ADDED Requirements

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
