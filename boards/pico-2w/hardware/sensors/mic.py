"""Modular MAX4466 ADC microphone noise sensor driver conforming to duck-typed sensor protocol.

Works on both Raspberry Pi Pico 2W (RP2350) and ESP32-C6 MicroPython ports.

Optional settings (read from settings.config if present):
    PIN_MIC_ADC        ADC pin number
    MIC_FULL_SCALE_DB  dB above the noise floor that maps to 100%  (default 40.0)
    MIC_MIN_FLOOR      minimum RMS floor in ADC counts (default 4.0 on RP2, 16.0 on ESP32)
    MIC_GATE_DB        dB above the floor ignored as jitter (default 1.0)
    MIC_RELEASE        decay factor per window, 0..1 (default 0.2)
"""

try:
    from settings import config
except ImportError:
    config = None

try:
    from machine import Pin, ADC
except ImportError:
    Pin = None
    ADC = None

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    from math import sqrt
except ImportError:
    sqrt = None

try:
    from math import log10
except ImportError:
    log10 = None

try:
    import utime as time
except ImportError:
    import time


def _ticks_ms():
    if hasattr(time, "ticks_ms"):
        return time.ticks_ms()
    return int(time.time() * 1000)


def _ticks_diff(t1, t0):
    if hasattr(time, "ticks_diff"):
        return time.ticks_diff(t1, t0)
    return t1 - t0


def _is_esp32():
    """True when running on an ESP32-family MicroPython port."""
    try:
        import sys
        return "ESP32" in sys.implementation._machine.upper()
    except Exception:
        return False


