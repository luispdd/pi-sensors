## ADDED Requirements

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
