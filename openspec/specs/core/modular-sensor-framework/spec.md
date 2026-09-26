# Modular Sensor Framework Specification

## Purpose

Establishes a pluggable, duck-typed sensor framework and isolated UI controller abstraction, enabling sensor-agnostic telemetry sampling, storage, network exposure, and board-specific display rendering across diverse microcontroller targets.

## Requirements

### Requirement: Modular Sensor Driver Protocol
The system SHALL require all sensor drivers to conform to a standard duck-typed protocol exposing metric metadata (`key`, `unit`, `interval_ms`), an initialization method, and a `read()` method returning numeric readings or a key-value dictionary of metrics.

#### Scenario: Multi-metric sensor read
- **WHEN** a composite sensor driver (such as DHT22) is read via its `read()` method
- **THEN** it SHALL return a dictionary mapping metric keys to numeric values (e.g. `{"temperature": 23.4, "humidity": 55.2}`) or `None` on read failure

#### Scenario: Single-metric sensor read
- **WHEN** a single-metric sensor driver (such as an ADC light sensor) is read via its `read()` method
- **THEN** it SHALL return a numeric measurement or a dictionary containing its configured metric key and numeric value

#### Scenario: Sensor read error handling
- **WHEN** a sensor driver encounters a hardware communication or checksum error during `read()`
- **THEN** it SHALL return `None` or raise a designated exception, allowing the registry to preserve the last valid reading and update error statistics without crashing

### Requirement: Dynamic Sensor Registry and Sensor-Agnostic AppState
The system SHALL maintain a dynamic sensor registry within `AppState` storing sensor configuration, latest readings, timestamps, and error counters keyed by metric name without hardcoded sensor attributes.

#### Scenario: Dynamic sensor registration on startup
- **WHEN** the system initializes configured sensor modules during startup
- **THEN** `AppState` SHALL register each metric key along with its measurement unit and sampling interval in an internal sensor registry

#### Scenario: Dynamic metric update
- **WHEN** a sensor driver produces a fresh valid reading
- **THEN** `AppState` SHALL update the stored value for that metric key and record the current UTC timestamp

### Requirement: Dynamic CoAP and HTTP Endpoint Exposure
The system SHALL expose SenML-compliant aggregated telemetry and dynamic per-metric endpoints derived directly from the registered sensor metrics.

#### Scenario: Aggregated /sensors SenML response
- **WHEN** a request is made to `GET /sensors` via CoAP or HTTP
- **THEN** the system SHALL construct a SenML array containing an entry for every active registered metric with its name (`n`), unit (`u`), numeric value (`v`), and timestamp

#### Scenario: Individual metric endpoint query
- **WHEN** a CoAP `GET /sensors/<metric_key>` is requested for any registered metric
- **THEN** the system SHALL return the specific metric value, unit, and timestamp matching the requested key

### Requirement: Standardized Board UI Controller Abstraction
The system SHALL isolate board-specific display layouts, screen rendering, and button handling behind a standardized `UIController` interface in `hardware/ui.py`.

#### Scenario: Core loop UI update
- **WHEN** the core application loop ticks
- **THEN** it SHALL call `ui_controller.update(app_state)` passing the generic `AppState`, allowing the board-specific UI controller to render telemetry without requiring sensor-specific logic in the core loop

#### Scenario: UI controller button event handling
- **WHEN** user button activity is detected
- **THEN** `ui_controller.handle_button(press_type, app_state)` SHALL execute the appropriate display or operational state change for that specific board

### Requirement: Decoupled Service Runner Architecture
The system SHALL encapsulate asynchronous background tasks (including periodic sensor sampling, display refreshing, button polling, LED status signaling, WiFi network management, HTTP web serving, CoAP serving, and NTP synchronization) in dedicated service runner functions (`run_*_task(app_state, ...)`) exported from their respective modules rather than embedding monolithic loops inside `main.py`.

#### Scenario: Clean entrypoint orchestration
- **WHEN** a board initializes and starts its concurrent background execution
- **THEN** `main.py` SHALL import and launch these decoupled runners via `asyncio.gather` without implementing service-specific retry, connection, or protocol logic

#### Scenario: Service reusability across boards
- **WHEN** migrating or adding microcontroller targets
- **THEN** core service runners (such as `services.ntp_service.run_ntp_task`, `services.telemetry.run_sensor_task`, and `services.network_manager.run_network_task`) SHALL be reusable across board implementations without duplication

### Requirement: Transient Bus Fault Resilience in Sensor Drivers
Sensor drivers implementing timing-sensitive single-wire or bit-banged protocols SHALL implement bounded retry logic upon detecting momentary communication timeouts or bus collisions before declaring a measurement failure.

#### Scenario: Transparent recovery from interrupt jitter
- **WHEN** an asynchronous task switch or high-priority hardware interrupt momentarily corrupts a sensor read pulse train
- **THEN** the sensor driver SHALL pause briefly (e.g. 100 ms) and attempt a single retry, preventing transient context switching from disrupting telemetry logging
