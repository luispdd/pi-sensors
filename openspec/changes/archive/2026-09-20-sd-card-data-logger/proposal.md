## Why

The Pico 2W board already reads DHT22 sensor data and can query remote boards via CoAP, but all telemetry is ephemeral — lost on power cycle, with no historical record. Adding SD card logging enables persistent time-series storage per board per day, turning the Pico 2W into a standalone data recorder without requiring an always-on host PC.

## What Changes

- **New capability**: SD card data logger service that buffers sensor readings in RAM and flushes to CSV files on the SD card on a scheduled or on-demand basis.
- **New capability**: NTP time synchronisation service that syncs the board's RTC from the internet once per logging session (and nightly), providing UTC wall-clock timestamps.
- **New capability**: Logger session control via a dedicated second button (GP13/Pin 17) with a multi-stage interaction: arm → NTP sync + CoAP discovery → confirm screen → active logging → flush+stop.
- **New capability**: Active CoAP sensor-node discovery — pico-2w multicasts to `224.0.1.187` to enumerate all reachable boards advertising temperature or humidity resources, then polls them every 5 minutes during a logging session.
- **Modified capability**: CoAP node advertisement — the `.well-known/core` response now includes a `/logger` resource so other nodes can discover that this board has data-logger capabilities.
- **Modified capability**: TFT display — the normal sensor screen gains a logging status section in the lower area (boards tracked, buffered-read count, last NTP timestamp) when a logging session is active; the header line and separator are dropped to reclaim space only if required.
- **New**: Per-device UTC-timestamped CSV files written to `/sensor-data/` on the SD card, one file per board per day (e.g. `2026-09-20-pico-2w.csv`), with append-resume across power cycles.

## Capabilities

### New Capabilities

- `core/data-logger`: Persistent SD card logging service — session lifecycle (arm/active/flush), in-memory ring buffer, per-device daily CSV file management with append-resume, CoAP sensor polling of remote boards.
- `core/ntp-sync`: NTP time synchronisation — syncs `time.time()` from the internet before each logging session starts and nightly; surfaces errors to the display if WiFi or NTP is unavailable.
- `boards/pico-2w/logger-button`: Logger session control button — GP13 dedicated button with short-press and long-press detection driving the five-stage logger state machine (IDLE → STAGING → CONFIRM → ACTIVE → IDLE).

### Modified Capabilities

- `core/iotmesh/coap-node`: `/logger` resource added to `.well-known/core` advertisement and a new `GET /logger` endpoint returning current logger status as JSON.
- `core/display-service`: `render_status` extended with an optional logging status section at the bottom of the TFT screen; compact layout (header + separator removed) triggered automatically when vertical space is insufficient.

## Impact

- **New files**: `boards/pico-2w/services/data_logger.py`, `boards/pico-2w/hardware/sd_storage.py`
- **Modified files**: `boards/pico-2w/main.py`, `boards/pico-2w/core/state.py`, `boards/pico-2w/hardware/display.py`, `boards/pico-2w/hardware/controls.py`, `boards/pico-2w/services/coap_server.py`, `boards/pico-2w/settings/config.py`
- **Hardware**: Requires a second push button wired to GP13 (Pin 17); SD card already wired on GP22 via SPI0
- **SD driver**: `lib/sdcard.mpy` already present; MicroPython `os.mount` and `uos` used for filesystem ops
- **NTP**: MicroPython built-in `ntptime` module; requires active WiFi connection at session start
- **SPI bus**: SD card and TFT share SPI0; SD storage module must re-initialise SPI baudrate (10 MHz) before each access and TFT display must restore its baudrate (20 MHz) after; no new wiring needed
- **CoAP**: Existing `microcoapy` client used for multicast discovery and remote sensor polling; `_handle_response` callback extended to parse resource types from CoRE Link Format
