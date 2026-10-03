## Context

See `proposal.md` for motivation. Both the Raspberry Pi Pico 2 W (RP2350) and Waveshare ESP32-C6-Zero run MicroPython with an asynchronous architecture (`uasyncio`), modular sensor drivers, and dynamic SenML export. This design establishes how immediate display responsiveness (10-second rolling window) and long-term occupancy logging (5-minute period accumulator) coexist in the modular `PIRSensor` driver without code divergence.

## Goals / Non-Goals

**Goals:**
- Provide real-time, responsive visual feedback on the Pico 2 W ST7735 TFT display and ESP32-C6 SSD1306 OLED DETAILS screen: 10 seconds of constant hand motion reaches 100%, and 10 seconds of silence decays back to 0%.
- Eliminate the 2.0s–2.5s display update latency by pushing `motion` metrics directly into `AppState` on every 1.0s sample tick (mirroring `MicSensor`).
- Configure board-appropriate GPIO input modes: `Pin.PULL_DOWN` on Pico 2 W GP12 to overcome RP2350 default pull-up states, and high-impedance `Pin.IN` without pull-down on ESP32-C6 GPIO 4 to eliminate voltage divider attenuation on the AM312 CMOS push-pull output.
- Maintain accurate long-term occupancy duty cycle logging in the Pico 2 W 5-minute CSV files via an independent period accumulator (`active_ticks / total_ticks`).

**Non-Goals:**
- Changing display screen layouts or adding new display lines.
- Modifying the SD card 6-column CSV schema (`timestamp,device_id,temperature_c,humidity_pct,light_pct,motion_pct`).
- Altering the SenML JSON telemetry format (`{"n": "motion", "u": "%", "v": <pct>}`).

## Decisions

### Decision 1: Board-Specific Pin Mode: `Pin.PULL_DOWN` (Pico 2 W) vs `Pin.IN` (ESP32-C6)
- **Choice**: Initialize Pico 2 W GP12 with `Pin(self.pin_num, Pin.IN, Pin.PULL_DOWN)` and ESP32-C6 GPIO 4 with `Pin(self.pin_num, Pin.IN)`.
- **Rationale**:
  - **Pico 2 W (RP2350)**: RP2350 hardware pad architecture enables internal pull-ups by default upon reset. If initialized as floating `Pin.IN`, the pin floats HIGH, causing the circular buffer to artificially increment +10% every second up to 100% without motion. Configuring `Pin.PULL_DOWN` holds the line at steady 0V when the AM312 output is inactive.
  - **ESP32-C6**: The AM312 active CMOS push-pull output has an internal series output resistor. Enabling the ESP32-C6 internal ~45kΩ pull-down resistor forms a voltage divider that attenuates the active HIGH output voltage below the ESP32-C6 input high threshold ($V_{IH}$), preventing motion detection. High-impedance `Pin.IN` without pull-down allows clean 3.3V logic level detection.
- **Alternatives Considered**: A uniform pin mode across boards failed in hardware: `Pin.IN` broke Pico 2 W (stuck at 100%), while `Pin.PULL_DOWN` broke ESP32-C6 (stuck at 0%). Board-tailored initialization is necessary.

### Decision 2: 10-Slot Circular Buffer with Fixed Denominator for Live Motion
- **Choice**: Maintain a 10-element `bytearray(10)` circular buffer sampled at 1.0 Hz with fixed divisor `10`.
  $$\text{last\_motion} = \text{round}\left(\frac{\text{active\_count}}{10} \times 100.0, 1\right)$$
- **Rationale**: Avoids the startup distortion where a single active sample right after boot jumped to 100% due to dynamic sample count denominators. Each second of motion adds exactly $+10\%$, and each second of idle subtracts $-10\%$ once the window rolls. Constant movement for 10s yields 100%, and 10s of quiet returns to 0%.
- **Alternatives Considered**: 0.5s sampling (20 slots) was considered, but 1.0s sampling matches the physical AM312 hold time (~2.3s) with minimal CPU and timer wakeups.

### Decision 3: Decoupled 5-Minute Logging Accumulator with Reset-on-Poll
- **Choice**: Maintain two integer counters in `PIRSensor`: `self._period_active_ticks` and `self._period_total_ticks`.
  - Every 1-second sample tick: increment `_period_total_ticks += 1`, and if active HIGH, `_period_active_ticks += 1`.
  - Expose `get_period_motion(reset=True)`: returns `round((_period_active_ticks / total) * 100.0, 1)` and clears both counters to zero.
  - Expose `AppState.get_period_motion_and_reset()` so `DataLogger.poll_and_buffer()` retrieves the true 5-minute average duty cycle during periodic SD logging.
- **Rationale**: Keeps zero runtime allocations, decoupling the fast 10-second display response from the 5-minute statistical logging requirement.
- **Alternatives Considered**: Logging the 10-second rolling snapshot to SD would only record whether someone was moving during the last 10 seconds before the 5-minute log tick, missing movements earlier in the 5-minute block.

### Decision 4: Direct `AppState` Push on Sample Tick
- **Choice**: Accept optional `app_state` parameter in `PIRSensor.__init__` and call `self.app_state.update_metric("motion", self.last_motion)` on every sample tick. Retain duck-typed `read()` returning `{"motion": self.last_motion}` for fallback compatibility.
- **Rationale**: Mirrors the architecture proven in `MicSensor`, bypassing the 2.0s–2.5s slow DHT22 telemetry loop and providing immediate visual feedback on the OLED and TFT displays.
- **Alternatives Considered**: Polling `pir.read()` inside `telemetry.py` only; caused visible lag on button-driven DETAILS transitions and live monitoring.

## Risks / Trade-offs

- **[Risk] AM312 Hardware Inhibit Time (~2.5s)**: After asserting HIGH for ~2.5s, the AM312 internal analog front-end requires ~2.5s of blind inhibit time to stabilize before retriggering.
  $\rightarrow$ **Mitigation**: The 10-second rolling window smoothly absorbs this hold time: a single trigger keeps OUT high for 2–3 seconds (registering 20%–30% motion), and repeated waving stays high across consecutive cycles to reach 100%.
- **[Risk] DataLogger Polling Jitter**: Network or NTP staging could cause `DataLogger` to poll at 302 seconds instead of exactly 300 seconds.
  $\rightarrow$ **Mitigation**: The accumulator divides by the actual recorded `_period_total_ticks` rather than an assumed constant, preserving exact mathematical duty cycle precision regardless of timing jitter.
