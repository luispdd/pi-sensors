## 1. Modular PIR Sensor Drivers & Unit Tests

- [x] 1.1 Implement `boards/pico-2w/hardware/sensors/pir.py` with `PIRSensor` class, 300-slot `bytearray` circular buffer, non-blocking 1.0s sample task, duck-typed `read()` method, and create unit tests in `boards/pico-2w/test/test_pir_sensor.py`
- [x] 1.2 Implement `boards/esp32c6/hardware/sensors/pir.py` with `PIRSensor` class matching the duck-typed interface, and create unit tests in `boards/esp32c6/test/test_pir_sensor.py`
- [x] 1.3 Add hardware pin and window constants (`PIN_PIR = 12` on Pico 2 W, `PIN_PIR = 4` on ESP32-C6, and `PIR_WINDOW_S = 300` on both) to `settings/config.py` on both boards

## 2. Firmware Integration & SenML Telemetry

- [x] 2.1 Update `boards/pico-2w/main.py` to register the PIR sensor with `AppState` and spawn `pir.run_sampling_task()`, verifying SenML serialization includes `{"n": "motion", "u": "%", "v": ...}`
- [x] 2.2 Update `boards/esp32c6/main.py` to register the PIR sensor with `AppState` and spawn `pir.run_sampling_task()`, verifying SenML serialization includes `{"n": "motion", "u": "%", "v": ...}`
- [x] 2.3 Verify in `boards/pico-2w/test/test_coap_endpoints.py` and `boards/esp32c6/test/test_coap_endpoints.py` that `/sensors` and `/info` reflect the registered `motion` metric without modifying OLED/TFT display rendering

## 3. Pico 2 W DataLogger & SD Card Logging

- [x] 3.1 Update `AppState.buffer_reading()` in `boards/pico-2w/core/state.py` and `DataLogger.poll_and_buffer()` in `boards/pico-2w/services/data_logger.py` to extract and buffer the `motion` metric
- [x] 3.2 Update `CSV_HEADER` in `boards/pico-2w/hardware/sd_storage.py` to `timestamp,device_id,temperature_c,humidity_pct,light_pct,motion_pct\n` and format the 6th column in `write_rows`
- [x] 3.3 Update `boards/pico-2w/services/log_sync.py` to parse the 6th column `motion` while preserving backward compatibility for 4- and 5-column rows, and verify with updated tests in `boards/pico-2w/test/test_data_logger.py`

## 4. End-to-End Validation & Verification

- [x] 4.1 Run full MicroPython test suites across `boards/pico-2w` and `boards/esp32c6` to verify zero test regressions
- [x] 4.2 Verify backend controller test suite in `controller/backend/` ensures dynamic metric ingestion of `motion` persists into SQLite and is exposed via `/api/capabilities`
