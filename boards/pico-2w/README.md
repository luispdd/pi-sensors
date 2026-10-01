# Pico 2 W ST7735 TFT Node (`pico-2w`)

This directory contains the firmware for the `pico-2w` board (Raspberry Pi Pico 2 W / RP2350).
The board drives an ST7735 TFT display (128x160) and MicroSD card reader over a shared SPI0 peripheral bus, and participates in the `iotmesh` network over WiFi via CoAP and HTTP.

## Peripherals & Hardware Wiring

The ST7735 TFT display and the MicroSD card reader share the **SPI0** hardware bus. Chip Select (CS) pins enforce mutual exclusion. Analog sensors utilize dedicated ADC channels, with the microphone referenced to low-noise analog ground (AGND).

| Peripheral | Signal | Pico 2 W Pin (GPIO) | Physical Pin | Notes |
|---|---|---|---|---|
| **AM312 PIR** | OUT | GP12 | Pin 16 | Motion sensor digital input (active HIGH) |
| **Data Logger Button** | In | GP13 | Pin 17 | Dedicated logging button (active LOW, pull-up) |
| **User Button** | In | GP14 | Pin 19 | Reset/Acknowledge button (active LOW, pull-up) |
| **DHT22** | DATA | GP15 | Pin 20 | Temp/Humidity 1-Wire data line |
| **MicroSD Card** | MISO | GP16 | Pin 21 | Shared SPI0 MISO (SD only) |
| **ST7735 TFT** | CS | GP17 | Pin 22 | Active-LOW TFT chip select |
| **Shared SPI0** | SCK | GP18 | Pin 24 | Shared clock for TFT (20MHz) & SD (10MHz) |
| **Shared SPI0** | MOSI | GP19 | Pin 25 | Shared data line (TFT SDA, SD MOSI) |
| **ST7735 TFT** | DC | GP20 | Pin 26 | Data / Command selector |
| **ST7735 TFT** | RESET | GP21 | Pin 27 | Active-LOW hardware reset pulse |
| **MicroSD Card** | CS | GP22 | Pin 29 | Active-LOW SD chip select |
| **ALS-PT19** | OUT | GP26 | Pin 31 | ADC0 ambient light sensor |
| **MAX4466 Mic** | OUT | GP27 | Pin 32 | ADC1 electret microphone analog output |
| **Analog Ground** | AGND | — | Pin 33 | Low-noise ground reference for MAX4466 & ADC |
| **System Power** | 3V3(OUT) | — | Pin 36 | 3.3V power rail (RT6154A SMPS) |


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
