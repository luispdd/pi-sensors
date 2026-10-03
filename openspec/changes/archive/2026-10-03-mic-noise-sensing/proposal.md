# Proposal: mic-noise-sensing

## Why

The MAX4466 electret microphone amplifier is already physically wired to both the pico-2w (GP27 / ADC1) and the esp32c6 (GPIO 5 / ADC1_CH5) and the pin assignments are documented in their specs, but no firmware reads the signal. Adding noise sensing closes the gap between hardware and software, gives each board a fourth real environmental metric, and surfaces that metric automatically through the existing modular sensor framework — including CoAP `/sensors`, the controller's capabilities registry, and the dashboard — with minimal new code.

## What Changes

- **New shared microphone sensor driver** (`hardware/sensors/mic.py`) implementing the duck-typed sensor protocol: async background sampling loop (RMS energy over adaptive noise floor, dB scaled to %), `"noise"` metric key, `%` unit.
- **pico-2w**: registers `MicSensor` on `PIN_MIC_ADC = 27`; `render_status()` row 1 becomes `PIR:12% N:34%` (PIR activity and noise combined on one line).
- **esp32c6**: registers `MicSensor` on `PIN_MIC_ADC = 5`; the existing generic `render_details_view` already handles new metrics dynamically — noise appears as the third data row in DETAILS_MODE automatically.
- **Dashboard / controller**: no code changes required — `noise` appears in CoAP SenML responses and is upserted into `sensor_capabilities` by existing discovery/sync logic.

## Capabilities

### New Capabilities

- `hardware/mic-sensor`: Shared ADC microphone sensor driver conforming to the duck-typed sensor protocol, with async RMS sampling, adaptive noise floor tracking, and %-scaled noise output.

### Modified Capabilities

- `boards/pico-2w`: New `noise` metric registered and displayed; `render_status()` STATUS_MODE row 1 combines PIR activity and noise on a single line.
- `boards/esp32c6`: New `noise` metric registered; DETAILS_MODE auto-renders it as the third metric row via the existing generic details view.

## Impact

- **New file**: `boards/pico-2w/hardware/sensors/mic.py` (shared driver, copied into `boards/esp32c6/hardware/sensors/mic.py`)
- **Modified**: `boards/pico-2w/main.py` — import and register `MicSensor`, add `mic_sensor.run_sampling_task()` to `asyncio.gather`
- **Modified**: `boards/esp32c6/main.py` — same registration and gather addition
- **Modified**: `boards/pico-2w/hardware/display.py` — `render_status()` and `update_from_state()` updated to pass and render a combined PIR+noise line
- **No changes**: esp32c6 UI, AppState on either board, CoAP/HTTP servers, controller, dashboard
