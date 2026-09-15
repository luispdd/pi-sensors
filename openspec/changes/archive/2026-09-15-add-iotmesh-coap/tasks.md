## 1. Setup and Dependencies

- [x] 1.1 Add `microCoAPy` to `src/lib/` and verify it can be imported successfully via the REPL.

## 2. Core State Updates

- [x] 2.1 Update `AppState` in `src/state.py` to include `display_override_text` and `display_override_expires_at` and verify attributes can be set.
- [x] 2.2 Update `display.py` to check `AppState` for active overrides before rendering sensor data and verify the screen displays text correctly when an override is active.

## 3. CoAP Endpoints

- [x] 3.1 Implement CoAP `GET /id` returning node identity and verify using a CoAP client.
- [x] 3.2 Implement CoAP `GET` for individual sensors (`/sensors/temperature`, `/sensors/humidity`, `/sensors/light`) returning SenML and verify outputs using a CoAP client.
- [x] 3.3 Implement CoAP `GET /sensors` returning a SenML Pack array of all sensors and verify outputs using a CoAP client.
- [x] 3.4 Implement CoAP `POST /display` to set the override state and reset the 60-second timer, and verify the display updates when the endpoint is hit.

## 4. Discovery and Network

- [x] 4.1 Implement `GET /.well-known/core` returning the CoRE Link Format string and verify response format.
- [x] 4.2 Integrate the CoAP server loop into `main.py`, binding UDP port 5683, and verify it coexists with the HTTP server without blocking.
