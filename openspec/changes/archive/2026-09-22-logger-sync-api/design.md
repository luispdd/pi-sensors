## Context

The mesh logger previously split persistent records into separate CSV files per device, appending data every hour in whatever order it was polled. This created a pagination time-travel problem when trying to expose an HTTP/CoAP synchronization API: if a controller paginated through records with a strict `limit` and `since=timestamp` filter, it could accidentally skip interleaved data across different files. 

See proposal.md - Why.

## Goals / Non-Goals

**Goals:**
- Provide a robust way for an external controller to pull all historical logged data via CoAP/HTTP.
- Prevent data loss during synchronization by eliminating the time-travel race condition.
- Guarantee that a single reading cannot be duplicated in the controller's database even if multiple logger nodes capture it.

**Non-Goals:**
- Controller database schema implementation.
- Complex K-way merge sorting logic in MicroPython.
- Bi-directional sync (the logger is push-only or poll-only, not receiving data from the controller).

## Decisions

### 1. Sensor Node Timestamps
**Decision**: NTP synchronization is pushed down to the sensor nodes (e.g. `pico-1w`). When polled via `/sensors`, the node will inject its own generated ISO-8601 UTC timestamp into the response.
**Rationale**: If loggers generated the timestamp upon receipt, two different loggers receiving the same broadcast reading would assign it slightly different timestamps. Pushing this to the sensor node guarantees that a single physical reading has one immutable timestamp, allowing a downstream controller database to safely UPSERT `(device_id, timestamp)` and perfectly deduplicate records from multiple redundant loggers.
**Alternatives Considered**: Relying on loggers to timestamp and forcing the controller to deduplicate based on fuzzy time-matching. Rejected as too fragile.

### 2. Unified Daily Files
**Decision**: SD storage will write to a unified daily file (`YYYY-MM-DD.csv`) containing data from all active nodes instead of `YYYY-MM-DD-<device-id>.csv`.
**Rationale**: Storing all data in one file allows for a simple linear cursor for pagination, completely avoiding the need to balance or merge-sort across multiple files during an API request. 
**Alternatives Considered**: A global sequence ID (adds persistence overhead). A per-device API sync (requires the controller to know all devices upfront). 

### 3. File Line Cursor Pagination
**Decision**: The `/log` API will use a physical file cursor (`filename:line_number`) for pagination instead of a timestamp.
**Rationale**: The cursor is a pure transport mechanic. It allows the controller to reliably download the file in chunks without missing rows, even if new data is appended during the sync. 
**Alternatives Considered**: `since=timestamp` with a `limit`. Rejected due to the pagination time-travel trap when multiple timestamps are identical.

### 4. Strict In-Memory Sorting
**Decision**: Before the logger flushes its RAM buffer to the unified SD card file, it will sort all buffered records by `(timestamp, device_id)`.
**Rationale**: Guarantees a deterministic, strictly ordered CSV file on the SD card. Since polling happens in a tight 5-minute window, the chronological order of the unified file is maintained hour-by-hour.

## Risks / Trade-offs

- **Risk: Memory Exhaustion during Sort** → **Mitigation**: The logger buffer is strictly limited to 12 readings per board per hour. Sorting this small list in MicroPython RAM is trivial and safe.
- **Risk: NTP failure on Sensor Node** → **Mitigation**: If NTP fails, the sensor node will lack a valid time. The logger will have to fall back to its own time (or reject the reading). The spec requires periodic NTP sync attempts to minimize this window.
