# Raspberry Pi Pico 2 W Specification

## Purpose

Provides firmware implementation and hardware interfacing for the Raspberry Pi Pico 2 W (`pico-2w`) node, integrating environmental sensing (DHT22, AM312 PIR, ALS-PT19 light sensor), audio monitoring (MAX4466 microphone), dual-button controls, an ST7735 128×160 color TFT display, and local MicroSD card data logging into the IoTMesh sensor network.

## Board Hardware Architecture & Layout Reference

### Board Details
- **Model**: Raspberry Pi Pico 2 W
- **Microcontroller**: RP2350 (Dual ARM Cortex-M33 or Dual RISC-V Hazard3 cores @ up to 150 MHz)
- **Memory**:
  - 520 KB On-Chip SRAM (across 10 banks)
  - 4 MB On-Board QSPI Flash
  - 8 KB OTP (One-Time Programmable) storage
  - Hardware Secure Boot & SHA-256 accelerator
- **Wireless Subsystem**:
  - Infineon CYW43439 2.4 GHz Wi-Fi 4 (802.11b/g/n) & Bluetooth 5.2
  - Onboard User LED connected to CYW43439 (`WL_GPIO0`, addressed in MicroPython as `Pin("LED")`)
- **Power Architecture**:
  - Input: 1.8V to 5.5V via `VSYS` (Pin 39) or 5V via Micro-USB `VBUS` (Pin 40)
  - Onboard SMPS: Richtek RT6154A buck-boost DC-DC converter delivering 3.3V up to 1.6A on `3V3(OUT)` (Pin 36)
- **ADC Architecture**:
  - 12-bit SAR ADC (500 ksps, 4 external channels exposed on RP2350, 3 broken out on Pico header: GP26, GP27, GP28)
  - Dedicated low-noise analog ground `AGND` (Pin 33) and reference voltage `ADC_VREF` (Pin 35)

### Complete 40-Pin Header Layout

The Raspberry Pi Pico 2 W features a standard 40-pin 2.54mm dual-in-line header:

```
                          +---[ Micro-USB ]---+
            GP0 (Pin 1)  -| [ ]           [ ] |-  Pin 40: VBUS (5V USB input)
            GP1 (Pin 2)  -| [ ]           [ ] |-  Pin 39: VSYS (1.8V - 5.5V)
            GND (Pin 3)  -| [ ]           [ ] |-  Pin 38: GND
            GP2 (Pin 4)  -| [ ]           [ ] |-  Pin 37: 3V3_EN (Regulator enable)
            GP3 (Pin 5)  -| [ ]           [ ] |-  Pin 36: 3V3(OUT) (3.3V power)
            GP4 (Pin 6)  -| [ ]           [ ] |-  Pin 35: ADC_VREF (ADC reference)
            GP5 (Pin 7)  -| [ ]           [ ] |-  Pin 34: GP28 (ADC2)
            GND (Pin 8)  -| [ ]  RP2350   [ ] |-  Pin 33: AGND (Analog Ground)
            GP6 (Pin 9)  -| [ ]           [ ] |-  Pin 32: GP27 (ADC1) [MAX4466 Mic]
            GP7 (Pin 10) -| [ ]           [ ] |-  Pin 31: GP26 (ADC0) [Light Sensor]
            GP8 (Pin 11) -| [ ]  CYW43439 [ ] |-  Pin 30: RUN (Reset)
            GP9 (Pin 12) -| [ ]           [ ] |-  Pin 29: GP22 (SD_CS)
            GND (Pin 13) -| [ ]           [ ] |-  Pin 28: GND
           GP10 (Pin 14) -| [ ]           [ ] |-  Pin 27: GP21 (TFT_RESET)
           GP11 (Pin 15) -| [ ]           [ ] |-  Pin 26: GP20 (TFT_DC)
     [PIR] GP12 (Pin 16) -| [ ]           [ ] |-  Pin 25: GP19 (SPI0 MOSI)
 [Log Btn] GP13 (Pin 17) -| [ ]           [ ] |-  Pin 24: GP18 (SPI0 SCK)
            GND (Pin 18) -| [ ]           [ ] |-  Pin 23: GND
[User Btn] GP14 (Pin 19) -| [ ]           [ ] |-  Pin 22: GP17 (TFT_CS)
   [DHT22] GP15 (Pin 20) -| [ ]           [ ] |-  Pin 21: GP16 (SPI0 MISO)
                          +-------------------+
```

