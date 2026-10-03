# ESP32-C6 Specification

## Purpose

Provides firmware implementation and hardware interfacing for the Waveshare ESP32-C6-Zero node, integrating environmental sensing, local display, button controls, onboard RGB LED status indication, and audio sensing into the IoTMesh sensor network.

## Board Hardware Architecture & Layout Reference

### Board Details
- **Model**: Waveshare ESP32-C6-Zero-M (Header version, SKU: 26976) / ESP32-C6-Zero (SKU: 27035)
- **SoC**: Espressif ESP32-C6FH8
- **Core Architecture**:
  - High-Performance (HP) Core: 32-bit RISC-V single-core up to 160 MHz
  - Low-Power (LP) Core: 32-bit RISC-V coprocessor up to 20 MHz
- **Memory**:
  - 8 MB In-Package SPI Flash
  - 512 KB HP SRAM
  - 16 KB LP SRAM
  - 320 KB ROM
- **Wireless Connectivity**:
  - Wi-Fi 6 (2.4 GHz 802.11ax/b/g/n)
  - Bluetooth 5 (LE)
  - IEEE 802.15.4 (Zigbee 3.0 and Thread)
- **Power**:
  - 5V Input via USB-C or 5V pin
  - Onboard 3.3V LDO: ME6217C33M5G (800 mA max output)
- **Onboard Peripherals**:
  - Onboard Addressable WS2812 RGB LED (NeoPixel) on GPIO 8 (Color order: `ORDER = (0, 1, 2, 3)` RGB)
  - BOOT Button: Connected to GPIO 9 (active LOW, strapping pin)
  - RESET Button: Connected to CHIP_PU (active LOW hardware reset)
  - Ceramic 2.4 GHz Antenna

### Pinout Header Layout

The board features a dual-row 18-pin DIP header (2×9 pins) with 2.54mm pitch and castellated edges:

```
                  +---[ USB-C ]---+
   (Left Header)  |               |  (Right Header)
  Left 1:   5V   -| [ ]       [ ] |-  Right 1:  TX (GP16)
  Left 2:  GND   -| [ ]       [ ] |-  Right 2:  RX (GP17)
  Left 3:  3V3   -| [ ]       [ ] |-  Right 3:  GP14
  Left 4:  GP0   -| [ ]   C6  [ ] |-  Right 4:  GP15
  Left 5:  GP1   -| [ ]       [ ] |-  Right 5:  GP18
  Left 6:  GP2   -| [ ]  RGB  [ ] |-  Right 6:  GP19
  Left 7:  GP3   -| [ ] (GP8) [ ] |-  Right 7:  GP20
  Left 8:  GP4   -| [ ]       [ ] |-  Right 8:  GP21
  Left 9:  GP5   -| [ ]       [ ] |-  Right 9:  GP22
                  +---------------+
```

### Complete Hardware Pin Mapping Table

