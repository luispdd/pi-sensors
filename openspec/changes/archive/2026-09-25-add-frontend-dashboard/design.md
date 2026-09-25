## Context

See `proposal.md` for the motivation. The backend provides a RESTful API via `aiohttp` at `/api/*`. The frontend will run independently and communicate with these endpoints via HTTP.

## Goals / Non-Goals

**Goals:**
- Rapidly prototype the user interface for the IoTMesh dashboard.
- Create a clean separation between the frontend presentation and backend logic.
- Ensure the architecture is modular enough to allow for future framework migrations if desired.

**Non-Goals:**
- Implementing persistent backend alerts.
- Implementing editable backend settings via the UI.
- Complex authentication or authorization (v1 assumes a trusted LAN).

## Decisions

### 1. Framework & Tech Stack
**Decision**: Use Angular, Angular Material, and `ng-apexcharts` for the POC.
**Rationale**: The developer is highly familiar with this stack, allowing for rapid iteration of the POC.
**Alternatives Considered**: React/Vite. While preferred for lightweight/highly customized premium UI, Angular was chosen for speed of delivery in this specific instance.

### 2. Component Architecture
**Decision**: Use modern Angular Standalone Components and Signal based features. Avoid RxJS where possible.
**Rationale**: Reduces boilerplate compared to `NgModule` and aligns with modern Angular best practices, making the code easier to read and potentially migrate later.

### 3. API Communication
**Decision**: Use the modern `@Service()` decorator from `@angular/core` and `httpResource` from `@angular/common/http` for API communication and reactive data fetching.
**Rationale**: Angular v22's `@Service()` decorator automatically registers services in root DI without `@Injectable({ providedIn: 'root' })` boilerplate. Pairing it with `httpResource` provides native Signal integration (`value`, `isLoading`, `error`, `reload`), relying cleanly on the ambient injection context without manual injector passing. `provideHttpClient()` powers the HTTP transport and testing infrastructure.

### 4. Styling Approach
**Decision**: Utilize custom CSS variables (tokens) to override Angular Material's default styling where necessary to achieve the dark theme and specific hex colors requested.
**Rationale**: Ensures we meet the aesthetic requirements (dark theme, teal accents) while still leveraging Material's robust interactive components (Data Grids, Dialogs).

## Risks / Trade-offs

- **Risk: Angular Material Styling Rigidity** -> Material can be hard to customize deeply.
  **Mitigation**: Rely heavily on CSS variables for colors and borders as defined in the initial spec constraints. Avoid fighting structural Material styles unless necessary.
- **Risk: Polling Overhead** -> Frequent polling of `/api/nodes` or `/api/status` might create unnecessary network traffic.
  **Mitigation**: Keep polling intervals reasonable (e.g., matching the backend's sync interval) and consider using RxJS `switchMap` and `takeUntil` to manage subscriptions efficiently.
