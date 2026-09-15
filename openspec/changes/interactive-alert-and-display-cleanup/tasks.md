## 1. Hardware Configuration & Sensor Deprecation

- [x] 1.1 Update `src/config.py` to remove LM393 definitions, add `PIN_BUTTON = 14` and `PIN_LED_ALERT = 16`, and verify configuration imports without errors.
- [x] 1.2 Update `src/sensors.py` to remove LM393 reading and light status logic from `SensorReader`, and verify DHT22 readings continue to operate.

## 2. State & Display Updates

- [x] 2.1 Update `AppState` in `src/state.py` to remove light attributes and add `alert_active`, `alert_message`, `last_caller`, and `known_nodes` cache, and verify state setter/clearer methods.
- [x] 2.2 Update `src/display.py` to remove old lines 1–3, render the IP without `http://`, display `/info`, and render `Last: <caller>` on the bottom line. Verify formatting with display unit test.

## 3. Alert Hardware Controls & Button Integration

- [x] 3.1 Implement button monitoring task on GP14 and alert LED output on GP16 in `src/main.py`, verifying that pressing the button clears active alerts and extinguishes the LED.

## 4. CoAP & HTTP Endpoints

- [x] 4.1 Update `src/coap_server.py` to remove `GET /sensors/light`, exclude `rt="light"` from discovery and collection, and implement caller resolution via node cache and discovery probe. Verify with CoAP test suite.
- [x] 4.2 Update `src/webserver.py` to expose `GET /info` responding with updated environmental telemetry. Verify with HTTP query.
