## Context

The system runs on the Raspberry Pi Pico W microcontroller powered by MicroPython.
Constraints include:
- Limited RAM (~264KB SRAM, shared with MicroPython heap).
- DHT22 requires a 1-wire timing protocol with a minimum ~1-2s sampling period between successive reads to avoid self-heating and read timeouts.
- Single-threaded core execution where cooperative multitasking (`uasyncio`) is preferred over blocking calls or multi-threading to handle sensor reading, display refresh, and non-blocking HTTP request processing smoothly.
- OLED SSD1306 display is 128x64 (or 128x32) pixels with 8x8 character font (16 characters wide per line, 8 lines total on 128x64).

## Goals / Non-Goals

**Goals:**
- Provide a clean, modular MicroPython project structure.
- Use `uasyncio` for non-blocking concurrent operations: sensor polling, OLED screen rendering, WiFi keepalive, and HTTP request dispatching.
- Implement an atomic in-memory request counter that increments upon each WiFi `/sensors` request.
- Design an OLED display layout that clearly presents:
  1. Real-time temperature, humidity, and light state
  2. Full route for remote access (e.g. `http://<IP>/sensors`)
  3. Total requests served via WiFi (`Hits: <count>`)
- Load WiFi credentials securely from an untracked external `secrets.py` file (`src/secrets.py`, ignored by Git). If missing or invalid, display an error message on the OLED screen.
- Maintain all source code within `src/`, with external libraries located in `src/lib/` (including `src/lib/ssd1306.py` from `stlehmann/micropython-ssd1306`).

**Non-Goals:**
- Cloud telemetry streaming (MQTT, InfluxDB, Home Assistant discovery).
- Persistent historical data storage on flash filesystem (SPI flash wear avoidance).
- TLS/HTTPS support (computationally expensive on Pico W; local network HTTP is sufficient).

## Decisions

### 1. Concurrency & State Architecture: Shared `AppState` Container
- **Rationale**: An in-memory object holds the latest valid sensor readings (`temperature`, `humidity`, `light_level`), network info (`ip_address`, `wifi_status`), and `request_count`.
- Coroutines:
  - `sensor_task`: Updates `temperature`, `humidity`, `light_detected`.
  - `http_server_task`: Listens on port 80, increments `request_count` on `/sensors`, and responds with JSON.
  - `display_task`: Renders the screen from `AppState` at regular refresh intervals.
  - `wifi_watchdog_task`: Monitors link and attempts reconnection if dropped.
- **Format of `/sensors` response**:
  ```json
  {
    "temperature_c": 22.4,
    "humidity_pct": 58.1,
    "light": "light",
    "light_detected": true,
    "requests_served": 42,
    "uptime_s": 345,
    "status": "ok"
  }
  ```

### 2. OLED Screen Layout Design (128x64)
- MicroPython standard 8x8 character font provides 16 characters per line, with 8 total lines:
  - Line 0 (y=0):  `T:23.4C  H:55%`
  - Line 1 (y=10): `Light: Bright`
  - Line 2 (y=18): `----------------`
  - Line 3 (y=26): `URL for Data:`
  - Line 4 (y=36): `http://<IP>`
  - Line 5 (y=46): `/sensors`
  - Line 6 (y=56): `Reqs: <count>`
- If the IP is long (e.g., 15 chars like `192.168.100.250`), `http://` on line 4 and IP + `/sensors` fit within 16 characters per line cleanly.

### 3. Pin Mapping & Hardware Configuration
- Pico Pin 36 (3V3 OUT) & Pin 38 (GND) power the breadboard rails.
- SSD1306 OLED: I2C ID 0, SDA = GP0 (Pin 1), SCL = GP1 (Pin 2), Freq = 400kHz.
- DHT22: GP15 (Pin 20) with 1-second to 2-second sampling interval.
- LM393 DO: GP14 (Pin 19) configured as `machine.Pin.IN`.

## Risks / Trade-offs

- **[Risk] DHT22 Read Glitches**: DHT22 sensors occasionally produce `ETIMEDOUT` or checksum errors due to single-wire timing sensitivity.
  - *Mitigation*: Wrap sensor read in try/except; retain previous reading, and retry on next tick.
- **[Risk] WiFi Drops / Router Reboot**: Pico W WiFi may disconnect.
  - *Mitigation*: Background watchdog checks connection and reconnects non-blockingly.
- **[Risk] High Request Rate / Memory Pressure**: Multiple rapid WiFi requests could exhaust heap.
  - *Mitigation*: Keep connection handling minimal, close sockets immediately, and run `gc.collect()` periodically.
