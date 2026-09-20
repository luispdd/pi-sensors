"""Hardware abstractions for physical input button and alert LED on Pico 2 W."""

from settings import config

try:
    from machine import Pin
except ImportError:
    Pin = None


try:
    import time
except ImportError:
    time = None


class Button:
    """Encapsulates active-LOW push button with pull-up resistor and edge detection."""

    def __init__(self, pin_num=getattr(config, "PIN_BUTTON", 14)):
        self.pin_num = pin_num
        self.pin = None
        self._last_state = False

        if Pin is not None and self.pin_num is not None:
            try:
                self.pin = Pin(self.pin_num, Pin.IN, Pin.PULL_UP)
            except Exception as e:
                print(f"[controls] Button Pin({self.pin_num}) init error: {e}")

    def is_pressed(self):
        """Returns True if the button is currently pressed (active LOW)."""
        if self.pin is not None:
            try:
                return self.pin.value() == 0
            except Exception:
                return False
        return False

    def was_pressed(self):
        """Returns True once per press on the transition from unpressed to pressed."""
        current = self.is_pressed()
        pressed_edge = current and not self._last_state
        self._last_state = current
        return pressed_edge


class ButtonLog:
    """Encapsulates logger button on GP13 with press-duration tracking (short vs long press)."""

    def __init__(self, pin_num=getattr(config, "PIN_BUTTON_LOG", 13), long_press_ms=1000):
        self.pin_num = pin_num
        self.long_press_ms = long_press_ms
        self.pin = None
        self._last_state = False
        self._press_start_ms = None

        if Pin is not None and self.pin_num is not None:
            try:
                self.pin = Pin(self.pin_num, Pin.IN, Pin.PULL_UP)
            except Exception as e:
                print(f"[controls] ButtonLog Pin({self.pin_num}) init error: {e}")

    def _now_ms(self):
        if time is not None:
            if hasattr(time, "ticks_ms"):
                return time.ticks_ms()
            return int(time.time() * 1000)
        return 0

    def _ticks_diff(self, end, start):
        if time is not None and hasattr(time, "ticks_diff"):
            return time.ticks_diff(end, start)
        return end - start

    def is_pressed(self):
        """Returns True if the button is currently pressed (active LOW)."""
        if self.pin is not None:
            try:
                return self.pin.value() == 0
            except Exception:
                return False
        return False

    def was_pressed_start(self):
        """Returns True on falling edge (transition to pressed) and records start timestamp."""
        current = self.is_pressed()
        falling_edge = current and not self._last_state
        self._last_state = current
        if falling_edge:
            self._press_start_ms = self._now_ms()
        return falling_edge

    def release_type(self):
        """Polls button state. On rising edge (transition from pressed to released),

        computes duration and returns 'short' (< 1000ms) or 'long' (>= 1000ms).
        Returns None if button is still held or unpressed.
        """
        current = self.is_pressed()
        released = False
        duration = 0

        if self._last_state and not current:
            # Rising edge (released)
            released = True
            if self._press_start_ms is not None:
                duration = self._ticks_diff(self._now_ms(), self._press_start_ms)
                self._press_start_ms = None
        elif not self._last_state and current:
            # Falling edge (pressed)
            self._press_start_ms = self._now_ms()

        self._last_state = current

        if released:
            return "long" if duration >= self.long_press_ms else "short"
        return None


class AlertLED:
    """Encapsulates alert/notification indicator LED (supports GPIO pin number or 'LED')."""

    def __init__(self, pin_num=getattr(config, "PIN_LED_ALERT", "LED")):
        self.pin_num = pin_num
        self.pin = None
        self.is_on = False

        if Pin is not None and self.pin_num is not None:
            try:
                self.pin = Pin(self.pin_num, Pin.OUT)
                self.pin.value(0)
            except Exception as e:
                print(f"[controls] AlertLED Pin({self.pin_num}) init error: {e}")

    def on(self):
        """Turns the LED on."""
        self.is_on = True
        if self.pin is not None:
            try:
                self.pin.value(1)
            except Exception as e:
                print(f"[controls] AlertLED on error: {e}")

    def off(self):
        """Turns the LED off."""
        self.is_on = False
        if self.pin is not None:
            try:
                self.pin.value(0)
            except Exception as e:
                print(f"[controls] AlertLED off error: {e}")

    def set(self, state):
        """Sets the LED to on (True) or off (False)."""
        if state:
            self.on()
        else:
            self.off()
