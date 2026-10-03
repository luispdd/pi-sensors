## MODIFIED Requirements

### Requirement: AM312 GPIO motion signal sampling
The firmware SHALL monitor the digital output pin of an AM312 PIR motion sensor at an interval of 1.0 second using a non-blocking asynchronous coroutine. On Raspberry Pi Pico 2 W (RP2350), the input pin SHALL be configured with an internal pull-down resistor (`Pin.PULL_DOWN`) to prevent unconfigured pad pull-up defaults from floating HIGH. On Waveshare ESP32-C6, the input pin SHALL be configured as a high-impedance digital input without an internal pull-down resistor (`Pin.IN`) to prevent voltage divider attenuation on the AM312 active CMOS output stage.

#### Scenario: Motion pin sampled high
- **WHEN** the AM312 sensor asserts its output pin HIGH upon detecting infrared movement
- **THEN** the periodic 1-second sample coroutine SHALL register an active motion tick (`1`) for that sample interval

#### Scenario: Motion pin sampled low
- **WHEN** the AM312 sensor output pin is LOW in the absence of infrared movement
- **THEN** the periodic 1-second sample coroutine SHALL register an idle tick (`0`) for that sample interval

#### Scenario: Pico 2 W GPIO pin initialization
- **WHEN** the AM312 PIR sensor is initialized on Raspberry Pi Pico 2 W
- **THEN** the firmware SHALL configure the input pin with `Pin.PULL_DOWN`

#### Scenario: ESP32-C6 GPIO pin initialization
- **WHEN** the AM312 PIR sensor is initialized on Waveshare ESP32-C6
- **THEN** the firmware SHALL configure the input pin as `Pin.IN` without `Pin.PULL_DOWN`

### Requirement: Rolling 300-second duty cycle calculation
The sensor driver SHALL maintain a fixed-capacity 10-sample circular buffer representing the trailing 10 seconds of activity for live display and telemetry, while maintaining a period accumulator for SD card data logging. On each 1-second sample, the driver SHALL record the newest binary sample, evict the oldest sample from the 10-sample buffer, compute the live active duty cycle percentage as `(active_samples / 10) * 100.0`, immediately update `AppState.metrics["motion"]`, and increment the logging period accumulator counters.

#### Scenario: Full window motion percentage computation
- **WHEN** the sensor driver has recorded at least 10 samples and exactly 10 samples were active HIGH during the trailing 10 seconds
- **THEN** the calculated motion percentage SHALL be rounded to one decimal place as `100.0%`

#### Scenario: Initial warm-up before full window
- **WHEN** the node has booted recently and fewer than 10 samples have elapsed
- **THEN** the sensor driver SHALL compute the duty cycle over the 10-sample buffer (initialized with idle zero ticks) without division-by-zero errors or artificially inflated percentages

#### Scenario: Rapid decay after motion stops
- **WHEN** motion ceases and 10 consecutive idle LOW samples are recorded
- **THEN** the calculated motion percentage SHALL return to `0.0%` within 10 seconds

#### Scenario: Periodic logging accumulator
- **WHEN** the periodic data logger queries the PIR sensor for 5-minute SD card persistence
- **THEN** the sensor driver SHALL return the average duty cycle percentage across the entire logging period `(period_active_ticks / period_total_ticks) * 100.0` and reset the period accumulator counters for the next logging interval
