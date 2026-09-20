## 1. Config & Hardware Pin Setup

- [x] 1.1 Add `PIN_BUTTON_LOG = 13`, `SENSOR_LOG_INTERVAL_S = 300`, `LOG_FLUSH_INTERVAL_S = 3600`, and `LOG_SD_ROOT = "/sensor-data"` to `boards/pico-2w/settings/config.py`; verify the values are importable from `config` in a REPL session
- [x] 1.2 Verify `SD_CS = 22`, `SPI_SPEED_SD_INIT`, and `SPI_SPEED_SD_DATA` are already present in `config.py` (no change needed — just confirm before proceeding)

## 2. SD Storage Module

- [x] 2.1 Create `boards/pico-2w/hardware/sd_storage.py` with an `SDStorage` class that accepts the shared `SPI` object and the `tft_cs` pin reference; implement `mount()` and `unmount()` using `sdcard.SDCard` + `os.mount("/sd")`; verify mount succeeds on hardware with a card inserted
- [x] 2.2 Implement `SDStorage._acquire_bus()` that sets `tft_cs` HIGH and calls `spi.init(baudrate=SPI_SPEED_SD_DATA)` before any SD access; verify TFT continues rendering correctly after an SD mount/unmount cycle
- [x] 2.3 Implement `SDStorage.ensure_dir(path)` that creates `/sd/sensor-data` if absent using `os.mkdir`; verify directory exists after first call
- [x] 2.4 Implement `SDStorage.open_daily_file(device_id, date_str)` that returns an open file handle in append mode for `/sd/sensor-data/<date_str>-<device_id>.csv`, writing the CSV header `timestamp,device_id,temperature_c,humidity_pct` only when the file is newly created; verify by checking file content after first and second open
- [x] 2.5 Implement `SDStorage.write_rows(file_handle, rows)` that writes each row as a CSV line and calls `file_handle.flush()`; verify rows appear in the file after write
- [x] 2.6 Implement `SDStorage.flush_buffers(buffers, date_str)` that mounts the card, iterates over `buffers` dict, opens the daily file per device, writes rows, closes files, and unmounts; returns `True` on success or raises on failure; verify end-to-end with two boards' worth of data

## 3. AppState Extensions

- [x] 3.1 Add logger state constants `LOGGER_IDLE = 0`, `LOGGER_STAGING = 1`, `LOGGER_CONFIRM = 2`, `LOGGER_ACTIVE = 3` to `boards/pico-2w/core/state.py`
- [x] 3.2 Add fields to `AppState.__init__`: `logger_state = LOGGER_IDLE`, `logging_active = False`, `log_buffers = {}`, `log_buffered_count = 0`, `log_ntp_time_str = None`, `log_error = None`, `log_active_nodes = {}`; verify all fields are accessible after instantiation
- [x] 3.3 Add `AppState.buffer_reading(device_id, ts, temp, hum)` that appends to `log_buffers[device_id]` (creating it if absent), enforces max-12 cap by popping index 0 on overflow, and increments `log_buffered_count`; verify cap behaviour with a unit test or manual loop
- [x] 3.4 Add `AppState.clear_buffers()` that resets `log_buffers = {}` and `log_buffered_count = 0`; verify state after call
- [x] 3.5 Add `AppState.set_logger_error(msg)` and `AppState.clear_logger_error()` helpers that set/clear `log_error`; verify via REPL

## 4. Logger Button (ButtonLog)

- [x] 4.1 Add a `ButtonLog` class to `boards/pico-2w/hardware/controls.py` with `pin_num` defaulting to `config.PIN_BUTTON_LOG`; initialise GP13 as `Pin.IN` with `Pin.PULL_UP`; verify `.is_pressed()` returns `True` when button held
- [x] 4.2 Implement press-duration tracking in `ButtonLog`: record `ticks_ms()` on the falling edge in `was_pressed_start()` and compute duration on the rising edge in `release_type()` returning `"short"` (< 1000 ms), `"long"` (≥ 1000 ms), or `None` (still held); verify via timed manual presses

## 5. NTP Sync

- [x] 5.1 Create `boards/pico-2w/services/ntp_service.py` with `sync_ntp()` that calls `ntptime.settime()` and returns `(True, "HH:MM UTC")` on success or `(False, error_str)` on `OSError`; verify return values in both WiFi-connected and WiFi-absent states
- [x] 5.2 Add a midnight re-sync check in the logger task loop: compare current UTC date (`time.localtime()[2]`) against stored `_last_sync_day`; if changed, call `sync_ntp()` and update `AppState.log_ntp_time_str` on success; verify by advancing mock time in a test or waiting for day change on hardware

## 6. CoAP Discovery Extension

- [x] 6.1 Extend `CoapServer._handle_response` to detect `rt="temperature"` or `rt="humidity"` in the CoRE Link Format payload string and populate `AppState.log_active_nodes[sender_ip] = device_id` when found; verify by sending a mock `.well-known/core` response with sensor resource types
- [x] 6.2 Add `CoapServer.fire_sensor_discovery()` that sends `coap.getNonConf("224.0.1.187", 5683, ".well-known/core")` and always adds the local board to `AppState.log_active_nodes` using `config.DEVICE_ID`; verify local board appears in `log_active_nodes` after call
- [x] 6.3 Add `GET /logger` handler in `CoapServer` returning `{"active": <bool>, "buffered": <int>, "last_ntp": <str|null>}` as JSON with `COAP_CONTENT`; verify response with `coap-client` or `coap.getNonConf`
- [x] 6.4 Add `</logger>;rt="data-logger";if="logger"` to the `.well-known/core` CoRE Link Format string in `_handle_well_known_core`; verify presence in discovery response

