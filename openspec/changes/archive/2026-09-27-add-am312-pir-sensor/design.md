## Context

See `proposal.md` for motivation. Both the Raspberry Pi Pico 2 W and Waveshare ESP32-C6-Zero run MicroPython with an asynchronous architecture (`uasyncio`), modular sensor drivers, and dynamic SenML export. This design establishes how the AM312 PIR motion sensor is sampled, aggregated, and persisted without burdening constrained microcontrollers or modifying local displays.

## Goals / Non-Goals

**Goals:**
- Provide continuous motion activity tracking via active-time duty cycle percentage over a 300-second (5-minute) rolling window.
- Implement an O(1), zero-allocation circular buffer driver (`bytearray(300)`) resilient to MicroPython garbage collection.
- Sample the AM312 digital signal non-blockingly at 1.0 Hz in a cooperative asyncio task.
- Map hardware GPIOs: `GP12` (Pin 16) on Raspberry Pi Pico 2 W and `GPIO 4` on Waveshare ESP32-C6-Zero.
- Extend Pico 2 W SD card logging (`sd_storage.py`, `data_logger.py`, `log_sync.py`) to record `motion_pct` as a 6th CSV column with backward compatibility.

**Non-Goals:**
- Rendering motion values on local OLED or TFT displays (per requirements, motion is exclusively visualised on the dashboard).
- Schema alterations to the controller backend database (the SQLite `readings` table stores metrics dynamically as JSON).
- Hardcoding metric keys or colors in the frontend dashboard (the Angular `CapabilitiesService` dynamically registers and styles new metrics).

## Decisions

### Decision 1: Asyncio Coroutine Polling at 1 Hz vs Hardware IRQ

- **Choice**: A cooperative `asyncio` background task sampling `pin.value()` once every 1.0 second.
- **Rationale**: The AM312 PIR sensor hardware latches output `HIGH` for ~2 to 3 seconds on motion detection. A 1.0-second sample tick is guaranteed to observe any active pulse without missing events. In MicroPython, hardware pin interrupts (`Pin.irq`) and hardware timers run in hard interrupt context where memory allocation is prohibited and context collisions with the CYW43439 / ESP-Hosted WiFi stack can occur.
- **Alternatives Considered**:
  - *Hardware Pin IRQ (`Pin.IRQ_RISING` / `Pin.IRQ_FALLING`)*: Microsecond-precise timestamps, but vulnerable to interrupt bounce, ISR allocation limits, and Wi-Fi collision panics.
  - *`machine.Timer` periodic callback*: Subject to hard timer interrupt constraints in MicroPython.

### Decision 2: Pre-allocated 300-Sample Ring Buffer (`bytearray`)

- **Choice**: Pre-allocate a 300-byte `bytearray(300)` representing 1 sample per second over the 300-second window, maintaining a rolling sum of active ticks.
- **Rationale**:
  - Memory consumption is strictly 300 bytes of heap once at boot.
  - Updating the moving window is $O(1)$ and produces zero garbage collection overhead:
    $$\text{active\_count} = \text{active\_count} + \text{new\_tick} - \text{buffer}[\text{head}]$$
    $$\text{buffer}[\text{head}] = \text{new\_tick}$$
    $$\text{head} = (\text{head} + 1) \pmod{300}$$
- **Alternatives Considered**:
  - *Standard Python `list` with `.append()` and `.pop(0)`*: Constantly allocates and frees heap nodes, accelerating memory fragmentation.
  - *Bit-packed integer or bitarray*: Saves ~260 bytes of RAM, but introduces bitwise shift complexity and integer allocations in MicroPython without meaningful benefit.

### Decision 3: Backward-Compatible 6-Column SD Card Logging

- **Choice**: Append `motion_pct` as the 6th column: `timestamp,device_id,temperature_c,humidity_pct,light_pct,motion_pct`.
- **Rationale**:
  - In `sd_storage.py`, if a board does not supply motion, an empty string `""` is written (e.g. `2026-09-26T18:00:00Z,pico-1w,21.5,45.0,,`).
  - In `log_sync.py`, row parsing checks `len(parts) >= 6` for motion, while seamlessly processing legacy 4-column (temp, hum) and 5-column (temp, hum, light) lines.
- **Alternatives Considered**:
  - *Creating separate CSV files for motion*: Adds file handle overhead and complicates synchronization.

## Risks / Trade-offs

- **[Risk] Board warmup period before 300 samples elapse**
  → *Mitigation*: During the first 300 seconds after boot, divide active ticks by `elapsed_samples` rather than 300 so the reported duty cycle is accurate immediately without waiting 5 minutes.
- **[Risk] Pin floating when motion is absent**
  → *Mitigation*: Configure the input pin with internal pull-down (`Pin.PULL_DOWN`), ensuring steady 0V reference.
- **[Risk] SD card buffer memory limit on Pico 2 W**
  → *Mitigation*: Buffer rows remain lightweight dictionaries (`"motion": <float>`), well within the existing 13-row buffer ceiling per active node.
