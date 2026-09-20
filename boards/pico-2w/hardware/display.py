"""ST7735 TFT Display driver wrapper for Raspberry Pi Pico 2 W with SPI bus arbitration."""

import sys
import time
from settings import config

try:
    from machine import SPI, Pin
except ImportError:
    SPI = None
    Pin = None

try:
    from ST7735 import TFT
    from sysfont import sysfont
except ImportError:
    try:
        from lib.ST7735 import TFT
        from lib.sysfont import sysfont
    except ImportError:
        TFT = None
        sysfont = None


class TFTDisplay:
    def __init__(
        self,
        spi_bus=config.SPI_BUS,
        sck_pin=config.SPI_SCK,
        mosi_pin=config.SPI_MOSI,
        miso_pin=config.SPI_MISO,
        cs_pin=config.TFT_CS,
        dc_pin=config.TFT_DC,
        reset_pin=config.TFT_RESET,
        sd_cs_pin=config.SD_CS,
        baudrate=config.SPI_SPEED_TFT,
        width=config.TFT_WIDTH,
        height=config.TFT_HEIGHT,
    ):
        self.width = width
        self.height = height
        self.baudrate = baudrate
        self.tft = None
        self.spi = None

        if SPI is not None and Pin is not None and TFT is not None:
            try:
                # Ensure SD card CS is held HIGH (inactive) during TFT ops
                self.sd_cs = Pin(sd_cs_pin, Pin.OUT, value=1)

                self.spi = SPI(
                    spi_bus,
                    baudrate=baudrate,
                    polarity=0,
                    phase=0,
                    sck=Pin(sck_pin),
                    mosi=Pin(mosi_pin),
                    miso=Pin(miso_pin),
                )
                self.tft = TFT(self.spi, dc_pin, reset_pin, cs_pin)
                self.tft.initr()
                self.tft.rgb(config.TFT_MADCTL == 0x00)
                time.sleep_ms(10)
                self.clear()
            except Exception as e:
                print(f"[display] TFT initialization failed: {e}")
                self.tft = None

    MAX_LINE_LEN = 20

    def _acquire_bus(self):
        """Sets SD_CS HIGH and updates SPI frequency to TFT baudrate."""
        if self.sd_cs is not None:
            self.sd_cs.value(1)
        if self.spi is not None:
            try:
                self.spi.init(baudrate=self.baudrate)
            except Exception:
                pass

    def clear(self):
        """Clears the display (fills with black)."""
        if self.tft is not None:
            try:
                self._acquire_bus()
                self.tft.fill(TFT.BLACK)
            except Exception as e:
                print(f"[display] Clear error: {e}")

    def power_off(self):
        """Blanks and powers off the display for semi-sleep mode."""
        self.clear()

    def show_splash(self, title="Pico 2W Station", subtitle="Starting..."):
        """Displays a startup splash screen."""
        if self.tft is None:
            return
        try:
            self._acquire_bus()
            self.tft.fill(TFT.BLACK)
            self.tft.text((10, 20), title[:self.MAX_LINE_LEN], TFT.GREEN, sysfont, 1)
            self.tft.line((0, 40), (self.width, 40), TFT.WHITE)
            self.tft.text((10, 50), subtitle[:self.MAX_LINE_LEN], TFT.YELLOW, sysfont, 1)
        except Exception as e:
            print(f"[display] Splash error: {e}")

    def show_message(self, text):
        """Displays an override text message on the TFT screen."""
        if self.tft is None:
            return
        try:
            if isinstance(text, (bytes, bytearray)):
                text = text.decode("utf-8")
            else:
                text = str(text)

            self._acquire_bus()
            self.tft.fill(TFT.BLACK)
            self.tft.text((5, 5), "[Message]", TFT.RED, sysfont, 1)
            self.tft.line((0, 18), (self.width, 18), TFT.WHITE)

            lines = []
            for raw_line in text.split("\n"):
                while len(raw_line) > self.MAX_LINE_LEN:
                    lines.append(raw_line[:self.MAX_LINE_LEN])
                    raw_line = raw_line[self.MAX_LINE_LEN:]
                lines.append(raw_line)

            y = 25
            for l in lines[:10]:
                self.tft.text((5, y), l, TFT.WHITE, sysfont, 1)
                y += 12
        except Exception as e:
            print(f"[display] Message render error: {e}")

    def render_staging_screen(self):
        """Displays transitional screen when logger is synchronizing NTP and discovering nodes."""
        if self.tft is None:
            return
        try:
            self._acquire_bus()
            self.tft.fill(TFT.BLACK)
            self.tft.text((5, 5), "LOGGER SETUP", TFT.CYAN, sysfont, 1)
            self.tft.line((0, 18), (self.width, 18), TFT.WHITE)
            self.tft.text((10, 50), "Preparing...", TFT.YELLOW, sysfont, 1)
            self.tft.text((10, 70), "Scanning net...", TFT.WHITE, sysfont, 1)
            self.tft.text((10, 90), "Syncing NTP...", TFT.GRAY if hasattr(TFT, "GRAY") else TFT.WHITE, sysfont, 1)
        except Exception as e:
            print(f"[display] Staging render error: {e}")

    def render_confirm_screen(self, date_str=None, time_str=None, nodes=None, error=None):
        """Renders full-screen confirmation layout for LOGGER SETUP."""
        if self.tft is None:
            return
        try:
            self._acquire_bus()
            self.tft.fill(TFT.BLACK)

            # Title
            self.tft.text((5, 5), "LOGGER SETUP", TFT.CYAN, sysfont, 1)
            self.tft.line((0, 18), (self.width, 18), TFT.WHITE)

            # UTC Date/Time
            d_str = date_str if date_str else "--"
            t_str = time_str if time_str else "--:-- UTC"
            self.tft.text((5, 25), f"{d_str} {t_str}"[:self.MAX_LINE_LEN], TFT.WHITE, sysfont, 1)

            if error:
                # Error mode: display error in red and only cancel option
                self.tft.text((5, 45), "ERROR:", TFT.RED, sysfont, 1)
                self.tft.text((5, 60), str(error)[:self.MAX_LINE_LEN], TFT.RED, sysfont, 1)

                self.tft.line((0, 130), (self.width, 130), TFT.WHITE)
                self.tft.text((5, 140), "[hold] CANCEL", TFT.YELLOW, sysfont, 1)
            else:
                # Normal mode: list discovered boards
                self.tft.text((5, 45), "Boards to log:", TFT.GREEN, sysfont, 1)
                y = 60
                node_names = list(nodes.values()) if isinstance(nodes, dict) else (nodes if nodes else [])
                for name in node_names[:4]:
                    self.tft.text((8, y), f"* {str(name)[:14]}", TFT.WHITE, sysfont, 1)
                    y += 14

                # Action prompts at bottom
                self.tft.line((0, 125), (self.width, 125), TFT.WHITE)
                self.tft.text((5, 132), "[click] START", TFT.GREEN, sysfont, 1)
                self.tft.text((5, 146), "[hold]  CANCEL", TFT.YELLOW, sysfont, 1)
        except Exception as e:
            print(f"[display] Confirm render error: {e}")

    def render_status(
        self,
        temp=None,
        hum=None,
        ip=None,
        wifi_status="connected",
        requests_served=0,
        config_error=None,
        last_caller=None,
        override_text=None,
        logging_active=False,
        log_active_nodes=None,
        log_buffered_count=0,
        log_ntp_time_str=None,
        log_error=None,
        force_compact=False,
    ):
        """Renders telemetry and status on TFT screen, including logging section when active."""
        if self.tft is None:
            return

        if override_text:
            self.show_message(override_text)
            return

        try:
            self._acquire_bus()
            self.tft.fill(TFT.BLACK)

            # Telemetry Line (starts near top now that header is removed)
            t_str = f"{temp:.1f}C" if temp is not None else "--.-C"
            h_str = f"{hum:.0f}%" if hum is not None else "--%"
            line0 = f"T:{t_str} H:{h_str}"
            self.tft.text((5, 8), line0, TFT.GREEN, sysfont, 1)

            # Network Status
            if config_error or wifi_status == "config_error":
                err_msg = config_error if config_error else "Config Error"
                self.tft.text((5, 24), err_msg[:self.MAX_LINE_LEN], TFT.RED, sysfont, 1)
                self.tft.text((5, 38), "Check secrets.py", TFT.YELLOW, sysfont, 1)
            elif ip and wifi_status == "connected":
                clean_ip = str(ip).replace("http://", "").replace("https://", "").strip()
                self.tft.text((5, 24), clean_ip[:self.MAX_LINE_LEN], TFT.WHITE, sysfont, 1)
                self.tft.text((5, 38), "CoAP: /display", TFT.CYAN, sysfont, 1)
            else:
                status_label = "Connecting..." if wifi_status == "connecting" else "WiFi: Offline"
                self.tft.text((5, 24), status_label[:self.MAX_LINE_LEN], TFT.YELLOW, sysfont, 1)
                self.tft.text((5, 38), "Waiting for net", TFT.WHITE, sysfont, 1)

            # Requests served
            self.tft.text((5, 52), f"Reqs: {requests_served}", TFT.WHITE, sysfont, 1)

            # Last caller
            caller_str = str(last_caller) if last_caller else "--"
            self.tft.text((5, 66), f"Last: {caller_str}", TFT.PURPLE, sysfont, 1)

            # Logging Section (rendered when logging_active is True)
            if logging_active:
                divider_y = 78
                self.tft.line((0, divider_y), (self.width, divider_y), TFT.WHITE)

                # Format active board names: up to 7 characters each, wrapping across up to two lines
                # 128 px screen / ~6 px per 5x8 char = 20 chars fit on a line with 5 px margins
                max_line_len = 20
                node_names = list(log_active_nodes.values()) if isinstance(log_active_nodes, dict) else (log_active_nodes if log_active_nodes else [])
                short_ids = [str(n)[:7] for n in node_names]

                log_lines = []
                curr = "LOG"
                for sid in short_ids:
                    sep = " " if curr else ""
                    candidate = f"{curr}{sep}{sid}"
                    if len(candidate) <= max_line_len:
                        curr = candidate
                    else:
                        if curr:
                            log_lines.append(curr)
                        indent = " " if len(f" {sid}") <= max_line_len else ""
                        curr = f"{indent}{sid}"
                if curr:
                    log_lines.append(curr)

                y_log = 84
                for l in log_lines[:2]:
                    self.tft.text((5, y_log), l[:max_line_len], TFT.CYAN, sysfont, 1)
                    y_log += 12

                # Buffered readings line
                buf_line = f"Buf: {log_buffered_count} reads"
                self.tft.text((5, y_log), buf_line[:max_line_len], TFT.YELLOW, sysfont, 1)
                y_log += 12

                # NTP time line or error message
                if log_error:
                    self.tft.text((5, y_log), str(log_error)[:max_line_len], TFT.RED, sysfont, 1)
                else:
                    ntp_line = f"NTP: {log_ntp_time_str}" if log_ntp_time_str else "NTP: --:--"
                    self.tft.text((5, y_log), ntp_line[:max_line_len], TFT.GREEN, sysfont, 1)

        except Exception as e:
            print(f"[display] Render error: {e}")

    def update_from_state(self, app_state):
        """Extracts display parameters from AppState and renders them."""
        # Check logger state first
        logger_state = getattr(app_state, "logger_state", None)

        if logger_state == 1:  # LOGGER_STAGING
            self.render_staging_screen()
            return
        elif logger_state == 2:  # LOGGER_CONFIRM
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

        override_text = app_state.display_override_text if app_state.is_display_overridden() else None
        self.render_status(
            temp=app_state.temperature_c,
            hum=app_state.humidity_pct,
            ip=app_state.ip_address,
            wifi_status=app_state.wifi_status,
            requests_served=app_state.requests_served,
            config_error=app_state.config_error,
            last_caller=app_state.last_caller,
            override_text=override_text,
            logging_active=getattr(app_state, "logging_active", False),
            log_active_nodes=getattr(app_state, "log_active_nodes", {}),
            log_buffered_count=getattr(app_state, "log_buffered_count", 0),
            log_ntp_time_str=getattr(app_state, "log_ntp_time_str", None),
            log_error=getattr(app_state, "log_error", None),
        )

    def update(
        self,
        temp=None,
        hum=None,
        ip=None,
        wifi_status="connected",
        requests_served=0,
        config_error=None,
        last_caller=None,
        override_text=None,
        app_state=None,
        **kwargs,
    ):
        """Backwards-compatible update method accepting either app_state or discrete values."""
        if app_state is not None:
            self.update_from_state(app_state)
        else:
            self.render_status(
                temp=temp,
                hum=hum,
                ip=ip,
                wifi_status=wifi_status,
                requests_served=requests_served,
                config_error=config_error,
                last_caller=last_caller,
                override_text=override_text,
            )


# Compatibility alias matching OLEDDisplay interface
OLEDDisplay = TFTDisplay