### Complete Hardware Pin Mapping Table

| Physical Pin | Signal / GPIO | Function / Alternate | Connected Peripheral | Signal Direction / Type | Current Usage Notes |
|:---|:---|:---|:---|:---|:---|
| **Pin 1** | `GP0` | UART0 TX / I2C0 SDA / SPI0 RX | Free GPIO | — | Available digital I/O |
| **Pin 2** | `GP1` | UART0 RX / I2C0 SCL / SPI0 CSn | Free GPIO | — | Available digital I/O |
| **Pin 3** | `GND` | Ground | System Ground | Power Ground | Digital ground return |
| **Pin 4** | `GP2` | I2C1 SDA / SPI0 SCK | Free GPIO | — | Available digital I/O |
| **Pin 5** | `GP3` | I2C1 SCL / SPI0 TX | Free GPIO | — | Available digital I/O |
| **Pin 6** | `GP4` | UART1 TX / I2C0 SDA | Free GPIO | — | Available digital I/O |
| **Pin 7** | `GP5` | UART1 RX / I2C0 SCL | Free GPIO | — | Available digital I/O |
| **Pin 8** | `GND` | Ground | System Ground | Power Ground | Digital ground return |
| **Pin 9** | `GP6` | I2C1 SDA / SPI0 RX | Free GPIO | — | Available digital I/O |
| **Pin 10** | `GP7` | I2C1 SCL / SPI0 CSn | Free GPIO | — | Available digital I/O |
| **Pin 11** | `GP8` | UART1 TX / I2C0 SDA | Free GPIO | — | Available digital I/O |
| **Pin 12** | `GP9` | UART1 RX / I2C0 SCL | Free GPIO | — | Available digital I/O |
| **Pin 13** | `GND` | Ground | System Ground | Power Ground | Digital ground return |
| **Pin 14** | `GP10` | I2C1 SDA / SPI1 SCK | Free GPIO | — | Available digital I/O |
| **Pin 15** | `GP11` | I2C1 SCL / SPI1 TX | Free GPIO | — | Available digital I/O |
| **Pin 16** | `GP12` | UART0 TX / I2C0 SDA | AM312 PIR Motion Sensor | Input (Digital) | Active-HIGH motion pulse output |
| **Pin 17** | `GP13` | UART0 RX / I2C0 SCL | Data Logger Button | Input (Digital) | Active-LOW, internal pull-up (`PIN_BUTTON_LOG`) |
| **Pin 18** | `GND` | Ground | System Ground | Power Ground | Digital ground return |
| **Pin 19** | `GP14` | UART1 TX / I2C1 SDA | User / Ack Button | Input (Digital) | Active-LOW, internal pull-up (`PIN_BUTTON`) |
| **Pin 20** | `GP15` | UART1 RX / I2C1 SCL | DHT22 Temperature & Humidity | Bidirectional (1-Wire) | 1-Wire data line with pull-up |
| **Pin 21** | `GP16` | SPI0 MISO / UART0 TX | MicroSD Card Reader (MISO) | Input (SPI) | Shared SPI0 MISO (TFT does not use MISO) |
| **Pin 22** | `GP17` | SPI0 CSn / UART0 RX | ST7735 TFT Display (CS) | Output (Digital) | Active-LOW chip select for TFT |
| **Pin 23** | `GND` | Ground | System Ground | Power Ground | Digital ground return |
| **Pin 24** | `GP18` | SPI0 SCK / I2C1 SDA | Shared SPI0 Clock (SCK) | Output (SPI) | Clock signal for both ST7735 and MicroSD |
| **Pin 25** | `GP19` | SPI0 MOSI / I2C1 SCL | Shared SPI0 Data Out (MOSI) | Output (SPI) | MOSI signal for both ST7735 and MicroSD |
| **Pin 26** | `GP20` | I2C0 SDA / SPI0 RX | ST7735 TFT Data/Command (DC)| Output (Digital) | LOW = Command, HIGH = Data |
| **Pin 27** | `GP21` | I2C0 SCL / SPI0 CSn | ST7735 TFT Reset (RESET) | Output (Digital) | Active-LOW hardware reset pulse |
| **Pin 28** | `GND` | Ground | System Ground | Power Ground | Digital ground return |
| **Pin 29** | `GP22` | SPI0 SCK | MicroSD Card Reader (CS) | Output (Digital) | Active-LOW chip select for SD card |
| **Pin 30** | `RUN` | Hardware Reset | Reset Pin | Input | Pull to GND to reset RP2350 |
| **Pin 31** | `GP26` | ADC0 / I2C1 SDA | ALS-PT19 Ambient Light Sensor | Input (Analog ADC) | Analog voltage output from ADA2748 |
| **Pin 32** | `GP27` | ADC1 / I2C1 SCL | MAX4466 Electret Microphone | Input (Analog ADC) | **Analog OUT**. Dedicated audio ADC input |
| **Pin 33** | `AGND` | Analog Ground Reference | MAX4466 / ADC Ground | Power Ground | **Low-noise analog ground** for microphone & ADC |
| **Pin 34** | `GP28` | ADC2 / UART0 TX | Free ADC / GPIO | Input (Analog ADC) | Available analog ADC2 or digital GPIO |
| **Pin 35** | `ADC_VREF`| ADC Voltage Reference | Internal / Filtered 3.3V | Power Reference | Decoupled 3.3V reference for ADC converter |
| **Pin 36** | `3V3(OUT)`| 3.3V Power Output | 3.3V System Power Rail | Power Rail | Powers ST7735, MicroSD, DHT22, PIR, MAX4466 |
| **Pin 37** | `3V3_EN` | Regulator Enable | SMPS Enable Pin | Input | Connect to GND to disable 3.3V rail |
| **Pin 38** | `GND` | Ground | System Ground | Power Ground | Digital ground return |
| **Pin 39** | `VSYS` | Main System Input (1.8–5.5V) | System Power Input | Power | Raw power input before buck-boost converter |
| **Pin 40** | `VBUS` | USB 5V Power Input | USB Power Rail | Power | 5V rail supplied directly by USB port |
| **Onboard** | `LED` | CYW43439 GPIO 0 | Status / Alert LED | Output | Controlled via `machine.Pin("LED")` |

