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
* `lib/` - Contains all required dependencies (like `microcoapy`, `ssd1306.py`, and `umqtt/`).
* `sensors.py`, `display.py`, `controls.py`, `state.py` - Core application modules.

## Dependencies & Installation

To install `umqtt.simple` via `mip`:

```bash
# Using mpremote CLI:
mpremote mip install umqtt.simple
```

Or from the MicroPython REPL:

```python
import mip
mip.install("umqtt.simple")
```
