## 1. Hardware Pin Configuration & Sensor Driver

- [x] 1.1 Define `PIN_LIGHT_ADC = 26` and `LIGHT_SCALE_FACTOR` in `boards/pico-2w/settings/config.py` and verify setting availability.
- [x] 1.2 Update `SensorReader` in `boards/pico-2w/hardware/sensors.py` to initialize `machine.ADC(Pin(config.PIN_LIGHT_ADC))` with graceful fallback when hardware ADC is unavailable, perform 32-sample ADC averaging to filter AC/PWM noise, compute `light_pct = min(100.0, round(raw_pct * config.LIGHT_SCALE_FACTOR, 1))`, and return `"light_pct"` in `read_sensors()`.

## 2. Core Application State & HTTP Web Server

- [x] 2.1 Update `AppState` in `boards/pico-2w/core/state.py` to track `self.light_pct`, update it in `update_sensors()`, serialize it in `to_dict()`, and update `buffer_reading()` to accept optional light parameter.
- [x] 2.2 Verify `WebServer` in `boards/pico-2w/services/webserver.py` provides `"light_pct"` in the JSON payload of `GET /info` and `GET /sensors`.

## 3. TFT Display Telemetry Integration

- [x] 3.1 Update `TFTDisplay.render_telemetry_screen` in `boards/pico-2w/hardware/display.py` to format the top telemetry row as `T:<temp>C H:<hum>% L:<val>%` (or `L:--%` when null) with integer percentage formatting `L:{light:.0f}%` without line wrap or clipping on the 128px screen.

## 4. IoTMesh CoAP Server Endpoints

- [x] 4.1 Update `_handle_well_known_core` in `boards/pico-2w/services/coap_server.py` to include `</sensors/light>;rt="light";if="sensor"` in the CoRE Link Format string.
- [x] 4.2 Update `_handle_sensors_collection` in `boards/pico-2w/services/coap_server.py` to include `{"n": "light", "u": "%", "v": self.app_state.light_pct}` in the SenML pack.
- [x] 4.3 Add dedicated route and handler `_handle_sensor_light` for `GET /sensors/light` in `boards/pico-2w/services/coap_server.py` returning SenML JSON `{"n": "light", "u": "%", "v": ...}`.

## 5. Data Logger & SD Card Storage

- [x] 5.1 Update CSV header in `boards/pico-2w/hardware/sd_storage.py` to `timestamp,device_id,temperature_c,humidity_pct,light_pct\n` and update `write_rows` to format the 5th column.
- [x] 5.2 Update `DataLogger.poll_and_buffer()` in `boards/pico-2w/services/data_logger.py` to pass local `light_pct` to `app_state.buffer_reading()` and extract light readings from remote nodes when available.
- [x] 5.3 Update `read_log_records` in `boards/pico-2w/services/log_sync.py` to parse the 5th column (`light_pct`) from CSV lines while maintaining backward compatibility with 4-column lines.

## 6. Testing & Documentation

- [x] 6.1 Add unit tests in `boards/pico-2w/test/` validating `SensorReader` with mock ADC, `AppState.to_dict()` output, 5-column CSV writing, and `log_sync` pagination with light data.
- [x] 6.2 Update `README.md` hardware table and API documentation to reflect the ADA2748 pinout on GP26 (Pin 31) and the new `light_pct` field and CoAP endpoints.
