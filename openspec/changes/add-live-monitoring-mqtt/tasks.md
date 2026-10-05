## 1. Controller database and ingestion

- [x] 1.1 Add idempotent `is_fine_tuned` migration in `controller/backend/db.py`, with `insert_readings` accepting the flag and returning only newly inserted rows. Verify with `test_db.py` cases for fresh DB, old DB upgrade and duplicate ignore.
- [x] 1.2 Add `is_fine_tuned` filter and output field to the readings query and `GET /api/readings`. Verify with `test_api.py` cases for `false` and omitted.
- [x] 1.3 Add WebSocket endpoint and client registry in the controller, with a broadcast hook called for every newly inserted row. Verify with a test that a connected client receives the pushed payload.
- [x] 1.4 Call the broadcast hook from the regular sync insert path. Verify with `test_poller.py` that new sync rows are pushed and duplicates are not.

## 2. Controller MQTT subscriber and live API

- [x] 2.1 Add the MQTT client dependency to `controller/pyproject.toml` and a subscriber task for `iotmesh/+/live` that parses messages and inserts with `is_fine_tuned = 1`. Verify with unit tests for valid, malformed and duplicate messages.
- [x] 2.2 Start the subscriber from `controller/backend/main.py` alongside the existing tasks. Verify manually with `mosquitto_pub` that a row appears and the WebSocket receives it.
- [x] 2.3 Add live start and stop methods to `coap_client.py` that send `POST /live/start` and `POST /live/stop` to a node. Verify with `test_coap_client.py`.
- [x] 2.4 Add `POST /api/live/start`, `POST /api/live/stop` and `GET /api/live/status` that loop over discovered nodes and keep in-memory live state. Verify with `test_api.py` for validation, per-node failure handling, repeated start and stop clearing state.

## 3. Boards (pico-2w, pico-1w, esp32c6)

- [x] 3.1 Install `umqtt.simple` via `mip` into each board's `lib/` and document the command in each board README. Verify the module imports on each board.
- [x] 3.2 Implement the live publisher service per board: start, same-rate ignore, rate switch, stop, error handling and no persistence. Verify with unit tests in each `boards/<board>/test` using a fake MQTT client.
- [x] 3.3 Add the `/live` resource to each board's CoAP server and `.well-known/core` with `rt="live-stream";if="actuator"`, and handle `POST /live/start` and `/live/stop` with the specified responses. Verify with each board's CoAP endpoint tests, including bad body and well-known links.
- [x] 3.4 Run `python3 -m unittest discover -s boards/<board>/test` for all three boards and confirm they pass.

## 4. Dashboard

- [x] 4.1 Add rate input with validation and Start/Stop live buttons wired to the new API. Verify in the browser that requests are sent with the right payload.
- [x] 4.2 Add per-node live status indicator from `GET /api/live/status`. Verify the indicator changes after Start and Stop and persists when navigating across pages.
- [x] 4.3 Add the Graphs toggle between regular-only and all data. Verify the chart request uses `is_fine_tuned=false` only in regular mode.
- [x] 4.4 Add the WebSocket client that appends matching readings to the displayed chart. Verify live points appear without polling and that non-matching or filtered readings are ignored.


## 5. Integration

- [x] 5.1 The Mosquitto server is already running on the controller host, so, verify the controller's ability to discover at least two boards, and when starting live mode, verify live points on the chart, `is_fine_tuned = 1` rows in the DB, and that Stop halts the data.
- [x] 5.2 Run `openspec validate --all` and confirm it passes.

## 6. Polling cadence and live telemetry refresh

- [x] 6.1 Fix `/nodes` page excessive polling: eliminate redundant duplicate calls to `/api/status` on page load and ensure status is refreshed automatically only every 5 minutes when live monitoring is inactive, like the other pages.
- [x] 6.2 Ensure graphs and dashboard telemetry views update automatically via WebSockets whenever new live MQTT data arrives at the controller and is stored in the database, verifying end-to-end real-time telemetry propagation to the UI without manual refresh.
- [x] 6.3 Fix Sync Status widget remaining stuck on `OFFLINE Last: Never`: ensure controller poller status and last sync time reflect periodic sync runs after the 5-minute interval, even when nodes were offline during frontend/backend startup.
- [x] 6.4 Fix root service lifecycles across page navigation: decouple `WebSocketService` from component-scoped `DestroyRef` and attach singleton `httpResource` instances (`sharedStatusResource`, `sharedLiveStatusResource`) to the root `EnvironmentInjector` so WebSockets and live monitoring status are not permanently destroyed upon navigating between pages.
- [x] 6.5 Fix Home page sync status displaying `OFFLINE` and sync interval displaying `—` upon page navigation and during active live monitoring, ensuring live indicator remains active when returning to the `/nodes` page.

## 7. Global toolbar live controls, extended time ranges, and local storage filter persistence

- [x] 7.1 Refactor Live Monitoring widget into an independent reusable component (`LiveControlsComponent`) and embed it inside or directly below the top toolbar on all primary pages (`Home`, `Nodes`, `Graphs`), ensuring live status and controls are globally accessible.
- [x] 7.2 Expand Graphs view time-range selector with sub-day options (10m, 1h, 3h, 6h, 1d, 3d, 7d, 14d, 30d, All) and update query generation to compute accurate ISO `since` timestamps for minute and hour offsets.
- [x] 7.3 Implement browser localStorage persistence for page filters: persist and restore selected device, metric, time range, and regular-only toggle on the Graphs page, and persist/restore selected metric and reading count on the Home page.

## 8. Live stream measurement timestamps, WebSocket propagation, and single-request lifecycle

- [x] 8.1 Clarify and verify board internal timestamp lifecycle: ensure requirements reflect that boards actively advance their internal timestamp via their internal execution loop (incrementing by the elapsed interval on each loop execution, e.g. adding 1 second each 1-second tick) with periodic NTP synchronization (e.g. 5 minutes) rather than calling ad-hoc timestamp fetches on every sensor read or live publish iteration, and verify that `live_publisher.py` across all 3 boards (`pico-2w`, `pico-1w`, `esp32c6`) uses the board's internal timestamp from `app_state`.
- [x] 8.2 Fix status and live status request lifecycle: ensure `/api/status` request is performed on page load and on every Sync Interval refresh, beside when the Refresh button is clicked, and ensure `ApiService` shares a single singleton `httpResource` without redundant calls.
- [x] 8.3 Fix reactive live status tracking in `ApiService`: ensure `liveStatusResourceRef` is properly linked to the shared resource signal so `isLiveActive` and `activeLiveRateMs` correctly track live status and prevent `LiveControlsComponent` from prematurely disconnecting the WebSocket.
- [x] 8.4 Provide chronologically sorted telemetry from backend and maintain chronological ordering in frontend: ensure controller query_readings and GET /api/readings always return readings sorted chronologically ascending by board timestamp (retrieving latest N in chronological order when limit is passed), and verify that HomeComponent and GraphsComponent maintain chronological ordering for merged live telemetry.
- [x] 8.5 End-to-end verification of live monitoring: start live monitoring at 5s, verify boards publish distinct timestamps, controller ingests and pushes them via WebSocket, and the frontend updates the live charts without manual refresh.
