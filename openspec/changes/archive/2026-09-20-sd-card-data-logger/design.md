## Context

The Pico 2W runs MicroPython on an RP2350. It has an ST7735 TFT (SPI0, 20 MHz, CS=GP17) and an SD card slot (SPI0, 10 MHz, CS=GP22) sharing the same SPI bus. The `lib/sdcard.mpy` driver and the SPI-arbitration skeleton in `TFTDisplay._acquire_bus()` are already in place. The main loop uses `uasyncio` with one task per subsystem. An existing `Button` class on GP14 drives the mode state machine; the `CoapServer` handles multicast discovery passively via `_handle_response`. See `proposal.md` for motivation.

## Goals / Non-Goals

**Goals:**
- Per-device daily CSV logging to SD card with append-resume
- Five-stage logger button UX on GP13 (IDLE → STAGING → CONFIRM → ACTIVE → flush/IDLE)
- NTP-gated session start with clear error surfacing
- Active CoAP multicast discovery filtered by resource type
- Integrated TFT status section; CONFIRM screen replaces normal display
- `GET /logger` CoAP endpoint; `/logger` in `.well-known/core`

**Non-Goals:**
- Log compression or binary file formats
- SD card hot-swap detection
- Remote triggering of a logging session (button-only control)
- Timezone conversion (UTC only)
- Changing the pico-1w firmware

## Decisions

### D1: SPI bus arbitration via shared object + speed reinit

Both TFT and SD must not assert CS simultaneously. The approach: `TFTDisplay` owns the `SPI` object and already calls `spi.init(baudrate=TFT_SPEED)` + `sd_cs.value(1)` in `_acquire_bus()`. `SDStorage` will receive the same `SPI` object reference and will call `spi.init(baudrate=SD_SPEED)` + `tft_cs.value(1)` before any SD access, then release by setting `sd_cs.value(1)` and returning control.

**Alternative considered**: Two separate SPI objects on the same pins. MicroPython does not reliably support this — both would fight over the hardware registers.

**Alternative considered**: A mutex/lock around SPI access. `uasyncio` uses cooperative scheduling; a blocking lock is unnecessary since SD writes happen only during flush (a bounded async step), not concurrently with TFT draws. Simple coding discipline (flush during a display task sleep window) is sufficient.

### D2: Logger state as orthogonal fields in AppState, not a new MODE_*

Logger state (`LOGGER_IDLE/STAGING/CONFIRM/ACTIVE`) is kept in `AppState.logger_state` separately from the display mode (`MODE_SENSOR_DISPLAY/SEMI_SLEEP/MESSAGE`). This avoids creating a combinatorial explosion of mode values and lets both state machines evolve independently.

The display task reads both `app_state.mode` and `app_state.logger_state` at render time and chooses the appropriate layout.

**Alternative considered**: A new `MODE_LOGGER_CONFIRM` display mode. Rejected because it would force the logger button logic into the existing button task and couple two independent concerns.

### D3: CoAP discovery — fire multicast, collect for 3 s, filter by rt=

During STAGING the logger fires `coap.getNonConf("224.0.1.187", 5683, ".well-known/core")`. The existing `_handle_response` callback is extended to detect sensor resource types in the CoRE Link Format string and populate a new `AppState.log_active_nodes` dict (`{ip: device_id}`) separately from the general `known_nodes`. A 3-second `asyncio.sleep` window lets responses arrive before CONFIRM is entered.

Resource type detection: scan the CoRE Link Format payload for `rt="temperature"` or `rt="humidity"` using simple string search (no regex — avoids memory cost on MicroPython).

**Alternative considered**: Reuse `known_nodes` and filter at confirm time. Rejected because `known_nodes` accumulates all nodes seen historically and does not retain resource-type metadata.

### D4: In-memory buffer as a plain list-of-dicts per board, capped at 12

`AppState.log_buffers` is a dict keyed by `device_id`, each value a list of at most 12 dicts `{ts, temp, hum}`. On overflow the oldest entry (`list.pop(0)`) is dropped. Plain lists avoid importing `collections.deque` which may not be available on all MicroPython builds.

At 5-minute intervals, 12 entries = 1 hour — matching the auto-flush interval. The total byte cost per board at flush time is under 1 KB.

### D5: Long-press detection in a new button_log_task with ticks_ms tracking

`ButtonLog` (a new class or extended `Button`) records `ticks_ms()` on the falling edge (press) and computes duration on the rising edge (release). No timer interrupt needed — the 50 ms polling loop gives ±50 ms precision, more than adequate for a 1000 ms threshold.

### D6: Compact display layout decided at render time, not stored in state

`render_status` computes `use_compact = logging_active and <condition>` inline. The condition is currently always `False` (3 logging rows always fit below y=95 without removing the header in the 128×160 TFT). The compact path is implemented for future extensibility and activated only if future additions push content beyond y=160.

### D7: NTP via ntptime.settime(), once at STAGING + nightly midnight re-sync

`ntptime.settime()` sets `time.time()` to UTC epoch. After a successful call, `time.localtime()` returns correct UTC fields. The logger task compares the current UTC date each hour; if the day changes it triggers a re-sync attempt. Re-sync failure during an active session is logged to serial only and does not interrupt the session.

### D8: SDStorage mounts and unmounts the SD card per flush

Mount at flush start, write all files, unmount at flush end. This avoids holding the filesystem mounted continuously (which could corrupt the FAT if power is lost between flushes) and makes the SD card safe to remove between sessions.

## Risks / Trade-offs

- **SPI bus contention** → Mitigation: Flush is triggered only from `button_log_task` or `logger_task`, both of which are async and yield between operations. The display task can interleave normally between SD writes via `asyncio.sleep` gaps in the flush loop.
- **NTP dependency at session start** → Mitigation: Error is surfaced clearly; user can cancel and retry. The staging confirm screen makes the dependency explicit.
- **CoAP discovery window (3 s) may miss slow-responding nodes** → Mitigation: Acceptable trade-off for responsiveness. The user sees the list before confirming.
- **SD card absent or full during auto-flush** → Mitigation: Error shown on display; buffer retained for next flush attempt. No data loss within the 12-entry buffer window.
- **MicroPython memory pressure** → Mitigation: Buffer is bounded (12 entries × N boards); CSV rows are written and discarded immediately during flush; no full file is held in memory.

## Migration Plan

No migration needed — this is additive. Existing behaviour (sensor display, CoAP server, HTTP server, original button) is unchanged. New tasks in `main.py` are opt-in at boot; if `PIN_BUTTON_LOG` is not wired, `ButtonLog.is_pressed()` returns `False` and the logger remains idle.

## Open Questions

- What abbreviation scheme to use for board IDs longer than 3 characters on the LOG line? (Assumption: first 3 chars of the device ID. Can be revisited without changing specs.)
