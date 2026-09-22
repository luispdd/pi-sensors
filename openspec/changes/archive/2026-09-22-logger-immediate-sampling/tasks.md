## 1. State Buffer Capacity and Retention

- [x] 1.1 Update `AppState.buffer_reading()` in `boards/pico-2w/core/state.py` to increase ring buffer capacity to 13 entries per board and verify with unit tests
- [x] 1.2 Implement a buffer retention method in `AppState` to slice off flushed rows while retaining remaining entries and recalculating `log_buffered_count`

## 2. Logger Immediate Sampling and Auto-Flush Slicing

- [x] 2.1 Update `DataLogger.auto_flush_loop()` in `boards/pico-2w/services/data_logger.py` to await an immediate `poll_and_buffer()` call before entering the periodic sleep loop
- [x] 2.2 Update `DataLogger.flush_to_sd()` in `boards/pico-2w/services/data_logger.py` to write the first 12 records per board on periodic flushes (`end_session=False`) while retaining the 13th in `AppState`, while flushing all entries on session stop (`end_session=True`)

## 3. Testing and Verification

- [x] 3.1 Add unit test in `boards/pico-2w/test/test_data_logger.py` validating immediate $T=0$ buffer population, buffer capacity of 13, periodic 12-record flush with 13th-entry retention, and full manual stop flush
- [x] 3.2 Run `python3 -m unittest discover -s boards/pico-2w/test` to verify all tests pass cleanly without regression
