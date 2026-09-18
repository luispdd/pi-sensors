# Pico DHT22 Screen Node

This folder contains the complete firmware for the `pico-1w` board.
This device integrates a DHT22 sensor and an SSD1306 OLED screen, communicating via the `iotmesh` protocol over CoAP.

## Deployment

This directory is self-contained. It includes the core logic as well as the shared libraries (e.g. `microcoapy`) required to run.

To deploy this firmware to the device, simply copy the entire contents of this folder to the root of the microcontroller's filesystem.

```bash
# Example deployment using mpremote:
mpremote fs cp -r ./* :
```

## Structure

* `main.py` - Entry point for the application.
* `lib/` - Contains all required dependencies (like `microcoapy` and `ssd1306.py`).
* `sensors.py`, `display.py`, `controls.py`, `state.py` - Core application modules.
