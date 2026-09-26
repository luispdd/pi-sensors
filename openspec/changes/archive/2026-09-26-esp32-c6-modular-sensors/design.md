## Context

The current firmware architecture in `boards/pico-1w` and `boards/pico-2w` couples specific sensor types and hardware pins directly to the application state (`AppState`), telemetry loop, CoAP server, and HTTP web server. Adding a third board—the Waveshare ESP32-C6-Zero—requires adapting to a new microcontroller architecture (ESP32-C6 RISC-V) and pinout while avoiding code divergence.

See [proposal.md](proposal.md) for motivation and capability definitions.

## Goals / Non-Goals

**Goals:**
- Define a uniform, duck-typed "Sensor Protocol" for sensor drivers in MicroPython (`key`, `unit`, `interval_ms`, and `read()`).
- Refactor `AppState` and background monitoring tasks to be completely sensor-agnostic, supporting dynamic metric registration, caching, timestamping, and SenML generation.
- Isolate board-specific display rendering, screen cycling, and button input handling into a standardized `hardware/ui.py` module (`UIController`).
- Build the `boards/esp32c6` firmware as the first reference implementation using the onboard WS2812 RGB LED (GPIO 8), DHT22, SSD1306 OLED display, and button.
- Validate `boards/esp32c6` end-to-end with the existing controller backend discovery poller and frontend dashboard.
- Migrate `pico-1w` and `pico-2w` to the modular architecture without altering external network behaviors or user interfaces.

**Non-Goals:**
- Creating a shared external library or symlink tree for sensor drivers across boards (per design decision, each board keeps self-contained driver files under `hardware/sensors/` for simplicity and independence).
- Changing the IoTMesh CoAP/HTTP communication protocol or SenML payload formats consumed by the controller.
- Modifying the controller backend or frontend schemas (the controller already supports dynamic sensor capabilities via SenML).

## Decisions

### Decision 1: Duck-Typed Sensor Driver Contract
- **Choice**: Sensors implement a duck-typed Python class contract rather than relying on abstract base classes (`abc` module is unavailable or heavy in MicroPython).
- **Contract**:
  - `metrics`: list of metric definitions `[{"key": "temperature", "unit": "Cel"}, {"key": "humidity", "unit": "%"}]`
  - `interval_ms`: default sampling period in milliseconds
  - `init()`: hardware pin and peripheral configuration
  - `read()`: returns a dictionary `{key: value}` or a single numeric scalar (for single-metric sensors), or `None` on failure
- **Rationale**: Keeps sensor drivers small, self-contained, easily testable in isolation, and minimal in RAM footprint on embedded MicroPython runtimes.
- **Alternatives considered**:
  - Formal OOP class hierarchy: Adds runtime overhead and import complexity without benefit in MicroPython.
  - Functional tuples/callbacks: Harder to manage stateful sensors (such as smoothing filters or calibrated sensors).

### Decision 2: Self-Contained Sensor Drivers in Each Board Directory
- **Choice**: Place sensor driver files directly under `boards/<board>/hardware/sensors/` (e.g. `dht22.py`, `light.py`).
- **Rationale**: Aligns with the project requirement that boards remain self-contained deployable directories. If board-specific pin configurations or tweaks are needed, they remain isolated without cross-board regressions.
- **Alternatives considered**:
  - Symlinked or shared root library `lib/sensors/`: Can complicate flashing tools like `ampy`, `mpremote`, or `rshell`, which deploy single board folders.

### Decision 3: Sensor-Agnostic AppState and Dynamic SenML Generation
- **Choice**: `AppState` stores sensor telemetry in an internal dictionary indexed by metric key:
  ```python
  sensors = {
      "temperature": {"val": 21.5, "unit": "Cel", "ts": "2026-09-26T10:00:00", "err": 0},
      "humidity": {"val": 52.0, "unit": "%", "ts": "2026-09-26T10:00:00", "err": 0}
  }
  ```
  CoAP `/sensors` and HTTP `/info` build SenML items dynamically by iterating over `sensors.values()`. Individual routes `/sensors/<key>` resolve dynamically.
- **Rationale**: Eliminates hardcoded `self.temp`, `self.hum`, `self.light` fields. Adding a new sensor requires zero modifications to network services or core loops.
- **Alternatives considered**:
  - Static dataclass/attributes on `AppState`: Requires modifying `AppState` every time a sensor is added or removed.

### Decision 4: Isolated Board Personality (`hardware/ui.py`)
- **Choice**: All display layout (text, graphics, splash screen, sleep rendering) and button state machine transitions are housed in `hardware/ui.py` exposing a standard `UIController` class:
  ```python
  class UIController:
      def __init__(self, app_state): ...
      def show_splash(self): ...
      def update(self, app_state): ...
      def handle_button(self, press_type, app_state): ...
  ```
