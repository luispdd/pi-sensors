## Why

The Raspberry Pi Pico 2 W board (`boards/pico-2w`) currently uses a stub implementation for environmental sensing that returns `None` for temperature and humidity. To match the hardware capabilities of the Pico 1 W node, physical DHT22 temperature and humidity sensor reading must be enabled on GP15.

## What Changes

- Add `PIN_DHT22 = 15` configuration setting to `boards/pico-2w/settings/config.py`.
- Replace `boards/pico-2w/hardware/sensors.py` stub with active MicroPython `dht.DHT22` hardware reader, matching the error-resilient implementation from Pico 1 W.
- Enable live temperature and humidity sampling across periodic background tasks (`sensor_task`), HTTP endpoints (`/info`), and CoAP IoTMesh sensor resources (`/sensors`, `/sensors/temperature`, `/sensors/humidity`).

## Capabilities

### New Capabilities
- `hardware/pico-2w-dht22-sensor`: Physical DHT22 temperature and humidity sensor hardware configuration and driver integration on Pico 2 W (GP15).

### Modified Capabilities
- `core/sensor-monitoring`: Extends hardware telemetry collection on Pico 2 W to read live ambient temperature and relative humidity values via `SensorReader`.

## Impact

- `boards/pico-2w/settings/config.py`: Adds `PIN_DHT22` pin mapping.
- `boards/pico-2w/hardware/sensors.py`: Replaces stub with `dht.DHT22` hardware driver logic.
- Background tasks (`sensor_task`) and web/CoAP services on Pico 2 W will begin serving live environment readings instead of `None`.
