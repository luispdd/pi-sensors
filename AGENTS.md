-Do not ever stage or commit files on your own.
-Don't modify the external libraries, like `lib/microcoapy`, etc. in the codebase.
-Don't ever take decisions about new functionalities or user-facing changes without consulting the user.

## Operational Pitfalls & Gotchas
- **No Speculative Sensors / Metrics**: Never invent unrequested sensor types, metrics, or mock labels. Only implement sensors explicitly confirmed by the user.
- **Metric Key Consistency**: The modular sensor framework uses canonical keys (`temperature`, `humidity`, `light`, `motion`). Always access metric values via `app_state.get_metric_val("<key>")` or maintain compatibility property bridges in `AppState` instead of assuming arbitrary property names.
- **Immediate Display Update on Mode Switch**: Always trigger an immediate render call upon button-triggered mode transitions (e.g. `STATUS_MODE` <-> `DETAILS_MODE`) to prevent visual display freeze while waiting for the background display loop tick.
- **SD SPI Arbitration on Pico 2 W**: When reading SD directory contents for `DETAILS_MODE`, mount, read `/sd/sensor-data/`, cache, and unmount immediately to keep shared SPI0 bus unblocked for ST7735 TFT rendering.
- **OpenSpec MODIFIED Scenarios Retention**: A `MODIFIED` requirement block completely replaces the existing requirement block during archive/validation. Never drop existing `#### Scenario:` blocks from the main spec in a delta spec unless intentionally removing them with `REMOVED`.
- **Board UI Architecture Separation**: Do not assume display files are shared or identically named across boards. Pico 2 W uses `boards/pico-2w/hardware/display.py` (ST7735 TFT), whereas ESP32-C6 uses `boards/esp32c6/hardware/ui.py` (SSD1306 OLED).
- **ESP32 ADC Attenuation for DC-Biased Sensors**: When configuring `machine.ADC` on ESP32 MicroPython for DC-biased sensors (e.g., MAX4466 centered at $V_{CC}/2 \approx 1.65\text{V}$), pass `atten` directly in the constructor `ADC(pin, atten=ADC.ATTN_11DB)` because `adc.atten()` is not supported on newer MicroPython/IDF5 builds. Default 0 dB attenuation caps at ~1.0V/1.1V, completely saturating the ADC at 65535 and preventing AC swing detection (claps register $\le 0.7\%$). Also provide a `math.log` fallback for `math.log10` since `log10` is missing from many MicroPython builds.
- **Board-Specific PIR GPIO Input Pulls**: Pico 2 W (RP2350) GPIO pads enable internal pull-ups by default upon reset; unpulled inputs float HIGH and peg rolling motion at 100%, requiring `Pin(pin, Pin.IN, Pin.PULL_DOWN)`. Conversely, ESP32-C6 internal pull-down (~45kΩ) forms a voltage divider with the AM312 output stage attenuating HIGH pulses below $V_{IH}$ (causing 0% detection failure); ESP32-C6 requires high-impedance `Pin(pin, Pin.IN)` without pull-down.
- **Fixed-Point Rounding Trap in Decay Filters**: In exponential smoothing `last = round(last + (0 - last) * release, 1)`, a decay factor like `release = 0.2` locks at `0.2%` forever ($0.2 \times 0.8 = 0.16 \xrightarrow{\text{round}} 0.2$). Always maintain an unrounded float accumulator (`_smoothed_pct`) and snap to `0.0` when below a threshold before rounding for external consumers.
- **MicroPython Platform Detection**: Do not use `sys.implementation._machine` (does not exist in MicroPython and raises `AttributeError`). Check `getattr(sys, "platform", "")` (`"esp32"` vs `"rp2"`) or `os.uname().machine`.

## Verification Commands
- **Unit Tests**: `python3 -m unittest discover -s boards/<board>/test`
- **OpenSpec Validation**:
  - Main specs: `openspec validate --specs`
  - Archived changes: `openspec validate --archived`
  - All: `openspec validate --all`

