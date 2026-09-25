## Why

The dashboard currently displays all sensor data as a single aggregated time-series line, making it impossible to visually distinguish readings from different boards. Metric selectors are also hardcoded, requiring a frontend code change each time a new sensor type is added to any board.

## What Changes

- **Multi-series charts (Home & Graphs)**: Each board's readings are rendered as an independent series with a distinct color; charts that previously collapsed all data into one line now show one line per board.
- **Dynamic metric discovery**: A new `/api/capabilities` endpoint aggregates chartable sensor types (name + unit) from all known boards by probing their CoAP `/sensors` endpoint. The frontend fetches this once on startup to populate metric selectors dynamically instead of using hardcoded constants.
- **Backend sensor capability registry**: A new `sensor_capabilities` SQLite table stores per-board sensor metadata (`device_id`, `metric_key`, `unit`) populated during discovery and sync cycles.
- **Home page selectors**: Two new independent controls — a metric selector (populated from `/api/capabilities`) and a count selector (10 | 50 | 100 | 200 | All) — constrain the Home chart without coupling to each other.
- **Graphs day-range selector**: The existing "Points" limit selector is replaced by a day-range selector (Last 1d | 3d | 7d | 14d | 30d | All), mapping to `since` / `until` API query params.
- **Per-board stats table (Graphs)**: When multiple boards are visible, the four aggregate stat cards are replaced by a table with one row per board (Board | Min | Max | Avg | Latest), located beneath the chart.
- **Chart legend at bottom**: Both the Home and Graphs charts display a series legend at the bottom, identifying each board's color.

## Capabilities

### New Capabilities

- `core/sensor-capabilities`: Backend sensor capability registry — SQLite table, population logic, and the `GET /api/capabilities` HTTP endpoint.

### Modified Capabilities

- `frontend/dashboard`: Changes to the Home Dashboard Summary (metric + count selectors, multi-series chart), Interactive Time-Series Graphs (day-range selector, multi-series chart, per-board stats table, legend), and Reactive API Communication (new capability query on startup).
- `core/controller`: New HTTP endpoint `GET /api/capabilities` added to the management API surface.

## Impact

- **Backend**: New SQLite table (`sensor_capabilities`), new DB helper functions, discovery and sync hooks to call `/sensors` and persist capabilities, new aiohttp route `/api/capabilities`.
- **Frontend**: `ApiService` gains a `getCapabilities()` method. Metric constants and hardcoded `METRIC_CONFIGS` are replaced by dynamic values derived from the capabilities response. `GraphsComponent` and `HomeComponent` gain new selectors and multi-series chart logic. `HomeComponent` readings resource becomes reactive on the selected count.
- **Data contract**: New response shape for `/api/capabilities`; SenML fields (`n`, `u`) from boards drive the registry.
- **No board firmware changes required**: capability metadata is already available via the existing `/sensors` CoAP endpoint.
