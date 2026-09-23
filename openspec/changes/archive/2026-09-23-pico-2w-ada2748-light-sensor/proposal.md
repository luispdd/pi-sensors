## Why

The Raspberry Pi Pico 2 W environmental monitoring station currently monitors ambient temperature and relative humidity using a DHT22 sensor, but lacks ambient illuminance telemetry. Integrating the Adafruit ALS-PT19 (ADA2748) analog ambient light sensor on GP26 (ADC0) enables the Pico 2 W node to measure ambient lighting conditions as a percentage (0.0% - 100.0%), display it on the local TFT screen, log it alongside temperature and humidity to the SD card, and serve it via HTTP and IoTMesh CoAP endpoints.

## What Changes

- Add hardware ADC support for the Adafruit ALS-PT19 (ADA2748) light sensor connected to GP26 (ADC0 / Pin 31) on Pico 2 W in `settings/config.py` (`PIN_LIGHT_ADC`, `LIGHT_SCALE_FACTOR`) and `hardware/sensors.py`.
- Update `SensorReader.read_sensors()` to sample the ADC channel using 32-sample averaging to filter AC/PWM flicker, apply `LIGHT_SCALE_FACTOR`, clamp to 100.0%, and return `light_pct` (rounded to 1 decimal place) alongside temperature and humidity.
- Update `AppState` in `core/state.py` to store `light_pct`, include it in `to_dict()`, and update `buffer_reading` to record light values in log buffers.
- Update local ST7735 TFT display in `hardware/display.py` to render `L:<pct>%` (e.g. `L:50%` or `L:--%` if unavailable) on the telemetry line alongside `T:<temp>C H:<hum>%`.
- Update IoTMesh CoAP server in `services/coap_server.py`:
  - Advertise `</sensors/light>;rt="light";if="sensor"` in `GET /.well-known/core`.
  - Include light reading `{"n": "light", "u": "%", "v": <pct>}` in `GET /sensors` SenML Pack.
  - Implement dedicated `GET /sensors/light` endpoint returning SenML JSON for light.
- Update HTTP web server in `services/webserver.py`: `GET /info` and `GET /sensors` include `light_pct` in the JSON payload.
- Update SD card data logging (`hardware/sd_storage.py`, `services/data_logger.py`, `services/log_sync.py`):
  - Extend CSV log format with a 5th column: `timestamp,device_id,temperature_c,humidity_pct,light_pct`.
  - Log local node's `light_pct` during data logger polling and buffer flushing.
  - Support parsing optional 5th `light_pct` column in `log_sync.py`.

## Capabilities

### New Capabilities
- `hardware/pico-2w-light-sensor`: Hardware pin configuration (GP26 / ADC0) and analog sampling driver for the Adafruit ALS-PT19 (ADA2748) light sensor breakout on Pico 2 W.

### Modified Capabilities
- `core/sensor-monitoring`: Ambient telemetry sampling extended to include ambient light percentage (`light_pct`) alongside temperature and humidity.
- `core/display-service`: ST7735 TFT telemetry status view displays light percentage (`L:<pct>%`).
- `core/iotmesh/coap-node`: IoTMesh CoAP server advertises and serves light sensor telemetry on `GET /sensors`, `GET /sensors/light`, and in `/.well-known/core`.
- `core/data-logger`: Data logger buffers, CSV headers, and log records include ambient light percentage column.

## Impact

- **Hardware**: Uses GPIO 26 (Pin 31, ADC0) on the Raspberry Pi Pico 2 W board.
- **APIs**:
  - HTTP `GET /info` and `GET /sensors` JSON responses now include `"light_pct": float | null`.
  - CoAP `GET /.well-known/core` includes `</sensors/light>;rt="light";if="sensor"`.
  - CoAP `GET /sensors` includes `{"n": "light", "u": "%", "v": ...}`.
  - CoAP `GET /sensors/light` added as a new route.
- **Storage**: CSV schema for SD logging updated from 4 columns to 5 columns (`timestamp,device_id,temperature_c,humidity_pct,light_pct`).
- **Compatibility**: Pico 1 W remains unchanged; records without light data leave `light_pct` empty.
