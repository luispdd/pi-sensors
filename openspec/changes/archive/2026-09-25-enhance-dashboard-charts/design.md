## Context

See `proposal.md - Why` for motivation.

The backend stores readings in SQLite with a dynamic JSON `metrics` column. Readings may use aliased keys (e.g. `temp` alongside `temperature`) inherited from the CoAP log format. The CoAP `/sensors` endpoint returns SenML — `[{"n": "<key>", "v": <float>, "u": "<unit>"}]` — which is the authoritative source for sensor metadata.

The frontend currently hardcodes three metric types (`temperature`, `humidity`, `light`) and renders a single chart series regardless of how many boards contributed data.

## Goals / Non-Goals

**Goals**
- One chart series per board, rendered with a distinct color from a cyclic palette.
- Metric selectors driven by `/api/capabilities` rather than frontend constants.
- Home page: count-based reading constraint (N total | All); Graphs page: day-range constraint.
- Per-board stats table beneath the Graphs chart when multiple boards are visible.
- Legend at the bottom of both charts.

**Non-Goals**
- Per-board reading limits (e.g. "50 per board"). The count selector controls the total query.
- Board color preferences or user-configurable palettes.
- Real-time streaming; polling cadence is unchanged.

## Decisions

### D1 — Sensor capability registry in SQLite, not derived from readings

**Decision**: Store capabilities in a dedicated `sensor_capabilities` table populated by probing `/sensors` during discovery and sync, rather than introspecting `metrics` keys from stored readings.

**Rationale**: The SenML `/sensors` response is the authoritative source and includes unit information. Introspecting readings would require scanning potentially large datasets and still lacks unit data. The table approach is O(1) to query and is updated automatically whenever a board is discovered or synced.

**Alternative considered**: Deriving chartable metrics by scanning all distinct `metrics` keys across readings and cross-referencing a frontend lookup table. Rejected because it couples the frontend to a hardcoded registry and misses unit metadata for new sensor types.

### D2 — `/api/capabilities` returns deduplicated keys across all boards

**Decision**: The endpoint returns unique `{key, unit}` pairs across all registered boards. If two boards report the same metric key with different units (unlikely in practice), the first-seen unit wins.

**Rationale**: The metric selector is a per-metric UI control, not per-board. A deduplicated list keeps the selector simple and avoids showing duplicate metric buttons.

**Alternative considered**: Returning per-board capabilities as a nested map. Rejected as unnecessary for the current use case.

### D3 — Frontend fetches capabilities once on startup, no periodic refresh

**Decision**: The capability list is fetched once when the application initialises and cached for the session lifetime.

**Rationale**: Sensor types change only when new hardware is added — a rare, deliberate event. A full page refresh (or app restart) is an acceptable trigger for picking up new sensor types. Periodic polling would add unnecessary network overhead.

### D4 — Multi-series grouping performed client-side

**Decision**: The API returns all readings for the requested time range; the frontend groups them by `device_id` to build one series per board.

**Rationale**: The backend does not need to know about chart rendering. Grouping is a cheap in-memory operation given the number of boards and data points involved. Adding a server-side grouping endpoint would introduce unnecessary coupling.

### D5 — Day-range selector replaces the Points selector on Graphs page

**Decision**: A "Last X days" dropdown (1d | 3d | 7d | 14d | 30d | All) drives the `since` query parameter. The previous count-based limit selector is removed from the Graphs view.

**Rationale**: Time-range semantics are more meaningful for time-series analysis. The Home page retains the count-based selector because its use case is a quick snapshot, not deep historical analysis. Keeping the count limit on Graphs alongside a day selector would create confusing interactions.

**Alternative considered**: Offering both selectors simultaneously on Graphs with documented precedence rules. Rejected for UI simplicity.

### D6 — Statistics table beneath chart replaces card widgets

**Decision**: The four aggregate stat cards above the chart are removed. Instead, a statistics table (Board | Min | Max | Avg | Latest) is always positioned beneath the chart whenever readings are present, providing consistent per-board analysis for single-board as well as multi-board views.

**Rationale**: Displaying statistics in a structured table directly beneath the chart keeps the layout clean, avoids redundant card widgets, and provides uniform presentation across single-node and multi-node selections.

