## 1. Shared State — AppState (all boards)

- [x] 1.1 Add `MODE_DETAILS = 3` constant to `core/state.py` alongside the existing mode constants, and add `_previous_mode` field (default `MODE_SENSOR_DISPLAY`) to `AppState.__init__`. Verify the constant is importable and `_previous_mode` exists on a freshly constructed `AppState`.
- [x] 1.2 Add `enter_details_mode()` method to `AppState` that sets `mode = MODE_DETAILS` and clears alerts; update `enter_semi_sleep()` and `enter_message_mode()` to save `self.mode` into `_previous_mode` before changing mode; add `restore_previous_mode()` that sets `mode = _previous_mode` and resets `_previous_mode = MODE_SENSOR_DISPLAY`. Verify via the existing test suite or a quick REPL check that transitions set `_previous_mode` correctly.
- [x] 1.3 In `AppState.update_metric()`, after updating `val`, compare against `_metrics[key]["min"]` and `_metrics[key]["max"]` and update them (initialise both to `None` on first non-None value). Add `"min": None, "max": None` to the metric dict in `register_sensor()` and in the inline creation path. Verify that after two readings the `min` and `max` values in `_metrics` reflect the lower and higher value respectively.

## 2. pico-1w — Button Rework & DETAILS_MODE

- [ ] 2.1 Add `MODE_DETAILS = 3` to `boards/pico-1w/hardware/ui.py` constants block. Verify constant is present.
- [ ] 2.2 Rewrite `handle_button()` in `boards/pico-1w/hardware/ui.py` to implement the new semantics: long press → `app_state.enter_semi_sleep()` + `power_off()`; short press in STATUS_MODE → `app_state.enter_details_mode()`; short press in DETAILS_MODE → `app_state.enter_sensor_mode()`; short press in MESSAGE_MODE → `app_state.restore_previous_mode()` + `power_on()`; any press in SEMI_SLEEP → `app_state.restore_previous_mode()` + `power_on()` (fire on falling edge, not release). Verify each transition by tracing through the logic manually or via a stub test.
- [ ] 2.3 Update `poll_button()` in `boards/pico-1w/hardware/ui.py`: when `app_state.mode == MODE_SEMI_SLEEP`, fire `handle_button("wake", app_state)` on the falling edge (button pressed, `val == 0` and `_btn_last_val == 1`) instead of waiting for release. Verify that SEMI_SLEEP wakeup fires immediately on press, not on release.
- [ ] 2.4 Add `render_details_view(app_state)` to `boards/pico-1w/hardware/ui.py`. Uses `OLEDDisplay`; renders a header `[DETAILS]`, then one row per metric (temperature, humidity) in format `<KEY>: <cur> <min> <max>` (all truncated to `MAX_LINE_LEN`), then a blank fourth row. Values formatted to one decimal place; `--` for `None`. Verify the screen text layout by reading the method and confirming y-positions don't exceed 64px.
- [ ] 2.5 Update `update()` in `boards/pico-1w/hardware/ui.py` to dispatch to `render_details_view(app_state)` when `mode == MODE_DETAILS`. Verify by tracing the `update()` dispatch path.

## 3. esp32c6 — Button Rework & DETAILS_MODE

- [ ] 3.1 Add `MODE_DETAILS = 3` to `boards/esp32c6/hardware/ui.py` constants block. Verify constant is present.
- [ ] 3.2 Rewrite `handle_button()` in `boards/esp32c6/hardware/ui.py` with the same new semantics as task 2.2. Verify each transition path manually.
- [ ] 3.3 Update `poll_button()` in `boards/esp32c6/hardware/ui.py`: fire on falling edge when in SEMI_SLEEP (same pattern as task 2.3). Verify wakeup fires on press, not release.
- [ ] 3.4 Add `render_details_view(app_state)` to `boards/esp32c6/hardware/ui.py`. Same layout as task 2.4, using the direct `self.oled` API (fill, text, show). Verify y-positions fit within 64px OLED height.
- [ ] 3.5 Update `update()` in `boards/esp32c6/hardware/ui.py` to dispatch to `render_details_view(app_state)` when `mode == MODE_DETAILS`. Verify dispatch path.

## 4. pico-2w — State Constants & Button Rework

