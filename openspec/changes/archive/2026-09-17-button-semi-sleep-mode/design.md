## Context

The station runs concurrent background tasks for periodic sensor sampling, display refresh, button monitoring, network management, and server handling. State is shared across components via a centralized application state. The previous alert boolean distinguished normal display from message override; there was no mechanism for powering the display down or pausing periodic sensor reads.

See [proposal.md](proposal.md) for motivation.

## Goals / Non-Goals

**Goals:**
- Introduce three named mode constants replacing the `alert_active` boolean.
- Add `MODE_SEMI_SLEEP` with display off and sensor loop idle.
- Gate the `POST /display` path so it queues a pending message (LED on, display off) when in semi-sleep, only showing it after the next button press.
- Support on-demand DHT22 reads for HTTP `/info` and CoAP sensor endpoints during semi-sleep.
- Keep all existing CoAP and HTTP response shapes unchanged.

**Non-Goals:**
- Hardware power gating (the microcontroller remains fully powered; this is a software idle only).
- WiFi or CoAP server suspension during semi-sleep.
- Persisting mode across power cycles.

## Decisions

### D1 — Single `mode` integer field in application state (replaces `alert_active`)

**Decision**: Replace `alert_active: bool` with `mode: int` initialised to `MODE_SENSOR_DISPLAY = 0`. Add `MODE_SEMI_SLEEP = 1` and `MODE_MESSAGE = 2` as named mode constants.

**Rationale**: A single mode field makes all invalid state combinations impossible (e.g., `alert_active=True` concurrently with semi-sleep). Existing display override queries check for `mode == MODE_MESSAGE`.

**Alternative considered**: Two separate booleans (`alert_active`, `semi_sleep`). Rejected: allows invalid overlapping states and obscures state machine intent.

### D2 — Flag-gating inside periodic tasks (no task cancellation)

**Decision**: Periodic tasks (sensor sampling and display refresh) remain active across mode switches but branch on the active mode:
- When not in `MODE_SEMI_SLEEP`: perform regular work and sleep for the configured interval.
- When in `MODE_SEMI_SLEEP`: remain in a lightweight idle sleep loop (~100 ms).

**Rationale**: Dynamically cancelling and recreating tasks on embedded runtimes introduces race conditions and overhead. A simple idle branch is robust and costs negligible CPU. The display is explicitly cleared once upon entering semi-sleep.

**Alternative considered**: Event-based task suspension. Rejected: adds synchronization complexity for minimal gain in this architecture.

### D3 — Pending message stored in state; LED used as notification signal

**Decision**: Add a pending message field to the application state. When an actuation command arrives in `MODE_SEMI_SLEEP`, store the payload as pending and turn on the alert LED while keeping the display powered off. On the next button press, transition to `MODE_MESSAGE` and display the pending message.

**Rationale**: The LED serves as a silent "message waiting" notification without illuminating the display unattended, keeping the screen dark until operator interaction.

**Alternative considered**: Immediately waking and showing messages received in semi-sleep. Rejected: contradicts the user requirement for the display to stay off in semi-sleep.

### D4 — Synchronous on-demand DHT22 read (~250 ms block accepted)

**Decision**: When an HTTP or CoAP sensor request arrives during `MODE_SEMI_SLEEP`, trigger a synchronous DHT22 read to refresh cached telemetry before returning the response.

**Rationale**: The DHT22 requires ~250 ms to read. During semi-sleep, inbound telemetry requests are infrequent, and embedded network loops accommodate brief synchronous reads without degrading overall stability.

**Alternative considered**: Returning stale cached telemetry without reading. Rejected: callers require fresh data on demand.

### D5 — Encapsulated state management methods

**Decision**: Provide explicit transition methods on the application state (`enter_sensor_mode`, `enter_semi_sleep`, `enter_message_mode`) and query/mutator methods for pending messages, request counting, caller resolution, node caching, and network status updates.

**Rationale**: Multiple concurrent components (button monitoring, CoAP server, HTTP server, network manager) interact with application state. Centralizing transitions and updates prevents state divergence and keeps transitions auditable.

### D6 — Encapsulated hardware controls (Button and Alert LED)

**Decision**: Encapsulate hardware pin operations for the button (GP14) and alert indicator (GP16) into dedicated control abstractions. The button abstraction encapsulates active-LOW pull-up logic and transition edge detection, while the LED abstraction manages on/off/set states.

**Rationale**: Eliminates raw GPIO manipulation, manual edge detection tracking, and platform-specific pin error handling from the main coordination logic.

### D7 — Decoupled display interface

**Decision**: Separate pure coordinate rendering from state extraction, allowing the display component to render either directly from an application state snapshot or from explicit parameters.

**Rationale**: Decouples the presentation layer from tight internal knowledge of the application state structure.


## System Components & Reference Libraries

The system architecture is organized into modular components. External libraries used in this project serve as reference implementations for equivalent libraries in other programming languages or runtimes:

- **Application State**: Central model managing telemetry values, network connectivity status, request counters, discovered mesh nodes, and mode state transitions.
- **Physical Controls**:
  - *Button*: Encapsulates physical push button input on GP14 with active-LOW pull-up and press edge detection.
  - *Alert LED*: Controls the visual notification indicator on GP16.
- **Display Service**: Manages OLED rendering (real-time telemetry, override alert messages, startup splash, and power-off state).
  - *Reference Library*: `stlehmann/micropython-ssd1306` (SSD1306 I2C display controller driver).
- **Sensor Service**: Manages DHT22 environmental sensor sampling, failure counting, and on-demand reads in semi-sleep mode.
- **Communication Services**:
  - *CoAP Server*: Implements IoTMesh discovery, SenML telemetry collections, and display actuation endpoints.
    - *Reference Library*: `microcoapy` (CoAP protocol implementation).
  - *HTTP Server*: Serves JSON telemetry via `/info` and `/sensors`.
- **Task Orchestration**: Coordinates concurrent background loops for sensor sampling, display refresh, network connectivity keepalive, and button event processing.


## Risks / Trade-offs

- **250 ms block on CoAP loop** → accepted (D4). Only occurs during semi-sleep, when continuous polling is already suspended.
- **Sensor reader coupling to servers** → The CoAP and HTTP servers hold a reference to the sensor reader for on-demand reads. This is a minor coupling increase but unavoidable for on-demand reads without a complex async read pipeline.
- **Display idle polling at 10 Hz** → Negligible CPU cost; no measurable impact on network or CoAP latency.
- **LED notification indicator** → The LED is active both in `MODE_MESSAGE` and when a message is pending in `MODE_SEMI_SLEEP`. These states are distinguishable by whether the display is illuminated or dark.