### D7 — 10-color unified palette with deterministic assignment

**Decision**: A fixed 10-color palette is shared between board rendering (`BOARD_PALETTE`) and metric categorization (`METRIC_PALETTE`). Metrics are assigned colors alphabetically by metric key in `CapabilitiesService` so that colors remain identical across page refreshes. Boards are assigned colors cyclically by device index in `chartSeries`.

Palette (hex):
`#2DD4BF`, `#38BDF8`, `#FBBF24`, `#A78BFA`, `#F472B6`, `#34D399`, `#FB923C`, `#818CF8`, `#E879F9`, `#4ADE80`

**Rationale**: Shared palette maintains visual harmony across the dashboard. Alphabetical sorting ensures determinism for arbitrary unknown metric keys discovered at runtime without needing persistent client-side configuration.

### D8 — SenML key used as-is as the canonical `metric_key`

**Decision**: The `n` field from the SenML `/sensors` response is stored directly as `metric_key` in `sensor_capabilities` and used to look up values in the readings `metrics` JSON.

**Implication**: Existing readings that stored aliased keys (e.g. `temp` instead of `temperature`) will not match a capability entry of `temperature`. The reading extraction logic must check both the SenML canonical key and known aliases. A small alias map (e.g. `temp` → `temperature`, `hum` → `humidity`) covers the current boards without requiring schema changes.

### D9 — CoAP log packet sizing and adaptive fallback

**Decision**: The default log pagination size is set to 5 records (`LOG_PAGE_SIZE = 5`). In addition, `CoapClient.get_log()` includes adaptive back-off: if an empty payload (`b''`) is received with response code `2.05 Content`, it automatically retries with half the page size (`size = max(1, size // 2)`).

**Rationale**: Constrained microcontrollers (such as the Raspberry Pi Pico W) use lightweight UDP buffers of ~1024 bytes. Batches of 10 readings exceed this limit, causing the node to send 0-byte datagrams and stalling synchronization. A default of 5 records (~530 bytes) fits comfortably in a single UDP packet, and adaptive fallback prevents deadlocks if individual records expand.

### D10 — Sync status reporting and dashboard fidelity

**Decision**: The poller classifies overall sync failure into `STATUS_OFFLINE` only when loggers are unreachable (connection timeout or network unreachable), and `STATUS_ERROR` when nodes responded but encountered execution errors. The dashboard UI directly preserves and displays `OK`, `ERROR`, `PARTIAL`, `IDLE`, and `OFFLINE` instead of converting errors into offline.

**Rationale**: Operators must be able to distinguish between boards that are physically disconnected or powered down versus boards that are online and responding to discovery pings but failing on synchronization operations.

### D11 — Unbounded historical readings queries

**Decision**: In `controller/backend/api.py`, omitting the `limit` query parameter passes `limit=None` to `db.query_readings()`, returning all matching records without an arbitrary default 100-record limit or 1000-record clamp.

**Rationale**: The Graphs view filters by time range (`since`), and the Home page offers an explicit "All" option. Imposing a default limit of 100 artificially truncated multi-board series to 50 records per board and rendered time-range selectors on Graphs ineffective.

## Risks / Trade-offs

- **Alias drift** → If boards change the key name they log in `/log` without changing the `/sensors` response, metric values will silently stop appearing. Mitigation: document the alias map; validate by comparing a live `/sensors` response against stored readings keys during board setup.
- **`/sensors` called during sync** → Adds one extra CoAP round-trip per board per sync cycle. Mitigation: the request is made only after a successful log sync completes; failure is non-fatal.
- **Large "All" queries** → Selecting "All" time range on Graphs with many months of data could return a large payload. No server-side guard is applied; the user is expected to understand the trade-off.

## Migration Plan

1. Deploy backend with schema migration (`ALTER TABLE` or `CREATE TABLE IF NOT EXISTS sensor_capabilities`).
2. Trigger a manual `/api/discover` call post-deploy to populate `sensor_capabilities` for existing boards.
3. Deploy frontend — metric selectors will populate from the API on first load. No user action required.
4. Rollback: reverting the frontend to the previous build restores hardcoded metrics. Reverting the backend drops the route; the table can remain without side effects.

## Open Questions

None.
