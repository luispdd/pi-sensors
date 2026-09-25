## 1. Project Setup

- [x] 1.1 Scaffold a new Angular standalone application named `dashboard` within a new `frontend/` directory and verify `ng build` completes successfully.
- [x] 1.2 Install Angular Material, `ng-apexcharts`, and `apexcharts` dependencies and verify they are present in `package.json`.
- [x] 1.3 Setup global CSS variables (tokens) in `styles.css` matching the design color palette (e.g., `--bg-page`, `--accent`) and verify they apply correctly to a test element.

## 2. API Integration

- [x] 2.1 Implement TypeScript interfaces matching the backend payload schemas (e.g., `Node`, `Status`, `Reading`).
- [x] 2.2 Create an `ApiService` using `httpResource` to wrap the backend endpoints (`/api/nodes`, `/api/status`, `/api/readings`, `/api/display`) and verify it compiles and unit tests pass.

## 3. Shared Components

- [x] 3.1 Implement the `StatusPillComponent` representing online/offline states and verify it renders the correct colors based on inputs.
- [x] 3.2 Implement the main `LayoutComponent` featuring a fixed 56px icon rail and a router outlet, verifying that router navigation correctly swaps views.

## 4. Views Implementation

- [x] 4.1 Implement the Nodes view (`/nodes`) with a Material Data Grid displaying all nodes and verify sorting/filtering functionality works against mock data.
- [x] 4.2 Implement the Home view (`/`) consisting of summary metric cards and a primary chart, verifying data populates correctly from the `ApiService`.
- [x] 4.3 Implement the Graphs view (`/graphs`) with interactive selection controls and an `apx-chart` component, verifying time-series data rendering.
- [x] 4.4 Implement a message action Material Dialog to send text to display-capable nodes, verifying the dialog form validation and the submission call to `ApiService.postDisplay`.

## 5. Final Polish

- [x] 5.1 Ensure the application handles empty states and gracefully fails when backend calls error out, verifying the UI displays friendly error messages instead of crashing.
- [x] 5.2 Build the production bundle and verify the static files can be served successfully.
