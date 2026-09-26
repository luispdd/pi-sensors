## Why

The sensor stations currently monitor temperature, relative humidity, and ambient light, but lack presence or activity monitoring. Integrating the AM312 passive infrared (PIR) motion sensor into the Raspberry Pi Pico 2 W and Waveshare ESP32-C6-Zero boards enables detecting occupancy and human movement. Because PIR motion is a time-varying binary trigger rather than a steady scalar value, continuous duty-cycle sampling over a rolling window (5 minutes / 300 seconds) is required to compute a meaningful motion activity percentage for long-term graphing and persistent SD card data logging.

## What Changes

- **PIR Sensor Driver (`hardware/sensors/pir.py`)**: Implement a modular duck-typed sensor driver for both Pico 2 W and ESP32-C6 featuring a 300-second circular buffer sampled at 1.0 Hz via a non-blocking asyncio coroutine to calculate active time duty cycle (`motion`, unit `%`).
- **Board Hardware Pin Mappings**: Configure GP12 (Physical Pin 16) on Raspberry Pi Pico 2 W and GPIO 4 on Waveshare ESP32-C6-Zero as digital inputs with pull-down resistors.
- **Sensor Registration & SenML Telemetry**: Register the PIR sensor with `AppState` on both boards, dynamically exporting `{"n": "motion", "u": "%", "v": <pct>}` across CoAP and HTTP `/sensors` and `/info` endpoints.
- **DataLogger & SD Storage Schema Update**: Update Pico 2 W `AppState.buffer_reading`, `DataLogger`, and `SDStorage` to include `motion_pct` as a 6th column in the unified daily CSV file (`timestamp,device_id,temperature_c,humidity_pct,light_pct,motion_pct`), with backward-compatible row parsing in `log_sync.py`.
- **Display Scope Preservation**: Preserve existing OLED and TFT screen layouts without alteration; the motion metric is consumed exclusively by the controller backend and frontend dashboard.

## Capabilities

### New Capabilities
- `hardware/am312-pir-sensor`: Modular duck-typed driver for AM312 PIR motion sensor measuring active duty cycle over a 300-second window, sampled non-blockingly at 1 Hz and exposed via SenML.

### Modified Capabilities
- `core/data-logger`: Extend in-memory buffering, CSV schema, and log sync parsing to record and serve `motion_pct` alongside temperature, humidity, and light.

## Impact

- **Firmware Codebase**:
  - `boards/pico-2w/settings/config.py`: Add `PIN_PIR = 12`, `PIR_WINDOW_S = 300`.
  - `boards/esp32c6/settings/config.py`: Add `PIN_PIR = 4`, `PIR_WINDOW_S = 300`.
  - `boards/pico-2w/hardware/sensors/pir.py` and `boards/esp32c6/hardware/sensors/pir.py`: New driver modules.
  - `boards/pico-2w/main.py` and `boards/esp32c6/main.py`: Register PIR sensor and gather sampling task.
  - `boards/pico-2w/core/state.py`, `boards/pico-2w/services/data_logger.py`, `boards/pico-2w/hardware/sd_storage.py`, `boards/pico-2w/services/log_sync.py`: 6th column motion support.
- **Backend & Dashboard**:
  - Automatically compatible through existing SenML dynamic capability discovery and JSON metric storage.
