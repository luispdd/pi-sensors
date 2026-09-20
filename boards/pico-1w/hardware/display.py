"""SSD1306 OLED Display service for Raspberry Pi Pico W."""

import sys
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


class OLEDDisplay:
    def __init__(
        self,
        sda_pin=config.PIN_I2C_SDA,
        scl_pin=config.PIN_I2C_SCL,
        i2c_id=config.I2C_ID,
        freq=config.I2C_FREQ,
        width=config.OLED_WIDTH,
        height=config.OLED_HEIGHT,
    ):
        self.width = width
        self.height = height
        self.oled = None
        self.i2c = None

        if I2C is not None and Pin is not None and ssd1306 is not None:
            try:
                self.i2c = I2C(i2c_id, sda=Pin(sda_pin), scl=Pin(scl_pin), freq=freq)
                self.oled = ssd1306.SSD1306_I2C(self.width, self.height, self.i2c)
            except Exception as e:
                print(f"[display] OLED initialization failed: {e}")
                self.oled = None

    def clear(self):
        """Clears the display."""
        if self.oled is not None:
            try:
                self.oled.fill(0)
                self.oled.show()
            except Exception as e:
                print(f"[display] Clear error: {e}")

    def power_off(self):
        """Blanks and powers off the display for semi-sleep mode."""
        if self.oled is not None:
            try:
                self.oled.fill(0)
                self.oled.show()
            except Exception as e:
                print(f"[display] Power off error: {e}")

    MAX_LINE_LEN = 16 # Length of a line in characters for ssd1306 128x64 OLED display (8x5 font)

    def show_splash(self, title="Pico Station", subtitle="Starting..."):
        """Displays a startup splash screen."""
        if self.oled is None:
            return
        try:
            self.oled.fill(0)
            self.oled.text(title[:  self.MAX_LINE_LEN], 0, 16)
            self.oled.hline(0, 30, self.width, 1)
            self.oled.text(subtitle[:self.MAX_LINE_LEN], 0, 38)
            self.oled.show()
        except Exception as e:
            print(f"[display] Splash error: {e}")

    def show_message(self, text):
        """Displays an override text message on the OLED screen."""
        if self.oled is None:
            return
        try:
            if isinstance(text, (bytes, bytearray)):
                text = text.decode("utf-8")
            else:
                text = str(text)

            self.oled.fill(0)
            self.oled.text("[Message]", 0, 0)
            self.oled.hline(0, 10, self.width, 1)

            # Simple line wrapping for max_line_len chars per line
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
        """Renders sensor data, network status, remote route, request count, and last caller.

        Coordinate mapping (8x8 font, bounds y: 0..63):
        - Line 0 (y=2):  T:23.4C  H:55%
        - Line 1 (y=16): <ip> (without http://) / WiFi status / Config Error
        - Line 2 (y=28): /info / status info / Guidance message
        - Line 3 (y=40): Reqs: <count>
        - Line 4 (y=52): Last: <caller>
        """
        if self.oled is None:
            return

        if override_text:
            self.show_message(override_text)
            return

        try:
            self.oled.fill(0)

            # Line 0: Temperature & Humidity (y=2)
            t_str = f"{temp:.1f}C" if temp is not None else "--.-C"
            h_str = f"{hum:.0f}%" if hum is not None else "--%"
            line0 = f"T:{t_str} H:{h_str}"
            self.oled.text(line0[:self.MAX_LINE_LEN], 0, 2)

            # Line 1 & Line 2: Network info / Route / Error (y=16, y=28)
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

            # Line 3: Request count (y=40)
            line3 = f"Reqs: {requests_served}"
            self.oled.text(line3[:self.MAX_LINE_LEN], 0, 40)

            # Line 4: Last caller (y=52)
            caller_str = str(last_caller) if last_caller else "--"
            line4 = f"Last: {caller_str}"
            self.oled.text(line4[:self.MAX_LINE_LEN], 0, 52)

            self.oled.show()
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


