## Why

The `pi-screen-camera` project — a standalone Pico 2 W (RP2350) board driving an ST7735 TFT display and SD card reader — currently lives in a separate repository with only hardware validation tests. It needs to be integrated into this monorepo as a new board type so it can participate in the IoTMesh network alongside the existing sensor station. The existing board should also be renamed from `pico-dh22-screen` to `pico-1w` to establish a naming convention based on board generation rather than capabilities (which may change over time).

## What Changes

- **Rename** `boards/pico-dh22-screen` → `boards/pico-1w` across the codebase and all openspec references.
- **Add** `boards/pico-2w/` as a new board type for the Raspberry Pi Pico 2 W (RP2350), mirroring the directory structure of `pico-1w` (`settings/`, `hardware/`, `services/`, `core/`, `lib/`, `test/`).
- **Integrate WiFi, HTTP, and CoAP services** into `pico-2w` so the node is discoverable on the mesh and its TFT display is exposed as a remote actuator (`POST /display`).
- **Adapt the display service** for the ST7735 TFT (128×160, SPI) instead of the SSD1306 OLED (128×64, I2C), including shared SPI bus arbitration with the SD card reader.
- **Provide stub sensor and controls modules** in `pico-2w` (DHT22, button, alert LED) matching the `pico-1w` interface, ready for future hardware integration.
- **Migrate hardware validation test scripts** from the source project into `boards/pico-2w/test/`, updating import paths to match the monorepo convention.
- **Update the root README** to document both board types.

## Capabilities

### New Capabilities

- `hardware/pico-2w-tft-display`: Hardware-specific spec for the ST7735 TFT display on the Pico 2 W, covering SPI bus configuration, shared bus arbitration with the SD card, and display driver initialization.

### Modified Capabilities

- `core/display-service`: The display service spec currently references the SSD1306 OLED exclusively. It needs to be generalized to support multiple display hardware types (SSD1306 OLED on pico-1w, ST7735 TFT on pico-2w) while preserving the same display mode semantics.
- `core/iotmesh/coap-node`: The CoAP node spec references `GET /sensors/light` which was already removed from the implementation. The spec should also clarify that sensor endpoints may return `null` values on boards where sensors are not yet wired.
- `core/iotmesh/display-actuator`: The display actuator spec references OLED-specific behavior. It needs to be generalized to work with any display type while preserving the same CoAP interface and mode semantics.

## Impact

- **Directory structure**: `boards/pico-dh22-screen/` renamed to `boards/pico-1w/`; new `boards/pico-2w/` created.
- **OpenSpec references**: All `pico-dh22-screen` path references in `openspec/changes/interactive-alert-and-display-cleanup/` updated.
- **Root README**: Project structure diagram and deployment documentation updated for both boards.
- **New library dependencies**: `ST7735.py`, `sysfont.py`, `sdcard.mpy` added to `boards/pico-2w/lib/`.
- **Shared library reuse**: `microcoapy/` copied into `pico-2w/lib/` (same pattern as `pico-1w` — each board is self-contained for deployment).
