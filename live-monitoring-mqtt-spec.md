# Live Monitoring via MQTT — Change Spec

Adds an **on-demand, ephemeral** live-data path alongside the existing
5-minute logger→controller sync, which is left completely unchanged.
No backlog, no cursor, no history replay on this new path — forward-only
while active, nothing persisted about "where it left off."

## What stays exactly as-is

- Logger's 60-min buffer → SD write cadence: unchanged.
- Controller's existing pull-based sync from the logger (`GET /log?cursor=`
  or current equivalent): unchanged, keeps running independently.
- Node discovery (CoAP broadcast/multicast `.well-known/core`): unchanged,
  reused as-is to resolve a node's current IP before sending it a live
  command.

## New: MQTT broker

Mosquitto, runs on the same device as the controller. Not discovered by
nodes — its address is passed to a node directly in the `/live/start`
request body (see below), so no `rt="mqtt-broker"` advertisement or
broker-discovery logic is needed anywhere.

## New CoAP resource on every sensor-capable node (not just the logger)

Add to core resource-types (`rt=`) vocabulary:

| `rt=` | path | `if=` | notes |
|---|---|---|---|
| `live-stream` | `/live` | `actuator` | controller-triggered; node publishes its own readings to MQTT while active |

### `POST /live/start` — unicast, per node
Body (JSON): `{"broker": "<controller_ip>:<port>", "rate_ms": <n>}`
Node connects to the given broker as an MQTT client and publishes its
readings to `iotmesh/<device_id>/live` at the requested interval until
stopped or disconnected. No ack/response tracking needed beyond normal
CoAP.

### `POST /live/stop` — broadcast, non-confirmable, sent to **all** nodes
No body. Every node that isn't currently live simply no-ops. This is the
only stop mechanism — no per-node targeted stop, no confirmation
required, no max-duration/auto-stop safety (explicitly not needed).

## Controller: new HTTP API endpoints

| Method | Path | Behavior |
|---|---|---|
| POST | `/api/live/start` | Body `{device_id, rate_ms}`. Resolve node IP from existing node-discovery cache, send it CoAP `POST /live/start` with this controller's own broker address. Record `{device_id, rate_ms, started_at}` in local `live_subscriptions` state (for status display only — not used for resume logic). |
| POST | `/api/live/stop` | Send CoAP broadcast `POST /live/stop`. Clear all entries from `live_subscriptions` regardless of per-node delivery confirmation. |
| GET | `/api/live/status` | Return current `live_subscriptions` contents (controller's own record, not queried from nodes). |

No auto-start on controller boot — live mode is only ever initiated from
the web UI, never automatically.

## Controller: MQTT subscriber → DB → WebSocket

- Subscribe to `iotmesh/+/live`. Every message → insert into the existing
  readings table exactly like a regular sync insert, same idempotent
  `(timestamp, device_id)` constraint, **plus** `is_fine_tuned = true`.
- **Every insert, from either path** (regular 5-min sync *and* live MQTT),
  triggers a push over the controller's WebSocket to connected clients:
  `{device_id, timestamp, metrics, is_fine_tuned}`. Regular syncs get this
  too — no reason to scope it to live-only.

## Database

Add one column to the readings table:

```sql
ALTER TABLE readings ADD COLUMN is_fine_tuned BOOLEAN NOT NULL DEFAULT 0;
```

Regular logger-synced rows: `is_fine_tuned = 0` (unchanged default).
Live MQTT rows: `is_fine_tuned = 1`.

## Frontend

- Per-node control (Nodes page / node detail): rate input + start button →
  `POST /api/live/start`. Global "stop live" button (Home or Nodes page) →
  `POST /api/live/stop`.
- Live status indicator per node, sourced from `GET /api/live/status`.
- Graphs page: toggle to filter `is_fine_tuned = false` only ("regular")
  vs. no filter ("fine-tuned" / all data), same chart either way.
- WebSocket client: append incoming points to whichever chart is currently
  showing that `device_id`/metric, instead of polling. Browser does not
  need to stay open for data to keep being stored — this only affects
  what's shown live while a tab is open.

## Open / left to implementer's discretion

- MQTT QoS for the `live` topic: not specified here; QoS 0 is a reasonable
  default given there's no backlog/replay to protect (a dropped live
  sample is simply not shown — the regular 5-min sync still captures the
  underlying reading independently).
