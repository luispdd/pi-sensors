"""Configuration settings for Raspberry Pi Pico W sensor station."""

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
        # Python standard library 'secrets' was imported instead of local secrets.py
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

# Hardware Pin Mappings (GPIO numbers)
PIN_DHT22 = 15      # GP15 (Pin 20) - DHT22 Data line
PIN_LM393 = 14      # GP14 (Pin 19) - LM393 Digital Out (DO)
LM393_ACTIVE_LOW = True  # Most LM393 photoresistor boards output 0 (LOW) when illuminated
PIN_I2C_SDA = 0     # GP0 (Pin 1) - I2C0 SDA for SSD1306 OLED
PIN_I2C_SCL = 1     # GP1 (Pin 2) - I2C0 SCL for SSD1306 OLED

# I2C & OLED Display Settings
I2C_ID = 0
I2C_FREQ = 400_000  # 400kHz
OLED_WIDTH = 128
OLED_HEIGHT = 64

# Timing & Intervals (in seconds)
SENSOR_READ_INTERVAL_S = 2.0       # DHT22 requires >= 1-2s between readings
DISPLAY_REFRESH_INTERVAL_S = 1.0   # Refresh OLED display every second

# HTTP Server Configuration
HTTP_PORT = 80

# CoAP & IoTMesh Configuration
COAP_PORT = 5683
DEVICE_ID = getattr(secrets, "DEVICE_ID", "pico-1") if (WIFI_CONFIG_ERROR is None and 'secrets' in locals() and hasattr(secrets, "DEVICE_ID")) else "pico-1"
DEVICE_TYPE = getattr(secrets, "DEVICE_TYPE", "rp2040") if (WIFI_CONFIG_ERROR is None and 'secrets' in locals() and hasattr(secrets, "DEVICE_TYPE")) else "rp2040"
DISPLAY_OVERRIDE_DURATION_S = 60
