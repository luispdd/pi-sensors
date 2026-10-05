## Why

The controller only gets data through the 5-minute pull sync from the logger, so the dashboard cannot show near-live readings while testing. This change adds an on-demand, ephemeral live path so every board can report at a user-chosen rate. The existing sync is left untouched.

## What Changes

- Add a Mosquitto MQTT broker running on the controller device.
- Add a CoAP `/live` resource (`POST /live/start`, `POST /live/stop`) to every sensor-capable board. When live, a board connects to the broker as an MQTT client (`umqtt.simple`, installed via `mip` into each board's own `lib/`) and publishes its readings to `iotmesh/<device_id>/live` every `rate_ms`.
- Add controller endpoints `POST /api/live/start {rate_ms}`, `POST /api/live/stop` and `GET /api/live/status`. Start and stop are unicast CoAP requests sent to every currently discovered node, so any number of boards is supported. A repeated start with the same `rate_ms` is ignored by a node that is already live. A start with a different `rate_ms` makes it switch to the new rate.
- Add a controller MQTT subscriber on `iotmesh/+/live` that stores each message in `readings` with the node's own timestamp and `is_fine_tuned = 1`, using the existing `INSERT OR IGNORE` so a logger row with the same key wins.
- Add a controller WebSocket that pushes every new reading (live or regular sync) to dashboard clients.
- Add `is_fine_tuned` column to `readings` (default 0).
- Dashboard: global live monitoring widget embedded inside or below the toolbar on every page (Home, Nodes, Graphs), live status indicators, Graphs toggle between regular-only and all data, extended time-range options (10m, 1h, 3h, 6h, 1d, 3d, 7d, 14d, 30d, All), localStorage persistence for page filter selections, and live chart updates over WebSocket.

Non-goals: acks, auto-stop or duration limits, backlog/replay, retention policy, broker auth, broadcast CoAP messages, per-node start/stop.

## Capabilities

### New Capabilities
- `core/iotmesh/live-stream`: board-side `/live` CoAP resource and MQTT publishing behaviour, shared by all boards.

### Modified Capabilities
- `core/controller`: live start/stop/status API, MQTT subscriber ingestion, `is_fine_tuned` column, WebSocket push (added as new requirements).
- `frontend/dashboard`: live controls widget on all views, status indicator, graph filter toggle, extended time ranges, localStorage filter persistence, and WebSocket-driven updates (added and modified requirements).

## Impact

- `controller/backend`: `api.py`, `db.py`, `coap_client.py`, `main.py`, new MQTT subscriber and WebSocket modules. New dependency for the MQTT client (e.g. `aiomqtt`) in `pyproject.toml`.
- `boards/pico-2w`, `boards/pico-1w`, `boards/esp32c6`: `services/coap_server.py`, new live-publisher service, `lib/umqtt/` via `mip`. `lib/microcoapy` is not modified.
- `frontend/dashboard`: Nodes/Home controls, Graphs page, WebSocket client.
- System: Mosquitto must be installed and running on the controller host.
