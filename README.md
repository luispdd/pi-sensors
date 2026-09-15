# Raspberry Pi Pico W Environmental Sensor Station & Interactive Alert Terminal

A standalone, non-blocking environmental monitor and interactive notification terminal powered by the **Raspberry Pi Pico W** running MicroPython. It samples ambient temperature and humidity with a DHT22 sensor, renders telemetry and caller diagnostics on an SSD1306 OLED screen, serves telemetry over HTTP (`GET /info`), and integrates with local mesh networks via **IoTMesh CoAP** (RFC 7252). Remote alert messages sent via `POST /display` trigger a physical alert LED and stay on-screen until dismissed with a physical button.

---

## Features

- **Environmental Sensing**:
  - **DHT22**: Temperature (°C) and relative humidity (%) with fault tolerance and error retention.
- **Physical Controls & Alert Notification**:
  - **Alert LED (GP16)**: Illuminates whenever an active display alert message is received.
  - **Reset/Acknowledge Button (GP14)**: Physical button wired to ground (internal pull-up) to acknowledge alerts, turning off the LED and restoring the default metrics screen.
- **SSD1306 I2C OLED Display (128x64)**:
  - Line 0: Real-time temperature (°C) and humidity (%).
  - Line 1: Clean local IPv4 address (protocol prefix stripped).
  - Line 2: Remote endpoint route (`/info`).
  - Line 3: Cumulative request hit counter (`Reqs: <count>`).
  - Line 4: Last caller identification (`Last: <node-id or IP-octet>`).
  - Custom alert overlay when an alert message is received via CoAP `POST /display`.
- **Networking & Dual-Protocol Services**:
  - **WiFi Manager**: Non-blocking connection management with background keepalive and automatic reconnection.
  - **Asynchronous HTTP Web Server**: Exposes `GET /info` (and `GET /sensors`) returning structured JSON telemetry.
  - **IoTMesh CoAP Server (UDP 5683)**:
    - `GET /.well-known/core`: CoRE Link Format discovery.
    - `GET /id`: Station identity (`DEVICE_ID` & `DEVICE_TYPE`).
    - `GET /sensors`: SenML Pack array of temperature and humidity measurements.
    - `GET /sensors/temperature` & `GET /sensors/humidity`: Individual SenML sensor endpoints.
    - `POST /display`: Displays custom alert text and illuminates the alert LED until the physical button is pressed.
    - **Caller Resolution**: Caches network node IDs from CoRE link discoveries; probes unknown callers to resolve IDs, falling back to the caller's last IP octet.

---

## Hardware Wiring Diagram

Connect components to the Raspberry Pi Pico W as follows:

| Component | Component Pin | Pico W Pin Name | Pico W Physical Pin | Notes |
| :--- | :--- | :--- | :--- | :--- |
| **Common Power** | VCC / + | 3V3 OUT | Pin 36 | Powers sensors & display |
| **Common Ground**| GND / - | GND | Pin 38 (or any GND) | Common ground rail |
| **SSD1306 OLED** | SDA | GP0 (I2C0 SDA) | Pin 1 | Default I2C bus 0 |
| | SCL | GP1 (I2C0 SCL) | Pin 2 | 400kHz I2C bus |
| **DHT22** | DATA (OUT) | GP15 | Pin 20 | Temp & Humidity data line |
| **Reset Button** | Pin A | GP14 | Pin 19 | Configured with internal pull-up |
| | Pin B | GND | Pin 18 / Pin 38 | Pressed = LOW |
| **Alert LED** | Anode (+) | GP16 | Pin 21 | Active HIGH |
| | Cathode (-) | GND | Pin 18 / Pin 38 | In series with **330Ω** resistor |

> [!TIP]
> If using a raw 4-pin DHT22 sensor (rather than a 3-pin breakout board with a built-in resistor), connect a 4.7kΩ–10kΩ pull-up resistor between the DATA pin and 3V3.

---

## OLED Screen Layout (128x64)

### Normal Monitoring Mode
```text
+----------------+
|T:23.4C  H:58%  |  Line 0 (y=2):  Temp & Humidity
|192.168.1.238   |  Line 1 (y=16): Host IP (no prefix)
|/info           |  Line 2 (y=28): Primary HTTP route
|Reqs: 42        |  Line 3 (y=40): Cumulative request counter
|Last: 238       |  Line 4 (y=52): Last caller (node ID or octet)
+----------------+
```

### Alert Overlay Mode (`POST /display`)
When a remote message is received, the alert LED on GP16 turns **ON** and the display switches to the alert screen indefinitely until the GP14 button is pressed:
```text
+----------------+
|[Alert]         |  Title banner
|----------------|  Divider
|Meeting in      |  Alert message text
|Room 3          |  (wrapped up to 5 lines)
|                |
+----------------+
```
Pressing the reset button turns off the LED and restores normal monitoring mode.

### Network Status & Configuration Errors
When disconnected or reconnecting:
```text
+----------------+
|T:23.4C  H:58%  |
|Connecting...   |  WiFi status
|Waiting for net |  Diagnostics
|Reqs: 0         |
|Last: --        |
+----------------+
```

If `secrets.py` is missing or invalid:
```text
+----------------+
|T:23.4C  H:58%  |
|No secrets.py   |  Error cause
|Check secrets.py|  Remediation instructions
|Reqs: 0         |
|Last: --        |
+----------------+
```

