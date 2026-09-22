## MODIFIED Requirements

### Requirement: Logger session lifecycle
The system SHALL support a discrete logger session controlled by the user. A session begins when the user arms the logger after a successful NTP sync and network discovery, and ends when the user requests a flush. When no session is active, no readings SHALL be buffered and no SD card writes SHALL occur.

#### Scenario: Session starts after confirmation
- **WHEN** the user confirms start after the staging phase completes with a valid NTP timestamp and at least the local board discovered
- **THEN** the system SHALL immediately transition the UI and state to active logging, immediately capture and buffer an initial reading for all active nodes in the background, update `AppState.logging_active` to `True`, and continue periodic sampling every `SENSOR_LOG_INTERVAL_S` seconds (default 300)

#### Scenario: Session ends on flush request
- **WHEN** the user short-presses the logger button while a session is active
- **THEN** the system SHALL flush all buffered readings to the SD card, reset the buffer, and set `AppState.logging_active` to `False`

#### Scenario: No logging without session
- **WHEN** no logging session is active
- **THEN** the system SHALL not read sensors for logging purposes, not buffer readings, and not write to the SD card

### Requirement: In-memory ring buffer
While a session is active, the system SHALL buffer one reading per source board per sample interval. The buffer SHALL hold at most 13 readings per board (one hour's worth plus initial sample at 5-minute intervals). When the buffer is full for a given board, the oldest unwritten entry SHALL be discarded to make room for new readings. The total count of all buffered readings across all boards SHALL be tracked in `AppState.log_buffered_count`.

#### Scenario: Buffer accumulates readings
- **WHEN** a logging session begins or `SENSOR_LOG_INTERVAL_S` elapses while active
- **THEN** one reading per active board SHALL be appended to that board's buffer and `AppState.log_buffered_count` SHALL increment accordingly

#### Scenario: Buffer overflow discards oldest entry
- **WHEN** a board's buffer already holds 13 entries and a new reading arrives before a flush
- **THEN** the oldest entry SHALL be removed and the new entry SHALL be appended, keeping the buffer size at 13

### Requirement: Hourly automatic flush
While a session is active, the system SHALL automatically flush buffered readings to the SD card every `LOG_FLUSH_INTERVAL_S` seconds (default 3600). An automatic flush SHALL write the first 12 buffered readings per board to the daily CSV file and retain the 13th reading in the buffer as the first reading of the subsequent cycle without ending the session.

#### Scenario: Automatic flush triggers
- **WHEN** a logging session is active and `LOG_FLUSH_INTERVAL_S` seconds have elapsed since the last flush
- **THEN** the system SHALL write the first 12 buffered readings per board to the daily CSV file and retain the 13th reading in memory, updating `AppState.log_buffered_count` without ending the session
