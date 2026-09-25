## Why

The backend controller currently exposes APIs for status, nodes, readings, synchronization, and display, but lacks a user interface. This change adds a frontend dashboard to visualize IoT mesh data, manage nodes, and view system status.

## What Changes

- Create a new framework-agnostic component-based Single Page Application (SPA).
- Implement a global layout with a fixed icon rail and main content area.
- Add a Home (`/`) page with summary metric cards, a primary chart, and a top nodes list.
- Add a Nodes (`/nodes`) page with a data grid of all nodes and derived online/offline statuses.
- Add a Graphs (`/graphs`) page with an interactive time-series chart and data controls.
- Add an action dialog to send plain text messages to display-capable nodes.
- Exclude Alerts and Editable Settings for the initial implementation.

## Capabilities

### New Capabilities
- `frontend/dashboard`: The dashboard user interface consuming existing backend APIs.

### Modified Capabilities

## Impact

- Adds a new frontend application folder/project.
- Will consume the existing `controller/backend/api.py` endpoints without requiring backend modifications.
