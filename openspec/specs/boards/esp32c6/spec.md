# ESP32-C6 Specification

## Purpose

Provides firmware implementation and hardware interfacing for the Waveshare ESP32-C6-Zero node, integrating environmental sensing, local display, button controls, and onboard RGB LED status indication into the IoTMesh sensor network.

## Requirements

### Requirement: ESP32-C6-Zero Hardware Peripherals Interfacing
The system SHALL initialize and interface with the hardware peripherals of the Waveshare ESP32-C6-Zero board, including the SSD1306 I2C OLED display on GPIO 0 (SDA) and GPIO 1 (SCL), the DHT22 sensor on GPIO 2, the user push button on GPIO 3, and the onboard WS2812 RGB LED on GPIO 8.

#### Scenario: Board startup initialization
- **WHEN** the ESP32-C6-Zero board powers on or resets
- **THEN** the system SHALL initialize GPIO pins, configure the onboard RGB LED on GPIO 8, initialize the SSD1306 I2C display driver on GPIO 0/1, configure the push button input on GPIO 3 with internal pull-up, and register the connected DHT22 sensor module on GPIO 2

#### Scenario: Onboard RGB LED status signaling
- **WHEN** network connectivity changes (connecting to WiFi, connected to mesh, or experiencing errors)
- **THEN** the system SHALL drive the onboard RGB LED on GPIO 8 using RGB byte order (`ORDER = (0, 1, 2, 3)`) to match the Waveshare ESP32-C6-Zero hardware channel mapping, log each status transition to the console, and indicate status via configured colors (dim blue during WiFi connection, solid green when mesh ready, dim amber on message alert, and dim red on error)

### Requirement: ESP32-C6-Zero Button Interaction
The system SHALL detect short-press and long-press inputs on the user button to control screen power and display modes.

#### Scenario: Button short press cycles display mode
- **WHEN** the user presses and releases the button in under 1000 ms
- **THEN** the system SHALL cycle the display mode between sensor telemetry display, message display (if present), and semi-sleep mode

#### Scenario: Button long press toggles display power
- **WHEN** the user presses and holds the button for 1000 ms or more
- **THEN** the system SHALL toggle the OLED display power state on or off without altering network or sensing operations

### Requirement: IoTMesh CoAP and HTTP Service Advertising
The system SHALL run CoAP and HTTP servers advertising node capabilities and serving sensor telemetry under the standard IoTMesh schema.

#### Scenario: Mesh discovery advertising
- **WHEN** a multicast discovery probe is received on CoAP port 5683
- **THEN** the system SHALL respond with the board's device ID, board type (`esp32c6`), and advertised resource endpoints including `/sensors` and `/info`

#### Scenario: Telemetry query via CoAP /sensors
- **WHEN** a CoAP `GET /sensors` request is received
- **THEN** the system SHALL return a SenML-formatted payload containing temperature and humidity metrics with measurement units and timestamps

### Requirement: Clean Entrypoint and Modular Service Orchestration
The system entrypoint `main.py` SHALL serve strictly as a lean orchestrator (~50 lines) that initializes shared state and peripherals, registering sensors and delegating concurrent asynchronous lifecycle loops to modular service runners without inlining business logic.

#### Scenario: Startup task orchestration
- **WHEN** the system enters `main()` on boot
- **THEN** it SHALL initialize `AppState`, hardware peripherals (`UIController`, status LED, network manager), register modular sensor drivers, and launch service tasks concurrently using `asyncio.gather`

#### Scenario: Delegated service tasks
- **WHEN** background execution starts
- **THEN** the application SHALL delegate execution to standalone runners including `run_sensor_task`, `run_display_task`, `run_button_task`, `run_led_task`, `run_network_task`, `run_webserver_task`, `run_coap_task`, `run_ntp_task`, and `memory_task` exported from their dedicated modules

### Requirement: Heap Memory Management & Network Buffer Preservation
The system SHALL execute periodic garbage collection on the ESP32-C6 to prevent MicroPython heap fragmentation from starving the shared ESP-IDF / lwIP network packet buffer pool.

#### Scenario: Periodic background memory collection
- **WHEN** the application is running concurrently in `asyncio.gather`
- **THEN** a dedicated background `memory_task` SHALL trigger `gc.collect()` at configured intervals (every 5 seconds) to reclaim freed memory blocks

#### Scenario: Network polling loop maintenance
- **WHEN** the CoAP asynchronous polling loop processes UDP traffic
- **THEN** it SHALL trigger periodic garbage collection (every ~2 seconds) to keep network socket buffers available for incoming discovery and outgoing SenML responses

### Requirement: DHT22 Pin Pull-Up and Transient Read Error Recovery
The DHT22 sensor driver SHALL configure GPIO 2 with an internal pull-up (`Pin.IN, Pin.PULL_UP`) and provide transient timing error recovery with a single bounded retry to prevent momentary FreeRTOS or WiFi interrupt delays from registering as read failures.

#### Scenario: Transient interrupt collision recovery
- **WHEN** a DHT22 read attempt encounters a transient timeout (`ETIMEDOUT` / `OSError`) due to background interrupt or context-switch jitter
- **THEN** the driver SHALL pause for 100 ms and attempt a single immediate retry before raising or logging a read error

#### Scenario: Persistent hardware fault handling
- **WHEN** both the initial read attempt and the 100 ms retry fail
- **THEN** the driver SHALL increment its read error counter, log the error message, and preserve previously cached valid readings in `AppState`