---

## Installation & Deployment

### 1. Install MicroPython on the Pico W
1. Download the latest Raspberry Pi Pico W MicroPython firmware (`.uf2`) from [micropython.org](https://micropython.org/download/RPI_PICO_W/).
2. Hold down the **BOOTSEL** button on your Pico W while plugging it into your computer via USB.
3. Drag and drop the `.uf2` file into the `RPI-RP2` drive. The board will automatically reboot into MicroPython.

### 2. Configure WiFi Credentials & Device Identity (`secrets.py`)
Copy the template from `src/secrets.py.example`:
```bash
cp src/secrets.py.example src/secrets.py
```
Edit `src/secrets.py`:
```python
WIFI_SSID = "Your_WiFi_Network"
WIFI_PASSWORD = "Your_WiFi_Password"
DEVICE_ID = "pico-livingroom"
DEVICE_TYPE = "rp2040"
```

### 3. Upload Files to Pico W

#### Option A: Using `mpremote` (CLI)
Install `mpremote`:
```bash
pip install mpremote
```
Upload the library directory and source files:
```bash
# Upload libraries
mpremote mkdir :lib
mpremote cp -r src/lib/ :lib/

# Upload source modules
mpremote cp src/secrets.py src/config.py src/state.py src/sensors.py src/display.py src/network_manager.py src/webserver.py src/coap_server.py src/main.py :
```
Run `main.py`:
```bash
mpremote run src/main.py
```

#### Option B: Using Thonny IDE
1. Open [Thonny IDE](https://thonny.org/).
2. Set the interpreter (bottom-right corner) to **MicroPython (Raspberry Pi Pico)**.
3. Upload `src/lib/` to `/lib/` on the Pico W device.
4. Save your `secrets.py` and the Python modules from `src/` to the root of the Pico:
   - `secrets.py`
   - `config.py`
   - `state.py`
   - `sensors.py`
   - `display.py`
   - `network_manager.py`
   - `webserver.py`
   - `coap_server.py`
   - `main.py`
5. Click **Run current script (F5)** or reboot the device.

---

## API Usage

### 1. HTTP Telemetry (`GET /info`)
Fetches current environmental measurements and station telemetry. (Also available under `/sensors`).

#### Example Request
```bash
curl -i http://<PICO_IP>/info
```

#### Example Response
```http
HTTP/1.1 200 OK
Content-Type: application/json
Access-Control-Allow-Origin: *
Connection: close
Content-Length: 98

{
  "temperature_c": 22.4,
  "humidity_pct": 58.1,
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
| `requests_served`| `integer` | Cumulative count of HTTP and CoAP requests served |
| `uptime_s` | `integer` | Device uptime in seconds since boot |
| `status` | `string` | System operational status (`"ok"`) |

---

### 2. IoTMesh CoAP API (UDP port 5683)

#### Discovery (`GET /.well-known/core`)
```bash
coap-client -m get coap://<PICO_IP>/.well-known/core
```
**Response (2.05 Content, Link Format):**
```text
</id>;rt="core.d";ep="pico-livingroom";dt="rp2040",</sensors>;rt="sensor-collection";if="sensor",</sensors/temperature>;rt="temperature";if="sensor",</sensors/humidity>;rt="humidity";if="sensor",</display>;rt="display";if="actuator"
```

#### Sensor Collection (`GET /sensors`)
```bash
coap-client -m get coap://<PICO_IP>/sensors
```
**Response (SenML Pack JSON):**
```json
[
  {"n": "temperature", "u": "Cel", "v": 22.4},
  {"n": "humidity", "u": "%RH", "v": 58.1}
]
```

#### Individual Sensor Readings
- **Temperature**: `coap-client -m get coap://<PICO_IP>/sensors/temperature`
- **Humidity**: `coap-client -m get coap://<PICO_IP>/sensors/humidity`

#### Trigger Display Alert (`POST /display`)
```bash
coap-client -m post -e "Meeting in Room 3" coap://<PICO_IP>/display
```
- Returns `2.04 Changed`.
- Displays `"Meeting in Room 3"` on the OLED screen.
- Turns on the GP16 alert LED.
- Resolves the caller identifier (or last IP octet) and logs it on `Last: <caller>`.
- Persists until the user presses the GP14 button.

---

## Project Structure

```text
pi-sensors-dht22-light/
├── README.md
├── AGENTS.md
├── src/
│   ├── config.py           # Hardware pin configurations, timings, and secrets loader
│   ├── secrets.py.example  # Template for untracked WiFi credentials & device ID
│   ├── state.py            # AppState container (metrics, caller cache, alert flags)
│   ├── sensors.py          # DHT22 sensor driver with error resilience
│   ├── display.py          # SSD1306 OLED renderer (metrics, /info, caller, alerts)
│   ├── network_manager.py  # Non-blocking WiFi connection & reconnect watchdog
│   ├── webserver.py        # Asynchronous HTTP server for GET /info
│   ├── coap_server.py      # Asynchronous IoTMesh CoAP server (RFC 7252)
│   ├── main.py             # Entry point orchestrating tasks (sensors, display, button, CoAP, web)
│   └── lib/
│       ├── ssd1306.py      # SSD1306 I2C OLED driver
│       └── microcoapy/     # Lightweight MicroPython CoAP implementation
└── openspec/               # OpenSpec specs, changes, and verification artifacts
```
