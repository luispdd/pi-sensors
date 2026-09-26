"""Onboard WS2812 RGB LED status controller for Waveshare ESP32-C6-Zero."""

from settings import config

try:
    import neopixel
    from machine import Pin
except ImportError:
    neopixel = None
    Pin = None


class RGBStatusLED:
    """Controls onboard WS2812 RGB LED on GPIO 8 for status signaling."""

    COLOR_OFF = (0, 0, 0)
    COLOR_BOOT = (15, 15, 0)       # Dim yellow
    COLOR_CONNECTING = (0, 0, 25)   # Dim blue
    COLOR_CONNECTED = (0, 25, 0)    # Dim green
    COLOR_ERROR = (35, 0, 0)        # Dim red
    COLOR_ALERT = (35, 15, 0)       # Dim amber

    STATUS_MAP = {
        "off": COLOR_OFF,
        "boot": COLOR_BOOT,
        "connecting": COLOR_CONNECTING,
        "connected": COLOR_CONNECTED,
        "error": COLOR_ERROR,
        "alert": COLOR_ALERT,
    }

    def __init__(self, pin_num=config.PIN_RGB_LED, num_pixels=1):
        self.pin_num = pin_num
        self.num_pixels = num_pixels
        self._np = None
        self._current_color = self.COLOR_OFF
        self._current_status = "off"

        if Pin is not None and neopixel is not None:
            try:
                self._np = neopixel.NeoPixel(Pin(self.pin_num), self.num_pixels)
                # Waveshare ESP32-C6-Zero onboard WS2812 LED uses RGB channel order
                # instead of standard WS2812 GRB. Set ORDER to RGB mapping.
                self._np.ORDER = (0, 1, 2, 3)
                self.off()
            except Exception as e:
                print(f"[led] NeoPixel init error on GPIO {self.pin_num}: {e}")

    def set_color(self, r, g, b):
        """Sets RGB color (0-255 each) and writes to LED."""
        self._current_color = (r, g, b)
        if self._np is not None:
            try:
                self._np[0] = (r, g, b)
                self._np.write()
            except Exception as e:
                print(f"[led] Write error: {e}")

    def set_status(self, status, reason=None):
        """Sets status based on named status string."""
        status_name = status.lower()
        if status_name != self._current_status:
            reason_str = f" ({reason})" if reason else ""
            print(f"[led] Status changed: {self._current_status} -> {status_name}{reason_str}")
        color = self.STATUS_MAP.get(status_name, self.COLOR_OFF)
        self._current_status = status_name
        self.set_color(*color)

    def off(self):
        """Turns the LED completely off."""
        self.set_status("off")

    @property
    def current_status(self):
        return self._current_status

    @property
    def current_color(self):
        return self._current_color


# Global default instance
_default_led = None


def get_status_led():
    global _default_led
    if _default_led is None:
        _default_led = RGBStatusLED()
    return _default_led


async def run_led_task(app_state, led=None):
    """Updates onboard WS2812 RGB LED based on system and network status."""
    try:
        import uasyncio as asyncio
    except ImportError:
        import asyncio

    if led is None:
        led = get_status_led()

    while True:
        try:
            if getattr(app_state, "config_error", None) or getattr(app_state, "wifi_status", None) == "config_error":
                err = getattr(app_state, "config_error", None) or getattr(app_state, "wifi_status", None)
                led.set_status("error", reason=f"config_error={err}")
            elif getattr(app_state, "mode", 0) == 2 or (hasattr(app_state, "has_pending_message") and app_state.has_pending_message()):
                has_pending = app_state.has_pending_message() if hasattr(app_state, "has_pending_message") else False
                led.set_status("alert", reason=f"mode={getattr(app_state, 'mode', None)}, pending_message={has_pending}")
            elif getattr(app_state, "wifi_status", None) == "connecting":
                led.set_status("connecting")
            elif getattr(app_state, "wifi_status", None) == "connected":
                led.set_status("connected")
            else:
                led.set_status("off", reason=f"wifi_status={getattr(app_state, 'wifi_status', None)}")
        except Exception as e:
            print(f"[led] Error in led task: {e}")
        await asyncio.sleep(0.2)

