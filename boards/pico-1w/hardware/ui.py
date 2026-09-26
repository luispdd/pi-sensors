"""Isolated UI and interaction controller using SSD1306 OLED and controls for Raspberry Pi Pico W."""

import time
from settings import config
from hardware.display import OLEDDisplay
from hardware.controls import Button, AlertLED

# Display Modes (matching AppState)
MODE_SENSOR_DISPLAY = 0
MODE_SEMI_SLEEP = 1
MODE_MESSAGE = 2


class UIController:
    """Manages SSD1306 OLED display rendering, power control, alert LED, and button interactions for Pico 1 W."""

    MAX_LINE_LEN = 16

    def __init__(self, app_state=None):
        self.app_state = app_state
        self.display = OLEDDisplay(
            sda_pin=config.PIN_I2C_SDA,
            scl_pin=config.PIN_I2C_SCL,
            i2c_id=config.I2C_ID,
            freq=config.I2C_FREQ,
            width=config.OLED_WIDTH,
            height=config.OLED_HEIGHT,
        )
        self.oled = self.display.oled
        self.button = Button(config.PIN_BUTTON)
        self.alert_led = AlertLED(config.PIN_LED_ALERT)
        self.display_on = True

        # Button timing state for long/short press detection
        self._btn_pressed_time = None
        self._btn_last_val = 1  # 1 = unpressed (pull-up)

    def power_off(self):
        """Blanks and powers off the display for semi-sleep mode."""
        self.display_on = False
        self.display.power_off()
        if self.alert_led:
            self.alert_led.off()

    def power_on(self):
        """Wakes up and turns on the OLED display."""
        self.display_on = True
        if self.oled is not None:
            try:
                if hasattr(self.oled, "poweron"):
                    self.oled.poweron()
            except Exception as e:
                print(f"[ui] OLED power on error: {e}")

    def toggle_display(self):
        """Toggles display power state."""
        if self.display_on:
            self.power_off()
        else:
            self.power_on()
        print(f"[ui] Display toggled: display_on={self.display_on}")

    def show_splash(self, title="Pico Station", subtitle="Starting..."):
        """Displays a startup splash screen."""
        self.display_on = True
        self.display.show_splash(title=title, subtitle=subtitle)

    def show_message(self, text):
        """Displays notification / override text message."""
        self.power_on()
        self.display.show_message(text)

    def render_sensor_view(self, app_state):
        """Renders sensor data, network status, request count, and last caller."""
        if not self.display_on:
            return

        metrics = app_state.get_all_metrics() if hasattr(app_state, "get_all_metrics") else {}
        t_val = metrics.get("temperature", {}).get("val") if "temperature" in metrics else getattr(app_state, "temperature_c", None)
        h_val = metrics.get("humidity", {}).get("val") if "humidity" in metrics else getattr(app_state, "humidity_pct", None)

        self.display.render_status(
            temp=t_val,
            hum=h_val,
            ip=getattr(app_state, "ip_address", None),
            wifi_status=getattr(app_state, "wifi_status", "disconnected"),
            requests_served=getattr(app_state, "requests_served", 0),
            config_error=getattr(app_state, "config_error", None),
            last_caller=getattr(app_state, "last_caller", None),
            override_text=None,
        )

    def update(self, app_state):
        """Called to refresh UI and Alert LED based on current app state."""
        if app_state is None:
            return

        # Synchronize Alert LED with active message mode or pending message
        if self.alert_led is not None:
            has_pending = hasattr(app_state, "has_pending_message") and app_state.has_pending_message()
            self.alert_led.set(app_state.mode == MODE_MESSAGE or has_pending)

        mode = getattr(app_state, "mode", MODE_SENSOR_DISPLAY)

        if mode == MODE_SEMI_SLEEP:
            if self.display_on:
                self.power_off()
            return
        else:
            if not self.display_on:
                self.power_on()

        if mode == MODE_MESSAGE or (hasattr(app_state, "is_display_overridden") and app_state.is_display_overridden()):
            msg = getattr(app_state, "display_override_text", None) or getattr(app_state, "pending_message", "")
            self.show_message(msg)
        else:
            self.render_sensor_view(app_state)

    def handle_button(self, press_type: str, app_state):
        """Executes operational transitions for short or long button press."""
        if press_type == "long":
            self.toggle_display()
            return

        # Short press transitions
        mode = getattr(app_state, "mode", MODE_SENSOR_DISPLAY)

        if mode == MODE_SENSOR_DISPLAY:
            print("[ui] Button short press: entering SEMI_SLEEP")
            if hasattr(app_state, "enter_semi_sleep"):
                app_state.enter_semi_sleep()
            else:
                app_state.mode = MODE_SEMI_SLEEP
            self.power_off()
            if self.alert_led:
                self.alert_led.off()

        elif mode == MODE_SEMI_SLEEP:
            if hasattr(app_state, "has_pending_message") and app_state.has_pending_message():
                print("[ui] Button short press: showing pending message")
                msg = app_state.pending_message
                if hasattr(app_state, "enter_message_mode"):
                    app_state.enter_message_mode(msg)
                else:
                    app_state.mode = MODE_MESSAGE
                if self.alert_led:
                    self.alert_led.on()
            else:
                print("[ui] Button short press: resuming sensor display")
                if hasattr(app_state, "enter_sensor_mode"):
                    app_state.enter_sensor_mode()
                else:
                    app_state.mode = MODE_SENSOR_DISPLAY
                if self.alert_led:
                    self.alert_led.off()
            self.power_on()

        elif mode == MODE_MESSAGE:
            print("[ui] Button short press: clearing message, resuming sensor display")
            if hasattr(app_state, "enter_sensor_mode"):
                app_state.enter_sensor_mode()
            else:
                app_state.mode = MODE_SENSOR_DISPLAY
            self.power_on()
            if self.alert_led:
                self.alert_led.off()

    def poll_button(self, app_state):
        """Polls button input pin and evaluates press duration."""
        if self.button is None or self.button.pin is None:
            # Fallback if hardware pin not available
            return

        try:
            val = self.button.pin.value()
            now = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)

            # Button is pressed (active LOW)
            if val == 0:
                if self._btn_last_val == 1:
                    self._btn_pressed_time = now
            else:
                # Button is released
                if self._btn_last_val == 0 and self._btn_pressed_time is not None:
                    duration = (now - self._btn_pressed_time) if hasattr(time, "ticks_ms") else int((time.time() * 1000) - self._btn_pressed_time)
                    if hasattr(time, "ticks_diff"):
                        duration = time.ticks_diff(now, self._btn_pressed_time)

                    self._btn_pressed_time = None
                    if duration >= 1000:
                        self.handle_button("long", app_state)
                    elif duration >= 50:  # Debounce minimum 50ms
                        self.handle_button("short", app_state)

            self._btn_last_val = val
        except Exception as e:
            print(f"[ui] Button poll error: {e}")

    async def run_display_task(self, app_state):
        """Asynchronously refreshes display on configured interval."""
        try:
            import uasyncio as asyncio
        except ImportError:
            import asyncio

        while True:
            try:
                self.update(app_state)
                await asyncio.sleep(config.DISPLAY_REFRESH_INTERVAL_S)
            except Exception as e:
                print(f"[ui] Error in display task: {e}")
                await asyncio.sleep(config.DISPLAY_REFRESH_INTERVAL_S)

    async def run_button_task(self, app_state):
        """Asynchronously polls physical button input."""
        try:
            import uasyncio as asyncio
        except ImportError:
            import asyncio

        while True:
            try:
                self.poll_button(app_state)
            except Exception as e:
                print(f"[ui] Error in button task: {e}")
            await asyncio.sleep(0.05)
