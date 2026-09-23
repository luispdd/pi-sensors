## Purpose

Provides an active central controller that discovers IoTMesh nodes over CoAP, synchronizes persistent sensor logs into a local SQLite database with dynamic JSON metrics, runs a periodic polling loop with on-demand sync triggers, and exposes an HTTP management API.

## ADDED Requirements

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
- **THEN** the system SHALL query SQLite and return HTTP 200 with a JSON array of matching timestamped readings containing their dynamic metrics

#### Scenario: Proxy message alert to node display
- **WHEN** an HTTP `POST` is received at `/api/display` with a JSON payload specifying target node (`target`) and message text (`message`)
- **THEN** the system SHALL resolve the target node's IP and forward a CoAP `POST /display` request with the plain text message, returning HTTP 200 on success

#### Scenario: Controller health and status query
- **WHEN** an HTTP `GET` is received at `/api/status`
- **THEN** the system SHALL return HTTP 200 with a JSON object detailing controller uptime, poller status, logger cursors, and total ingested record counts
