## Why

The current sensor station uses an HTTP server (pull-based) for telemetry. By implementing the `IoTMesh — Service Spec (v0.1)`, we transition the node to a decentralized, discovery-based model using standard IoT protocols (CoAP, CoRE Link Format, SenML). This allows independent nodes on the local network to discover this device and interact with its sensors and display without requiring a central server or static IP configuration.

## What Changes

- Add `microCoAPy` dependency to support CoAP over UDP.
- Implement UDP broadcast listening on `255.255.255.255:5683` to respond to CoRE Link Format discovery requests (`GET /.well-known/core`).
- Expose the device identity via `GET /id`.
- Expose individual sensors via CoAP `GET` endpoints: `/sensors/temperature`, `/sensors/humidity`, and `/sensors/light`.
- Add a new `rt="light"` type to the vocabulary for the LM393 digital light sensor.
- Expose a `sensor-collection` via `GET /sensors` returning all sensor readings in a single SenML Pack.
- Expose a CoAP `POST /display` endpoint that temporarily overrides the OLED display with a custom text message for 60 seconds.
- The existing HTTP webserver is preserved for backward compatibility (may be removed in a future task).

## Capabilities

### New Capabilities
- `iotmesh/coap-node`: Implements CoAP communication, CoRE Link discovery, and SenML payload formatting as defined by the IoTMesh Service Spec.
- `iotmesh/display-actuator`: Implements the 60-second temporary OLED display override via `POST /display`.

### Modified Capabilities

## Impact

- Adds new network binding on UDP port 5683.
- Adds `microCoAPy` library which increases RAM utilization on the constrained Pico W.
- Modifies the display rendering loop in `display.py` to handle the 60-second override state machine.