---

## Requirements

### Requirement: Pico 2 W Hardware Peripherals Interfacing
The system SHALL initialize and interface with the hardware peripherals of the Raspberry Pi Pico 2 W board:
- ST7735 128×160 color TFT display on shared SPI0 (SCK GP18, MOSI GP19, CS GP17, DC GP20, RESET GP21)
- MicroSD card reader on shared SPI0 (SCK GP18, MOSI GP19, MISO GP16, CS GP22)
- DHT22 temperature and humidity sensor on GP15 (Pin 20)
- AM312 PIR motion sensor on GP12 (Pin 16)
- ALS-PT19 ambient light sensor on GP26 (Pin 31, `ADC0`)
- MAX4466 electret microphone analog output on GP27 (Pin 32, `ADC1`)
- Dedicated user / reset button on GP14 (Pin 19, active-LOW, internal pull-up)
- Dedicated data logger control button on GP13 (Pin 17, active-LOW, internal pull-up)
- Onboard status LED via CYW43439 (`WL_GPIO0`)

#### Scenario: Board startup initialization
- **WHEN** the Pico 2 W board powers on or resets
- **THEN** the system SHALL configure shared SPI0 bus pins, initialize display and SD card drivers, configure digital inputs with internal pull-ups for GP13 and GP14, initialize ADC0 on GP26 for light sensing, initialize ADC1 on GP27 for microphone sampling, and configure GP12 for motion interrupts

