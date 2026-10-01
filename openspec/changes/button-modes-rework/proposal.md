## Why

The primary button on all boards currently uses short press to toggle between active display and semi-sleep, and long press to toggle the display on/off arbitrarily — a fragile, confusing model with no room for additional interactions. Introducing a modal display design (STATUS_MODE / DETAILS_MODE / SEMI_SLEEP / MESSAGE_MODE) unlocks richer per-board information views and creates a coherent, extensible interaction pattern.

## What Changes

- **BREAKING**: Primary button (GP14 / equivalent) short press behaviour changes on all boards. Short press no longer toggles semi-sleep; it cycles between STATUS_MODE and DETAILS_MODE. Long press now universally enters SEMI_SLEEP from any mode; any press exits SEMI_SLEEP restoring the previous mode.
- Add `MODE_DETAILS` constant (value `3`) to `AppState` on all boards.
- Add `_previous_mode` tracking to `AppState` so SEMI_SLEEP and MESSAGE_MODE can restore the prior mode on exit.
- Add per-metric `min` / `max` tracking (boot-scoped) to `AppState._metrics` on all boards (used by DETAILS_MODE display on pico-1w and esp32c6).
- **pico-1w**: New DETAILS_MODE screen showing current / min / max per sensor metric (temperature, humidity) using one line per metric.
- **esp32c6**: New DETAILS_MODE screen showing current / min / max per sensor metric (temperature, humidity) using one line per metric.
- **pico-2w**: New DETAILS_MODE screen showing a paginated SD file listing from `/sd/sensor-data/`. File list is refreshed on every entry into DETAILS_MODE. Secondary button (GP13) advances the page while in DETAILS_MODE; in STATUS_MODE the secondary button continues its existing data logger lifecycle role.
- **pico-2w STATUS_MODE**: PIR activity added as a new second line; existing network / request / caller lines shift down one position.
- MESSAGE_MODE: external messages still interrupt immediately; short press on primary button discards the message and restores the previous mode (was: always returning to STATUS_MODE).

## Capabilities

### New Capabilities

- `core/display-modes`: Defines the four-mode display interaction model (STATUS_MODE, DETAILS_MODE, SEMI_SLEEP, MESSAGE_MODE), button semantics for each mode, and the previous-mode restore contract.

### Modified Capabilities

- `boards/pico-2w`: Button interaction requirements change (long press → SEMI_SLEEP; short press → cycle modes); STATUS_MODE layout adds PIR line; DETAILS_MODE (SD file listing) is introduced.
- `boards/esp32c6`: Button interaction requirements change; DETAILS_MODE (sensor min/max table) is introduced.
- `boards/pico-dh22-screen`: Button interaction requirements change; DETAILS_MODE (sensor min/max table) is introduced.

## Impact

- `core/state.py` (all boards): new mode constant, previous-mode tracking, min/max per metric.
- `hardware/ui.py` (all 3 boards): button handlers, new `render_details_view()`, updated `update()` dispatcher.
- `hardware/display.py` (pico-2w): `render_status()` updated for PIR line; new `render_details()` for SD file listing.
- `hardware/sd_storage.py` (pico-2w): new `list_files()` helper returning sorted filenames from the data directory.
- No API, network protocol, or CoAP schema changes.
