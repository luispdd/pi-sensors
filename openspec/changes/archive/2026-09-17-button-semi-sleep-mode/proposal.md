## Why

The station currently runs its sensor loop and OLED display continuously, with no way to reduce activity when the node is unattended. Adding a "semi-sleep" mode accessible via the physical button gives the operator a low-effort way to silence the display and stop continuous sensor polling, while keeping the node network-reachable and capable of receiving alert messages.

## What Changes

- **New mode constant set**: Replace the `alert_active` boolean in `AppState` with three named integer constants (`MODE_SENSOR_DISPLAY`, `MODE_SEMI_SLEEP`, `MODE_MESSAGE`) and a single `mode` field, making state transitions explicit and readable.
- **New `MODE_SEMI_SLEEP` state**: When the button is pressed while in `MODE_SENSOR_DISPLAY`, the node enters semi-sleep: the display is cleared and turned off, and the sensor polling loop becomes idle (polling the mode flag at a slow tick instead of reading the DHT22).
- **Button cycle**: The physical button now cycles through three states:
  - `MODE_SENSOR_DISPLAY` → button → `MODE_SEMI_SLEEP`
  - `MODE_SEMI_SLEEP` → button (no pending message) → `MODE_SENSOR_DISPLAY`
  - `MODE_SEMI_SLEEP` → button (pending message) → `MODE_MESSAGE`
  - `MODE_MESSAGE` → button → `MODE_SENSOR_DISPLAY`
- **Pending message during semi-sleep**: A `POST /display` received while in `MODE_SEMI_SLEEP` does not turn the display on; instead, the message is stored as `pending_message` in `AppState` and the alert LED is turned on to signal a waiting notification.
- **On-demand sensor reads in semi-sleep**: HTTP `GET /info` and any CoAP sensor endpoint (`GET /sensors`, `/sensors/temperature`, `/sensors/humidity`) received during `MODE_SEMI_SLEEP` trigger a synchronous DHT22 read before responding (~250 ms blocking call accepted).
- **Startup**: Node always starts in `MODE_SENSOR_DISPLAY`.

## Capabilities

### New Capabilities

### Modified Capabilities

- `display-service`: Add semi-sleep display state — clear and blank the screen on entering semi-sleep; resume normal refresh on exit. Replace `alert_active` boolean semantics with the `mode` constant.
- `iotmesh/display-actuator`: `POST /display` in semi-sleep stores the payload as a pending message and turns on the LED without showing it. Button press in semi-sleep with a pending message transitions to `MODE_MESSAGE`; second button press transitions to `MODE_SENSOR_DISPLAY`.
- `sensor-monitoring`: Sensor loop enters an idle polling branch in `MODE_SEMI_SLEEP`; on-demand DHT22 reads are performed synchronously when a sensor request arrives during semi-sleep.

## Impact

- `controls.py`: New module encapsulating `Button` (active-LOW, pull-up, edge detection) and `AlertLED` hardware classes.
- `state.py`: New mode constants, `pending_message` field; full encapsulation of requests, caller resolution, network updates, and mode transitions.
- `main.py`: `button_task` implements the three-state cycle using `Button` and `AlertLED`; `sensor_task` and `display_task` each gain an idle branch; display updates use `oled.update_from_state(app_state)`.
- `display.py`: New `power_off()` method called on entering semi-sleep; decoupled presentation layer (`render_status`) from state mapping (`update_from_state`).
- `config.py`: Centralized `sys.path` bootstrapping for `lib/` directory.
- `coap_server.py`: `_handle_display` checks `mode` to decide whether to show or queue; sensor handlers check `mode` and call `reader.read_sensors()` on demand. `CoapServer` receives a `reader` reference.
- `webserver.py`: `handle_client` checks `mode` and performs on-demand read for `/info`. `WebServer` receives a `reader` reference.
- No API contract changes; CoAP and HTTP response shapes are unchanged.

