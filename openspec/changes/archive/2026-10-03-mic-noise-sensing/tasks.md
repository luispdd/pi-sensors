## 1. Shared MicSensor Driver

- [x] 1.1 Create `boards/pico-2w/hardware/sensors/mic.py` with the `MicSensor` class: `name = "mic"`, `metrics = [{"key": "noise", "unit": "%"}]`, `__init__(pin, window_ms=50, sample_interval_s=0.01, ...)`, `init()` that calls `ADC(Pin(pin))` and silently ignores `AttributeError`/`TypeError` from `adc.atten(ADC.ATTN_11DB)`, RMS calculation over adaptive noise floor with dB scaling, `read()` returning `{"noise": last_noise_pct}`, `run_sampling_task()` async loop, and `create_sensor(pin, ...)` factory. Verify the file parses without import errors by running `python3 -c "import ast; ast.parse(open('boards/pico-2w/hardware/sensors/mic.py').read()); print('OK')"` from `boards/pico-2w/`.

- [x] 1.2 Copy `mic.py` verbatim to `boards/esp32c6/hardware/sensors/mic.py`. Verify the file exists and is byte-for-byte identical: `diff boards/pico-2w/hardware/sensors/mic.py boards/esp32c6/hardware/sensors/mic.py`.

## 2. pico-2w Integration

- [x] 2.1 In `boards/pico-2w/main.py`: add `from hardware.sensors.mic import create_sensor as create_mic`, instantiate `mic_sensor = create_mic(pin=getattr(config, "PIN_MIC_ADC", 27))`, call `app_state.register_sensor(mic_sensor)`, and add `mic_sensor.run_sampling_task()` to `asyncio.gather`. Verify the file parses cleanly: `python3 -m py_compile boards/pico-2w/main.py`.

- [x] 2.2 In `boards/pico-2w/hardware/display.py` `render_status()`: add `noise=None` parameter; replace the PIR-only line at y=22 with a combined line formatted as `PIR:<pir>% N:<noise>%` (using `--` for absent values); ensure the combined string fits within `MAX_LINE_LEN = 20` characters. Verify by visual inspection that `"PIR:100% N:100%"` (16 chars) fits the limit.

- [x] 2.3 In `boards/pico-2w/hardware/display.py` `update_from_state()`: pass `noise=app_state.get_metric_val("noise")` to the `render_status()` call. Also update the `update()` backwards-compatible method signature to accept and forward a `noise` keyword argument. Verify the file parses: `python3 -m py_compile boards/pico-2w/hardware/display.py`.

## 3. esp32c6 Integration

- [x] 3.1 In `boards/esp32c6/main.py`: add `from hardware.sensors.mic import create_sensor as create_mic`, instantiate `mic_sensor = create_mic(pin=getattr(config, "PIN_MIC_ADC", 5))`, call `app_state.register_sensor(mic_sensor)`, and add `mic_sensor.run_sampling_task()` to `asyncio.gather`. Verify the file parses cleanly: `python3 -m py_compile boards/esp32c6/main.py`.

## 4. Unit Tests

- [x] 4.1 Create `boards/pico-2w/test/test_mic_sensor.py` covering: (a) `read()` before any sample returns `{"noise": 0.0}`; (b) after injecting a mock ADC sequence with known RMS/dB levels, `read()` returns the expected percentage; (c) adaptive floor tracking; (d) `init()` with a mock ADC whose `atten()` raises `AttributeError` does not raise and sets `_adc`. Run with `python3 -m unittest discover -s boards/pico-2w/test` and confirm the new tests pass.

- [x] 4.2 Create `boards/esp32c6/test/test_mic_sensor.py` with the same test cases (adjusted for `pin=5`). Run `python3 -m unittest discover -s boards/esp32c6/test` and confirm all tests pass.

## 5. Validation

- [x] 5.1 Run `openspec validate --specs` and confirm no validation errors. Address any reported issues before marking done.
