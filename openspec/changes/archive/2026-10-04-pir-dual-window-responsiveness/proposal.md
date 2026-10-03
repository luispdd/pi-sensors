## Why

The current AM312 PIR motion sensor driver computes an active duty cycle over a rigid 300-second (5-minute) rolling window. While suitable for 5-minute SD logging, this long window makes the live physical displays (Pico 2 W TFT and ESP32-C6 OLED DETAILS screen) and real-time telemetry sluggish and counter-intuitive:
- 10 seconds of constant hand movement only yields ~3% motion activity, requiring 5 minutes of continuous motion to reach 100%.
- Once movement stops, the value remains frozen for 5 minutes until samples evict from the 300-sample buffer.
- On the ESP32-C6, internal pull-down resistor configuration (`Pin.PULL_DOWN`) loads the AM312 CMOS push-pull output, causing intermittent HIGH logic detection.
- Polling motion via the 2.5-second DHT22 telemetry loop introduces display latency.

Separating immediate display responsiveness (10-second rolling window) from persistent SD data logging (5-minute period duty cycle accumulator) provides instant, accurate visual feedback while preserving meaningful occupancy logging.

## What Changes

- **PIR GPIO Configuration**: Configure the AM312 digital input with `Pin.PULL_DOWN` on Pico 2 W (preventing RP2350 default pull-up states from floating HIGH) and as high-impedance `Pin.IN` without pull-down on ESP32-C6 (preventing CMOS output voltage attenuation).
- **Immediate 10-Second Display Window**: Update `PIR_WINDOW_S = 10` (sampled at 1.0s, 10 samples) for the live `motion` metric. 10 seconds of continuous movement registers as 100%, and 10 seconds without movement decays back to 0%.
- **Direct AppState Update**: Pass `app_state` to `PIRSensor` on instantiation (mirroring `MicSensor`), immediately updating `motion` on each 1-second sample tick without waiting for the 2.0s–2.5s slow telemetry loop.
- **SD Logging Period Accumulator**: Add a running interval accumulator (`active_ticks` / `total_ticks`) to `PIRSensor` and `AppState` for Pico 2 W `DataLogger`. When polled every 5 minutes (`SENSOR_LOG_INTERVAL_S = 300`), it logs the true 5-minute duty cycle and resets for the next interval.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `hardware/am312-pir-sensor`: Update motion sampling requirements to decouple the 10-second rolling window for live display/telemetry from the period accumulator for SD card data logging, and specify board-specific GPIO pull configurations (`Pin.PULL_DOWN` on Pico 2 W, `Pin.IN` on ESP32-C6).

## Impact

- **Firmware Codebase**:
  - `boards/pico-2w/settings/config.py`: Update `PIR_WINDOW_S = 10`.
  - `boards/esp32c6/settings/config.py`: Update `PIR_WINDOW_S = 10`.
  - `boards/pico-2w/hardware/sensors/pir.py`: Retain `Pin.PULL_DOWN`, implement 10-slot circular buffer, immediate `AppState` metric push, and logging interval accumulator.
  - `boards/esp32c6/hardware/sensors/pir.py`: Configure `Pin.IN` without pull-down, implement 10-slot circular buffer, immediate `AppState` metric push, and logging interval accumulator.
  - `boards/pico-2w/main.py` and `boards/esp32c6/main.py`: Pass `app_state=app_state` to `create_pir`.
  - `boards/pico-2w/services/data_logger.py`: Retrieve the 5-minute period accumulator value for SD card CSV logging.
- **Unit Tests**:
  - `boards/pico-2w/test/test_pir_sensor.py` and `boards/esp32c6/test/test_pir_sensor.py`: Update tests for 10-second window, push updates, and logging accumulator.
  - `boards/pico-2w/test/test_data_logger.py`: Verify 5-minute period motion logging and reset behavior.
