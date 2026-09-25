## Purpose
Provides a framework-agnostic user interface to visualize IoT mesh data, monitor node status, and perform basic operations like messaging capable nodes.

## ADDED Requirements

### Requirement: Global Layout Navigation
The dashboard MUST provide a consistent global layout with a fixed icon rail for navigating between primary views (Home, Nodes, Graphs) and a main content area.

#### Scenario: Navigate to Nodes view
- **WHEN** the user selects the "Nodes" icon from the rail
- **THEN** the main content area updates to display the Nodes data grid

### Requirement: Home Dashboard Summary
The Home view MUST present summary metrics including online node count, total records today, sync error count, and sync interval, along with a top-level chart of recent activity.

#### Scenario: View system metrics
- **WHEN** the user opens the Home page
- **THEN** the system displays aggregated metrics calculated from the underlying backend status and nodes data

### Requirement: Nodes Data Grid
The Nodes view MUST provide a sortable and filterable data grid listing all discovered nodes, displaying their IDs, types, capabilities, IP addresses and a derived online/offline status.

#### Scenario: Node goes offline
- **WHEN** a node's `last_seen` timestamp exceeds the defined threshold
- **THEN** its status in the grid is visually represented as "Offline"

### Requirement: Interactive Time-Series Graphs
The Graphs view MUST provide interactive time-series charts allowing the user to select specific nodes and metrics, and pan/zoom across historical data.

#### Scenario: View temperature history for a specific node
- **WHEN** the user selects a node and the "temperature" metric in the Graphs view
- **THEN** the chart visualizes the temperature readings over the selected time range

### Requirement: Send Node Messages
The dashboard MUST provide an action dialog allowing the user to send plain text messages to display-capable nodes.

#### Scenario: Send display message
- **WHEN** the user opens the message dialog for an online display node, enters text, and submits
- **THEN** the system triggers the backend display API to proxy the message to the target node

### Requirement: Reactive API Communication
The frontend MUST communicate with backend endpoints using reactive resource/query primitives, providing reactive state (`value`, `isLoading`, `error`, `reload`) for read queries while supporting action dispatching for mutations.

#### Scenario: Reactive query data binding
- **WHEN** a view requests data (such as `/api/nodes`, `/api/status`, or `/api/readings`)
- **THEN** a reactive resource reference is provided exposing reactive state that automatically re-fetches when query inputs change and tracks loading and error states
