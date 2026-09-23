## Context

See `proposal.md` for motivation. The Raspberry Pi Pico 2 W (RP2350) environmental station currently acquires telemetry exclusively from a DHT22 sensor (GP15) and shares SPI0 between an ST7735 TFT display and an SD card reader. GP26 (ADC0 / Pin 31) is unallocated and serves as the analog input channel for the Adafruit ALS-PT19 (ADA2748) ambient light sensor.

## Goals / Non-Goals

**Goals:**
- Provide analog voltage sampling from GP26 using MicroPython's `machine.ADC`.
- Standardize light measurement as a percentage `0.0% - 100.0%` (`light_pct`) rounded to 1 decimal place.
- Extend `AppState` to store `light_pct`, incorporate it into `to_dict()`, and update `buffer_reading()` to hold light readings.
- Display `L:<val>%` (or `L:--%`) on the TFT telemetry line alongside temperature and humidity.
- Serve light telemetry via HTTP (`GET /info`, `GET /sensors`) and IoTMesh CoAP (`GET /sensors`, `GET /sensors/light`, `GET /.well-known/core`).
- Log `light_pct` to daily CSV files on SD storage (`timestamp,device_id,temperature_c,humidity_pct,light_pct`) and maintain pagination support in `log_sync.py`.

**Non-Goals:**
- Changes to `boards/pico-1w` (which does not have the ADA2748 sensor installed).
- Non-linear lux calibration tables or raw voltage conversions in the default API.
- Dynamic hotplug detection for analog sensors.

## Decisions

### Decision 1: Measurement Format as Percentage (`0.0% - 100.0%`) with Sensitivity Scaling & 32-Sample Oversampling
- **Rationale**: The ALS-PT19 phototransistor generates an analog voltage across its onboard 10kΩ load resistor proportional to ambient illuminance. Under typical indoor room lighting (~100 to 300 Lux), phototransistor collector current is on the order of 5–15 µA, generating ~0.05–0.15 V, which corresponds to only ~1.5%–4.5% of the 3.3V reference. To provide intuitive, human-meaningful readings in residential environments without complex non-linear lux curves, the raw ADC percentage is multiplied by a configurable `LIGHT_SCALE_FACTOR` defined in `settings/config.py` (e.g., 5.0) and capped at 100.0%:
  `light_pct = min(100.0, round(raw_pct * LIGHT_SCALE_FACTOR, 1))`
  Furthermore, rapid fluctuations caused by AC lighting ripple (100Hz/120Hz) and LED PWM drivers are smoothed by averaging 32 successive 16-bit ADC samples (`read_u16()`) per measurement cycle.
- **Alternatives Considered**:
  - *Unscaled Raw ADC Percentage*: In indoor ambient lighting without direct sunlight, unscaled values stay below 3-5%, making the sensor appear non-responsive to users.
  - *Estimated Lux*: Phototransistor response varies with incident angle, color temperature, and component tolerances; estimating lux without per-device calibrated lux curves introduces deceptive precision.
  - *Raw 16-bit ADC Integer or Voltage*: Less human-readable and inconsistent with existing percentage units used for humidity (`%RH`).

### Decision 2: Hardware Pin Allocation GP26 (Pin 31, ADC0)
- **Rationale**: GP26 is the primary ADC channel (ADC0) on the RP2350 / Pico 2 W. It is completely unallocated in `boards/pico-2w/settings/config.py` and avoids interference with SPI0 (GP16-GP22) and control lines (GP13-GP15).
- **Alternatives Considered**: GP27 (ADC1), GP28 (ADC2). GP26 is the canonical choice for the first analog sensor.

### Decision 3: TFT Screen Layout on Single Telemetry Line
- **Rationale**: The top line at vertical coordinate `y=8` currently renders `T:<temp>C H:<hum>%`. Formatting light as `L:<val>%` (or `L:--%`) results in `T:22.4C H:58% L:50%`. At 6 pixels per character in `sysfont`, a 19-character string measures 114 pixels wide, fitting inside the 128-pixel TFT boundary with comfortable 5-pixel margins.
- **Alternatives Considered**: Moving light to a separate row would push network and data logger status downward, causing overlap or clipping with the SD logger status section.

### Decision 4: Backward-Compatible 5-Column CSV Storage
- **Rationale**: The CSV schema becomes `timestamp,device_id,temperature_c,humidity_pct,light_pct`. In `sd_storage.py`, rows without a light value write an empty string `""` for the 5th column. In `log_sync.py`, row parsing continues to support 4-column lines from earlier sessions or remote boards while parsing the 5th column when present.
- **Alternatives Considered**: Storing light in a separate CSV file would fragment daily session records and complicate synchronization.

### Decision 5: IoTMesh CoAP Endpoints
- **Rationale**: The CoAP server advertises `</sensors/light>;rt="light";if="sensor"` in `GET /.well-known/core`. `GET /sensors` appends `{"n": "light", "u": "%", "v": <pct>}` to the SenML pack. A dedicated `GET /sensors/light` handler returns single SenML objects.
- **Alternatives Considered**: Omitting individual `GET /sensors/light` and only supporting collection `GET /sensors` (violates existing pattern where temperature and humidity each have dedicated endpoints).

## Risks / Trade-offs

- **[Risk] Display overrun when light is 100% or temperature is negative (e.g. `T:-10.2C H:100% L:100%`)**
  - *Mitigation*: Format light without decimals on the TFT screen: `f"L:{light:.0f}%"` (or `L:--%`), keeping total length to 19-20 characters max (120 pixels max at 6px/char), safely within the 128px width.
- **[Risk] MicroPython environment without ADC support during mock/host testing**
  - *Mitigation*: Gracefully handle `ImportError` or `machine.ADC` being `None` in `hardware/sensors.py`, setting ADC instance to `None` and returning `None` for `light_pct`.
- **[Risk] Artificial lighting ripple (100/120Hz) and low indoor voltage output**
  - *Mitigation*: Smooth readings using 32-sample oversampling in `read_sensors()` and scale values using `LIGHT_SCALE_FACTOR` (default 5.0) in `settings/config.py` with an upper clamp at 100.0%.