### Requirement: MAX4466 Microphone Analog Interface on GP27 (ADC1)
The system SHALL configure GP27 (Pin 32, `ADC1`) as the analog input channel for the MAX4466 electret microphone amplifier.

#### Scenario: Microphone ADC initialization
- **WHEN** the sensor manager initializes on the Pico 2 W
- **THEN** it SHALL configure `PIN_MIC_ADC = 27` in `settings/config.py` and instantiate `machine.ADC(Pin(27))`

#### Scenario: Low-noise ground reference
- **WHEN** the MAX4466 microphone breakout is wired to the board
- **THEN** its ground pin SHALL be connected to `AGND` (Pin 33) to decouple analog sampling from high-frequency SPI switching and WiFi RF return currents

#### Scenario: Sound level sampling window
- **WHEN** sound pressure telemetry is read
- **THEN** the system SHALL sample GP27 over a dedicated observation window, calculate the AC RMS amplitude relative to a dynamic DC reference, and export relative noise percentage telemetry to `AppState` using an adaptive noise floor and dB scaling

### Requirement: MAX4466 Noise Metric Registration (pico-2w)
The pico-2w firmware SHALL register a `MicSensor` driver on `PIN_MIC_ADC = 27` (GP27 / ADC1) at startup, causing the `"noise"` metric (unit `%`) to appear in `AppState` and in all SenML telemetry responses.

#### Scenario: Noise sensor registered at boot
- **WHEN** the pico-2w board powers on and `main.py` executes
- **THEN** a `MicSensor` SHALL be registered via `app_state.register_sensor(...)` and its `run_sampling_task()` coroutine SHALL be added to `asyncio.gather` alongside other service tasks

#### Scenario: Noise metric in SenML response
- **WHEN** a CoAP or HTTP `GET /sensors` request is received
- **THEN** the SenML response SHALL include an entry with `n = "noise"`, `u = "%"`, and the current noise percentage value


### Requirement: Shared SPI0 Bus Arbitration
The system SHALL enforce chip-select mutual exclusion between the ST7735 TFT display (GP17) and MicroSD card (GP22) on the shared SPI0 peripheral (SCK GP18, MOSI GP19, MISO GP16).

#### Scenario: Display write access
- **WHEN** TFT display operations execute
- **THEN** TFT_CS (GP17) SHALL be asserted LOW, SD_CS (GP22) SHALL remain deasserted HIGH, and SPI clock SHALL run at 20 MHz

#### Scenario: SD card read/write access
- **WHEN** SD card logging operations execute
- **THEN** SD_CS (GP22) SHALL be asserted LOW, TFT_CS (GP17) SHALL remain deasserted HIGH, and SPI clock SHALL run at 10 MHz (or 400 kHz during init)

### Requirement: DETAILS_MODE SD File Listing View (pico-2w)
In DETAILS_MODE the pico-2w TFT display SHALL show a paginated listing of files from `/sd/sensor-data/`. The file list SHALL be fetched fresh from the SD card every time the system enters DETAILS_MODE. Each page SHALL display as many filenames as fit on screen, sorted alphanumerically. When additional files exist beyond the current page, the last visible line SHALL display `<Next page>`. When no further files exist, `<Next page>` SHALL NOT be shown.

#### Scenario: File list is refreshed on DETAILS_MODE entry
- **WHEN** the system transitions into DETAILS_MODE
- **THEN** the system SHALL mount the SD card, read the contents of `/sd/sensor-data/`, cache the sorted list, and unmount.

#### Scenario: First page is displayed on DETAILS_MODE entry
- **WHEN** DETAILS_MODE is entered and the file list has been loaded
- **THEN** the display SHALL show the first page of filenames starting at index 0.

#### Scenario: Next page shown when overflow exists
- **WHEN** the number of files exceeds the per-page capacity
- **THEN** the last line of the current page SHALL read `<Next page>`.

