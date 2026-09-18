## 1. Rename Board: pico-dh22-screen → pico-1w

- [x] 1.1 Rename `boards/pico-dh22-screen` to `boards/pico-1w` using `git mv`, and verify the directory exists at the new path with the same file count.
- [x] 1.2 Update `boards/pico-1w/README.md` to replace `pico-dh22-screen` with `pico-1w` in the board name reference, and verify the file contains no remaining occurrences of the old name.
- [x] 1.3 Update all `pico-dh22-screen` references in `openspec/changes/interactive-alert-and-display-cleanup/tasks.md` (7 occurrences) to `pico-1w`, and verify with grep that zero occurrences remain.
- [x] 1.4 Update the `pico-dh22-screen` reference in `openspec/changes/interactive-alert-and-display-cleanup/design.md` (line 47) to `pico-1w`, and verify with grep that zero occurrences remain.
- [x] 1.5 Verify with `grep -r "pico-dh22-screen" .` that zero references to the old name remain anywhere in the project.

## 2. Board Configuration & Settings

- [x] 2.1 Create `boards/pico-2w/settings/config.py` absorbing all constants from `pi-screen-camera/src/pins.py` (SPI bus, TFT, SD card, clock speeds, display geometry, MADCTL) and adding WiFi credential loading, CoAP/HTTP config, and device identity defaults (`DEVICE_ID = "pico-2w"`, `DEVICE_TYPE = "rp2350"`). Verify with `python3 -m py_compile`.
- [x] 2.2 Create `boards/pico-2w/settings/secrets.py.example` with the WiFi credential template matching `pico-1w`, and verify the file exists.

## 3. Core Application State

- [x] 3.1 Create `boards/pico-2w/core/state.py` adapted from `pico-1w`'s `core/state.py`, retaining `MODE_SENSOR_DISPLAY`, `MODE_SEMI_SLEEP`, `MODE_MESSAGE`, caller resolution, node caching, and `to_dict()`. Sensor fields default to `None`. Verify with `python3 -m py_compile`.

## 4. Hardware Modules

- [x] 4.1 Create `boards/pico-2w/hardware/display.py` wrapping the ST7735 TFT driver with SPI bus arbitration (CS exclusion, dynamic clock switching). Provide the same public interface as `pico-1w`'s `OLEDDisplay`: `clear()`, `power_off()`, `show_splash()`, `show_message()`, `render_status()`, `update_from_state()`. Verify with `python3 -m py_compile`.
- [x] 4.2 Create `boards/pico-2w/hardware/sensors.py` as a stub with `SensorReader` returning `None` for all readings, and `get_sensor_reader()` / `read_sensors()` functions matching `pico-1w`'s interface. Verify with `python3 -m py_compile`.
- [x] 4.3 Create `boards/pico-2w/hardware/controls.py` as a stub with `Button` and `AlertLED` classes where all methods are safe no-ops (no pin initialization). Verify with `python3 -m py_compile`.

## 5. Service Modules

- [x] 5.1 Create `boards/pico-2w/services/network_manager.py` adapted from `pico-1w`'s version, importing from `settings.config`. Verify with `python3 -m py_compile`.
- [x] 5.2 Create `boards/pico-2w/services/webserver.py` adapted from `pico-1w`'s version, importing from `settings.config` and `core.state`. Verify with `python3 -m py_compile`.
- [x] 5.3 Create `boards/pico-2w/services/coap_server.py` adapted from `pico-1w`'s version with device identity defaults `pico-2w`/`rp2350`. Sensor endpoints return `null` gracefully when `app_state` values are `None`. CoRE Link Format discovery exposes the display as actuator. Verify with `python3 -m py_compile`.

## 6. Application Entry Point

- [x] 6.1 Create `boards/pico-2w/main.py` as the async orchestrator adapted from `pico-1w`, spawning sensor_task (stub reader), display_task (TFT wrapper), button_task (stub), network_task, server_task, and coap_task. Verify with `python3 -m py_compile`.

## 7. Library Files

- [x] 7.1 Copy `ST7735.py` from `pi-screen-camera/src/lib/ST7735.py` to `boards/pico-2w/lib/ST7735.py` and verify file exists with matching line count (924 lines).
- [x] 7.2 Copy `sysfont.py` from `pi-screen-camera/src/lib/sysfont.py` to `boards/pico-2w/lib/sysfont.py` and verify file exists with matching line count (211 lines).
- [x] 7.3 Copy `sdcard.mpy` binary from `pi-screen-camera/src/lib/sdcard.mpy` to `boards/pico-2w/lib/sdcard.mpy` and verify checksums match.
- [x] 7.4 Copy the `microcoapy/` directory from `boards/pico-1w/lib/microcoapy/` to `boards/pico-2w/lib/microcoapy/` and verify all files are present.

## 8. Test Scripts

- [x] 8.1 Migrate `test_sd.py` from `pi-screen-camera/src/test/` to `boards/pico-2w/test/`, updating `import pins` to `from settings import config` and all `pins.XXX` references to `config.XXX`. Verify with `python3 -m py_compile`.
- [x] 8.2 Migrate `test_tft.py` with the same import path updates. Verify with `python3 -m py_compile`.
- [x] 8.3 Migrate `test_combined.py` with the same import path updates. Verify with `python3 -m py_compile`.
- [x] 8.4 Migrate `test_sd_to_tft.py` with the same import path updates. Verify with `python3 -m py_compile`.

## 9. Documentation

- [x] 9.1 Create `boards/pico-2w/README.md` documenting the board type (Pico 2 W / RP2350), hardware (ST7735 TFT, SD card, shared SPI0), current capabilities (WiFi, HTTP, CoAP with display actuator), wiring table, and deployment instructions. Verify the file exists and contains the wiring table.
- [x] 9.2 Update the root `README.md` to reflect the new project structure with both `pico-1w/` and `pico-2w/` boards, replacing all references to `pico-dh22-screen` and adding a section for the pico-2w board capabilities. Verify with `grep -c "pico-dh22-screen" README.md` returning 0.

## 10. Final Verification

- [x] 10.1 Run `grep -r "pico-dh22-screen" .` from the project root and verify zero matches remain across the entire project.
- [x] 10.2 Run `python3 -m py_compile` on all new `.py` files under `boards/pico-2w/` to verify syntax correctness.
- [x] 10.3 Verify `find boards/pico-2w -type f | wc -l` returns the expected file count (matching the design's directory structure).
