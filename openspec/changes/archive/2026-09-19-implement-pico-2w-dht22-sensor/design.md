## Context

The Pico 2 W firmware currently includes a stub `SensorReader` class in `boards/pico-2w/hardware/sensors.py` returning `None` values for temperature and humidity. See `proposal.md` for motivation. The Pico 1 W implementation (`boards/pico-1w/hardware/sensors.py`) provides a working, fault-tolerant MicroPython `dht.DHT22` integration.

## Goals / Non-Goals

**Goals:**
- Add `PIN_DHT22 = 15` in `boards/pico-2w/settings/config.py`.
- Migrate `SensorReader` in `boards/pico-2w/hardware/sensors.py` from stub to real `dht.DHT22` hardware reader.
- Handle hardware import/read failures gracefully with error counters and fallback state without interrupting asyncio loops.

**Non-Goals:**
- Adding additional physical sensors (e.g. ambient light sensors or BMP280) to Pico 2 W in this change.
- Altering the existing ST7735 display layouts, HTTP `/info` endpoint format, or CoAP sensor resource contracts.

## Decisions

### Decision 1: Shared Hardware Reader Implementation
- **Choice**: Use the exact `SensorReader` pattern from Pico 1 W (`dht.DHT22(Pin(15))`).
- **Rationale**: Keeps sensor error-handling, rounding (1 decimal place), and telemetry dictionary keys identical across all board implementations in the repository.
- **Alternatives Considered**: Creating a Pico 2 W specific driver. Rejected because MicroPython's `dht` module is standard across RP2040 and RP2350 ports.

### Decision 2: Pin Mapping Allocation
- **Choice**: Map DHT22 Data pin to GP15 (Pin 20).
- **Rationale**: GP15 is free on Pico 2 W (SPI0 uses GP16-GP19, TFT control uses GP20-GP21, SD CS uses GP22, Button uses GP14).

## Risks / Trade-offs

- **[Sensor Read Failures / Timing Timeouts]** → MicroPython `dht` reads can occasionally fail due to strict 1-wire timing. **Mitigation**: Catch exceptions during `.measure()`, retain previous valid readings, and increment `read_errors` count.
