# MAX4466 Microphone Sensor Specification

## Purpose

Provides a shared, duck-typed ADC microphone sensor driver for the MAX4466 electret microphone amplifier, measuring ambient noise level as a percentage based on RMS energy over an adaptive noise floor via a background async sampling loop.

## Requirements

### Requirement: MicSensor Duck-Typed Protocol Conformance
The `MicSensor` driver SHALL conform to the modular sensor protocol: it SHALL expose `name = "mic"`, `metrics = [{"key": "noise", "unit": "%"}]`, a `read()` method returning `{"noise": <float>}`, and a `run_sampling_task()` async coroutine.

#### Scenario: read() returns current noise percentage
- **WHEN** `read()` is called on a `MicSensor` instance
- **THEN** it SHALL return `{"noise": <last_noise_pct>}` where `last_noise_pct` is the most recently calculated noise percentage in the range 0.0–100.0

#### Scenario: read() before any sample is taken
- **WHEN** `read()` is called before the sampling task has executed at least once
- **THEN** it SHALL return `{"noise": 0.0}`

### Requirement: MicSensor RMS and Adaptive Decibel Sampling
The `MicSensor` SHALL sample the ADC across a configurable window in a background async task, calculate root-mean-square (RMS) AC amplitude relative to a dynamic DC reference, and compute noise level percentage using a decibel scale relative to an adaptive noise floor.

#### Scenario: Sampling window and RMS calculation
- **WHEN** a sampling window executes (default 50 ms)
- **THEN** the driver SHALL read raw ADC values over the window duration, subtract a running DC offset reference, calculate variance and RMS AC amplitude, and update the DC reference for subsequent windows

#### Scenario: Adaptive noise floor tracking
- **WHEN** RMS measurements are recorded over time
- **THEN** the driver SHALL maintain a rolling average of RMS history (default 2.0 s window) to track background ambient noise, immediately following lower silence levels and adapting upward slowly near baseline while respecting a configurable minimum floor clamp

#### Scenario: Decibel scaling and attack/release ballistics
- **WHEN** converting the current window RMS to a noise percentage
- **THEN** the driver SHALL calculate the decibel level above the noise floor ($20 \log_{10}(\text{RMS} / \text{floor})$), subtract a noise gate threshold (default 1.0 dB), scale to a 0.0–100.0% range over a full-scale span (default 40.0 dB), and apply instant attack with smooth exponential release decay (default 0.2 factor)

#### Scenario: Continuous background cooperative task
- **WHEN** `run_sampling_task()` is launched via `asyncio.gather`
- **THEN** it SHALL continuously execute sampling windows, yielding control between windows with `await asyncio.sleep(sample_interval_s)`, and update the latest noise percentage

#### Scenario: Optional AppState metric update
- **WHEN** `MicSensor` is instantiated with an `app_state` reference and finishes calculating a sample window
- **THEN** it SHALL call `app_state.update_metric("noise", last_noise_pct)` directly to provide immediate state updates

### Requirement: MicSensor Configurable Tuning Parameters
The `MicSensor` SHALL support configurable acoustic and sampling parameters, with defaults overridable via `settings.config`.

#### Scenario: Default and configuration override loading
- **WHEN** `MicSensor` is instantiated
- **THEN** it SHALL load `PIN_MIC_ADC`, `MIC_FULL_SCALE_DB` (default 40.0 dB), `MIC_MIN_FLOOR` (default 16.0 counts on ESP32, 4.0 counts on RP2350), `MIC_GATE_DB` (default 1.0 dB), and `MIC_RELEASE` (default 0.2) from configuration if available

### Requirement: MicSensor ADC Initialization
The `MicSensor` SHALL initialize the ADC pin at construction and apply full-scale attenuation on platforms that support it (ESP32), falling back silently on platforms that do not (RP2350).

#### Scenario: ADC init on RP2350
- **WHEN** `MicSensor` is instantiated on a Raspberry Pi Pico 2 W (RP2350)
- **THEN** it SHALL call `machine.ADC(Pin(pin_num))` and proceed without error; any call to `adc.atten()` that raises `AttributeError` or `TypeError` SHALL be silently ignored

#### Scenario: ADC init on ESP32-C6
- **WHEN** `MicSensor` is instantiated on an ESP32-C6 board
- **THEN** it SHALL call `machine.ADC(Pin(pin_num))` and then `adc.atten(ADC.ATTN_11DB)` to configure the full 3.3 V input range

#### Scenario: ADC hardware unavailable
- **WHEN** the ADC cannot be initialized (hardware error or missing `machine` module)
- **THEN** `MicSensor` SHALL set `_adc = None`, log the error, and return `{"noise": 0.0}` from all subsequent `read()` calls without raising

### Requirement: MicSensor Factory Function
The module SHALL expose a `create_sensor(pin, ...)` factory function that instantiates and returns a `MicSensor`.

#### Scenario: Factory instantiation
- **WHEN** `create_sensor(pin=config.PIN_MIC_ADC)` is called
- **THEN** it SHALL return a fully initialized `MicSensor` bound to the given pin
