# Data Logger Specification

## Purpose

Provides persistent time-series sensor data storage by buffering readings in memory and writing UTC-timestamped CSV files to an SD card, one file per board per day, with automatic append-resume across power cycles.

## Requirements

### Requirement: Logger session lifecycle
The system SHALL support a discrete logger session controlled by the user. A session begins when the user arms the logger after a successful NTP sync and network discovery, and ends when the user requests a flush. When no session is active, no readings SHALL be buffered and no SD card writes SHALL occur.

#### Scenario: Session starts after confirmation
- **WHEN** the user confirms start after the staging phase completes with a valid NTP timestamp and at least the local board discovered
- **THEN** the system SHALL transition to active logging, begin buffering sensor readings every `SENSOR_LOG_INTERVAL_S` seconds (default 300), and update `AppState.logging_active` to `True`

#### Scenario: Session ends on flush request
- **WHEN** the user short-presses the logger button while a session is active
- **THEN** the system SHALL flush all buffered readings to the SD card, reset the buffer, and set `AppState.logging_active` to `False`

#### Scenario: No logging without session
- **WHEN** no logging session is active
- **THEN** the system SHALL not read sensors for logging purposes, not buffer readings, and not write to the SD card

### Requirement: In-memory ring buffer
While a session is active, the system SHALL buffer one reading per source board per sample interval. The buffer SHALL hold at most 12 readings per board (one hour's worth at 5-minute intervals). When the buffer is full for a given board, the oldest unwritten entry SHALL be discarded to make room for new readings. The total count of all buffered readings across all boards SHALL be tracked in `AppState.log_buffered_count`.

#### Scenario: Buffer accumulates readings
- **WHEN** a logging session is active and `SENSOR_LOG_INTERVAL_S` elapses
- **THEN** one reading per active board SHALL be appended to that board's buffer and `AppState.log_buffered_count` SHALL increment accordingly

#### Scenario: Buffer overflow discards oldest entry
- **WHEN** a board's buffer already holds 12 entries and a new reading arrives before a flush
- **THEN** the oldest entry SHALL be removed and the new entry SHALL be appended, keeping the buffer size at 12

### Requirement: Hourly automatic flush
While a session is active, the system SHALL automatically flush buffered readings to the SD card every `LOG_FLUSH_INTERVAL_S` seconds (default 3600). An automatic flush SHALL NOT end the session.

#### Scenario: Automatic flush triggers
- **WHEN** a logging session is active and `LOG_FLUSH_INTERVAL_S` seconds have elapsed since the last flush
- **THEN** the system SHALL write all buffered readings to their respective daily CSV files and clear the buffers without ending the session

### Requirement: Unified daily CSV files
The system SHALL write sensor readings to a unified daily CSV file at `/sensor-data/<YYYY-MM-DD>.csv` on the SD card containing readings from all source boards. Each file SHALL include a header row on creation and SHALL be opened in append mode if the file for the current UTC date already exists, allowing resume after a power cycle. Prior to writing buffered readings to the file, the system SHALL strictly sort the batch of buffered records first by timestamp (ascending) and then by device ID (ascending) to guarantee a deterministic chronological order in the log file.

#### Scenario: New file created for a new day or missing file
- **WHEN** the system flushes data and no CSV file exists for the current UTC date
- **THEN** the system SHALL create the file, write the header `timestamp,device_id,temperature_c,humidity_pct`, and then append the buffered, strictly sorted rows

#### Scenario: Existing daily file resumed
- **WHEN** the system flushes data and a CSV file for the current UTC date already exists
- **THEN** the system SHALL open the file in append mode and write only the data rows, without repeating the header, using the strict sorting rule

#### Scenario: UTC timestamps in rows
- **WHEN** a sensor reading is buffered
- **THEN** the timestamp stored SHALL be a UTC ISO-8601 string in the format `YYYY-MM-DDTHH:MM:SS` provided by the sensor node itself or derived from `time.localtime()` as a fallback

### Requirement: Remote board sensor polling
While a session is active, the system SHALL poll each discovered remote board's `/sensors` CoAP endpoint at the same `SENSOR_LOG_INTERVAL_S` interval as local reads. A remote board that does not respond within the polling timeout SHALL have no entry buffered for that interval — the gap SHALL be silently skipped rather than recorded as a null row.

#### Scenario: Remote board responds
- **WHEN** the logger polls a discovered remote board's `/sensors` endpoint and receives a valid SenML JSON response
- **THEN** the reading SHALL be buffered under that board's device ID with a UTC timestamp

#### Scenario: Remote board offline or timeout
- **WHEN** the logger polls a discovered remote board and receives no response within the CoAP polling timeout
- **THEN** no entry SHALL be added to that board's buffer for that interval

### Requirement: SD card failure handling
If the SD card is absent, unreadable, or full during a flush, the system SHALL surface an error message via `AppState.log_error` and display it on the TFT. The logging session SHALL remain active and buffering SHALL continue so that data is not lost if the card becomes available again.

#### Scenario: SD card missing or unreadable
- **WHEN** the system attempts a flush and the SD card cannot be mounted
- **THEN** the system SHALL set `AppState.log_error` to a short error string (e.g. `"SD: mount fail"`), display it on the TFT, and retain buffered readings

#### Scenario: SD card write failure
- **WHEN** the system mounts the SD card but fails to write (e.g. card full, filesystem error)
- **THEN** the system SHALL set `AppState.log_error`, display it, and retain buffered readings without ending the session