#### Scenario: Secondary button advances page
- **WHEN** the secondary button (GP13) is short-pressed while in DETAILS_MODE
- **THEN** the display SHALL advance to the next page of filenames, wrapping back to the first page after the last.

#### Scenario: No next page indicator on last page
- **WHEN** all files fit on the current page or the last page is displayed
- **THEN** `<Next page>` SHALL NOT appear.

#### Scenario: SD card absent or mount fails
- **WHEN** the SD card cannot be mounted when entering DETAILS_MODE
- **THEN** the display SHALL show an error message (e.g., `SD: unavailable`) and the file list SHALL be empty.

### Requirement: STATUS_MODE Layout with PIR Activity (pico-2w)
The STATUS_MODE view on the TFT SHALL display PIR motion activity and noise level combined on the second displayed line, immediately after the primary telemetry line (temperature / humidity / light). All subsequent lines (network status, CoAP route, requests served, last caller, and the logging section when active) SHALL be positioned below the combined PIR+noise line.

#### Scenario: PIR activity line is rendered in STATUS_MODE
- **WHEN** the system is in STATUS_MODE and the TFT is on
- **THEN** the second line of the display SHALL show both PIR motion activity and noise level in the format `PIR:<pir>% N:<noise>%`, with `--` shown for either value when it is unavailable.

#### Scenario: PIR and noise combined line is rendered in STATUS_MODE
- **WHEN** the system is in STATUS_MODE and the TFT is on
- **THEN** the second line of the display SHALL show both PIR motion activity and noise level in the format `PIR:<pir>% N:<noise>%`, with `--` shown for either value when it is unavailable


### Requirement: Pico 2 W Primary Button Interaction
The primary button (GP14, active-LOW, pull-up) SHALL implement the mode-transition contract defined in `core/display-modes`:
- Short press in STATUS_MODE → DETAILS_MODE.
- Short press in DETAILS_MODE → STATUS_MODE.
- Long press (≥ 1000 ms) from any active mode → SEMI_SLEEP (previous mode saved).
- Any press from SEMI_SLEEP → restore previous mode and wake display.
- Short press in MESSAGE_MODE → discard message, restore previous mode.

#### Scenario: Short press toggles between STATUS_MODE and DETAILS_MODE
- **WHEN** the primary button is short-pressed while in STATUS_MODE or DETAILS_MODE
- **THEN** the system SHALL transition to the other mode without blanking the TFT display.

#### Scenario: Long press enters SEMI_SLEEP
- **WHEN** the primary button is held for ≥ 1000 ms in STATUS_MODE or DETAILS_MODE
- **THEN** the system SHALL enter SEMI_SLEEP and blank the TFT display.

#### Scenario: Any press restores from SEMI_SLEEP
- **WHEN** the primary button is pressed while in SEMI_SLEEP
- **THEN** the system SHALL restore the previous mode and turn on the TFT display.

### Requirement: Pico 2 W Secondary Button Interaction
The secondary button (GP13, active-LOW, pull-up) SHALL behave differently depending on the current mode:
- In STATUS_MODE: the button SHALL continue to drive the data logger lifecycle (IDLE → CONFIRM → ACTIVE and associated transitions) unchanged.
- In DETAILS_MODE: short press SHALL advance the SD file listing to the next page; long press SHALL have no effect.
- In all other modes (SEMI_SLEEP, MESSAGE_MODE): the button SHALL be ignored.

#### Scenario: Secondary button runs logger lifecycle in STATUS_MODE
- **WHEN** the secondary button is short-pressed while in STATUS_MODE and the logger is IDLE
- **THEN** the system SHALL begin the logger staging process (unchanged behaviour).

#### Scenario: Secondary button advances file page in DETAILS_MODE
- **WHEN** the secondary button is short-pressed while in DETAILS_MODE
- **THEN** the file listing SHALL advance to the next page (wrapping to first after last).

#### Scenario: Secondary button ignored outside STATUS_MODE and DETAILS_MODE
- **WHEN** the secondary button is pressed while in SEMI_SLEEP or MESSAGE_MODE
- **THEN** the system SHALL take no action.