## 7. Data Logger Service

- [x] 7.1 Create `boards/pico-2w/services/data_logger.py` with a `DataLogger` class that holds references to `AppState`, `SDStorage`, and `CoapServer`; expose `async run_staging()`, `start_session()`, `stop_and_flush()`, `async poll_and_buffer()`, and `async auto_flush_loop()`
- [x] 7.2 Implement `run_staging()`: call `sync_ntp()` → update `AppState.log_ntp_time_str` or `log_error`; call `fire_sensor_discovery()` → `asyncio.sleep(3.0)`; then set `AppState.logger_state = LOGGER_CONFIRM`; verify state transitions in sequence
- [x] 7.3 Implement `poll_and_buffer()`: for each entry in `AppState.log_active_nodes`, send CoAP `getNonConf` to `/sensors`; on response parse SenML JSON for temperature and humidity; call `AppState.buffer_reading()`; skip silently on timeout; verify buffer grows after each poll cycle
- [x] 7.4 Implement `auto_flush_loop()`: `asyncio.sleep(LOG_FLUSH_INTERVAL_S)` then call `SDStorage.flush_buffers()`; on success call `AppState.clear_buffers()`; on failure call `AppState.set_logger_error()`; loop without ending session; verify buffer is cleared after successful flush
- [x] 7.5 Implement `stop_and_flush()`: call `SDStorage.flush_buffers()` immediately; on success clear buffers and set `logger_state = LOGGER_IDLE`, `logging_active = False`; on failure set error and stay in `LOGGER_ACTIVE`; verify both paths on hardware

## 8. Logger Button Task in main.py

- [x] 8.1 Instantiate `ButtonLog` and `DataLogger` in `main()` and create `button_log_task` as a new asyncio task alongside existing tasks; verify no existing tasks are disturbed
- [x] 8.2 Implement `button_log_task` loop: poll `ButtonLog` at 50 ms intervals; on release call `button_log.release_type()` and dispatch to the correct logger state handler based on `AppState.logger_state` and press type per spec; verify each state transition fires correctly
- [x] 8.3 Wire IDLE + short-press → `asyncio.create_task(data_logger.run_staging())`; verify TFT shows `"Preparing..."` during staging
- [x] 8.4 Wire CONFIRM + short-press (no error) → `data_logger.start_session()` + `asyncio.create_task(data_logger.auto_flush_loop())`; verify logging status section appears on TFT
- [x] 8.5 Wire CONFIRM + long-press → clear error + `logger_state = LOGGER_IDLE`; verify normal display is restored
- [x] 8.6 Wire ACTIVE + short-press → `asyncio.create_task(data_logger.stop_and_flush())`; verify CSV file(s) written on SD card and TFT shows success briefly

## 9. Display Integration

- [x] 9.1 Add `render_confirm_screen(date_str, time_str, nodes, error)` to `TFTDisplay` that renders the full-screen LOGGER SETUP layout per the display-service spec; verify both the no-error and error variants render correctly
- [x] 9.2 Add `render_staging_screen()` to `TFTDisplay` that shows `"Preparing..."` / `"Scanning..."`; verify it appears during the 3-second staging window
- [x] 9.3 Extend `render_status()` to accept `logging_active`, `log_active_nodes`, `log_buffered_count`, `log_ntp_time_str`, `log_error` parameters; when `logging_active` is `True` render the logging section (divider, LOG line, Buf line, NTP/error line) below existing content; verify layout at y=108–147 matches spec
- [x] 9.4 Implement compact layout fallback: if the logging section bottom would exceed y=160, omit the title line (y=5) and its separator (y=18) and shift all content up by 19 px; verify compact path triggers correctly when forced
- [x] 9.5 Update `update_from_state()` to route to `render_staging_screen()` when `logger_state == LOGGER_STAGING`, `render_confirm_screen()` when `logger_state == LOGGER_CONFIRM`, and pass the new logging fields to `render_status()` when in `LOGGER_ACTIVE`

## 10. Integration Verification

- [x] 10.1 Full session walkthrough on hardware: press logger button → staging screen → confirm screen with date, time, and pico-1w listed → short press start → logging status visible on TFT → wait 5 min → verify `AppState.log_buffered_count` increments → press button to flush → verify CSV file on SD card has correct header and data rows for both boards
- [x] 10.2 Error path — no WiFi: disconnect WiFi → press logger button → verify NTP error shown on confirm screen and short press is ignored → long press → verify normal display restored
- [x] 10.3 Error path — SD card absent: start session successfully → remove SD card → wait for auto-flush → verify `AppState.log_error` set and error shown in logging section on TFT → reinsert SD card → trigger manual flush → verify file written correctly
- [x] 10.4 Resume path: start session → accumulate readings → power cycle board → start new session for same UTC day → flush → verify existing CSV file contains both pre-cycle and post-cycle rows without duplicate header
- [x] 10.5 CoAP discovery verification: send `coap-client GET coap://\<pico-2w-ip\>/.well-known/core` → verify `/logger;rt="data-logger"` present; send `GET coap://\<pico-2w-ip\>/logger` → verify JSON response

