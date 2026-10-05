# Controller Specification

## Purpose

Provides an active central controller that discovers IoTMesh nodes over CoAP, synchronizes persistent sensor logs into a local SQLite database with dynamic JSON metrics, runs a periodic polling loop with on-demand sync triggers, and exposes an HTTP management API.

## Requirements

### Requirement: CoAP Node Discovery
The system SHALL discover IoTMesh nodes on the local area network by broadcasting and multicasting CoAP `GET /.well-known/core` discovery requests to UDP port 5683 and caching responding node identities, IP addresses, and advertised resource types (`rt`).

#### Scenario: Network discovery identifies sensor and logger nodes
- **WHEN** a discovery scan is triggered on startup or via API
- **THEN** the system SHALL send discovery probes to broadcast and multicast destinations, parse responding CoRE Link Format payloads, and register discovered nodes with their IP addresses, device IDs, and advertised capabilities in local state

#### Scenario: Periodic refresh updates node cache
- **WHEN** a known node ceases to respond or updates its IP
- **THEN** subsequent discovery scans SHALL update the local node registry accordingly

### Requirement: Cursor-Based Log Synchronization
The system SHALL synchronize historical sensor logs from nodes advertising data sync capabilities (`rt="data-sync"`) using cursor-based pagination over CoAP `GET /log?cursor=<c>&size=<s>`. Synchronization SHALL perform a catch-up burst of sequential paginated requests until the end of available logs is reached.

#### Scenario: Initial sync from oldest log entry
- **WHEN** synchronization begins for a logger node with no recorded sync cursor
- **THEN** the system SHALL request `GET /log?size=50` without a cursor, ingest the returned records, update the recorded cursor to `next_cursor`, and continue requesting subsequent pages until `data` is empty or `next_cursor` matches the requested cursor

#### Scenario: Resuming sync from existing cursor
- **WHEN** synchronization triggers for a logger node with an existing recorded cursor
- **THEN** the system SHALL send `GET /log?cursor=<last_cursor>&size=50` and advance sequentially until caught up with the newest record

#### Scenario: Adaptive pagination prevents UDP packet overflow
- **WHEN** fetching log pages over CoAP (`GET /log`) from constrained nodes
- **THEN** the system SHALL use a default page size of 5 records to fit safely within 1024-byte UDP datagram buffers, and upon receiving an empty payload (`b''`) with a `2.05 Content` response code, SHALL automatically retry with half the page size (`size = max(1, size // 2)`) to avoid synchronization deadlocks

### Requirement: Decoupled Sync Execution and Background Cadence
The system SHALL provide a decoupled synchronization operation that is executable on demand and periodically driven by an automated background loop. An asynchronous lock SHALL ensure that on-demand sync requests and automated cadence executions do not run concurrently.

#### Scenario: On-demand sync execution
- **WHEN** an on-demand sync is requested while no sync is currently running
- **THEN** the system SHALL acquire the sync lock, run the catch-up synchronization loop across all discovered loggers, update cursors and records, and return the sync summary

#### Scenario: Concurrent sync request rejected or queued safely
- **WHEN** an on-demand sync is requested while an automated or prior sync is actively executing
- **THEN** the system SHALL safely handle the collision without corrupting the sync cursor or issuing overlapping requests to the logger

#### Scenario: Background cadence loop
- **WHEN** the controller service is running
- **THEN** the system SHALL automatically execute the synchronization routine every 300 seconds

#### Scenario: Sync status error and reachability reporting
- **WHEN** a background cadence or on-demand sync execution completes across discovered loggers
- **THEN** if all loggers fail, the system SHALL mark the overall sync status as `offline` only when nodes are unreachable (connection timeout or failure), and as `error` when communication was established but log retrieval or parsing failed

### Requirement: Dynamic Telemetry Ingestion into SQLite
The system SHALL ingest synchronized sensor records into a local SQLite database preserving all reported sensor measurements dynamically in a JSON metrics structure without requiring fixed schema columns. The database SHALL enforce unique records by `(timestamp, device_id)` to ensure idempotency.

#### Scenario: Dynamic metric ingestion
- **WHEN** log records containing arbitrary sensor keys (e.g. temperature, humidity, light, pressure) are received
- **THEN** the system SHALL store the record with its UTC timestamp, source device ID, and the complete key-value dictionary serialized as JSON in `metrics`

#### Scenario: Duplicate record deduplication
- **WHEN** a log record with a `(timestamp, device_id)` tuple already present in SQLite is processed during catch-up or replay
- **THEN** the system SHALL ignore or update the duplicate without creating duplicate rows or erroring

#### Scenario: Sync cursor persistence
- **WHEN** a batch of log records is successfully ingested
- **THEN** the system SHALL persist the updated `next_cursor` and timestamp in SQLite `sync_state` for that logger node

### Requirement: HTTP Management and Proxy API
The system SHALL expose an HTTP REST API on port 8000 allowing operators and automated tools to control the controller and retrieve data using standard HTTP clients like `curl`.

#### Scenario: Trigger on-demand sync via HTTP
- **WHEN** an HTTP `POST` is received at `/api/sync`
- **THEN** the system SHALL execute the sync operation and return HTTP 200 with the count of newly ingested records and sync status

#### Scenario: List discovered nodes
- **WHEN** an HTTP `GET` is received at `/api/nodes`
- **THEN** the system SHALL return HTTP 200 with a JSON array of all discovered nodes, their IP addresses, and advertised capabilities

#### Scenario: Force immediate network discovery scan
- **WHEN** an HTTP `POST` is received at `/api/discover`
- **THEN** the system SHALL execute a fresh CoAP discovery burst and return HTTP 200 with the discovered node list

#### Scenario: Query dynamic historical readings
- **WHEN** an HTTP `GET` is received at `/api/readings` with optional `device_id`, `since`, and `limit` query parameters
- **THEN** the system SHALL query SQLite and return HTTP 200 with a JSON array of matching timestamped readings containing their dynamic metrics. If `limit` is omitted, the system SHALL return all matching records without an arbitrary default limit. When `limit` is provided, it SHALL be applied without an arbitrary upper bound clamp.

#### Scenario: Proxy message alert to node display
- **WHEN** an HTTP `POST` is received at `/api/display` with a JSON payload specifying target node (`target`) and message text (`message`)
- **THEN** the system SHALL resolve the target node's IP and forward a CoAP `POST /display` request with the plain text message, returning HTTP 200 on success

#### Scenario: Controller health and status query
- **WHEN** an HTTP `GET` is received at `/api/status`
- **THEN** the system SHALL return HTTP 200 with a JSON object detailing controller uptime, poller status, logger cursors, and total ingested record counts

#### Scenario: Query aggregated sensor capabilities
- **WHEN** an HTTP `GET` is received at `/api/capabilities`
- **THEN** the system SHALL return HTTP 200 with a JSON array of deduplicated chartable metric objects (`key`, `unit`) sourced from the `sensor_capabilities` registry

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
