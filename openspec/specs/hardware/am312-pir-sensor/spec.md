# AM312 PIR Sensor Specification

## Purpose

Enables passive infrared (PIR) motion sensing using the AM312 sensor, computing an active duty cycle percentage over a 300-second rolling window and exporting standard SenML telemetry across CoAP and HTTP.

## Requirements

### Requirement: AM312 GPIO motion signal sampling
The firmware SHALL monitor the digital output pin of an AM312 PIR motion sensor at an interval of 1.0 second using a non-blocking asynchronous coroutine. The pin SHALL be configured as a digital input with an internal pull-down resistor to prevent floating states when motion is absent.

#### Scenario: Motion pin sampled high
- **WHEN** the AM312 sensor asserts its output pin HIGH upon detecting infrared movement
- **THEN** the periodic 1-second sample coroutine SHALL register an active motion tick (`1`) for that sample interval

#### Scenario: Motion pin sampled low
- **WHEN** the AM312 sensor output pin is LOW in the absence of infrared movement
- **THEN** the periodic 1-second sample coroutine SHALL register an idle tick (`0`) for that sample interval

### Requirement: Rolling 300-second duty cycle calculation
The sensor driver SHALL maintain a fixed-capacity 300-sample circular buffer representing the trailing 300 seconds (5 minutes) of activity. On each 1-second sample, the driver SHALL record the newest binary sample, evict the oldest sample, and calculate the active duty cycle percentage as `(active_samples / total_samples_recorded) * 100.0`.

#### Scenario: Full window motion percentage computation
- **WHEN** the sensor driver has recorded at least 300 samples and exactly 45 samples were active HIGH during the trailing 300 seconds
- **THEN** the calculated motion percentage SHALL be rounded to one decimal place as `15.0%`

#### Scenario: Initial warm-up before full window
- **WHEN** the node has booted recently and fewer than 300 samples have elapsed
- **THEN** the sensor driver SHALL compute the duty cycle using the actual count of elapsed samples since initialization without division-by-zero errors

### Requirement: Modular sensor duck-typed interface and SenML export
The AM312 sensor driver SHALL adhere to the modular sensor protocol by exposing `name = "pir"`, `metrics = [{"key": "motion", "unit": "%"}]`, an `init()` method, and a `read()` method returning a dictionary `{"motion": <pct>}`. When registered with `AppState`, the metric SHALL be automatically formatted as SenML `{"n": "motion", "u": "%", "v": <pct>}` on `/sensors` endpoints.

#### Scenario: Reading sensor metric via AppState
- **WHEN** `AppState.read_registered_sensors()` or an HTTP/CoAP request queries `/sensors`
- **THEN** the system SHALL return the latest computed motion percentage under metric key `"motion"` with unit `"%"`

#### Scenario: Display exclusion
- **WHEN** the UI controllers render the active sensor display screens on the local OLED or TFT display
- **THEN** the motion metric SHALL NOT be rendered on the local physical display screen
