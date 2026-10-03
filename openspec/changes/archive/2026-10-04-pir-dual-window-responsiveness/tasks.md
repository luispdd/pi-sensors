## 1. Modular PIR Sensor Drivers & Configuration

- [x] 1.1 Update `boards/pico-2w/settings/config.py` and `boards/esp32c6/settings/config.py` to set `PIR_WINDOW_S = 10`, and verify configuration constants import cleanly
- [x] 1.2 Update `boards/pico-2w/hardware/sensors/pir.py` to retain `Pin.PULL_DOWN` (required to prevent RP2350 pull-up defaults from floating HIGH), implement the 10-slot circular buffer with fixed divisor `10`, accept `app_state` for immediate metric push on sample, and implement the period logging accumulator `get_period_motion(reset=True)`
- [x] 1.3 Update `boards/esp32c6/hardware/sensors/pir.py` to remove `Pin.PULL_DOWN` (high-impedance `Pin.IN` to prevent voltage attenuation on AM312 CMOS output), implement the 10-slot circular buffer with fixed divisor `10`, accept `app_state` for immediate metric push on sample, and implement the period logging accumulator `get_period_motion(reset=True)`
- [x] 1.4 Update unit tests in `boards/pico-2w/test/test_pir_sensor.py` and `boards/esp32c6/test/test_pir_sensor.py` to validate 10s ramp-up to 100%, 10s decay to 0%, immediate app_state pushes, and period accumulator reset; verify by running `python3 -m unittest boards/pico-2w/test/test_pir_sensor.py` and `python3 -m unittest boards/esp32c6/test/test_pir_sensor.py`

## 2. AppState & Main Entrypoint Integration

- [x] 2.1 Update `boards/pico-2w/main.py` and `boards/esp32c6/main.py` to pass `app_state=app_state` when invoking `create_pir()`, and verify mock initialization in tests
- [x] 2.2 Update `boards/pico-2w/core/state.py` to expose `get_period_motion_and_reset()` query method that retrieves and resets the registered PIR sensor's period accumulator (falling back to standard motion metric if unaccumulated)

## 3. DataLogger SD Logging Integration

- [x] 3.1 Update `DataLogger.poll_and_buffer()` in `boards/pico-2w/services/data_logger.py` to query `app_state.get_period_motion_and_reset()` for the local board's buffered motion value, and verify with updated unit tests in `boards/pico-2w/test/test_data_logger.py`

## 4. End-to-End Validation

- [x] 4.1 Run full unit test suites across all boards (`python3 -m unittest discover -s boards/pico-2w/test` and `python3 -m unittest discover -s boards/esp32c6/test`) to verify zero regressions
- [x] 4.2 Run `openspec validate --all` to verify that all OpenSpec change artifacts and delta specs comply with schema standards
