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

    def _acquire_bus(self):
        """Sets SD_CS HIGH and updates SPI frequency to TFT baudrate."""
        if hasattr(self, "sd_cs") and self.sd_cs is not None:
            self.sd_cs.value(1)
        if self.spi is not None:
            try:
                self.spi.init(baudrate=self.baudrate)
            except Exception:
                pass

    def clear(self):
        """Clears the display (fills with BLACK)."""
        if self.tft is not None:
            try:
                self._acquire_bus()
                self.tft.fill(TFT.BLACK)
            except Exception as e:
                print(f"[display] Clear error: {e}")

    def power_off(self):
        """Blanks the display for semi-sleep mode by filling solid BLACK."""
        self.clear()

    def show_splash(self, title="Pico 2W Station", subtitle="Starting..."):
        """Displays a startup splash screen."""
        if self.tft is None:
            return
        try:
            self._acquire_bus()
            self.tft.fill(TFT.BLACK)
            self.tft.text((10, 20), title[:16], TFT.GREEN, sysfont, 1)
            self.tft.line((0, 40), (self.width, 40), TFT.WHITE)
            self.tft.text((10, 50), subtitle[:16], TFT.YELLOW, sysfont, 1)
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
                while len(raw_line) > 16:
                    lines.append(raw_line[:16])
                    raw_line = raw_line[16:]
                lines.append(raw_line)

            y = 25
            for l in lines[:10]:
                self.tft.text((5, y), l, TFT.WHITE, sysfont, 1)
                y += 12
        except Exception as e:
            print(f"[display] Message render error: {e}")

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
    ):
        """Renders telemetry and status on TFT screen."""
        if self.tft is None:
            return

        if override_text:
            self.show_message(override_text)
            return

        try:
            self._acquire_bus()
            self.tft.fill(TFT.BLACK)

            # Header
            self.tft.text((5, 5), "Pico 2 W IoTMesh", TFT.CYAN, sysfont, 1)
            self.tft.line((0, 18), (self.width, 18), TFT.WHITE)

            # Telemetry Line
            t_str = f"{temp:.1f}C" if temp is not None else "--.-C"
            h_str = f"{hum:.0f}%" if hum is not None else "--%"
            line0 = f"T:{t_str} H:{h_str}"
            self.tft.text((5, 25), line0, TFT.GREEN, sysfont, 1)

            # Network Status
            if config_error or wifi_status == "config_error":
                err_msg = config_error if config_error else "Config Error"
                self.tft.text((5, 45), err_msg[:16], TFT.RED, sysfont, 1)
                self.tft.text((5, 60), "Check secrets.py", TFT.YELLOW, sysfont, 1)
            elif ip and wifi_status == "connected":
                clean_ip = str(ip).replace("http://", "").replace("https://", "").strip()
                self.tft.text((5, 45), clean_ip[:16], TFT.WHITE, sysfont, 1)
                self.tft.text((5, 60), "CoAP: /display", TFT.CYAN, sysfont, 1)
            else:
                status_label = "Connecting..." if wifi_status == "connecting" else "WiFi: Offline"
                self.tft.text((5, 45), status_label[:16], TFT.YELLOW, sysfont, 1)
                self.tft.text((5, 60), "Waiting for net", TFT.WHITE, sysfont, 1)

            # Requests served
            self.tft.text((5, 80), f"Reqs: {requests_served}", TFT.WHITE, sysfont, 1)

            # Last caller
            caller_str = str(last_caller) if last_caller else "--"
            self.tft.text((5, 95), f"Last: {caller_str}", TFT.PURPLE, sysfont, 1)

        except Exception as e:
            print(f"[display] Render error: {e}")

    def update_from_state(self, app_state):
        """Extracts display parameters from AppState and renders them."""
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
