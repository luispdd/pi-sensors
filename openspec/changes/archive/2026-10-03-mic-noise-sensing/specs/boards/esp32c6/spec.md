## ADDED Requirements

### Requirement: MAX4466 Noise Metric Registration (esp32c6)
The esp32c6 firmware SHALL register a `MicSensor` driver on `PIN_MIC_ADC = 5` (GPIO 5 / ADC1_CH5) at startup, causing the `"noise"` metric (unit `%`) to appear in `AppState` and in all SenML telemetry responses.

#### Scenario: Noise sensor registered at boot
- **WHEN** the esp32c6 board powers on and `main.py` executes
- **THEN** a `MicSensor` SHALL be registered via `app_state.register_sensor(...)` and its `run_sampling_task()` coroutine SHALL be added to `asyncio.gather` alongside other service tasks

#### Scenario: Noise metric in SenML response
- **WHEN** a CoAP or HTTP `GET /sensors` request is received
- **THEN** the SenML response SHALL include an entry with `n = "noise"`, `u = "%"`, and the current noise percentage value

## MODIFIED Requirements

### Requirement: DETAILS_MODE Sensor Summary View (esp32c6)
In DETAILS_MODE the esp32c6 OLED display SHALL render a summary table displaying all available registered sensors (temperature in Cel, humidity in %, motion in %, noise in %). The first line SHALL be a header label `[DETAILS]`. Each sensor metric SHALL be rendered on its own line in the format `<key>: <cur> <min> <max>` (labels: `T` for temperature, `H` for humidity, `M` for motion, `N` for noise) displaying current, session minimum, and session maximum values.

#### Scenario: DETAILS_MODE renders temperature and humidity stats
- **WHEN** the system is in DETAILS_MODE and the OLED is on
- **THEN** the display SHALL show rows in the format `<key>: <cur> <min> <max>` truncated to MAX_LINE_LEN, with `--` substituted for any None values.

#### Scenario: DETAILS_MODE shows placeholder for future sensor
- **WHEN** the system is in DETAILS_MODE and fewer than 4 metrics are registered
- **THEN** any remaining data row(s) SHALL be blank, reserving space for future sensor metrics.

#### Scenario: DETAILS_MODE renders all registered sensors including motion and noise
- **WHEN** the system is in DETAILS_MODE with temperature, humidity, motion, and noise sensors registered
- **THEN** the display SHALL render four data rows in order (`T`, `H`, `M`, `N`) showing current, minimum, and maximum values for each sensor metric.

### Requirement: MAX4466 Microphone Analog Interface on GP5
The system SHALL sample the analog output of the MAX4466 electret microphone amplifier on GPIO 5 (`ADC1_CH5`) to measure sound pressure / ambient noise levels.

#### Scenario: Audio sampling configuration
- **WHEN** audio telemetry is enabled on the ESP32-C6
- **THEN** the system SHALL configure GPIO 5 as an ADC input using `machine.ADC(Pin(5))` with 12-bit resolution (0–4095) and full-scale attenuation (11dB / 3.3V range)

#### Scenario: Peak-to-peak sound level calculation
- **WHEN** a noise sample window executes
- **THEN** the driver SHALL sample GPIO 5 continuously over a sampling window (e.g., 50 ms), compute the AC RMS amplitude relative to a dynamic DC reference, and translate the value into relative noise percentage telemetry using an adaptive noise floor and dB scaling


