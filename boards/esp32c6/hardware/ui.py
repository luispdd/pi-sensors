"""Isolated UI and interaction controller using SSD1306 OLED for Waveshare ESP32-C6-Zero."""

import time
from settings import config

try:
    from machine import I2C, Pin
except ImportError:
    I2C = None
    Pin = None

try:
    import ssd1306
except ImportError:
    try:
        from lib import ssd1306
    except ImportError:
        ssd1306 = None


# Display Modes (matching AppState)
MODE_SENSOR_DISPLAY = 0
MODE_SEMI_SLEEP = 1
MODE_MESSAGE = 2
MODE_DETAILS = 3


class UIController:
    """Manages SSD1306 OLED display rendering, power control, and button interactions for ESP32-C6-Zero."""

    MAX_LINE_LEN = 16

    def __init__(self, app_state=None):
        self.app_state = app_state
        self.oled = None
        self.i2c = None
        self.button_pin = None
        self.display_on = True

        # Button timing state
        self._btn_pressed_time = None
        self._btn_last_val = 1  # 1 = unpressed (pull-up)

        self._init_hardware()

    def _init_hardware(self):
        """Initializes I2C, SSD1306 OLED display, and Button pin."""
        if Pin is None:
            return

        # Initialize Button pin (active LOW, pull-up)
        try:
            self.button_pin = Pin(config.PIN_BUTTON, Pin.IN, Pin.PULL_UP)
        except Exception as e:
            print(f"[ui] Button init error on GPIO {config.PIN_BUTTON}: {e}")

        # Initialize I2C & SSD1306 OLED
        if I2C is not None and ssd1306 is not None:
            try:
                try:
                    self.i2c = I2C(
                        getattr(config, "I2C_ID", 0),
                        sda=Pin(config.PIN_I2C_SDA),
                        scl=Pin(config.PIN_I2C_SCL),
                        freq=getattr(config, "I2C_FREQ", 400_000),
                    )
                except Exception:
                    # ESP32 software / general I2C fallback
                    self.i2c = I2C(
                        sda=Pin(config.PIN_I2C_SDA),
                        scl=Pin(config.PIN_I2C_SCL),
                        freq=getattr(config, "I2C_FREQ", 400_000),
                    )

                self.oled = ssd1306.SSD1306_I2C(
                    config.OLED_WIDTH,
                    config.OLED_HEIGHT,
                    self.i2c,
                )
                self.oled.fill(0)
                self.oled.show()
                self.display_on = True
            except Exception as e:
                print(f"[ui] SSD1306 OLED init error: {e}")
                self.oled = None

    def power_off(self):
        """Blanks and powers off the OLED display for semi-sleep mode."""
        self.display_on = False
        if self.oled is not None:
            try:
                self.oled.fill(0)
                self.oled.show()
                if hasattr(self.oled, "poweroff"):
                    self.oled.poweroff()
            except Exception as e:
                print(f"[ui] OLED power off error: {e}")

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

    def show_splash(self, title="ESP32-C6 Node", subtitle="Starting..."):
        """Displays a startup splash screen."""
        if self.oled is None:
            return
        try:
            self.power_on()
            self.oled.fill(0)
            self.oled.text(title[:self.MAX_LINE_LEN], 0, 16)
            self.oled.hline(0, 30, config.OLED_WIDTH, 1)
            self.oled.text(subtitle[:self.MAX_LINE_LEN], 0, 38)
            self.oled.show()
        except Exception as e:
            print(f"[ui] Splash error: {e}")

    def show_message(self, text):
        """Displays notification / override text message."""
        if self.oled is None:
            return
        try:
            self.power_on()
            if isinstance(text, (bytes, bytearray)):
                text = text.decode("utf-8")
            else:
                text = str(text)

            self.oled.fill(0)
            self.oled.text("[Message]", 0, 0)
            self.oled.hline(0, 10, config.OLED_WIDTH, 1)

            # Simple line wrapping
            lines = []
            for raw_line in text.split("\n"):
                while len(raw_line) > self.MAX_LINE_LEN:
                    lines.append(raw_line[:self.MAX_LINE_LEN])
                    raw_line = raw_line[self.MAX_LINE_LEN:]
                lines.append(raw_line)

            y = 14
            for l in lines[:5]:
                self.oled.text(l, 0, y)
                y += 10
            self.oled.show()
        except Exception as e:
            print(f"[ui] Message render error: {e}")

    def render_sensor_view(self, app_state):
        """Renders sensor data, network status, request count, and last caller."""
        if self.oled is None or not self.display_on:
            return

        try:
            self.oled.fill(0)

            # Line 0 (y=2): Temperature & Humidity
            metrics = app_state.get_all_metrics() if hasattr(app_state, "get_all_metrics") else {}
            t_val = metrics.get("temperature", {}).get("val") if "temperature" in metrics else getattr(app_state, "temperature_c", None)
            h_val = metrics.get("humidity", {}).get("val") if "humidity" in metrics else getattr(app_state, "humidity_pct", None)

            t_str = f"{t_val:.1f}C" if t_val is not None else "--.-C"
            h_str = f"{h_val:.0f}%" if h_val is not None else "--%"
            line0 = f"T:{t_str} H:{h_str}"
            self.oled.text(line0[:self.MAX_LINE_LEN], 0, 2)

            # Line 1 (y=16) & Line 2 (y=28): Network info / Route / Error
            wifi_status = getattr(app_state, "wifi_status", "disconnected")
            config_error = getattr(app_state, "config_error", None)
            ip = getattr(app_state, "ip_address", None)

            if config_error or wifi_status == "config_error":
                err_msg = config_error if config_error else "Config Error"
                self.oled.text(err_msg[:self.MAX_LINE_LEN], 0, 16)
                self.oled.text("Check secrets.py", 0, 28)
            elif ip and wifi_status == "connected":
                clean_ip = str(ip).replace("http://", "").replace("https://", "").strip()
                self.oled.text(clean_ip[:self.MAX_LINE_LEN], 0, 16)
                self.oled.text("/info", 0, 28)
            else:
                status_label = "Connecting..." if wifi_status == "connecting" else "WiFi: Offline"
                self.oled.text(status_label[:self.MAX_LINE_LEN], 0, 16)
                self.oled.text("Waiting for net", 0, 28)

            # Line 3 (y=40): Request count
            reqs = getattr(app_state, "requests_served", 0)
            self.oled.text(f"Reqs: {reqs}"[:self.MAX_LINE_LEN], 0, 40)

            # Line 4 (y=52): Last caller
            last_caller = getattr(app_state, "last_caller", None)
            caller_str = str(last_caller) if last_caller else "--"
            self.oled.text(f"Last: {caller_str}"[:self.MAX_LINE_LEN], 0, 52)

            self.oled.show()
        except Exception as e:
            print(f"[ui] Render sensor view error: {e}")

    METRIC_LABELS = {
        "temperature": "T",
        "humidity": "H",
        "light": "L",
        "motion": "M",
        "noise": "N",
        "sound": "N",
    }

    def render_details_view(self, app_state):
        """Renders DETAILS_MODE: header + cur/min/max table for each registered metric."""
        if self.oled is None or not self.display_on:
            return
        try:
            self.oled.fill(0)
            # Header row at y=0
            self.oled.text("[DETAILS]", 0, 0)

            metrics = app_state.get_all_metrics() if hasattr(app_state, "get_all_metrics") else {}
            # Ordered display: temperature first, humidity second, then any additional registered metric
            known_order = ["temperature", "humidity"]
            keys_to_show = [k for k in known_order if k in metrics]
            for k in metrics:
                if k not in keys_to_show:
                    keys_to_show.append(k)

            # Up to 3 metric rows: y=12, 24, 36 (fits within 64px display)
            y = 12
            for key in keys_to_show[:3]:
                label = self.METRIC_LABELS.get(key, key[:1].upper())
                m = metrics.get(key, {})
                cur = m.get("val")
                mn  = m.get("min")
                mx  = m.get("max")
                cur_s = f"{cur:.1f}" if cur is not None else "--"
                mn_s  = f"{mn:.1f}"  if mn  is not None else "--"
                mx_s  = f"{mx:.1f}"  if mx  is not None else "--"
                row = f"{label}:{cur_s} {mn_s} {mx_s}"
                self.oled.text(row[:self.MAX_LINE_LEN], 0, y)
                y += 12

            self.oled.show()
        except Exception as e:
            print(f"[ui] Details view render error: {e}")

    def update(self, app_state):
        """Called by the main loop to refresh the UI based on current app state."""
        if app_state is None:
            return

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
        elif mode == MODE_DETAILS:
            self.render_details_view(app_state)
        else:
            self.render_sensor_view(app_state)

    def handle_button(self, press_type: str, app_state):
        """Executes operational transitions for the primary button.

        press_type:
          'long'  - held >= 1000ms: enter SEMI_SLEEP from any active mode.
          'short' - released < 1000ms: cycle STATUS <-> DETAILS, or discard message.
          'wake'  - falling edge while in SEMI_SLEEP: restore previous mode.
        """
        mode = getattr(app_state, "mode", MODE_SENSOR_DISPLAY)

        if press_type == "wake" or mode == MODE_SEMI_SLEEP:
            print("[ui] Button press: waking from SEMI_SLEEP, restoring previous mode")
            if hasattr(app_state, "restore_previous_mode"):
                app_state.restore_previous_mode()
            else:
                app_state.mode = MODE_SENSOR_DISPLAY
            self.power_on()
            return

        if press_type == "long":
            print("[ui] Button long press: entering SEMI_SLEEP")
            if hasattr(app_state, "enter_semi_sleep"):
                app_state.enter_semi_sleep()
            else:
                app_state.mode = MODE_SEMI_SLEEP
            self.power_off()
            return

        # Short press transitions
        if mode == MODE_MESSAGE:
            print("[ui] Button short press: discarding message, restoring previous mode")
            if hasattr(app_state, "restore_previous_mode"):
                app_state.restore_previous_mode()
            else:
                app_state.mode = MODE_SENSOR_DISPLAY
            self.power_on()

        elif mode == MODE_SENSOR_DISPLAY:
            print("[ui] Button short press: STATUS_MODE -> DETAILS_MODE")
            if hasattr(app_state, "enter_details_mode"):
                app_state.enter_details_mode()
            else:
                app_state.mode = MODE_DETAILS

        elif mode == MODE_DETAILS:
            print("[ui] Button short press: DETAILS_MODE -> STATUS_MODE")
            if hasattr(app_state, "enter_sensor_mode"):
                app_state.enter_sensor_mode()
            else:
                app_state.mode = MODE_SENSOR_DISPLAY

    def poll_button(self, app_state):
        """Polls button input pin and evaluates press duration.

        When in SEMI_SLEEP the wakeup fires immediately on the falling edge
        (button pressed) so the user does not need to hold or release cleanly.
        """
        if self.button_pin is None:
            return

        try:
            val = self.button_pin.value()
            now = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)

            # Falling edge detected (button pressed, active LOW)
            if val == 0 and self._btn_last_val == 1:
                mode = getattr(app_state, "mode", MODE_SENSOR_DISPLAY)
                if mode == MODE_SEMI_SLEEP:
                    # Wake immediately on press — no need to wait for release
                    self.handle_button("wake", app_state)
                else:
                    self._btn_pressed_time = now

            # Rising edge detected (button released)
            elif val == 1 and self._btn_last_val == 0 and self._btn_pressed_time is not None:
                duration = time.ticks_diff(now, self._btn_pressed_time) if hasattr(time, "ticks_diff") else (now - self._btn_pressed_time)
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

