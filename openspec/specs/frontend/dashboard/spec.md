# Frontend Dashboard Specification

## Purpose

Provides a framework-agnostic user interface to visualize IoT mesh data, monitor node status, and perform basic operations like messaging capable nodes.

## Requirements

### Requirement: Global Layout Navigation
The dashboard MUST provide a consistent global layout with a fixed icon rail for navigating between primary views (Home, Nodes, Graphs) and a main content area.

#### Scenario: Navigate to Nodes view
- **WHEN** the user selects the "Nodes" icon from the rail
- **THEN** the main content area updates to display the Nodes data grid

### Requirement: Home Dashboard Summary
The Home view MUST present summary metrics including online node count, total records, sync status, and sync interval, along with a top-level multi-series chart of recent sensor activity. The chart MUST provide two independent selectors: a metric selector (dynamically populated from the capabilities API) and a count selector (10 | 50 | 100 | 200 | All). Changing one selector MUST NOT reset the other. Each discovered board MUST be rendered as a separate series with a distinct color and a legend displayed at the bottom of the chart.

#### Scenario: View system metrics
- **WHEN** the user opens the Home page
- **THEN** the system displays aggregated metrics calculated from the underlying backend status and nodes data. The sync status card MUST display the exact poller result (`OK`, `ERROR`, `PARTIAL`, `IDLE`, `OFFLINE`) without masking error states as offline

#### Scenario: Select metric on Home chart
- **WHEN** the user selects a metric from the metric selector on the Home page
- **THEN** the chart re-renders displaying that metric's values, one series per board, while the count selector retains its current value

#### Scenario: Select reading count on Home chart
- **WHEN** the user selects a count value (10 | 50 | 100 | 200 | All) from the count selector on the Home page
- **THEN** the chart re-renders using the selected total number of readings. When "All" is chosen, the frontend MUST omit the `limit` parameter to retrieve all stored readings from the backend without truncation, while the metric selector retains its current value

#### Scenario: Multiple boards visible on Home chart
- **WHEN** readings from more than one board are present
- **THEN** each board MUST appear as an independent, distinctly colored series with a bottom legend identifying each board by its device ID

### Requirement: Nodes Data Grid
The Nodes view MUST provide a sortable and filterable data grid listing all discovered nodes, displaying their IDs, types, capabilities, IP addresses and a derived online/offline status.

#### Scenario: Node goes offline
- **WHEN** a node's `last_seen` timestamp exceeds the defined threshold
- **THEN** its status in the grid is visually represented as "Offline"

### Requirement: Interactive Time-Series Graphs
The Graphs view MUST provide interactive time-series charts allowing the user to select specific nodes, metrics, and a time range. Metrics MUST be populated dynamically from the capabilities API. A day-range selector (Last 1d | 3d | 7d | 14d | 30d | All) MUST replace the previous count-based limit selector and constrain the chart to readings within the selected window; All means no time constraint. When All Nodes is selected, each board MUST be rendered as a separate series with a distinct color. A statistics table (Board | Min | Max | Avg | Latest) MUST appear beneath the chart whenever one or more boards contribute data, replacing the previous card-based widgets. A legend MUST be displayed at the bottom of the chart.

#### Scenario: View metric history for a specific node
- **WHEN** the user selects a single node and a metric in the Graphs view
- **THEN** the chart visualizes that metric's readings over the selected time range as a single series

#### Scenario: View all boards simultaneously
- **WHEN** the user selects All Nodes in the Graphs view
- **THEN** the chart renders one distinctly colored series per board for the selected metric, along with a legend at the bottom

#### Scenario: Select day range
- **WHEN** the user selects a day-range option (e.g. Last 7d)
- **THEN** the chart fetches readings with a `since` parameter set to the start of that window, omitting `limit` so that all readings within the window are displayed, and re-renders accordingly

#### Scenario: Select All time range
- **WHEN** the user selects All from the day-range selector
- **THEN** the chart fetches all stored readings without a time constraint or count limit and renders them

#### Scenario: Statistics table visible beneath chart
- **WHEN** one or more boards contribute readings to the current chart view
- **THEN** a table is displayed beneath the chart with one row per board showing Min, Max, Avg, and Latest values for the selected metric, replacing the card-based widgets

### Requirement: Send Node Messages
The dashboard MUST provide an action dialog allowing the user to send plain text messages to display-capable nodes.

#### Scenario: Send display message
- **WHEN** the user opens the message dialog for an online display node, enters text, and submits
- **THEN** the system triggers the backend display API to proxy the message to the target node

### Requirement: Reactive API Communication
The frontend MUST communicate with backend endpoints using reactive resource/query primitives, providing reactive state (`value`, `isLoading`, `error`, `reload`) for read queries while supporting action dispatching for mutations. The frontend MUST also fetch `GET /api/capabilities` once on application startup and cache the result for the lifetime of the session to drive metric selectors.

#### Scenario: Reactive query data binding
- **WHEN** a view requests data (such as `/api/nodes`, `/api/status`, or `/api/readings`)
- **THEN** a reactive resource reference is provided exposing reactive state that automatically re-fetches when query inputs change and tracks loading and error states

#### Scenario: Capabilities loaded on startup
- **WHEN** the application initialises
- **THEN** the frontend MUST request `GET /api/capabilities`, cache the response, and use it to populate the metric selector in both the Home and Graphs views without issuing further capability requests during the session
