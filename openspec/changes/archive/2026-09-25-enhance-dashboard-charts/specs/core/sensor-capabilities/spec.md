## Purpose

Provides a persistent registry of sensor types advertised by discovered IoTMesh nodes, storing each metric's key and measurement unit so the rest of the system can query chartable capabilities without hardcoding sensor type knowledge.

## ADDED Requirements

### Requirement: Sensor Capability Persistence
The system SHALL maintain a `sensor_capabilities` table in SQLite with columns `device_id`, `metric_key`, and `unit`, with a composite primary key of `(device_id, metric_key)`, storing the chartable sensor types reported by each discovered board.

#### Scenario: Capability record upserted on discovery
- **WHEN** a board is discovered or re-discovered and its CoAP `/sensors` endpoint is successfully queried
- **THEN** the system SHALL parse the SenML response and upsert one row per sensor entry (using `n` as `metric_key` and `u` as `unit`) into `sensor_capabilities` for that `device_id`

#### Scenario: Capability record upserted on sync
- **WHEN** a catch-up synchronization cycle completes for a board that exposes a `/sensors` endpoint
- **THEN** the system SHALL query that board's `/sensors` endpoint and upsert the returned capabilities, allowing new sensor types added to an existing board to be reflected without manual intervention

#### Scenario: Unreachable board during capability probe
- **WHEN** a CoAP `/sensors` request to a board times out or returns an error during discovery or sync
- **THEN** the system SHALL log the failure and continue without modifying the existing capability records for that board

### Requirement: Sensor Capabilities HTTP Endpoint
The system SHALL expose `GET /api/capabilities` returning a deduplicated list of all chartable metric types known across all registered boards.

#### Scenario: Query aggregated capabilities
- **WHEN** an HTTP `GET` is received at `/api/capabilities`
- **THEN** the system SHALL return HTTP 200 with a JSON array of objects, each containing `key` (the metric name) and `unit` (the measurement unit string), deduplicated across all boards so each unique `key` appears at most once

#### Scenario: No capabilities registered yet
- **WHEN** `GET /api/capabilities` is called and no boards have been discovered or probed yet
- **THEN** the system SHALL return HTTP 200 with an empty JSON array