class MicSensor:
    """Modular ADC microphone sensor driver measuring noise level percentage."""

    def __init__(
        self,
        pin=getattr(config, "PIN_MIC_ADC", None),
        window_ms=50,
        sample_interval_s=0.01,
        avg_window_s=2.0,
        full_scale_rms=3000.0,
        app_state=None,
    ):
        self.pin_num = pin
        self.window_ms = window_ms
        self.sample_interval_s = sample_interval_s
        self.avg_window_s = avg_window_s
        self.full_scale_rms = full_scale_rms  # kept for compatibility; level now uses dB scale
        self.app_state = app_state
        self.noise_floor = None  # adaptive RMS floor (ADC counts)
        self._rms_history = []
        self.name = "mic"
        self.metrics = [
            {"key": "noise", "unit": "%"},
        ]
        self.last_noise_pct = 0.0
        self.read_errors = 0
        self._adc = None
        self._ref = None  # running estimate of the DC offset (ADC counts)

        # Board-dependent tuning (overridable from settings.config)
        default_floor = 16.0 if _is_esp32() else 4.0
        self.min_floor = float(getattr(config, "MIC_MIN_FLOOR", default_floor))
        self.full_scale_db = float(getattr(config, "MIC_FULL_SCALE_DB", 40.0))
        self.gate_db = float(getattr(config, "MIC_GATE_DB", 1.0))
        self.release = float(getattr(config, "MIC_RELEASE", 0.2))

        self.init()

    def init(self, adc=None):
        """Initializes ADC hardware with 11dB attenuation if supported (needed on ESP32)."""
        if adc is not None:
            self._adc = adc
            try:
                atten_val = getattr(ADC, "ATTN_11DB", 3) if ADC is not None else 3
                if hasattr(self._adc, "atten"):
                    self._adc.atten(atten_val)
            except (AttributeError, TypeError):
                pass
            return

        if Pin is not None and ADC is not None and self.pin_num is not None:
            try:
                pin_obj = Pin(self.pin_num) if callable(Pin) else self.pin_num
                self._adc = ADC(pin_obj)
                try:
                    atten_val = getattr(ADC, "ATTN_11DB", 3)
                    if hasattr(self._adc, "atten"):
                        self._adc.atten(atten_val)
                except (AttributeError, TypeError):
                    pass
            except Exception as e:
                print(f"[mic] ADC hardware init error on pin {self.pin_num}: {e}")
                self._adc = None
        else:
            self._adc = None

    def sample(self):
        """Samples the ADC over window_ms and updates the noise level percentage."""
        if self._adc is None:
            self.init()
            if self._adc is None:
                return self.last_noise_pct

        start = _ticks_ms()
        samples = 0
        total = 0
        total_sq = 0
        ref = self._ref

        while _ticks_diff(_ticks_ms(), start) < self.window_ms:
            try:
                val = self._adc.read_u16()
                if val is None:
                    break
                if ref is None:
                    ref = val  # first ever sample seeds the DC offset
                d = val - ref  # centered value keeps integers small (no bigint/heap use)
                total += d
                total_sq += d * d
                samples += 1
            except (StopIteration, IndexError):
                break
            except Exception as e:
                self.read_errors += 1
                print(f"[mic] ADC read error ({self.read_errors}): {e}")
                break

        if samples > 1:
            mean_d = total / samples
            var = max(0.0, (total_sq / samples) - (mean_d * mean_d))
            rms = sqrt(var) if sqrt else (var ** 0.5)

            # Track DC offset so next window stays centered
            self._ref = ref + int(mean_d)

            # Rolling average of RMS over the last avg_window_s seconds (used for the floor only)
            step_time = (self.sample_interval_s + self.window_ms / 1000.0) if self.sample_interval_s else 0.05
            n_hist = max(1, int(round(self.avg_window_s / step_time)))
            self._rms_history.append(rms)
            del self._rms_history[:-n_hist]
            avg_rms = sum(self._rms_history) / len(self._rms_history)

            # Adaptive floor: follows lower silence immediately,
            # drifts upward very slowly only near ambient baseline (never during loud noise)
            if self.noise_floor is None or avg_rms < self.noise_floor:
                self.noise_floor = avg_rms
            elif avg_rms < (self.noise_floor * 1.5 + 50.0):
                self.noise_floor += (avg_rms - self.noise_floor) * 0.005

            # Level from the CURRENT window, in dB above the floor (fast reaction to claps)
            floor = max(self.noise_floor, self.min_floor)
            if log10 is not None:
                db = 20.0 * log10(max(rms, floor) / floor)
            else:
                db = 0.0
            db = max(0.0, db - self.gate_db)
            span = max(1.0, self.full_scale_db - self.gate_db)
            pct = min(100.0, db / span * 100.0)

            # Instant attack, smooth release
            if pct > self.last_noise_pct:
                new_pct = pct
            else:
                new_pct = self.last_noise_pct + (pct - self.last_noise_pct) * self.release
            self.last_noise_pct = min(100.0, max(0.0, round(new_pct, 1)))

            if self.app_state is not None:
                try:
                    self.app_state.update_metric("noise", self.last_noise_pct)
                except Exception:
                    pass
        elif ref is not None:
            self._ref = ref

        return self.last_noise_pct

    def sample_window(self):
        """Alias for sample()."""
        return self.sample()

    def read(self):
        """Duck-typed read method returning metric dictionary."""
        return {"noise": self.last_noise_pct}

    async def run_sampling_task(self):
        """Continuous cooperative asyncio task sampling noise."""
        while True:
            try:
                self.sample()
            except Exception as e:
                print(f"[mic] Error during sampling: {e}")
            await asyncio.sleep(self.sample_interval_s)


def create_sensor(
    pin=getattr(config, "PIN_MIC_ADC", None),
    window_ms=50,
    sample_interval_s=0.01,
    avg_window_s=2.0,
    full_scale_rms=3000.0,
    app_state=None,
):
    """Factory function for instantiating the MicSensor."""
    return MicSensor(
        pin=pin,
        window_ms=window_ms,
        sample_interval_s=sample_interval_s,
        avg_window_s=avg_window_s,
        full_scale_rms=full_scale_rms,
        app_state=app_state,
    )