- [ ] 4.1 Add `MODE_DETAILS = 3` to `boards/pico-2w/hardware/ui.py` constants block. Verify constant is present.
- [ ] 4.2 Rewrite `handle_button()` in `boards/pico-2w/hardware/ui.py` with the new semantics (same as task 2.2). Verify each transition path manually.
- [ ] 4.3 Update `poll_button()` in `boards/pico-2w/hardware/ui.py`: fire on falling edge when in SEMI_SLEEP (same pattern as task 2.3). Verify wakeup fires on press.
- [ ] 4.4 Update `handle_button_log()` in `boards/pico-2w/hardware/ui.py`: add a guard at the top — if `app_state.mode == MODE_DETAILS`, call `self._advance_file_page()` on short press and return; otherwise proceed with the existing logger lifecycle logic. Verify guard by tracing the dispatch.

## 5. pico-2w — SD File Listing

- [ ] 5.1 Add `list_files(path)` to `boards/pico-2w/hardware/sd_storage.py`. The method calls `os.listdir(path)` (SD must already be mounted by caller) and returns a sorted list of filenames. If the path does not exist or `listdir` fails, return an empty list. Verify by inspecting the method and confirming it returns a sorted list.
- [ ] 5.2 Add `_sd_file_list`, `_sd_file_page`, and `_sd_storage` fields to `UIController.__init__` in `boards/pico-2w/hardware/ui.py`. Add `_load_sd_file_list(sd_storage)` method: mounts SD, calls `sd_storage.list_files("/sd/sensor-data")`, caches sorted result in `_sd_file_list`, resets `_sd_file_page = 0`, then unmounts. On any exception, sets `_sd_file_list = []` and stores an error string. Verify mount/unmount and caching by reading the method.
- [ ] 5.3 Add `_advance_file_page()` method to `UIController`: increments `_sd_file_page`, wrapping to 0 after the last page. Verify wrap-around logic with a mental walkthrough (e.g., 15 files, 10 per page → pages 0 and 1, wraps at 2).

## 6. pico-2w — TFT Display Updates

- [ ] 6.1 Update `run_button_task()` in `boards/pico-2w/hardware/ui.py` to pass `sd_storage` through to `UIController` (store as `self._sd_storage`). Update `main.py` call if needed. Verify `_sd_storage` is accessible inside `UIController`.
- [ ] 6.2 Update `handle_button()` (or the `update()` dispatcher) to call `self._load_sd_file_list(self._sd_storage)` when transitioning into `MODE_DETAILS`. Verify the load is triggered exactly on mode entry.
- [ ] 6.3 Add `render_details(file_list, page, lines_per_page)` to `boards/pico-2w/hardware/display.py`. Renders a `[SD Files]` header, then filenames for the current page, then `<Next page>` on the last visible line when more files remain. Uses TFT text calls with sysfont at 12px line spacing. Verify the line count and y-positions don't exceed 160px for a full page of 10 filenames.
- [ ] 6.4 Add `render_details_view(app_state)` to `boards/pico-2w/hardware/ui.py` that calls `self.display.render_details(self._sd_file_list, self._sd_file_page, lines_per_page)`. Update `update()` to dispatch to it when `mode == MODE_DETAILS`. Verify dispatch path.
- [ ] 6.5 Update `render_status()` in `boards/pico-2w/hardware/display.py` to add a PIR activity line at y=22 and shift all subsequent lines down by 14px (new y values: ip/wifi at y=36, CoAP at y=50, Reqs at y=64, Last at y=78, divider at y=92, LOG lines at y=98/110/122). Update `render_sensor_view()` in `ui.py` to pass the PIR metric value. Verify visually that no line is cut off at y≥160.

## 7. Final Verification

- [ ] 7.1 Deploy to pico-1w and confirm: short press cycles STATUS↔DETAILS; DETAILS renders temp/humidity cur/min/max; long press blanks display and enters SEMI_SLEEP; any press wakes and restores previous mode; incoming CoAP message interrupts and short press returns to previous mode.
- [ ] 7.2 Deploy to esp32c6 and confirm the same button and display behaviours as 7.1.
- [ ] 7.3 Deploy to pico-2w and confirm: STATUS_MODE shows PIR line; short press cycles STATUS↔DETAILS; DETAILS_MODE shows SD file listing refreshed on each entry; secondary button in DETAILS_MODE pages through files; secondary button in STATUS_MODE still drives logger lifecycle; long press enters SEMI_SLEEP; any press wakes and restores previous mode.
