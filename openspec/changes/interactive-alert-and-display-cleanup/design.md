## Context

The environmental station currently tracks light via an LM393 sensor on GP14, renders an 8-line display showing `http://` prefixes and `/sensors`, and automatically expires remote display alerts after 60 seconds. See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**
- Free GP14 by deprecating LM393, reusing it for a physical acknowledgement button with internal pull-up.
- Drive a single-color alert LED on GP16 when an alert message is active.
- Require physical button press to dismiss `POST /display` messages and turn off the alert LED.
- Clean up OLED layout: remove lines 1–3, remove `http://`, display `/info`, and show `Last: <caller>` at the bottom.
- Cache network nodes from CoRE Link Format discovery (`/.well-known/core`) to resolve caller IDs, falling back to discovery probe and IP octet suffix.

**Non-Goals:**
- Adding persistent storage for alerts across device power cycles.
- Supporting multi-color or RGB PWM animations on the LED (standard ON/OFF digital pin).

## Decisions

### 1. Hardware Pin Assignment
- **Button Pin**: GP14 configured as `Pin(14, Pin.IN, Pin.PULL_UP)`. Active LOW (pressed to GND).
- **LED Pin**: GP16 configured as `Pin(16, Pin.OUT)`. Active HIGH (HIGH = illuminated).
- *Rationale*: Reuses the vacated GP14 from the LM393 sensor and uses an adjacent GP16 without conflicting with I2C (GP0, GP1) or DHT22 (GP15).

### 2. Alert State Machine in `AppState`
- Replace `display_override_expires_at` with a boolean `alert_active = False` and `alert_caller = None`.
- `set_display_override(text, caller=None)`: Sets `alert_active = True`, `display_override_text = text`, `alert_caller = caller`, and turns on the LED.
- `clear_display_override()`: Sets `alert_active = False`, `display_override_text = None`, and turns off the LED.
- *Rationale*: Completely decouples alert dismissal from timer ticks, making it strictly event-driven by the button.

### 3. Asynchronous Button Task
- Create a lightweight coroutine in `main.py` polling the button pin every 50ms with debouncing.
- When button press detected while `alert_active` is True, invoke `app_state.clear_display_override()`.

### 4. Discovery Caching and Caller Resolution
- Maintain `app_state.known_nodes = {}` mapping `{ip_str: device_id_str}`.
- When `CoapServer` handles incoming discovery responses from `.well-known/core`, parse `ep="<id>"` and populate `known_nodes`.
- When `POST /display` arrives from `sender_ip`:
  1. Check if `sender_ip` is in `known_nodes`. If yes, use device ID.
  2. If not, trigger a discovery probe via CoAP broadcast. If sender replies, store and use device ID.
  3. If still unknown, use `sender_ip.split(".")[-1]` (last octet).
  4. Record on `app_state.last_caller` to render on OLED Line 4.

## Risks / Trade-offs

- **[Risk] Discovery probe latency on POST /display** → *Mitigation*: Run discovery asynchronously without blocking the CoAP `2.04 Changed` response back to the client.
- **[Risk] Button contact bounce** → *Mitigation*: Debounce button inputs in the polling coroutine (e.g., require stable LOW across consecutive samples).
