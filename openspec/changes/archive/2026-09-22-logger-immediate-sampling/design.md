## Context

See `proposal.md` for motivation. Currently, `DataLogger.auto_flush_loop()` in `boards/pico-2w/services/data_logger.py` sleeps for `SENSOR_LOG_INTERVAL_S` (300 seconds) before calling `poll_and_buffer()` for the first time. The in-memory buffer limit in `boards/pico-2w/core/state.py` is hard-coded to 12 readings.

## Goals / Non-Goals

**Goals:**
- Guarantee that sensor data is buffered immediately ($T=0$) upon entering active logging mode so that even brief sessions record data.
- Maintain immediate UI responsiveness when transitioning to `ACTIVE` mode without waiting for network discovery or remote sensor polling.
- Ensure that every hourly auto-flush writes exactly 12 records (60 minutes of data) to the SD card while retaining the 13th reading in buffer for the next cycle.
- Retain full flush on manual stop (`stop_and_flush`), writing all remaining buffered readings.

**Non-Goals:**
- Modifying the CSV schema or storage directory layout (`/sd/sensor-data/YYYY-MM-DD.csv`).
- Altering the 5-minute sampling interval or 60-minute auto-flush interval values.

## Decisions

### 1. Execute initial sample asynchronously in `auto_flush_loop`
- **Decision**: Trigger `await self.poll_and_buffer()` as the first line of `auto_flush_loop()` prior to entering the sleep loop.
- **Rationale**: `start_session()` in `main.py` is synchronous and transitions the UI immediately (`logger_state = LOGGER_ACTIVE`, `logging_active = True`). Starting the initial poll inside the newly spawned `auto_flush_loop` task ensures the UI updates with zero latency while CoAP/HTTP polling happens asynchronously.
- **Alternatives considered**:
  - *Calling `poll_and_buffer()` synchronously inside `start_session()`*: Rejected because remote sensor discovery and CoAP requests are asynchronous and could freeze UI rendering and button detection during network timeouts.

### 2. Increase per-board ring buffer limit to 13
- **Decision**: In `AppState.buffer_reading()`, increase the buffer cap from 12 to 13 (`if len(buf) >= 13: buf.pop(0)`).
- **Rationale**: With the initial reading at $T=0$ and periodic readings at $T=5, 10, \dots, 60$, exactly 13 readings accumulate across a 60-minute span. A cap of 13 prevents dropping the $T=0$ sample before the auto-flush triggers.
- **Alternatives considered**:
  - *Expanding buffer to an arbitrary large number (e.g. 50)*: Unnecessary and could mask auto-flush stalls. 13 precisely matches the 60-minute cycle with an initial reading.

### 3. Partial flush on periodic auto-flush vs full flush on manual stop
- **Decision**: In `DataLogger.flush_to_sd(end_session)`:
  - When `end_session=False` (periodic auto-flush): slice the first 12 entries per board for SD writing (`rows[:12]`), retain the remaining entry (`rows[12:]`, the 13th reading) in `app_state.log_buffers`, and update `app_state.log_buffered_count` accordingly.
  - When `end_session=True` (session stop): write all rows in the buffer to SD and clear the buffers completely.
- **Rationale**: Guarantees that every periodic SD flush writes exactly 12 records (60 minutes of data), while cleanly seeding the next hour with the 60th-minute reading without special cycle-branching logic.
- **Alternatives considered**:
  - *Flushing 13 records on the first hour and 12 on subsequent hours*: Rejected because it introduces irregular batch sizes and complicates downstream log analysis.

## Risks / Trade-offs

- [Risk: Remote nodes unreachable during immediate start] -> Local reading is buffered immediately; remote node timeouts (2s) silently skip without blocking or failing the session.
- [Risk: Session stopped while auto-flush in progress] -> `_is_flushing` mutex in `flush_to_sd()` prevents concurrent SD card access.