| Physical Pin | Silk Label | SoC GPIO | Alternate Functions / Characteristics | Connected Peripheral | Signal Direction / Type | Current Usage Notes |
|:---|:---|:---|:---|:---|:---|:---|
| **Left 1** | `5V` | — | 5V Power Input / USB VBUS | 5V Power Rail | Power | Direct from USB-C port |
| **Left 2** | `GND` | — | Ground | Common Ground | Power Ground | System ground return |
| **Left 3** | `3V3` | — | 3.3V Regulated Output (800mA max) | 3.3V Power Rail | Power | Supplies SSD1306, DHT22, PIR, MAX4466 |
| **Left 4** | `0` | GPIO 0 | LP_GPIO0, ADC1_CH0 | SSD1306 OLED Display (SDA) | Bidirectional (I2C) | I2C0 SDA (400 kHz) |
| **Left 5** | `1` | GPIO 1 | LP_GPIO1, ADC1_CH1 | SSD1306 OLED Display (SCL) | Output (I2C) | I2C0 SCL (400 kHz) |
| **Left 6** | `2` | GPIO 2 | LP_GPIO2, ADC1_CH2 | DHT22 Temperature & Humidity | Bidirectional (1-Wire) | Configured with internal pull-up |
| **Left 7** | `3` | GPIO 3 | LP_GPIO3, ADC1_CH3 | User Button A (Primary) | Input (Digital) | Active-LOW, internal pull-up (Mode/Sleep toggle) |
| **Left 8** | `4` | GPIO 4 | LP_GPIO4, ADC1_CH4, MTMS | AM312 PIR Motion Sensor | Input (Digital) | Active-HIGH motion pulse output |
| **Left 9** | `5` | GPIO 5 | LP_GPIO5, ADC1_CH5, MTDI | MAX4466 Electret Microphone | Input (Analog ADC) | **Analog OUT**. Only free ADC pin on the header |
| **Right 1** | `TX` | GPIO 16 | U0TXD | UART0 TX | Output (UART) | Serial console / programming debug |
| **Right 2** | `RX` | GPIO 17 | U0RXD | UART0 RX | Input (UART) | Serial console / programming debug |
| **Right 3** | `14` | GPIO 14 | Digital GPIO | Available GPIO | — | Available digital I/O |
| **Right 4** | `15` | GPIO 15 | Digital GPIO | Available GPIO | — | Available digital I/O |
| **Right 5** | `18` | GPIO 18 | SDIO_CMD / Digital GPIO | Available GPIO | — | Available digital I/O |
| **Right 6** | `19` | GPIO 19 | SDIO_CLK / Digital GPIO | Available GPIO | — | Available digital I/O |
| **Right 7** | `20` | GPIO 20 | SDIO_DATA0 / Digital GPIO | Available GPIO | — | Available digital I/O |
| **Right 8** | `21` | GPIO 21 | SDIO_DATA1 / Digital GPIO | Available GPIO | — | Available digital I/O |
| **Right 9** | `22` | GPIO 22 | SDIO_DATA2 / Digital GPIO | Settings / Secondary Button | Input (Digital) | Active-LOW, internal pull-up |
| **Onboard** | — | GPIO 8 | Strapping pin, WS2812 DIN | Onboard WS2812 RGB LED | Output | Driven via `neopixel.NeoPixel(Pin(8), 1)` |
| **Onboard** | `BOOT` | GPIO 9 | Strapping pin, Boot Mode | BOOT Push Button | Input | Pulls GPIO 9 to GND when pressed |
| **Onboard** | `RESET`| — | CHIP_PU Reset | RESET Push Button | Input | Pulls CHIP_PU to GND to hardware reset |

> [!IMPORTANT]
> **ADC Pin Constraint on ESP32-C6**: The ESP32-C6 ADC1 channels exist strictly on **GPIO 0 through GPIO 6**. GPIO 14 through GPIO 22 on the right header are strictly digital GPIOs. Since GPIO 0–4 are used by the OLED, DHT22, Button A, and PIR sensor, **GPIO 5 (`ADC1_CH5`) is the only exposed analog input pin** available for the MAX4466 microphone.

## Requirements

### Requirement: ESP32-C6-Zero Hardware Peripherals Interfacing
The system SHALL initialize and interface with the hardware peripherals of the Waveshare ESP32-C6-Zero board, including:
- SSD1306 I2C OLED display on GPIO 0 (SDA) and GPIO 1 (SCL)
- DHT22 temperature and humidity sensor on GPIO 2
- Primary user push button on GPIO 3 (active-LOW, pull-up)
- AM312 PIR motion sensor on GPIO 4 (active-HIGH)
- MAX4466 electret microphone analog output on GPIO 5 (`ADC1_CH5`)
- Secondary settings push button on GPIO 22 (active-LOW, pull-up)
- Onboard WS2812 RGB LED on GPIO 8

#### Scenario: Board startup initialization
- **WHEN** the ESP32-C6-Zero board powers on or resets
- **THEN** the system SHALL initialize GPIO pins, configure the onboard RGB LED on GPIO 8, initialize the SSD1306 I2C display driver on GPIO 0/1, configure the primary push button on GPIO 3 with internal pull-up, configure the secondary settings button on GPIO 22 with internal pull-up, configure the PIR motion input on GPIO 4, initialize the ADC channel on GPIO 5 for MAX4466 audio sampling, and register the connected DHT22 sensor module on GPIO 2

#### Scenario: Onboard RGB LED status signaling
- **WHEN** network connectivity changes (connecting to WiFi, connected to mesh, or experiencing errors)
- **THEN** the system SHALL drive the onboard RGB LED on GPIO 8 using RGB byte order (`ORDER = (0, 1, 2, 3)`) to match the Waveshare ESP32-C6-Zero hardware channel mapping, log each status transition to the console, and indicate status via configured colors (dim blue during WiFi connection, solid green when mesh ready, dim amber on message alert, and dim red on error)

### Requirement: MAX4466 Microphone Analog Interface on GP5
The system SHALL sample the analog output of the MAX4466 electret microphone amplifier on GPIO 5 (`ADC1_CH5`) to measure sound pressure / ambient noise levels.

#### Scenario: Audio sampling configuration
- **WHEN** audio telemetry is enabled on the ESP32-C6
- **THEN** the system SHALL configure GPIO 5 as an ADC input using `machine.ADC(Pin(5))` with 12-bit resolution (0–4095) and full-scale attenuation (11dB / 3.3V range)

