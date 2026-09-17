## 1. AppState — Mode Constants, State Transitions, and Encapsulation

- [x] 1.1 Add module-level constants `MODE_SENSOR_DISPLAY = 0`, `MODE_SEMI_SLEEP = 1`, `MODE_MESSAGE = 2` to `state.py` and replace the `alert_active` field with `mode: int = MODE_SENSOR_DISPLAY` and a new `pending_message: str | None = None` field. Verify by importing `state.py` in a REPL and asserting `AppState().mode == 0`.
- [x] 1.2 Remove `set_display_override()` and `clear_display_override()` and replace them with three transition methods: `enter_sensor_mode()`, `enter_semi_sleep()`, and `enter_message_mode(text, caller=None)`. Each method sets `self.mode`, updates `alert_message`, `display_override_text`, `pending_message`, and `last_caller` consistently. Verify by calling each in a REPL and asserting the expected `mode` and field values.
- [x] 1.3 Update `is_display_overridden()` to return `self.mode == MODE_MESSAGE`. Verify it returns `True` only after `enter_message_mode()` and `False` after `enter_sensor_mode()` or `enter_semi_sleep()`.
- [x] 1.4 Add encapsulation methods `record_request()`, `resolve_caller()`, `register_node()`, `update_wifi()`, `set_pending_message()`, and `has_pending_message()` to `AppState` in `state.py` to eliminate direct field mutations from external callers.

## 2. Display Module — `power_off()` and Presentation Decoupling

- [x] 2.1 Add `power_off()` to `OLEDDisplay` in `display.py` that calls `self.oled.fill(0)` and `self.oled.show()` if the display is initialised, matching the existing `clear()` pattern. Verify the method exists and does not raise when `oled is None`.
- [x] 2.2 Decouple display rendering by separating pure coordinate presentation (`render_status`) from state extraction (`update_from_state`), keeping `update` as a backwards-compatible delegator.

## 3. Main — Sensor and Display Task Idle Branches

- [x] 3.1 In `sensor_task` in `main.py`, wrap the DHT22 read block in `if app_state.mode != MODE_SEMI_SLEEP:` and add an `else: await asyncio.sleep(0.1)` idle branch. Verify by setting `app_state.mode = MODE_SEMI_SLEEP` and confirming no DHT22 read occurs during that interval.
- [x] 3.2 In `display_task` in `main.py`, update display call to `oled.update_from_state(app_state)` wrapped in `if app_state.mode != MODE_SEMI_SLEEP:` and add an `else: await asyncio.sleep(0.1)` idle branch. Verify that when mode is `MODE_SEMI_SLEEP` the display is not updated.
- [x] 3.3 Import `MODE_SENSOR_DISPLAY`, `MODE_SEMI_SLEEP`, and `MODE_MESSAGE` from `state` in `main.py`.

## 4. Hardware Controls & Button Task Three-State Cycle

- [x] 4.1 Create `controls.py` defining `Button` (active-LOW pull-up with edge detection `was_pressed()`) and `AlertLED` (`on()`, `off()`, `set()`) hardware classes.
- [x] 4.2 Rewrite `button_task` in `main.py` using `Button` and `AlertLED` to implement the full three-state cycle using transition methods:
  - `MODE_SENSOR_DISPLAY` → `app_state.enter_semi_sleep()` + `oled.power_off()` + `led.off()`
  - `MODE_SEMI_SLEEP` with `app_state.has_pending_message()` → `app_state.enter_message_mode(app_state.pending_message)` + `led.on()`
  - `MODE_SEMI_SLEEP` with no pending message → `app_state.enter_sensor_mode()` + `led.off()`
  - `MODE_MESSAGE` → `app_state.enter_sensor_mode()` + `led.off()`
- [x] 4.3 Update the LED sync line in `button_task`: `led.set(app_state.mode == MODE_MESSAGE or app_state.has_pending_message())`.
- [x] 4.4 Pass `oled` into `button_task` and verify it receives and calls `oled.power_off()` on entering semi-sleep.

## 5. CoAP Server — POST /display Semi-Sleep Queuing

- [x] 5.1 In `_handle_display` in `coap_server.py`, add a mode branch: if `app_state.mode == MODE_SEMI_SLEEP`, store the payload via `app_state.set_pending_message(text, caller=caller)` and return `2.04 Changed` without calling `enter_message_mode()`. Otherwise, call `app_state.enter_message_mode(text, caller=caller)` as before. Verify that a `POST /display` during semi-sleep sets `pending_message` and does not change `app_state.mode`.
- [x] 5.2 Add `reader: SensorReader` parameter to `CoapServer.__init__()` and store it as `self.reader`. Update the instantiation in `coap_task` in `main.py` to pass `reader`. Verify `CoapServer` stores the reference correctly.
- [x] 5.3 In `_handle_sensor_temperature`, `_handle_sensor_humidity`, and `_handle_sensors_collection`, add `if self.app_state.mode == MODE_SEMI_SLEEP: data = self.reader.read_sensors(); self.app_state.update_sensors(data)` before building the response payload. Verify that a CoAP `GET /sensors` during semi-sleep returns freshly read values.
- [x] 5.4 Use `app_state.record_request()` and `app_state.register_node()` in `coap_server.py` to encapsulate caller and node resolution.

## 6. HTTP Server — On-Demand Read for /info

- [x] 6.1 Add `reader: SensorReader` parameter to `WebServer.__init__()` and store it as `self.reader`. Update instantiation in `server_task` in `main.py` to pass `reader`. Verify `WebServer` stores the reference correctly.
- [x] 6.2 In `handle_client`, before building the `/info` JSON payload, add `if self.app_state.mode == MODE_SEMI_SLEEP: data = self.reader.read_sensors(); self.app_state.update_sensors(data)`. Verify that a `GET /info` during semi-sleep returns freshly read values.
- [x] 6.3 Use `app_state.record_request()` in `webserver.py` to encapsulate request counting and caller tracking.

## 7. Import Cleanup and Integration Verification

- [x] 7.1 Import `MODE_SEMI_SLEEP` (and other constants as needed) in `coap_server.py` and `webserver.py` from `state`. Verify no `NameError` is raised at module load.
- [x] 7.2 Centralize `sys.path` bootstrapping for `lib/` in `config.py` and remove duplicate search loops from `display.py` and `coap_server.py`.
- [x] 7.3 Boot the device and verify the startup mode is `MODE_SENSOR_DISPLAY` (display on with sensor metrics).
- [x] 7.4 Press the button once from `MODE_SENSOR_DISPLAY`: verify OLED goes blank and LED stays off.
- [x] 7.5 While in `MODE_SEMI_SLEEP`, send a `POST /display`: verify LED turns on but OLED stays blank.
- [x] 7.6 Press the button once from `MODE_SEMI_SLEEP` with a pending message: verify OLED shows the message and LED stays on.
- [x] 7.7 Press the button once from `MODE_MESSAGE`: verify OLED resumes sensor metrics and LED turns off.
- [x] 7.8 While in `MODE_SEMI_SLEEP`, send `GET /info` (HTTP) or `GET /sensors` (CoAP): verify the response contains freshly read sensor values and the node stays in `MODE_SEMI_SLEEP`.

