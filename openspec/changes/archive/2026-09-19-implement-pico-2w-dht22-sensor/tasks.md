## 1. Hardware Pin Configuration

- [x] 1.1 Add `PIN_DHT22 = 15` mapping to `boards/pico-2w/settings/config.py` and verify configuration loads without syntax errors.

## 2. Sensor Driver Implementation

- [x] 2.1 Update `boards/pico-2w/hardware/sensors.py` to replace stub `SensorReader` with physical MicroPython `dht.DHT22(Pin(15))` driver integration, matching error-resilient sampling logic from Pico 1 W.

## 3. Verification & Testing

- [x] 3.1 Verify syntax and import resolution of updated `boards/pico-2w/hardware/sensors.py` and `boards/pico-2w/main.py`.
