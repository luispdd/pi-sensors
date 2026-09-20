## Why

The station currently uses a passive light sensor that provides limited utility and has an OLED layout cluttered with redundant labels and protocol prefixes. Furthermore, remote messages on `/display` currently disappear automatically after 60 seconds without physical acknowledgement. Replacing the light sensor with a physical button and an alert LED transforms the station into an interactive notification terminal where alerts require physical dismissal, while cleaning up the display and enhancing node traceability.

## What Changes

- **Hardware**: Remove LM393 digital light sensor from GP14. Add a physical reset/acknowledge push button on GP14 and a single-color alert LED on GP16.
- **Alert Behavior**: Incoming CoAP `POST /display` messages turn on the alert LED and display the custom text indefinitely until the physical button is pressed, which clears the alert and turns off the LED.
- **Display Cleanup**:
  - Remove Lines 1, 2, and 3 (light reading, divider, and `"URL for Data:"` label).
  - Remove the `"http://"` prefix from the displayed host address.
  - Update the displayed route from `/sensors` to `/info`.
  - Add a bottom line displaying the caller of the last request (`Last: <id or ip-octet>`).
- **CoAP & Discovery Tracking**:
  - Remove `GET /sensors/light` endpoint and exclude `rt="light"` from `GET /.well-known/core` discovery.
  - Exclude light reading from `GET /sensors` collection.
  - Cache discovered nodes from `GET /.well-known/core`. When a `POST /display` request arrives, check if the sender's IP is in the cache; if not, trigger a discovery probe before falling back to displaying the last IP octet.
- **HTTP Server**: Support `GET /info` for device and sensor telemetry.

## Capabilities

### New Capabilities

### Modified Capabilities
- `sensor-monitoring`: Remove LM393 light sensor requirements, leaving DHT22 temperature and humidity sensing.
- `display-service`: Clean up OLED layout (remove lines 1–3, remove "http://", show `/info`, add last caller line).
- `iotmesh/coap-node`: Remove light sensor endpoint from CoAP router and discovery response; add caller tracking.
- `iotmesh/display-actuator`: Replace 60-second timer with persistent display until physical button press, and control alert LED.
- `wifi-http-service`: Expose `/info` endpoint.

## Impact

- GPIO pin GP14 remapped from input (light sensor) to input with pull-up (button).
- GPIO pin GP16 assigned as output for alert LED.
- API breaking change: `light` removed from telemetry payloads and CoAP endpoints.
