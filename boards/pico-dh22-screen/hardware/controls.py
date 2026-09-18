"""Hardware abstractions for physical input button and alert LED."""

from settings import config

try:
    from machine import Pin
except ImportError:
    Pin = None


class Button:
    """Encapsulates active-LOW push button with pull-up resistor and edge detection."""

    def __init__(self, pin_num=config.PIN_BUTTON):
        self.pin_num = pin_num
        self.pin = None
        self._last_state = False

        if Pin is not None:
            try:
                self.pin = Pin(self.pin_num, Pin.IN, Pin.PULL_UP)
            except Exception as e:
                print(f"[controls] Button Pin({self.pin_num}) init error: {e}")

    def is_pressed(self):
        """Returns True if the button is currently pressed (active LOW)."""
        if self.pin is not None:
            return self.pin.value() == 0
        return False

    def was_pressed(self):
        """Returns True once per press on the transition from unpressed to pressed."""
        current = self.is_pressed()
        pressed_edge = current and not self._last_state
        self._last_state = current
        return pressed_edge


class AlertLED:
    """Encapsulates alert/notification indicator LED."""

    def __init__(self, pin_num=config.PIN_LED_ALERT):
        self.pin_num = pin_num
        self.pin = None
        self.is_on = False

        if Pin is not None:
            try:
                self.pin = Pin(self.pin_num, Pin.OUT)
                self.pin.value(0)
            except Exception as e:
                print(f"[controls] AlertLED Pin({self.pin_num}) init error: {e}")

    def on(self):
        """Turns the LED on."""
        self.is_on = True
        if self.pin is not None:
            self.pin.value(1)

    def off(self):
        """Turns the LED off."""
        self.is_on = False
        if self.pin is not None:
            self.pin.value(0)

    def set(self, state):
        """Sets the LED to on (True) or off (False)."""
        if state:
            self.on()
        else:
            self.off()