#### Scenario: Peak-to-peak sound level calculation
- **WHEN** a noise sample window executes
- **THEN** the driver SHALL sample GPIO 5 continuously over a sampling window (e.g., 50 ms), compute the AC RMS amplitude relative to a dynamic DC reference, and translate the value into relative noise percentage telemetry using an adaptive noise floor and dB scaling

### Requirement: MAX4466 Noise Metric Registration (esp32c6)
The esp32c6 firmware SHALL register a `MicSensor` driver on `PIN_MIC_ADC = 5` (GPIO 5 / ADC1_CH5) at startup, causing the `"noise"` metric (unit `%`) to appear in `AppState` and in all SenML telemetry responses.

#### Scenario: Noise sensor registered at boot
- **WHEN** the esp32c6 board powers on and `main.py` executes
- **THEN** a `MicSensor` SHALL be registered via `app_state.register_sensor(...)` and its `run_sampling_task()` coroutine SHALL be added to `asyncio.gather` alongside other service tasks

#### Scenario: Noise metric in SenML response
- **WHEN** a CoAP or HTTP `GET /sensors` request is received
- **THEN** the SenML response SHALL include an entry with `n = "noise"`, `u = "%"`, and the current noise percentage value

### Requirement: DETAILS_MODE Sensor Summary View (esp32c6)
In DETAILS_MODE the esp32c6 OLED display SHALL render a summary table displaying all available registered sensors (temperature in Cel, humidity in %, motion in %, noise in %). The first line SHALL be a header label `[DETAILS]`. Each sensor metric SHALL be rendered on its own line in the format `<key>: <cur> <min> <max>` (labels: `T` for temperature, `H` for humidity, `M` for motion, `N` for noise) displaying current, session minimum, and session maximum values.

#### Scenario: DETAILS_MODE renders temperature and humidity stats
- **WHEN** the system is in DETAILS_MODE and the OLED is on
- **THEN** the display SHALL show rows in the format `<key>: <cur> <min> <max>` truncated to MAX_LINE_LEN, with `--` substituted for any None values.

#### Scenario: DETAILS_MODE shows placeholder for future sensor
- **WHEN** the system is in DETAILS_MODE and fewer than 4 metrics are registered
- **THEN** any remaining data row(s) SHALL be blank, reserving space for future sensor metrics.

#### Scenario: DETAILS_MODE renders all registered sensors including motion and noise
- **WHEN** the system is in DETAILS_MODE with temperature, humidity, motion, and noise sensors registered
- **THEN** the display SHALL render four data rows in order (`T`, `H`, `M`, `N`) showing current, minimum, and maximum values for each sensor metric.


### Requirement: ESP32-C6 Primary Button Interaction
The primary button (active-LOW, pull-up) SHALL implement the mode-transition contract defined in `core/display-modes`:
- Short press in STATUS_MODE → DETAILS_MODE.
- Short press in DETAILS_MODE → STATUS_MODE.
- Long press (≥ 1000 ms) from any active mode → SEMI_SLEEP (previous mode saved).
- Any press from SEMI_SLEEP → restore previous mode and wake display.
- Short press in MESSAGE_MODE → discard message, restore previous mode.

#### Scenario: Short press toggles between STATUS_MODE and DETAILS_MODE
- **WHEN** the primary button is short-pressed while in STATUS_MODE or DETAILS_MODE
- **THEN** the system SHALL transition to the other mode without blanking the display.

#### Scenario: Long press enters SEMI_SLEEP
- **WHEN** the primary button is held for ≥ 1000 ms in STATUS_MODE or DETAILS_MODE
- **THEN** the system SHALL enter SEMI_SLEEP and blank the OLED display.

#### Scenario: Any press restores from SEMI_SLEEP
- **WHEN** the primary button is pressed while in SEMI_SLEEP
- **THEN** the system SHALL restore the previous mode and turn on the OLED display.


### Requirement: IoTMesh CoAP and HTTP Service Advertising
The system SHALL run CoAP and HTTP servers advertising node capabilities and serving sensor telemetry under the standard IoTMesh schema.

#### Scenario: Mesh discovery advertising
- **WHEN** a multicast discovery probe is received on CoAP port 5683
- **THEN** the system SHALL respond with the board's device ID, board type (`esp32c6`), and advertised resource endpoints including `/sensors` and `/info`

#### Scenario: Telemetry query via CoAP /sensors
- **WHEN** a CoAP `GET /sensors` request is received
- **THEN** the system SHALL return a SenML-formatted payload containing temperature, humidity, motion, and audio metrics with measurement units and timestamps

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

