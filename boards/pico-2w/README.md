# Pico 2 W ST7735 TFT Node (`pico-2w`)

This directory contains the firmware for the `pico-2w` board (Raspberry Pi Pico 2 W / RP2350).
The board drives an ST7735 TFT display (128x160) and MicroSD card reader over a shared SPI0 peripheral bus, and participates in the `iotmesh` network over WiFi via CoAP and HTTP.

## Peripherals & Hardware Wiring

Both the ST7735 TFT display and the MicroSD card reader share the **SPI0** hardware bus. Chip Select (CS) pins enforce mutual exclusion.

| Peripheral | Signal | Pico 2 W Pin (GPIO) | Physical Pin |
|---|---|---|---|
| **Shared SPI0** | SCK | GP18 | Pin 24 |
| **Shared SPI0** | MOSI | GP19 | Pin 25 |
| **Shared SPI0** | MISO | GP16 | Pin 21 (SD MISO only) |
| **ST7735 TFT** | CS | GP17 | Pin 22 |
| **ST7735 TFT** | DC | GP20 | Pin 26 |
| **ST7735 TFT** | RESET | GP21 | Pin 27 |
| **SD Card** | CS | GP22 | Pin 29 |

## Capabilities

- **WiFi Network Connection**: Automatic connection & background keepalive loop via `NetworkManager`.
- **HTTP Server**: Serves telemetry JSON at `GET /info` and `GET /sensors`.
- **CoAP Server**: Implements IoTMesh protocol (UDP 5683), registering `.well-known/core` discovery and `/display` POST actuator.
- **TFT Display**: Renders network status, request count, and incoming remote CoAP messages.

## Structure

* `main.py` - Entry point and async orchestrator.
* `settings/` - `config.py` and `secrets.py` template.
* `services/` - `network_manager.py`, `webserver.py`, `coap_server.py`.
* `hardware/` - `display.py` (TFT driver wrapper with SPI arbitration), `sensors.py` (stub), `controls.py` (stub).
* `core/` - `state.py` application state management.
* `lib/` - Libraries: `ST7735.py`, `sysfont.py`, `sdcard.mpy`, `microcoapy/`.
* `test/` - Hardware validation scripts: `test_tft.py`, `test_sd.py`, `test_combined.py`, `test_sd_to_tft.py`.

## Deployment

Copy the entire contents of `boards/pico-2w/` to the root of the Pico 2 W filesystem:

```bash
# Example deployment using mpremote:
mpremote fs cp -r boards/pico-2w/* :
```
