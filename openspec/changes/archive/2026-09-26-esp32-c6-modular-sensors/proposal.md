## Why

The project currently supports two boards (Raspberry Pi Pico W and Pico 2 W), but the firmware code tightly couples specific sensors (DHT22 on GP15, ADC light sensor on GP26) directly into `AppState`, `SensorReader`, CoAP routes, and HTTP handlers. Introducing a third board—the Waveshare ESP32-C6-Zero—creates an opportunity to decouple sensor drivers and board-specific hardware from the core application loop. 

By establishing a modular "sensor protocol" (uniform duck-typed interface per sensor) and isolating board-specific UI interactions (display and button) into a dedicated interface, new sensors and boards can be added with minimal configuration. Developing the ESP32-C6-Zero first establishes a verified reference implementation for this modular architecture before migrating existing Pico boards.

## What Changes

- **ESP32-C6-Zero Board Support**: Create a new board directory `boards/esp32c6` with MicroPython firmware supporting the Waveshare ESP32-C6-Zero pinout, onboard RGB LED (NeoPixel/WS2812 on GPIO 8), connected DHT22 sensor, button, and SSD1306 OLED display.
- **Modular Sensor Protocol & Framework**: Establish a standard sensor driver interface (exposing metric name, unit, measurement interval, and synchronous/asynchronous `read()` methods) and a sensor-agnostic `AppState` that dynamically registers, polls, caches, and exposes metrics across CoAP and HTTP.
- **Isolated Board Personality (`hardware/ui.py`)**: Move display layout, screens, and button event handling into a standardized `UIController` module per board, keeping `main.py` and core application loops generic.
- **Decoupled Service Runners & Lean Orchestrator**: Encapsulate background lifecycle tasks (NTP sync, network management, telemetry, webserver, CoAP, UI) into dedicated, reusable service runners (`run_*_task`), keeping `main.py` lean and avoiding copy-pasting loops across boards.
- **Embedded Memory Stability & Bus Resilience**: Integrate proactive heap garbage collection routines and sensor-level single-retry recovery to prevent network buffer starvation and transient interrupt collisions on constrained single-core microcontrollers.
- **Sensor-Agnostic Monitoring & Endpoints**: Update sensor sampling and on-demand read mechanisms (during `SEMI_SLEEP`) to dynamically iterate over all registered sensor modules rather than hardcoded sensor variables.
- **Phased Rollout**: Implement and validate the ESP32-C6-Zero board end-to-end against the controller backend and frontend first, followed by migrating `pico-1w` and `pico-2w` to the modular architecture.

## Capabilities

### New Capabilities
- `boards/esp32c6`: Firmware implementation and configuration for the Waveshare ESP32-C6-Zero board, integrating DHT22, display, button, onboard RGB status LED, and IoTMesh networking.
- `core/modular-sensor-framework`: Duck-typed sensor driver contract, dynamic sensor registry, sensor-agnostic `AppState`, and isolated board UI controller abstraction.

### Modified Capabilities
- `core/sensor-monitoring`: Generalize periodic sampling and `SEMI_SLEEP` on-demand reads to operate dynamically over any registered sensor driver rather than fixed GPIOs and sensor types.

## Impact

- **Firmware Codebase**:
  - `boards/esp32c6/`: New complete board firmware following the modular structure.
  - `boards/pico-1w/` and `boards/pico-2w/`: Refactored to adopt the modular sensor protocol, sensor-agnostic `AppState`, and isolated `hardware/ui.py` after ESP32-C6 validation.
- **Controller Backend**:
  - Node discovery and polling continue to operate seamlessly via standard SenML over `/sensors` and `/info` endpoints.
- **Frontend Dashboard**:
  - Automatically receives metrics and capability entries for the ESP32-C6-Zero board via the existing capability discovery endpoints.