- **Rationale**: Keeps `main.py` minimal and nearly identical across boards. Boards with different displays (or no display) simply provide their own `UIController` without affecting the core loop.
- **Alternatives considered**:
  - Generic template-based UI engine: Overkill for embedded displays and consumes excess RAM.

### Decision 5: ESP32-C6-Zero Hardware Configuration & Onboard RGB LED
- **Choice**:
  - Onboard NeoPixel RGB LED on GPIO 8: Driven by MicroPython `neopixel.NeoPixel(machine.Pin(8), 1)` configured with `ORDER = (0, 1, 2, 3)` to match the board's physical RGB color channel order (preventing red/green inversion).
  - DHT22 on GPIO 2.
  - User Button on GPIO 3 (with internal pull-up).
  - SSD1306 OLED Display on I2C (SDA GPIO 0, SCL GPIO 1, 128x64).
- **Rationale**: Respects the physical pinout and onboard peripherals of the Waveshare ESP32-C6-Zero.

### Decision 6: Phased Implementation and Migration Strategy
- **Choice**:
  1. Build and test `boards/esp32c6` first using the new architecture.
  2. Validate with the controller backend and frontend.
  3. Migrate `boards/pico-1w` and `boards/pico-2w` to the proven modular architecture.
- **Rationale**: Isolates initial architectural development to the new board, ensuring production Pico nodes remain untouched until the design is proven end-to-end.

### Decision 7: Decoupled Service Runners and Lean Orchestrator (`main.py`)
- **Choice**: Move all async task implementations (`sensor_task`, `display_task`, `network_task`, `server_task`, `coap_task`, `ntp_task`) out of `main.py` into dedicated modules exposing standalone `run_*_task(app_state, ...)` runners. `main.py` is restricted to ~50 lines performing instantiation and launching tasks via `asyncio.gather`.
- **Rationale**: Prevents duplicating boilerplate loops across boards, keeps the entrypoint clean and readable, and facilitates reusability of service logic.

### Decision 8: Active Heap Garbage Collection for Shared-SRAM Architectures
- **Choice**: Introduce a lightweight `memory_task` running `gc.collect()` every 5 seconds, paired with periodic garbage collection in high-frequency networking loops (CoAP polling).
- **Rationale**: Unlike the RP2040 Pico W (which offloads WiFi packet buffers to a dedicated CYW43439 chip), the ESP32-C6 shares internal SRAM across MicroPython, FreeRTOS, and lwIP. Unmanaged heap fragmentation starves lwIP socket buffers, producing `OSError: [Errno 12] ENOMEM` on UDP transmissions. Proactive GC ensures memory blocks remain available for network buffers.

### Decision 9: Sensor Driver Pin Pull-Up & Single Transient Retry
- **Choice**: Configure DHT22 data pins with internal pull-up (`Pin.IN, Pin.PULL_UP`) and embed an immediate 100 ms retry inside `DHT22Sensor.read()` when `measure()` encounters a timeout.
- **Rationale**: Single-core microcontrollers running WiFi and FreeRTOS can introduce microsecond timing jitter during bit-banged pulse reads. A single 100 ms retry seamlessly absorbs momentary interrupt preemption without falsely logging telemetry failures.

## Risks / Trade-offs

- **[Risk] MicroPython Memory Fragmentation with Dynamic Dictionaries** → *Mitigation*: Pre-allocate the sensor registry dictionary during boot; update values in-place rather than reallocating dict objects on every reading.
- **[Risk] Board-specific Differences between RP2040 and ESP32-C6 MicroPython ports** (e.g. WiFi handling, timers, GPIO IRQ syntax) → *Mitigation*: Encapsulate platform-specific network and hardware initialization in `network/wifi.py` and `hardware/pins.py` while keeping core logic pure Python.
- **[Risk] Regressions in Pico 2 W SD Card Data Logging** → *Mitigation*: Refactor `DataLogger` during Phase 3 to accept a snapshot of `AppState.get_all_metrics()` while maintaining backward-compatible CSV formatting.

## Migration Plan

1. **Phase 1**: Implement `boards/esp32c6` with modular sensor drivers and `UIController`.
2. **Phase 2**: Run mock/real discovery against controller backend and verify frontend capability rendering.
3. **Phase 3**: Refactor `boards/pico-1w` to modular structure and verify regression-free operation.
4. **Phase 4**: Refactor `boards/pico-2w` (including `DataLogger` and secondary button) and verify SD logging and display functionality.
