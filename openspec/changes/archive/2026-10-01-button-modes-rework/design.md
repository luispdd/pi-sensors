## Context

All three boards share a `UIController` in `hardware/ui.py` that owns button polling (`poll_button`, `poll_button_log`) and dispatches to `handle_button` / `handle_button_log`. Mode transitions call into `AppState` (`enter_sensor_mode`, `enter_semi_sleep`, `enter_message_mode`). The pico-2w additionally owns `hardware/display.py` (TFT rendering) and `hardware/sd_storage.py`. See proposal.md for motivation.

Current mode constants live in both `core/state.py` and each board's `hardware/ui.py` as mirrored integers. The new `MODE_DETAILS = 3` must be added to both.

## Goals / Non-Goals

**Goals:**
- Introduce `MODE_DETAILS` as a first-class mode on all boards.
- Reroute primary button short press to cycle STATUS↔DETAILS, and long press to universally enter SEMI_SLEEP.
- Restore previous mode on SEMI_SLEEP and MESSAGE_MODE exit.
- Add boot-scoped min/max tracking to `AppState._metrics`.
- Implement DETAILS_MODE rendering: sensor min/max table (pico-1w, esp32c6); paginated SD file listing (pico-2w).
- Add PIR activity line to pico-2w STATUS_MODE layout.
- Add `list_files()` to `SDStorage`.

**Non-Goals:**
- Min/max display in DETAILS_MODE on pico-2w (deferred).
- Persistent min/max across reboots.
- Sorting / filtering of SD file listing beyond alphanumeric order.
- Any changes to network API, CoAP schemas, or telemetry payloads.

## Decisions

### D1: `MODE_DETAILS = 3` added to both `state.py` and `ui.py`
Both files already mirror mode constants. Adding the new constant in both places keeps the pattern consistent and avoids importing `state.py` inside `ui.py` just for a constant.

### D2: `_previous_mode` stored in `AppState`, updated via new state methods
New methods `enter_details_mode()` and updated `enter_semi_sleep()` / `enter_message_mode()` set `_previous_mode` before changing `mode`. A new `restore_previous_mode()` method returns `_previous_mode` and resets it to `MODE_SENSOR_DISPLAY`. This keeps mode logic in state and UI handlers simple.

### D3: SEMI_SLEEP wakeup: any press, not just short press
`poll_button` detects button press on the falling edge (button down). In SEMI_SLEEP the handler fires immediately on falling edge instead of waiting for the rising edge + duration check, so both short and long presses wake the device without requiring the user to count milliseconds.

**Alternative considered**: wait for release as usual. Rejected: awkward UX — the user would hold the button, nothing happens, then release to wake. Immediate-on-press feels natural.

### D4: Min/max updated inside `AppState.update_metric()`
`update_metric()` is the single write path for all sensor values. Adding min/max update logic there ensures all metric sources (direct reads, `update_sensors()`, registered sensor reads) benefit automatically without per-callsite changes.

```
Before:  _metrics[key] = {val, unit, ts, errors}
After:   _metrics[key] = {val, unit, ts, errors, min, max}
```

`min` and `max` initialise to `None`; on first non-None value both are set to that value.

### D5: SD file list cached in `UIController`, refreshed on each DETAILS_MODE entry
`UIController` gains `_sd_file_list: list` and `_sd_file_page: int`. On every transition into DETAILS_MODE, `_load_sd_file_list()` is called: it mounts the SD, calls `sd_storage.list_files()`, sorts the result, caches it, resets page to 0, then unmounts. The TFT then renders the cached list. This avoids blocking the display refresh loop with SD I/O after the initial load.

`list_files(path)` in `SDStorage` uses `os.listdir(path)` after mounting; it is the caller's responsibility to mount/unmount (consistent with the rest of `SDStorage`).

### D6: pico-2w per-page capacity is computed from TFT height and line spacing
TFT is 128×160. sysfont renders at 8px; `render_details()` uses 12px line spacing. After a header line at y=5 (height ~20px including separator), remaining height ≈ 140px → floor(140/12) = 11 lines available per page. `<Next page>` occupies the last slot when needed, so effective file count per page = 10 (or 11 on last page with no overflow). This constant is derived at render time from screen geometry, not hard-coded separately.

### D7: pico-2w secondary button routing gated on `app_state.mode`
`handle_button_log()` currently checks `logger_state`. A new guard is added at the top: if `app_state.mode == MODE_DETAILS`, dispatch to the file-page-advance handler and return early; otherwise proceed with the existing logger lifecycle logic.

### D8: pico-2w STATUS_MODE layout shift
Current `render_status()` places telemetry at y=8. PIR line is inserted at y=22. All subsequent lines shift down by 14px. The logging section divider (currently at y=78) moves to y=92; logger sub-lines follow at y=98+. This keeps all content within the 160px height.

```
y=8   T:<temp> H:<hum> L:<light>
y=22  PIR: <val>%                  <- NEW
y=36  <ip or wifi status>
y=50  CoAP: /display
y=64  Reqs: <n>
y=78  Last: <caller>
y=92  --- divider ---
y=98  LOG <nodes>
y=110 Buf: <n> reads
y=122 NTP: <time> / <error>
```

## Risks / Trade-offs

- **SD mount latency on DETAILS_MODE entry** → The file list load blocks `UIController` briefly (~100–300ms typical). Mitigated by loading once per mode entry and caching; subsequent renders use the cached list.
- **SD unavailable during file list load** → `list_files()` failure is caught; `_sd_file_list` is set to an empty list and an error string is displayed. No crash.
- **pico-2w STATUS_MODE layout shift** → Moving lines down by 14px on a 160px screen compresses the logging section from y=78 to y=92. Three logger sub-lines still fit (y=98, y=110, y=122) without clipping.
- **Falling-edge wakeup (D3) and long-press SEMI_SLEEP entry**: if the user holds the button ≥ 1000 ms from SEMI_SLEEP, the falling edge wakes immediately and the long-press path is never reached. This is correct and intentional.
