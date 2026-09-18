# Pico 2 W TFT Display & SPI Bus Specification

## Purpose

Defines the hardware interface and bus arbitration rules for the ST7735 TFT color display and SD card reader on the Pico 2 W (RP2350), both sharing a single SPI0 peripheral.

## Requirements

### Requirement: SPI0 Shared Bus Configuration
The system SHALL initialize a single SPI0 hardware peripheral with SCK on GP18, MOSI on GP19, and MISO on GP16 for communication with both the ST7735 TFT display and the SD card reader.

#### Scenario: SPI0 bus initialized
- **WHEN** the board firmware initializes hardware
- **THEN** SPI0 SHALL be configured with shared SCK (GP18), MOSI (GP19), and MISO (GP16) pins

### Requirement: Chip Select Mutual Exclusion
The system SHALL enforce mutual exclusion on the SPI0 bus by ensuring only one chip select pin is driven LOW at any time: TFT_CS (GP17) or SD_CS (GP22). Both chip select lines SHALL idle HIGH (3.3V).

#### Scenario: TFT access with SD idle
- **WHEN** the system accesses the TFT display
- **THEN** TFT_CS (GP17) SHALL be driven LOW and SD_CS (GP22) SHALL remain HIGH

#### Scenario: SD access with TFT idle
- **WHEN** the system accesses the SD card
- **THEN** SD_CS (GP22) SHALL be driven LOW and TFT_CS (GP17) SHALL remain HIGH

### Requirement: Dynamic SPI Clock Speed Switching
The system SHALL switch the SPI0 clock speed per device before each access:
- SD card identification/init: 400 kHz
- SD card data transfers: 10 MHz
- TFT pixel writes: 20 MHz

#### Scenario: Clock speed set for TFT
- **WHEN** the system begins a TFT display operation
- **THEN** SPI0 baudrate SHALL be set to 20 MHz before asserting TFT_CS

#### Scenario: Clock speed set for SD init
- **WHEN** the system initializes the SD card
- **THEN** SPI0 baudrate SHALL be set to 400 kHz for the identification phase

#### Scenario: Clock speed set for SD data
- **WHEN** the system reads or writes SD card data after initialization
- **THEN** SPI0 baudrate SHALL be set to 10 MHz

### Requirement: ST7735 TFT Display Initialization
The system SHALL initialize the ST7735 TFT display (128×160 pixels, 16-bit RGB565 color) using the `initr()` sequence with a hardware reset pulse on GP21 (RESET) of at least 10 ms, and a data/command selector on GP20 (DC).

#### Scenario: TFT display initialized successfully
- **WHEN** the display hardware module powers on
- **THEN** the ST7735 driver SHALL perform a hardware reset via GP21, execute the `initr()` initialization sequence, and set RGB color mode (MADCTL = 0x00)

### Requirement: ST7735 Display Driver Dependency
The system SHALL use the `boochow/MicroPython-ST7735` driver located at `boards/pico-2w/lib/ST7735.py` and the companion `sysfont.py` bitmap font for rendering text on the TFT display.

#### Scenario: Driver loading from lib directory
- **WHEN** the display service initializes on the pico-2w board
- **THEN** it SHALL import the `TFT` class from the `ST7735` module and `sysfont` from `sysfont` module located in `lib/`

### Requirement: SD Card Driver Dependency
The system SHALL use the MicroPython `sdcard` driver located at `boards/pico-2w/lib/sdcard.mpy` for SPI-based SD card access.

#### Scenario: SD card driver available
- **WHEN** firmware accesses the SD card
- **THEN** it SHALL import the `SDCard` class from the `sdcard` module located in `lib/`
