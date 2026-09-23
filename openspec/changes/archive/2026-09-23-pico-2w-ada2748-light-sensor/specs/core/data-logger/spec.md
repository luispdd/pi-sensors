## MODIFIED Requirements

### Requirement: In-memory ring buffer
While a session is active, the system SHALL buffer one reading per source board per sample interval, containing timestamp, device ID, temperature, humidity, and ambient light percentage (if provided by the node). The buffer SHALL hold at most 13 readings per board (one hour's worth plus initial sample at 5-minute intervals). When the buffer is full for a given board, the oldest unwritten entry SHALL be discarded to make room for new readings. The total count of all buffered readings across all boards SHALL be tracked in `AppState.log_buffered_count`.

#### Scenario: Buffer accumulates readings
- **WHEN** a logging session begins or `SENSOR_LOG_INTERVAL_S` elapses while active
- **THEN** one reading per active board (including temperature, humidity, and light percentage if available) SHALL be appended to that board's buffer and `AppState.log_buffered_count` SHALL increment accordingly

#### Scenario: Buffer overflow discards oldest entry
- **WHEN** a board's buffer already holds 13 entries and a new reading arrives before a flush
- **THEN** the oldest entry SHALL be removed and the new entry SHALL be appended, keeping the buffer size at 13

### Requirement: Unified daily CSV files
The system SHALL write sensor readings to a unified daily CSV file at `/sensor-data/<YYYY-MM-DD>.csv` on the SD card containing readings from all source boards. Each file SHALL include a header row on creation and SHALL be opened in append mode if the file for the current UTC date already exists, allowing resume after a power cycle. Prior to writing buffered readings to the file, the system SHALL strictly sort the batch of buffered records first by timestamp (ascending) and then by device ID (ascending) to guarantee a deterministic chronological order in the log file.

#### Scenario: New file created for a new day or missing file
- **WHEN** the system flushes data and no CSV file exists for the current UTC date
- **THEN** the system SHALL create the file, write the header `timestamp,device_id,temperature_c,humidity_pct,light_pct`, and then append the buffered, strictly sorted rows

#### Scenario: Existing daily file resumed
- **WHEN** the system flushes data and a CSV file for the current UTC date already exists
- **THEN** the system SHALL open the file in append mode and write only the data rows, without repeating the header, using the strict sorting rule

#### Scenario: UTC timestamps in rows
- **WHEN** a sensor reading is buffered
- **THEN** the timestamp stored SHALL be a UTC ISO-8601 string in the format `YYYY-MM-DDTHH:MM:SS` provided by the sensor node itself or derived from `time.localtime()` as a fallback
