"""SSD1306 OLED Display service for Raspberry Pi Pico W."""

import sys
import config

# Ensure local lib directory is in search path
for lib_dir in ("lib", "./lib", "/lib", "src/lib"):
    if lib_dir not in sys.path:
        sys.path.append(lib_dir)

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

    def show_splash(self, title="Pico Station", subtitle="Starting..."):
        """Displays a startup splash screen."""
        if self.oled is None:
            return
        try:
            self.oled.fill(0)
            self.oled.text(title[:16], 0, 16)
            self.oled.hline(0, 30, self.width, 1)
            self.oled.text(subtitle[:16], 0, 38)
            self.oled.show()
        except Exception as e:
            print(f"[display] Splash error: {e}")

    def update(
        self,
        temp=None,
        hum=None,
        light_state="dark",
        ip=None,
        wifi_status="connected",
        requests_served=0,
        config_error=None,
    ):
        """Renders sensor data, network status, remote URL, and request count.

        Coordinate mapping (8 lines, 8x8 font, bounds y: 0..63):
        - Line 0 (y=0):  T:23.4C  H:55%
        - Line 1 (y=10): Light: Bright / Light: Dark
        - Line 2 (y=20): Horizontal separator
        - Line 3 (y=24): URL for Data: / WiFi status / WiFi Config Err:
        - Line 4 (y=34): http://<ip> / IP address / Error details
        - Line 5 (y=44): /sensors / status info / Guidance message
        - Line 6 (y=54): Reqs: <count>
        """
        if self.oled is None:
            return

        try:
            self.oled.fill(0)

            # Line 0: Temperature & Humidity
            t_str = f"{temp:.1f}C" if temp is not None else "--.-C"
            h_str = f"{hum:.0f}%" if hum is not None else "--%"
            line0 = f"T:{t_str} H:{h_str}"
            self.oled.text(line0[:16], 0, 0)

            # Line 1: Light state
            l_str = "Bright" if (light_state == "light" or light_state is True) else "Dark"
            line1 = f"Light: {l_str}"
            self.oled.text(line1[:16], 0, 10)

            # Line 2: Horizontal rule
            self.oled.hline(0, 20, self.width, 1)

            # Lines 3, 4, 5: Network info, Remote URL, or Config Error
            if config_error or wifi_status == "config_error":
                err_msg = config_error if config_error else "Config Error"
                self.oled.text("WiFi Config Err:", 0, 24)
                self.oled.text(err_msg[:16], 0, 34)
                self.oled.text("Check secrets.py", 0, 44)
            elif ip and wifi_status == "connected":
                full_host = f"http://{ip}"
                if len(full_host) <= 16:
                    self.oled.text("URL for Data:", 0, 24)
                    self.oled.text(full_host, 0, 34)
                    self.oled.text("/sensors", 0, 44)
                else:
                    self.oled.text("http://", 0, 24)
                    self.oled.text(ip[:16], 0, 34)
                    self.oled.text("/sensors", 0, 44)
            else:
                status_label = "Connecting..." if wifi_status == "connecting" else "WiFi: Offline"
                self.oled.text(status_label[:16], 0, 24)
                self.oled.text("IP: None", 0, 34)
                self.oled.text("Waiting for net", 0, 44)

            # Line 6: Request count
            line6 = f"Reqs: {requests_served}"
            self.oled.text(line6[:16], 0, 54)

            self.oled.show()
        except Exception as e:
            print(f"[display] Render error: {e}")
