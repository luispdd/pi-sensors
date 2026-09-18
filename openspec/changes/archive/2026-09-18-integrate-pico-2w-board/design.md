## Context

The monorepo currently has a single board type at `boards/pico-dh22-screen/` for the Raspberry Pi Pico W (RP2040), structured into `settings/`, `hardware/`, `services/`, `core/`, and `lib/` directories. A separate repository (`pi-screen-camera`) contains hardware validation tests for a Pico 2 W (RP2350) with an ST7735 TFT display and SD card reader sharing SPI0, but has no networking or application logic.

See `proposal.md` for full motivation. The specs define the behavioral contracts for the new and modified capabilities.

## Goals / Non-Goals

**Goals:**
- Rename `boards/pico-dh22-screen` → `boards/pico-1w` and update all references.
- Create `boards/pico-2w/` mirroring the established directory structure with working WiFi, HTTP, and CoAP services.
- Expose the pico-2w TFT display as a discoverable IoTMesh actuator via CoAP.
- Provide interface-compatible stub modules for sensors and controls so the codebase compiles and runs cleanly.
- Migrate hardware validation tests from the source project with updated imports.

**Non-Goals:**
- Wiring or implementing DHT22 sensor hardware on the pico-2w board.
- Wiring or implementing a physical button or alert LED on the pico-2w board.
- Refactoring pico-1w code — it remains untouched beyond the rename.
- Extracting shared code into `libs/` — each board remains self-contained for deployment to device root.

## Decisions

### 1. Board Naming Convention
- **Decision**: Rename `pico-dh22-screen` → `pico-1w`; new board is `pico-2w`.
- *Rationale*: Names based on board generation (Pico W = 1w, Pico 2 W = 2w) are stable as capabilities change. The old name `pico-dh22-screen` couples the identity to current peripherals.

### 2. Self-Contained Board Directories
- **Decision**: Each board under `boards/` contains its own complete copy of all libraries (e.g., `microcoapy/`, display drivers) and is independently deployable to a device.
- *Alternative considered*: Shared `libs/` directory with symlinks or imports. Rejected because MicroPython boards are deployed by copying the board directory to the device root — shared dependencies would break deployment.
- *Rationale*: Deployment to Pico devices works by copying `boards/<board-name>/*` to the device's root filesystem. Each board must be self-contained.

### 3. TFT Display Wrapper (hardware/display.py)
- **Decision**: Create a new `hardware/display.py` for pico-2w that wraps ST7735 + sysfont, providing the same public interface as pico-1w's SSD1306 wrapper (`OLEDDisplay`): `clear()`, `power_off()`, `show_splash()`, `show_message()`, `render_status()`, `update_from_state()`.
- *Alternative considered*: Abstract base class shared between boards. Rejected because MicroPython on constrained devices benefits from simple, direct implementations without inheritance overhead.
- *Rationale*: Same interface means `main.py`, `coap_server.py`, and `webserver.py` can use the display module interchangeably without conditionals.

### 4. SPI Bus Arbitration in Display Module
- **Decision**: The `hardware/display.py` module on pico-2w SHALL manage SPI bus arbitration internally — switching clock speed and CS lines before each TFT access.
- *Rationale*: The display module is the primary consumer of the TFT. Encapsulating bus switching in the display module keeps the rest of the application unaware of shared-bus complexity. SD card access (future) will follow the same pattern through a separate module.

### 5. Pin Configuration: Absorb pins.py into settings/config.py
- **Decision**: The source project's `pins.py` constants are absorbed into `boards/pico-2w/settings/config.py`, alongside WiFi, CoAP, and app-level configuration — matching the pico-1w convention.
- *Alternative considered*: Keeping a separate `pins.py` at board root. Rejected because it diverges from the established monorepo convention and would require test scripts to use different import patterns per board.
- *Rationale*: Consistency across boards. All config lives in one module.

### 6. Test Script Import Path Migration
- **Decision**: Test scripts migrated to `boards/pico-2w/test/` will replace `import pins` with `from settings import config` and reference constants as `config.SPI_SCK` etc.
- *Rationale*: Follows the monorepo convention. The `sys.path` setup in each test script will add the board root to the path so `settings.config` is importable.

### 7. Stub Sensor and Controls Modules
- **Decision**: `hardware/sensors.py` provides a `SensorReader` that always returns `None` for temperature/humidity. `hardware/controls.py` provides `Button` and `AlertLED` classes where all methods are safe no-ops (no pin initialization).
- *Rationale*: Allows `main.py` to import and call these modules without conditionals or import guards. Future hardware integration only requires filling in the pin assignments and hardware init.

### 8. CoAP Service: Sensor Endpoints Return Null Gracefully
- **Decision**: The CoAP server on pico-2w registers `/sensors`, `/sensors/temperature`, and `/sensors/humidity` endpoints. When sensors return `None`, the SenML `v` field is `null`.
- *Alternative considered*: Omitting sensor endpoints entirely on pico-2w. Rejected because all boards should present a consistent CoAP interface, and `null` values clearly signal "not yet available" to mesh clients.
- *Rationale*: Uniform mesh discovery. Any IoTMesh client querying `/.well-known/core` gets the same endpoint structure regardless of board type.

### 9. Device Identity Defaults
- **Decision**: pico-2w defaults to `DEVICE_ID = "pico-2w"` and `DEVICE_TYPE = "rp2350"`.
- *Rationale*: Distinguishes this board from pico-1w (`rp2040`) in mesh discovery responses.

### 10. Directory Structure for pico-2w
- **Decision**: Full structure matching pico-1w:
  ```
  boards/pico-2w/
  ├── main.py
  ├── README.md
  ├── core/state.py
  ├── hardware/
  │   ├── display.py     (ST7735 TFT wrapper)
  │   ├── sensors.py     (stub)
  │   └── controls.py    (stub)
  ├── services/
  │   ├── network_manager.py
  │   ├── coap_server.py
  │   └── webserver.py
  ├── settings/
  │   ├── config.py
  │   ├── secrets.py.example
  │   └── secrets.py     (.gitignored)
  ├── lib/
  │   ├── ST7735.py
  │   ├── sysfont.py
  │   ├── sdcard.mpy
  │   └── microcoapy/
  └── test/
      ├── test_sd.py
      ├── test_tft.py
      ├── test_combined.py
      └── test_sd_to_tft.py
  ```

## Risks / Trade-offs

- **[Risk] Code duplication across boards** → *Mitigation*: Accepted trade-off for deployment simplicity. Each board is self-contained so `cp -r boards/<name>/* :` deploys to device. Shared patterns may be extracted to `libs/` in the future if boards multiply.
- **[Risk] OpenSpec reference updates may be incomplete** → *Mitigation*: Post-implementation grep for `pico-dh22-screen` to verify zero remaining references.
- **[Risk] Test scripts may have import path issues after migration** → *Mitigation*: Each test script updates its `sys.path` setup to include the board root directory for `settings.config` imports. Verify with `python3 -m py_compile` on each test file.
- **[Risk] Binary .mpy file may be architecture-specific** → *Mitigation*: The `sdcard.mpy` from the source project was compiled for the RP2350 and should work as-is. If issues arise, the `.py` source can be installed via `mip.install('sdcard')` on-device.
