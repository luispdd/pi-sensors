## Context

See `proposal.md – Why` for motivation. Both boards already have `PIN_MIC_ADC` set in `settings/config.py` and the hardware pin assignments documented in their board specs. The modular sensor framework (duck-typed `name` / `metrics` / `read()` / `create_sensor()` pattern) is established and working for DHT22, light, and PIR sensors. `AppState.to_senml()` and the CoAP `/sensors` endpoint are already fully dynamic — they iterate `_metrics` with no hardcoding — so a new sensor auto-appears in telemetry once registered. The esp32c6 `render_details_view` is similarly generic and already maps `"noise"` to label `N` in `METRIC_LABELS`.

## Goals / Non-Goals

**Goals:**
- Produce ambient noise level readings (0–100 % dynamic range) on both boards via an async sampling loop with adaptive noise floor and RMS energy estimation
- Surface the `noise` metric via SenML and via each board's on-device display
- Use a single shared driver file to avoid duplicating identical logic

**Non-Goals:**
- Calibrated SPL (dB SPL) — this is a relative proxy, not an acoustic measurement
- Any changes to the controller, dashboard, or CoAP/HTTP server code — the existing dynamic infrastructure picks up the new metric automatically
- Gain-control or AGC logic

## Decisions

### Shared driver file: `mic.py` — one file, copied to both boards

**Decision**: Write one `mic.py` and place identical copies under `boards/pico-2w/hardware/sensors/mic.py` and `boards/esp32c6/hardware/sensors/mic.py`.

**Rationale**: The two boards differ only in the `adc.atten()` call (ESP32 needs `ATTN_11DB`; RP2350 raises `AttributeError`). This is handled by a single `try/except` in `init()`. All other logic — async loop, RMS math, adaptive floor tracking, dB scaling, protocol conformance — is identical. A shared file means one place to fix bugs. The project does not have a cross-board shared library directory, so copying the file is consistent with how the other shared-logic drivers (e.g., `pir.py`) are structured.

**Alternative considered**: Board-specific subclasses. Rejected — the only difference is a one-liner attenuation call, which doesn't justify class hierarchy.

### Sampling strategy: async background task with RMS and adaptive floor

**Decision**: `MicSensor.run_sampling_task()` runs an infinite `while True` loop: acquire samples for 50 ms (tight inner loop calling `adc.read_u16()`), compute variance and RMS relative to dynamic DC offset, update an adaptive noise floor over a 2.0 s rolling history, calculate dB level above the noise floor, apply attack/release smoothing, store `last_noise_pct`, and `await asyncio.sleep(sample_interval_s)` (default 10 ms).

**Rationale**: The 50 ms acquisition window acquires a contiguous sample set. Calculating variance and RMS around dynamic DC offset rejects DC drift. The adaptive noise floor prevents steady background ambient noise from falsely pinning the reading high, while dB scaling maps human-perceived sound volume logarithmically to a 0–100% scale. Attack/release ballistics allow instant response to claps/transients with smooth decay.

**Alternative considered**: Raw peak-to-peak. Rejected — raw V_pp is vulnerable to DC quantization bias, ambient electrical noise, and does not match logarithmic human hearing perception.

### Noise unit: percentage (%) based on dB dynamic range

**Decision**: Scale $20 \log_{10}(\text{RMS} / \text{floor})$ minus gate threshold against a 40 dB full scale, clamped to 0–100% with smooth exponential decay.

**Rationale**: Matches the 0–100% convention used across other sensors on the dashboard and CoAP SenML. Using a relative dB scale above ambient floor avoids needing an absolute acoustic reference while providing intuitive sensitivity.

### pico-2w STATUS_MODE: combined PIR+noise line

**Decision**: Replace the current `PIR: <pir>%` line (row 1, y=22) with `PIR:<pir>% N:<noise>%`. All rows below remain at their existing y positions.

**Rationale**: The TFT is 160 px tall; a 14-character combined line fits the 20-char limit at 5×8 font (`PIR:100% N:100%` = 16 chars). Adding a separate row would push the logging section off the bottom when logging is active. Combining on one line adds the metric without disrupting the existing layout.

**`render_status()` signature change**: Add `noise=None` parameter. `update_from_state()` passes `app_state.get_metric_val("noise")`.

### esp32c6 DETAILS_MODE: no code change needed

`render_details_view` already dynamically renders up to 3 metric rows in registration order (temperature, humidity, then any additional key). Do not limit to 3 metrics. Registering `MicSensor` makes noise appear automatically as row 3 with label `N`. The `METRIC_LABELS` dict already maps `"noise": "N"`. Zero display code changes required.

## Risks / Trade-offs

- **50 ms blocking window** → Runs the ADC acquisition loop for 50 ms before yielding with `await asyncio.sleep()`. Acceptable given that other sensors (DHT22 timing-sensitive read) introduce comparable delays. Mitigated by cooperative async yielding between windows.
- **ADC sharing on RP2350** → GP27 (ADC1) is dedicated to the microphone with no other peripheral on that pin. No SPI arbitration needed — only ADC0 (GP26) is near shared SPI activity and uses AGND for decoupling.
- **MAX4466 output idle voltage** → The MAX4466 outputs a DC-biased signal (~VCC/2 at silence). Mitigated by centering samples around dynamic DC offset tracking (`_ref`), computing RMS AC swing, and tracking an adaptive noise floor rather than relying on raw peak-to-peak.
- **ESP32-C6 ADC non-linearity** → The ESP32 ADC is known for non-linearity near the rails even with 11 dB attenuation. Since we're reporting a relative `%` proxy (not calibrated SPL), this is acceptable. Gross non-linearities only affect the very top and bottom of the scale.

## Migration Plan

No data migration required. The `noise` metric appears in SenML after the firmware update; the controller upserts it into `sensor_capabilities` on the next discovery/sync cycle. No rollback risk — removing the sensor registration restores the previous behaviour.
