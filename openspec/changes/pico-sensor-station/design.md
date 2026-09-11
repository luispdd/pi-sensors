## Context

The system runs on the Raspberry Pi Pico W microcontroller powered by MicroPython.
Constraints include:
- Limited RAM (~264KB SRAM, shared with MicroPython heap).
- DHT22 requires a 1-wire timing protocol with a minimum ~1-2s sampling period between successive reads to avoid self-heating and read timeouts.
- Single-threaded core execution where cooperative multitasking (`uasyncio`) is preferred over blocking calls or multi-threading to handle sensor reading, display refresh, and non-blocking HTTP request processing smoothly.

## Goals / Non-Goals

**Goals:**
- Provide a clean, modular MicroPython project structure.
- Use `uasyncio` for non-blocking concurrent operations: sensor polling, OLED screen rendering, WiFi keepalive, and HTTP request dispatching.
- Implement robust error tolerance: temporary DHT22 checksum glitches or network drops will not cause watchdog reset or lock the device.
- Keep WiFi credentials and hardware pin assignments in a separate, easily editable configuration file (`config.py`).
- Include the standard, lightweight MicroPython `ssd1306.py` driver file.

**Non-Goals:**
- Cloud telemetry streaming (MQTT, InfluxDB, Home Assistant discovery) - can be added in a future iteration.
- Persistent historical data storage on flash filesystem (SPI flash wear avoidance).
- TLS/HTTPS support (computationally expensive on Pico W; local network HTTP is sufficient).

## Decisions

### 1. Concurrency: `uasyncio` Cooperative Multitasking
- **Rationale**: The Pico W needs to simultaneously serve HTTP traffic without interrupting OLED display updates or timing out DHT22 queries. Traditional blocking sockets would freeze the UI and sensors while waiting for incoming HTTP connections.
- **Alternatives**:
  - *Standard blocking sockets with timeout*: Leads to jitter in OLED refresh and delays in HTTP responses.
  - *_thread module*: Dual-core MicroPython is prone to race conditions, memory alloc deadlocks, and WiFi driver lockups on Pico W.

### 2. State Architecture: Shared `SensorState` Container
- **Rationale**: An in-memory object holds the latest valid `temperature`, `humidity`, `light_level`, `last_updated`, and `wifi_status`. The sensor task writes to it, while the OLED task and HTTP request handler read from it asynchronously.
- **Format of `/sensors` response**:
  ```json
  {
    "temperature_c": 22.4,
    "humidity_pct": 58.1,
    "light": "light",
    "light_detected": true,
    "uptime_s": 345,
    "status": "ok"
  }
  ```

### 3. Pin Mapping & Hardware Configuration
- Pico Pin 36 (3V3 OUT) & Pin 38 (GND) power the breadboard rails.
- SSD1306 OLED: I2C ID 0, SDA = GP0 (Pin 1), SCL = GP1 (Pin 2), Freq = 400kHz.
- DHT22: GP15 (Pin 20) with 1-second to 2-second sampling interval.
- LM393 DO: GP14 (Pin 19) configured as `machine.Pin.IN`.

## Risks / Trade-offs

- **[Risk] DHT22 Read Glitches**: DHT22 sensors occasionally produce `ETIMEDOUT` or checksum errors due to single-wire timing sensitivity.
  - *Mitigation*: Wrap sensor read in try/except; on exception, retain previous reading, log a warning, and retry on next tick.
- **[Risk] WiFi Drops / Router Reboot**: Pico W WiFi may disconnect or hang if router reconnects.
  - *Mitigation*: A background watchdog coroutine checks `wlan.isconnected()` and triggers non-blocking reconnection when disconnected.
- **[Risk] Memory Fragmentation**: Continuous HTTP socket handling can fragment the MicroPython heap over time.
  - *Mitigation*: Trigger `gc.collect()` periodically after handling HTTP requests.
