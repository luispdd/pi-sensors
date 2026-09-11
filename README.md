# Raspberry Pi Pico W Environmental Sensor Station

A standalone, non-blocking environmental monitor powered by the **Raspberry Pi Pico W** running MicroPython. It samples ambient temperature, humidity, and light levels, displays live metrics alongside a remote query URL and request hit counter on an SSD1306 OLED screen, and serves telemetry over local WiFi as JSON via an asynchronous HTTP endpoint.

---

## Features

- **Environmental Sensing**:
  - **DHT22**: Temperature (°C) and relative humidity (%) with fault tolerance and error retention.
  - **LM393 Photoresistor**: Digital ambient light state detection (bright / dark).
- **SSD1306 I2C OLED Display (128x64)**:
  - Real-time temperature, humidity, and light readings.
  - Active network status and local IP address.
  - Full remote access URL (`http://<IP>/sensors`).
  - Live cumulative counter of served HTTP requests (`Reqs: <count>`).
- **Networking & Asynchronous HTTP Web Server**:
  - Non-blocking WiFi connection manager with automatic background keepalive reconnects.
  - Asynchronous `uasyncio` HTTP server hosting `GET /sensors` returning structured JSON telemetry.
  - Increments cumulative API request counter upon each query.

---

## Hardware Wiring Diagram

Connect components to the Raspberry Pi Pico W as follows:

| Component | Component Pin | Pico W Pin Name | Pico W Physical Pin |
| :--- | :--- | :--- | :--- |
| **Common Power** | VCC / + | 3V3 OUT | Pin 36 |
| **Common Ground**| GND / - | GND | Pin 38 (or any GND) |
| **SSD1306 OLED** | SDA | GP0 (I2C0 SDA) | Pin 1 |
| | SCL | GP1 (I2C0 SCL) | Pin 2 |
| **DHT22** | DATA (OUT) | GP15 | Pin 20 |
| **LM393 Sensor** | DO (Digital Out)| GP14 | Pin 19 |

> [!TIP]
> If using a raw 4-pin DHT22 sensor (rather than a 3-pin breakout board with a built-in resistor), connect a 4.7kΩ–10kΩ pull-up resistor between the DATA pin and 3V3.

---

## OLED Screen Layout (128x64)

The screen is rendered using an 8x8 font across 8 horizontal lines:

```text
+----------------+
|T:23.4C  H:58%  |  Line 0: Temp & Humidity
|Light: Bright   |  Line 1: Light state
|----------------|  Line 2: Divider
|URL for Data:   |  Line 3: Endpoint description
|http://192.168.1|  Line 4: Host IP
|/sensors        |  Line 5: Route path
|Reqs: 42        |  Line 6: Cumulative hit count
+----------------+
```

When disconnected or connecting to WiFi, lines 3–5 dynamically indicate connection status (e.g. `WiFi: Connecting...` or `WiFi: Offline`).

If `secrets.py` is missing or credentials are not configured, the OLED screen reports a configuration error:
```text
+----------------+
|T:23.4C  H:58%  |  Line 0: Temp & Humidity
|Light: Bright   |  Line 1: Light state
|----------------|  Line 2: Divider
|WiFi Config Err:|  Line 3: Error title
|No secrets.py   |  Line 4: Specific error cause
|Check secrets.py|  Line 5: Remediation guidance
|Reqs: 0         |  Line 6: Cumulative hit count
+----------------+
```

---

## Installation & Deployment

### 1. Install MicroPython on the Pico W
1. Download the latest Raspberry Pi Pico W MicroPython firmware (`.uf2`) from [micropython.org](https://micropython.org/download/RPI_PICO_W/).
2. Hold down the **BOOTSEL** button on your Pico W while plugging it into your computer via USB.
3. Drag and drop the `.uf2` file into the `RPI-RP2` USB drive. The board will automatically reboot into MicroPython.

### 2. Configure WiFi Credentials (`secrets.py`)
WiFi credentials are kept in an untracked `secrets.py` file ignored by Git.

Copy the template from `src/secrets.py.example`:
```bash
cp src/secrets.py.example src/secrets.py
```
Edit `src/secrets.py` with your WiFi network settings:
```python
WIFI_SSID = "Your_WiFi_Network"
WIFI_PASSWORD = "Your_WiFi_Password"
```

### 3. Upload Files to Pico W

#### Option A: Using `mpremote` (CLI)
Install `mpremote` via pip:
```bash
pip install mpremote
```
Create the `lib` directory on the Pico and upload all application modules and credentials from `src/`:
```bash
mpremote mkdir :lib
mpremote cp src/lib/ssd1306.py :lib/
mpremote cp src/secrets.py src/config.py src/state.py src/sensors.py src/display.py src/network_manager.py src/webserver.py src/main.py :
```
Run `main.py`:
```bash
mpremote run src/main.py
```

#### Option B: Using Thonny IDE
1. Open [Thonny IDE](https://thonny.org/).
2. Set the interpreter (bottom-right corner) to **MicroPython (Raspberry Pi Pico)**.
3. In the Pico file explorer, create a folder named `lib` and upload `src/lib/ssd1306.py` into it.
4. Save your `secrets.py` and the remaining files from `src/` directly to the root of the Pico device:
   - `secrets.py`
   - `config.py`
   - `state.py`
   - `sensors.py`
   - `display.py`
   - `network_manager.py`
   - `webserver.py`
   - `main.py`
5. When `main.py` is saved to the root of the Pico, it automatically executes on every boot.

---

## API Usage

### `GET /sensors`
Fetches current environmental measurements and station telemetry.

#### Example Request
```bash
curl -i http://<PICO_IP>/sensors
```

#### Example Response
```http
HTTP/1.1 200 OK
Content-Type: application/json
Access-Control-Allow-Origin: *
Connection: close
Content-Length: 138

{
  "temperature_c": 22.4,
  "humidity_pct": 58.1,
  "light": "light",
  "light_detected": true,
  "requests_served": 1,
  "uptime_s": 42,
  "status": "ok"
}
```

#### JSON Fields
| Field | Type | Description |
| :--- | :--- | :--- |
| `temperature_c` | `float` \| `null` | Ambient temperature in degrees Celsius (°C) |
| `humidity_pct` | `float` \| `null` | Relative humidity percentage (%) |
| `light` | `string` | Ambient light state: `"light"` or `"dark"` |
| `light_detected` | `boolean` | `true` if ambient illumination is detected, `false` otherwise |
| `requests_served`| `integer` | Cumulative count of HTTP `/sensors` requests served |
| `uptime_s` | `integer` | Device uptime in seconds since boot |
| `status` | `string` | System status (`"ok"`) |

---

## Project Structure

```text
pi-sensors-dht22-light/
├── README.md
├── src/
│   ├── config.py           # Pin mappings, display & polling settings, secrets loader
│   ├── secrets.py.example  # Template for untracked WiFi credentials (secrets.py)
│   ├── state.py            # Shared application telemetry state container (AppState)
│   ├── sensors.py          # DHT22 & LM393 sensor drivers with error resilience
│   ├── display.py          # SSD1306 OLED renderer (live telemetry, remote URL, hits)
│   ├── network_manager.py  # Non-blocking WiFi connection & reconnect watchdog
│   ├── webserver.py        # Asynchronous HTTP server for GET /sensors
│   ├── main.py             # Root entry point orchestrating uasyncio coroutines
│   └── lib/
│       └── ssd1306.py      # stlehmann/micropython-ssd1306 OLED driver
└── openspec/               # OpenSpec change management and spec documentation
```

