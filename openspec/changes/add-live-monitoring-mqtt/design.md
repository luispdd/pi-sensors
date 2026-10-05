## Context

See proposal.md for motivation. The controller (aiohttp, SQLite) pulls logs from loggers over CoAP every 5 minutes and discovers nodes via CoAP `.well-known/core`. `readings` already has `UNIQUE(timestamp, device_id)` and `insert_readings` uses `INSERT OR IGNORE`. Boards (pico-2w, pico-1w, esp32c6) each have their own `services/coap_server.py` and `lib/`, and share no code. The live path is additive and must not change the sync.

## Goals / Non-Goals

**Goals:**
- Work with any number of boards by iterating the discovery cache. No board list is hardcoded.
- Keep the node-side code small and the same on every board.

**Non-Goals:**
- Delivery guarantees, backlog, retention, auth, auto-stop, broadcast CoAP, per-node control.

## Decisions

- **Unicast CoAP start/stop to each discovered node, one API pair for all nodes.** Alternative: broadcast stop and per-node start. Rejected, since one code path is simpler and discovery already gives IPs. Late-joining nodes are covered by pressing Start again, which is idempotent on nodes already live at the same rate.
- **Node is the MQTT client, controller hosts Mosquitto.** The broker address travels in the start body, so no broker discovery is needed. Alternative: controller polls over CoAP. Rejected because it needs a new request per sample per node and does not scale with the number of boards.
- **`umqtt.simple` installed with `mip` into each board's own `lib/`.** Boards keep independent trees. `lib/microcoapy` is not touched. The publisher runs as a small asyncio task in each board's services and uses the non-blocking approach already used by the other services. `umqtt.simple` is blocking on connect and publish, so calls are short and failures are caught and dropped.
- **Node timestamps only.** Live payload is `{timestamp, metrics}` using the same metric keys as the regular readings. The board maintains and advances its internal timestamp in its internal execution loop (incrementing the timestamp on each loop execution by the elapsed interval, e.g. adding 1 second every 1-second loop tick), anchored by periodic background NTP synchronization (e.g. 5 minutes) rather than performing ad-hoc timestamp fetches on every sensor read or live publication. The controller never substitutes arrival time.
- **Reuse `INSERT OR IGNORE`.** The logger row wins when it was inserted first. In the rare reverse order, the live row is kept with `is_fine_tuned = 1`, which is acceptable for a POC.
- **`is_fine_tuned` column with idempotent migration.** At `init_db`, check `PRAGMA table_info(readings)` and run `ALTER TABLE ... ADD COLUMN is_fine_tuned BOOLEAN NOT NULL DEFAULT 0` only if missing.
- **Controller MQTT subscriber as an asyncio task in the controller process** (library such as `aiomqtt`), QoS 0. Messages go through the existing insert function, then a shared "reading inserted" hook that pushes to WebSocket clients. The same hook is called by the regular sync, so both paths push.
- **WebSocket on the existing aiohttp app**, holding a set of connected clients, broadcasting JSON, and removing closed sockets.
- **Live status is the controller's own in-memory record.** It is cleared on stop and lost on controller restart. A node that fails the stop request is reported in the response.
- **Global Live Monitoring Controls Component.** Rather than restricting live controls to the Nodes view, an independent reusable component (`LiveControlsComponent`) is placed in or directly beneath the top toolbar on all primary routes (Home, Nodes, Graphs). It interacts with the singleton `ApiService` live methods and preserves active monitoring state across navigation.
- **Extended Time-Series Ranges.** The Graphs view supports sub-day range periods (10m, 1h, 3h, 6h) in addition to multi-day periods (1d, 3d, 7d, 14d, 30d, All). A helper dynamically computes the ISO `since` timestamp based on `Date.now() - durationMs`, allowing high-frequency live data to be visualized with high resolution.
- **Browser LocalStorage Filter Persistence.** User selections on the Graphs view (selected node ID, selected metric, time range, and regular-only toggle) and Home view (selected metric and count limit) are persisted to `localStorage` under distinct keys (`pi-sensors:graphs-filter`, `pi-sensors:home-filter`) and restored when components initialize.

## Risks / Trade-offs

- [A node misses the stop request and keeps publishing] → Accepted for the POC. The subscriber still stores its data, and pressing Stop again retries all nodes.
- [Controller restart loses live status while nodes keep publishing] → Accepted. Data is still ingested, and Stop reaches all discovered nodes.
- [Node clock not yet synced produces wrong timestamps] → Accepted by decision. Nodes use their own timestamps.
- [Blocking MQTT calls on constrained boards] → Keep payloads tiny, catch all errors, and drop the sample on failure.
- [Unauthenticated LAN broker] → Accepted for a short-lived test setup.
- [Table growth at high rates] → No retention. Short test runs only.

## Migration Plan

1. Install Mosquitto on the controller host and add the controller MQTT dependency.
2. Start the controller once so the column migration runs. Existing rows default to 0.
3. Run `mip` to install `umqtt.simple` into each board's `lib/`, then deploy the updated board firmware.

Rollback: stop live mode. The extra column is harmless and the sync path is unchanged.
