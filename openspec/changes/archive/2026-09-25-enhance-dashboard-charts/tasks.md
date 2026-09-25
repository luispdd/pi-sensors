## 1. Backend — Sensor Capability Registry

- [x] 1.1 Add `sensor_capabilities` table to `db.py` schema (`CREATE TABLE IF NOT EXISTS sensor_capabilities (device_id TEXT, metric_key TEXT, unit TEXT, PRIMARY KEY (device_id, metric_key))`) and verify `init_db()` creates the table on a fresh database
- [x] 1.2 Add `upsert_sensor_capability(device_id, metric_key, unit, db_path)` and `get_all_capabilities(db_path)` functions to `db.py` and verify they insert, update on conflict, and return the correct rows via unit test or manual sqlite3 check
- [x] 1.3 Add `probe_and_store_capabilities(node, db_path, coap_client)` helper in `poller.py` that calls `coap_client.get_sensors(ip)`, parses the SenML list, and calls `upsert_sensor_capability` for each entry; verify with an existing board that capability rows appear in SQLite after a manual call

## 2. Backend — Discovery and Sync Hooks

- [x] 2.1 In `PollerService.discover_and_register()`, after upserting each node, call `probe_and_store_capabilities` for nodes that expose a `/sensors` endpoint (catch exceptions, continue on failure); verify that running `/api/discover` populates `sensor_capabilities` rows
- [x] 2.2 In `PollerService.sync_logger()`, after a successful sync burst completes for a node, call `probe_and_store_capabilities`; verify that running `/api/sync` updates capability rows for the synced board

## 3. Backend — HTTP Endpoint

- [x] 3.1 Add `GET /api/capabilities` route to `api.py` that calls `db.get_all_capabilities()`, deduplicates by `metric_key` (first-seen unit wins), and returns a JSON array of `{"key": ..., "unit": ...}` objects; verify with `curl http://localhost:8000/api/capabilities` that it returns a valid JSON array
- [x] 3.2 Verify the endpoint returns an empty array when `sensor_capabilities` is empty (e.g. fresh database before any discovery)

## 4. Frontend — Capabilities Service

- [x] 4.1 Add `SensorCapability` interface (`key: string; unit: string`) and `getCapabilities(): HttpResourceRef<SensorCapability[]>` method to `ApiService` and `ReadingsQueryParams` model; verify the method compiles and returns the correct type
- [x] 4.2 Add a `CapabilitiesService` (or equivalent application-level singleton) that fetches `/api/capabilities` once on startup and exposes a reactive signal of the result; verify that after app init the capabilities are populated before any chart renders

## 5. Frontend — Dynamic Metric Selector

- [x] 5.1 Replace the hardcoded `METRIC_CONFIGS` / `AVAILABLE_METRICS` constants in `GraphsComponent` with values derived from the capabilities signal; include a display-unit mapping (`Cel` → `°C`, `%RH` → `%`) applied at render time so unknown units pass through as-is; verify that the metric pill buttons match the `/api/capabilities` response at runtime
- [x] 5.2 Apply the same dynamic metric source to the metric selector added to `HomeComponent`; verify the Home page metric selector reflects the live capabilities response

## 6. Frontend — Multi-Series Chart Logic

- [x] 6.1 Implement a `groupByDevice(readings, metricKey)` utility that returns a `Map<device_id, {x, y}[]>` and resolves metric key aliases (`temp` → `temperature`, `hum` → `humidity`, `light` → `light_pct`); verify with unit tests covering alias resolution and chronological ordering
- [x] 6.2 Update `GraphsComponent.chartSeries` computed signal to call `groupByDevice` and produce one ApexCharts series per board using the cyclic color palette defined in design.md D7; verify with two active boards that two distinct colored lines appear
- [x] 6.3 Update `HomeComponent.chartSeries` computed signal with the same multi-series logic; verify one line per board renders on the Home chart
- [x] 6.4 Configure both charts to display the ApexCharts legend at the bottom (`legend: { position: 'bottom' }`); verify the legend is visible beneath each chart

## 7. Frontend — Home Page Selectors

- [x] 7.1 Add a metric selector (pills or dropdown) to `HomeComponent` template positioned next to the count selector, bound to a `selectedMetric` signal; verify changing it re-renders the chart without resetting the count
- [x] 7.2 Add a count selector (`10 | 50 | 100 | 200 | All`) to `HomeComponent` template; make the `readingsResource` reactive on this signal (`All` omits the `limit` param); verify changing count re-renders the chart without resetting the metric

## 8. Frontend — Graphs Day-Range Selector

- [x] 8.1 Replace the "Points" limit selector in `GraphsComponent` template with a day-range dropdown (`Last 1d | 3d | 7d | 14d | 30d | All`); add `selectedDays` signal; remove `selectedLimit` signal and `AVAILABLE_LIMITS` constant; verify the dropdown renders correctly
- [x] 8.2 Update `GraphsComponent.readingsResource` params function to compute `since` from `selectedDays` (e.g. `new Date(Date.now() - days * 86400000).toISOString()`); `All` omits the `since` param; verify that selecting "Last 1d" returns only readings from the past 24 hours

## 9. Frontend — Per-Board Stats Table (Graphs)

- [x] 9.1 Add a `perBoardStats` computed signal in `GraphsComponent` that derives `{device_id, min, max, avg, latest}` per board from the grouped series data; verify the computed values are correct for two boards with known fixture data
- [x] 9.2 Replace the aggregate stat cards in `GraphsComponent` template with a statistics table (Board | Min | Max | Avg | Latest) rendered beneath the chart whenever readings are present for one or more boards; verify the table renders for single-board and multi-board selections

## 10. Validation

- [x] 10.1 Run `openspec validate --all --strict` and confirm zero errors
- [x] 10.2 Manually verify the full end-to-end flow with the live backend: discover boards → capabilities populated → frontend reflects dynamic metrics → multi-series chart renders with distinct colors and bottom legend → day-range and count selectors work independently → per-board stats table appears with multiple boards
