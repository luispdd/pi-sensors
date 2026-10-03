## ADDED Requirements

### Requirement: MAX4466 Noise Metric Registration (pico-2w)
The pico-2w firmware SHALL register a `MicSensor` driver on `PIN_MIC_ADC = 27` (GP27 / ADC1) at startup, causing the `"noise"` metric (unit `%`) to appear in `AppState` and in all SenML telemetry responses.

#### Scenario: Noise sensor registered at boot
- **WHEN** the pico-2w board powers on and `main.py` executes
- **THEN** a `MicSensor` SHALL be registered via `app_state.register_sensor(...)` and its `run_sampling_task()` coroutine SHALL be added to `asyncio.gather` alongside other service tasks

#### Scenario: Noise metric in SenML response
- **WHEN** a CoAP or HTTP `GET /sensors` request is received
- **THEN** the SenML response SHALL include an entry with `n = "noise"`, `u = "%"`, and the current noise percentage value

## MODIFIED Requirements

### Requirement: STATUS_MODE Layout with PIR Activity (pico-2w)
The STATUS_MODE view on the TFT SHALL display PIR motion activity and noise level combined on the second displayed line, immediately after the primary telemetry line (temperature / humidity / light). All subsequent lines (network status, CoAP route, requests served, last caller, and the logging section when active) SHALL be positioned below the combined PIR+noise line.

#### Scenario: PIR activity line is rendered in STATUS_MODE
- **WHEN** the system is in STATUS_MODE and the TFT is on
- **THEN** the second line of the display SHALL show both PIR motion activity and noise level in the format `PIR:<pir>% N:<noise>%`, with `--` shown for either value when it is unavailable.

#### Scenario: PIR and noise combined line is rendered in STATUS_MODE
- **WHEN** the system is in STATUS_MODE and the TFT is on
- **THEN** the second line of the display SHALL show both PIR motion activity and noise level in the format `PIR:<pir>% N:<noise>%`, with `--` shown for either value when it is unavailable

### Requirement: MAX4466 Microphone Analog Interface on GP27 (ADC1)
The system SHALL configure GP27 (Pin 32, `ADC1`) as the analog input channel for the MAX4466 electret microphone amplifier.

#### Scenario: Microphone ADC initialization
- **WHEN** the sensor manager initializes on the Pico 2 W
- **THEN** it SHALL configure `PIN_MIC_ADC = 27` in `settings/config.py` and instantiate `machine.ADC(Pin(27))`

#### Scenario: Low-noise ground reference
- **WHEN** the MAX4466 microphone breakout is wired to the board
- **THEN** its ground pin SHALL be connected to `AGND` (Pin 33) to decouple analog sampling from high-frequency SPI switching and WiFi RF return currents

#### Scenario: Sound level sampling window
- **WHEN** sound pressure telemetry is read
- **THEN** the system SHALL sample GP27 over a dedicated observation window, calculate the AC RMS amplitude relative to a dynamic DC reference, and export relative noise percentage telemetry to `AppState` using an adaptive noise floor and dB scaling


