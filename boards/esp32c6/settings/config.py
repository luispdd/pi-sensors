import sys

# Ensure local directories are in search path across all modules
for search_dir in ("lib", "./lib", "/lib", "settings", "./settings", "/settings"):
    if search_dir not in sys.path:
        sys.path.append(search_dir)

# Attempt to load credentials from external untracked secrets.py
WIFI_SSID = None
WIFI_PASSWORD = None
WIFI_CONFIG_ERROR = None

try:
    import secrets

    if hasattr(secrets, "WIFI_SSID") or hasattr(secrets, "WIFI_PASSWORD"):
        WIFI_SSID = getattr(secrets, "WIFI_SSID", None)
        WIFI_PASSWORD = getattr(secrets, "WIFI_PASSWORD", None)
    else:
        WIFI_CONFIG_ERROR = "No secrets.py"
except ImportError:
    WIFI_CONFIG_ERROR = "No secrets.py"

# Validate credentials if secrets.py was found
if WIFI_CONFIG_ERROR is None:
    if not WIFI_SSID or not WIFI_PASSWORD:
        WIFI_CONFIG_ERROR = "Empty SSID/Pwd"
    elif WIFI_SSID == "YOUR_WIFI_SSID" or WIFI_PASSWORD == "YOUR_WIFI_PASSWORD":
        WIFI_CONFIG_ERROR = "Default SSID/Pwd"


def has_valid_credentials():
    """Returns True if valid WiFi credentials are loaded."""
    return WIFI_CONFIG_ERROR is None


# WiFi Retry Interval
WIFI_RETRY_INTERVAL_S = 10

# Hardware Pin Mappings for Waveshare ESP32-C6-Zero
# Left Pin 4 (GPIO 0) -> SSD1306 Display SDA
# Left Pin 5 (GPIO 1) -> SSD1306 Display SCL (400 kHz)
# Left Pin 6 (GPIO 2) -> DHT22 DATA
# Left Pin 7 (GPIO 3) -> Button Pin A (active-LOW, PULL_UP)
# Onboard   (GPIO 8) -> Onboard WS2812 RGB LED (NeoPixel)
PIN_I2C_SDA = 0         # GPIO 0 - I2C SDA
PIN_I2C_SCL = 1         # GPIO 1 - I2C SCL
PIN_DHT22 = 2           # GPIO 2 - DHT22 Data line
PIN_BUTTON = 3          # GPIO 3 - User/Mode Button (active LOW, internal pull-up)
PIN_RGB_LED = 8         # GPIO 8 - Onboard WS2812 RGB LED (NeoPixel)

# I2C & SSD1306 OLED Display Settings
I2C_ID = 0
I2C_FREQ = 400_000      # 400kHz
OLED_WIDTH = 128
OLED_HEIGHT = 64
DISPLAY_WIDTH = OLED_WIDTH
DISPLAY_HEIGHT = OLED_HEIGHT

# Timing & Intervals (in seconds)
SENSOR_READ_INTERVAL_S = 2.5       # DHT22 requires >= 2s between readings
DISPLAY_REFRESH_INTERVAL_S = 1.0   # UI update interval

# HTTP & CoAP Server Configuration
HTTP_PORT = 80
COAP_PORT = 5683
DEFAULT_DEVICE_ID = "esp32c6"
DEFAULT_DEVICE_TYPE = "esp32c6"

DEVICE_ID = getattr(secrets, "DEVICE_ID", DEFAULT_DEVICE_ID) if (WIFI_CONFIG_ERROR is None and 'secrets' in locals() and hasattr(secrets, "DEVICE_ID")) else DEFAULT_DEVICE_ID
DEVICE_TYPE = getattr(secrets, "DEVICE_TYPE", DEFAULT_DEVICE_TYPE) if (WIFI_CONFIG_ERROR is None and 'secrets' in locals() and hasattr(secrets, "DEVICE_TYPE")) else DEFAULT_DEVICE_TYPE
