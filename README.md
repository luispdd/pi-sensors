# Raspberry Pi Pico Environmental Sensor Station & IoTMesh Nodes

A multi-board MicroPython project implementing environmental sensing, display actuators, and mesh network nodes using **IoTMesh CoAP** (RFC 7252) and HTTP services.

---

## Supported Boards

### 1. `pico-1w` — Pico W Environmental Station with SSD1306 OLED
Located in `boards/pico-1w/`.
- **Microcontroller**: Raspberry Pi Pico W (RP2040)
- **Peripherals**: DHT22 temperature & humidity sensor, SSD1306 OLED screen (I2C), GP14 reset button, GP16 alert LED.
- **Capabilities**: Full environmental telemetry, SSD1306 OLED status display, interactive alert notifications (`POST /display`), HTTP (`GET /info`), and CoAP server.

### 2. `pico-2w` — Pico 2 W TFT Display & SD Card Node
Located in `boards/pico-2w/`.
- **Microcontroller**: Raspberry Pi Pico 2 W (RP2350)
- **Peripherals**: ST7735 TFT color display (128x160), MicroSD card reader sharing hardware **SPI0** with bus arbitration.
- **Capabilities**: WiFi connectivity, CoAP IoTMesh server with display actuator, HTTP server, ST7735 TFT telemetry & alert rendering.

---

## Hardware Wiring Diagrams

### `pico-1w` (Raspberry Pi Pico W)
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

### `pico-2w` (Raspberry Pi Pico 2 W)
| Peripheral | Signal | Pico 2 W Pin (GPIO) | Physical Pin | Notes |
|---|---|---|---|---|
| **Shared SPI0** | SCK | GP18 | Pin 24 | Shared clock line |
| **Shared SPI0** | MOSI | GP19 | Pin 25 | Shared data out line |
| **Shared SPI0** | MISO | GP16 | Pin 21 | SD MISO line |
| **ST7735 TFT** | CS | GP17 | Pin 22 | Active LOW |
| **ST7735 TFT** | DC | GP20 | Pin 26 | Command/Data toggle |
| **ST7735 TFT** | RESET | GP21 | Pin 27 | Active LOW reset |
| **SD Card** | CS | GP22 | Pin 29 | Active LOW |

---

## API Usage

### 1. HTTP Telemetry (`GET /info`)
Fetches current environmental measurements and station telemetry. (Also available under `/sensors`).

#### Example Request
```bash
curl -i http://<NODE_IP>/info
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

---

### 2. IoTMesh CoAP API (UDP port 5683)

#### Discovery (`GET /.well-known/core`)
```bash
coap-client -m get coap://<NODE_IP>/.well-known/core
```

#### Sensor Collection (`GET /sensors`)
```bash
coap-client -m get coap://<NODE_IP>/sensors
```

#### Trigger Display Alert (`POST /display`)
```bash
coap-client -m post -e "Meeting in Room 3" coap://<NODE_IP>/display
```

---

## Project Structure

```text
pi-sensors-dht22-light/
├── README.md
├── AGENTS.md
├── boards/
│   ├── pico-1w/            # Pico W (RP2040) firmware (DHT22 + OLED + IoTMesh)
│   │   ├── main.py
│   │   ├── settings/
│   │   ├── services/
│   │   ├── hardware/
│   │   ├── core/
│   │   └── lib/
│   └── pico-2w/            # Pico 2 W (RP2350) firmware (ST7735 TFT + SD + IoTMesh)
│       ├── main.py
│       ├── settings/
│       ├── services/
│       ├── hardware/
│       ├── core/
│       ├── lib/
│       └── test/
└── openspec/               # OpenSpec specs, changes, and verification artifacts
```
