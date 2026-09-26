"""Isolated UI and interaction controller using ST7735 TFT and dual buttons for Raspberry Pi Pico 2 W."""

import time
from settings import config
from hardware.display import TFTDisplay
from hardware.controls import Button, ButtonLog, AlertLED

# Display Modes (matching AppState)
MODE_SENSOR_DISPLAY = 0
MODE_SEMI_SLEEP = 1
MODE_MESSAGE = 2

# Data Logger State Constants
LOGGER_IDLE = 0
LOGGER_STAGING = 1
LOGGER_CONFIRM = 2
LOGGER_ACTIVE = 3


class UIController:
    """Manages ST7735 TFT display rendering, power control, alert LED, and dual button interactions for Pico 2 W."""

    MAX_LINE_LEN = 20

    def __init__(self, app_state=None, display=None):
        self.app_state = app_state
        self.display = display if display is not None else TFTDisplay()
        self.tft = self.display.tft
        self.spi = self.display.spi
        self.button = Button(getattr(config, "PIN_BUTTON", 14))
        self.button_log = ButtonLog(getattr(config, "PIN_BUTTON_LOG", 13))
        self.alert_led = AlertLED(getattr(config, "PIN_LED_ALERT", "LED"))
        self.display_on = True

        # Button timing state for primary button (GP14)
        self._btn_pressed_time = None
        self._btn_last_val = 1  # 1 = unpressed (pull-up)

        # Active background flush loop task
        self._active_flush_loop_task = None

    def power_off(self):
        """Blanks the TFT display for semi-sleep mode."""
        self.display_on = False
        self.display.power_off()
        if self.alert_led:
            self.alert_led.off()

    def power_on(self):
        """Wakes up and turns on the TFT display."""
        self.display_on = True

    def toggle_display(self):
        """Toggles display power state."""
        if self.display_on:
            self.power_off()
        else:
            self.power_on()
        print(f"[ui] Display toggled: display_on={self.display_on}")

    def show_splash(self, title="Pico 2W Station", subtitle="Starting..."):
        """Displays a startup splash screen."""
        self.display_on = True
        self.display.show_splash(title=title, subtitle=subtitle)

    def show_message(self, text):
        """Displays notification / override text message."""
        self.power_on()
        self.display.show_message(text)

    def render_staging_screen(self):
        """Displays transitional screen when logger is staging."""
        self.power_on()
        self.display.render_staging_screen()

    def render_confirm_screen(self, date_str=None, time_str=None, nodes=None, error=None):
        """Renders full-screen confirmation layout for LOGGER SETUP."""
        self.power_on()
        self.display.render_confirm_screen(date_str=date_str, time_str=time_str, nodes=nodes, error=error)

    def render_sensor_view(self, app_state):
        """Renders sensor data, network status, request count, and last caller."""
        if not self.display_on:
            return

        metrics = app_state.get_all_metrics() if hasattr(app_state, "get_all_metrics") else {}
        t_val = metrics.get("temperature", {}).get("val") if "temperature" in metrics else getattr(app_state, "temperature_c", None)
        h_val = metrics.get("humidity", {}).get("val") if "humidity" in metrics else getattr(app_state, "humidity_pct", None)
        l_val = metrics.get("light", {}).get("val") if "light" in metrics else getattr(app_state, "light_pct", None)

        self.display.render_status(
            temp=t_val,
            hum=h_val,
            light=l_val,
            ip=getattr(app_state, "ip_address", None),
            wifi_status=getattr(app_state, "wifi_status", "disconnected"),
            requests_served=getattr(app_state, "requests_served", 0),
            config_error=getattr(app_state, "config_error", None),
            last_caller=getattr(app_state, "last_caller", None),
            override_text=None,
            logging_active=getattr(app_state, "logging_active", False),
            log_active_nodes=getattr(app_state, "log_active_nodes", {}),
            log_buffered_count=getattr(app_state, "log_buffered_count", 0),
            log_ntp_time_str=getattr(app_state, "log_ntp_time_str", None),
            log_error=getattr(app_state, "log_error", None),
        )

    def update(self, app_state):
        """Called to refresh UI and Alert LED based on current app state and logger state."""
        if app_state is None:
            return

        # Synchronize Alert LED with active message mode or pending message
        if self.alert_led is not None:
            has_pending = hasattr(app_state, "has_pending_message") and app_state.has_pending_message()
            self.alert_led.set(app_state.mode == MODE_MESSAGE or has_pending)

        # Check logger state first
        logger_state = getattr(app_state, "logger_state", LOGGER_IDLE)
        if logger_state == LOGGER_STAGING:
            self.render_staging_screen()
            return
        elif logger_state == LOGGER_CONFIRM:
            date_str = getattr(app_state, "log_date_str", None)
            if not date_str:
                from services.ntp_service import get_utc_date_str
                date_str = get_utc_date_str()
            self.render_confirm_screen(
                date_str=date_str,
                time_str=getattr(app_state, "log_ntp_time_str", None),
                nodes=getattr(app_state, "log_active_nodes", {}),
                error=getattr(app_state, "log_error", None),
            )
            return

        # Check display mode
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
        """Executes operational transitions for primary reset/mode button (GP14)."""
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

    def handle_button_log(self, rel: str, app_state, data_logger=None):
        """Dispatches data logger lifecycle transitions based on secondary button (GP13)."""
        if data_logger is None:
            return

        try:
            import uasyncio as asyncio
        except ImportError:
            import asyncio

        current_logger_state = getattr(app_state, "logger_state", LOGGER_IDLE)

        if current_logger_state == LOGGER_IDLE:
            if rel == "short":
                print("[ui] Logger button: IDLE -> short-press, running staging...")
                asyncio.create_task(data_logger.run_staging())

        elif current_logger_state == LOGGER_CONFIRM:
            if rel == "short":
                if not getattr(app_state, "log_error", None):
                    print("[ui] Logger button: CONFIRM -> short-press, starting session...")
                    data_logger.start_session()
                    if self._active_flush_loop_task is None or self._active_flush_loop_task.done():
                        self._active_flush_loop_task = asyncio.create_task(data_logger.auto_flush_loop())
                else:
                    print("[ui] Logger button: short-press ignored due to staging error.")
            elif rel == "long":
                print("[ui] Logger button: CONFIRM -> long-press, canceling to IDLE...")
                if hasattr(app_state, "clear_logger_error"):
                    app_state.clear_logger_error()
                app_state.logger_state = LOGGER_IDLE

        elif current_logger_state == LOGGER_ACTIVE:
            if rel == "short":
                print("[ui] Logger button: ACTIVE -> short-press, stopping and flushing...")
                asyncio.create_task(data_logger.stop_and_flush())

    def poll_button(self, app_state):
        """Polls primary button (GP14) and evaluates press duration."""
        if self.button is None or self.button.pin is None:
            return

        try:
            val = self.button.pin.value()
            now = time.ticks_ms() if hasattr(time, "ticks_ms") else int(time.time() * 1000)

            if val == 0:
                if self._btn_last_val == 1:
                    self._btn_pressed_time = now
            else:
                if self._btn_last_val == 0 and self._btn_pressed_time is not None:
                    duration = (now - self._btn_pressed_time) if hasattr(time, "ticks_ms") else int((time.time() * 1000) - self._btn_pressed_time)
                    if hasattr(time, "ticks_diff"):
                        duration = time.ticks_diff(now, self._btn_pressed_time)

                    self._btn_pressed_time = None
                    if duration >= 1000:
                        self.handle_button("long", app_state)
                    elif duration >= 50:
                        self.handle_button("short", app_state)

            self._btn_last_val = val
        except Exception as e:
            print(f"[ui] Button poll error: {e}")

    def poll_button_log(self, app_state, data_logger=None):
        """Polls secondary logger button (GP13)."""
        if self.button_log is None or data_logger is None:
            return

        try:
            rel = self.button_log.release_type()
            if rel is not None:
                self.handle_button_log(rel, app_state, data_logger)
        except Exception as e:
            print(f"[ui] ButtonLog poll error: {e}")

    async def run_display_task(self, app_state):
        """Asynchronously refreshes TFT display on configured interval."""
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

    async def run_button_task(self, app_state, data_logger=None):
        """Asynchronously polls both physical buttons."""
        try:
            import uasyncio as asyncio
        except ImportError:
            import asyncio

        while True:
            try:
                self.poll_button(app_state)
                if data_logger is not None:
                    self.poll_button_log(app_state, data_logger)
            except Exception as e:
                print(f"[ui] Error in button task: {e}")
            await asyncio.sleep(0.05)
