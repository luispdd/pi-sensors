import sys

# Ensure local lib and settings directories are in search path across all modules
for search_dir in ("lib", "./lib", "/lib", "src/lib", "settings", "./settings", "/settings"):
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

# Hardware Pin Mappings (GPIO numbers for Pico 2 W / RP2350)
PIN_DHT22 = 15      # GP15 (Pin 20) - DHT22 Data line
PIN_LIGHT_ADC = 26  # GP26 (Pin 31) - ADC0 for ADA2748 ALS-PT19 light sensor
LIGHT_SCALE_FACTOR = 4.0  # Linear scaling multiplier (8.0x: ~5% raw daylight -> 40%)
PIN_BUTTON = 14     # GP14 (Pin 19) - Reset/Acknowledge button (active LOW, internal pull-up)
PIN_BUTTON_LOG = 13 # GP13 (Pin 17) - Data logger control button (active LOW, internal pull-up)
PIN_LED_ALERT = "LED" 

SPI_BUS = 0
SPI_SCK = 18    # GP18 - Pin 24 - shared SCK
SPI_MOSI = 19   # GP19 - Pin 25 - shared MOSI (TFT SDA, SD MOSI)
SPI_MISO = 16   # GP16 - Pin 21 - SD MISO only (TFT has no MISO)

TFT_CS = 17     # GP17 - Pin 22 - TFT chip select (active LOW)
TFT_DC = 20     # GP20 - Pin 26 - data/command (LOW=cmd, HIGH=data)
TFT_RESET = 21  # GP21 - Pin 27 - reset (active LOW)

SD_CS = 22      # GP22 - Pin 29 - SD chip select (active LOW)

# SPI Clock Speeds
SPI_SPEED_SD_INIT = 400_000     # <=400 kHz required for SD identification phase
SPI_SPEED_SD_DATA = 10_000_000  # 10 MHz for SD data transfers after init
SPI_SPEED_TFT = 20_000_000      # 20 MHz for TFT pixel writes

# TFT Display Geometry
TFT_WIDTH = 128
TFT_HEIGHT = 160
TFT_MADCTL = 0x00

# Display geometry alias
DISPLAY_WIDTH = TFT_WIDTH
DISPLAY_HEIGHT = TFT_HEIGHT

# Timing & Intervals (in seconds)
SENSOR_READ_INTERVAL_S = 2.0       # DHT22 requires >= 1-2s between readings
DISPLAY_REFRESH_INTERVAL_S = 1.0
SENSOR_LOG_INTERVAL_S = 300        # Periodic logging sample interval (5 minutes)
LOG_FLUSH_INTERVAL_S = 3600        # SD card auto-flush interval (1 hour)

# Data Logger Storage Configuration
LOG_SD_ROOT = "/sensor-data"

# HTTP Server Configuration
HTTP_PORT = 80

# CoAP & IoTMesh Configuration
COAP_PORT = 5683
DEFAULT_DEVICE_ID = "pico-2w"
DEFAULT_DEVICE_TYPE = "rp2350"
DEVICE_ID = getattr(secrets, "DEVICE_ID", DEFAULT_DEVICE_ID) if (WIFI_CONFIG_ERROR is None and 'secrets' in locals() and hasattr(secrets, "DEVICE_ID")) else DEFAULT_DEVICE_ID
DEVICE_TYPE = getattr(secrets, "DEVICE_TYPE", DEFAULT_DEVICE_TYPE) if (WIFI_CONFIG_ERROR is None and 'secrets' in locals() and hasattr(secrets, "DEVICE_TYPE")) else DEFAULT_DEVICE_TYPE
