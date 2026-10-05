## ADDED Requirements

### Requirement: Live Monitoring Control API
The system SHALL expose `POST /api/live/start`, `POST /api/live/stop` and `GET /api/live/status`. Start and stop SHALL act on every node currently in the discovery cache, by sending each one a CoAP `POST /live/start` (with this controller's broker address and the requested `rate_ms`) or `POST /live/stop`. Live mode SHALL only be started from this API, never automatically on controller boot.

#### Scenario: Start live on all nodes
- **WHEN** an HTTP `POST` is received at `/api/live/start` with `{"rate_ms": N}`
- **THEN** the system SHALL send CoAP `POST /live/start` to every discovered node, record each node in its live status, and return HTTP 200 with the per-node result

#### Scenario: Start again to include a new node
- **WHEN** `POST /api/live/start` is sent again while some nodes are already live at the same `rate_ms`
- **THEN** the system SHALL send the request to all discovered nodes again, and nodes already live at that rate SHALL be unaffected

#### Scenario: Stop live on all nodes
- **WHEN** an HTTP `POST` is received at `/api/live/stop`
- **THEN** the system SHALL send CoAP `POST /live/stop` to every discovered node, clear its live status and return HTTP 200

#### Scenario: Unreachable node
- **WHEN** a CoAP request to one node fails
- **THEN** the system SHALL still process the remaining nodes and report that node's failure in the response

#### Scenario: Query live status
- **WHEN** an HTTP `GET` is received at `/api/live/status`
- **THEN** the system SHALL return HTTP 200 with the controller's own record of live nodes (`device_id`, `rate_ms`, `started_at`), without querying the nodes

#### Scenario: Invalid rate
- **WHEN** `POST /api/live/start` has a missing or non-positive `rate_ms`
- **THEN** the system SHALL return HTTP 400 and contact no node

### Requirement: Live MQTT Ingestion
The system SHALL run alongside a Mosquitto broker on the same device and SHALL subscribe to `iotmesh/+/live`. Each received message SHALL be stored in `readings` using the node's own timestamp and metrics, with `is_fine_tuned = 1`, via the same insert logic and `(timestamp, device_id)` uniqueness as regular sync.

#### Scenario: Live message stored
- **WHEN** a message arrives on `iotmesh/<device_id>/live`
- **THEN** the system SHALL insert a reading with the message's timestamp and `is_fine_tuned = 1`

#### Scenario: Collision with logger row
- **WHEN** a live message has the same `(timestamp, device_id)` as an existing row
- **THEN** the system SHALL keep the existing row and ignore the live value

#### Scenario: Malformed message
- **WHEN** a message on a live topic cannot be parsed
- **THEN** the system SHALL discard it and keep processing later messages

### Requirement: Fine-Tuned Reading Flag
The `readings` table SHALL have an `is_fine_tuned` boolean column, not null, default 0. Rows from the regular logger sync SHALL have `is_fine_tuned = 0`. Existing databases SHALL be migrated without losing data.

#### Scenario: Regular sync row
- **WHEN** a reading is ingested from the logger sync
- **THEN** it SHALL be stored with `is_fine_tuned = 0`

#### Scenario: Existing database upgraded
- **WHEN** the controller starts against a database without the column
- **THEN** the column SHALL be added and all existing rows SHALL have `is_fine_tuned = 0`

### Requirement: Readings Fine-Tuned Filter
`GET /api/readings` SHALL accept an optional `is_fine_tuned` query parameter. When given as `false`, only regular rows SHALL be returned. When omitted, all rows SHALL be returned. Returned readings SHALL include their `is_fine_tuned` value and SHALL be ordered chronologically ascending by timestamp (when `limit` is specified, it SHALL select the latest N records and return them in ascending order).

#### Scenario: Regular only
- **WHEN** `GET /api/readings?is_fine_tuned=false` is received
- **THEN** the response SHALL contain only rows with `is_fine_tuned = 0`

#### Scenario: No filter
- **WHEN** `GET /api/readings` is received without the parameter
- **THEN** the response SHALL contain both regular and live rows

#### Scenario: Chronological ascending order
- **WHEN** `GET /api/readings` is received with or without `limit`
- **THEN** the returned readings SHALL be ordered chronologically ascending by timestamp

### Requirement: WebSocket Reading Push
The system SHALL expose a WebSocket endpoint that pushes every newly inserted reading, from either the regular sync or live MQTT, as `{device_id, timestamp, metrics, is_fine_tuned}` to all connected clients. Rows ignored as duplicates SHALL NOT be pushed.

#### Scenario: Live reading pushed
- **WHEN** a live reading is inserted and a client is connected
- **THEN** the client SHALL receive that reading with `is_fine_tuned = true`

#### Scenario: Regular sync reading pushed
- **WHEN** a sync inserts new rows and a client is connected
- **THEN** the client SHALL receive each new row with `is_fine_tuned = false`

#### Scenario: No clients connected
- **WHEN** no WebSocket client is connected
- **THEN** readings SHALL still be stored normally
