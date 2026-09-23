## MODIFIED Requirements

### Requirement: CoRE Link Discovery
The system SHALL respond to `GET /.well-known/core` requests with a CoRE Link Format payload enumerating its identity, sensor endpoints (including `</sensors/light>;rt="light";if="sensor"` on boards equipped with a light sensor), and actuator endpoints.

#### Scenario: Discovery request received
- **WHEN** a CoAP `GET` is received on `/.well-known/core`
- **THEN** the system returns `2.05 Content` with the CoRE Link Format string, including `</sensors/light>;rt="light";if="sensor"` on boards with an active light sensor, or omitting it on boards without a light sensor

### Requirement: Individual Sensor Endpoints
The system SHALL expose `GET /sensors/temperature` and `GET /sensors/humidity`, and on boards with a light sensor SHALL expose `GET /sensors/light`, returning SenML JSON payloads. On boards where a sensor is not connected or unsupported, the corresponding SenML `v` field SHALL be `null` or the endpoint SHALL return `4.04 Not Found`.

#### Scenario: Sensor queried with hardware present
- **WHEN** a CoAP `GET` is received on `/sensors/temperature`, `/sensors/humidity`, or `/sensors/light` and the sensor is connected
- **THEN** the system returns `2.05 Content` with SenML JSON containing the numeric reading (`Cel` for temperature, `%RH` for humidity, `%` for light)

#### Scenario: Sensor queried with no hardware
- **WHEN** a CoAP `GET` is received on `/sensors/temperature`, `/sensors/humidity`, or `/sensors/light` and no corresponding sensor is connected
- **THEN** the system returns `2.05 Content` with SenML JSON where `v` is `null`

### Requirement: Sensor Collection Endpoint
The system SHALL expose `GET /sensors` returning a SenML Pack (JSON array) containing all sensor readings. On boards where sensors are not connected, readings SHALL have `null` values. On boards with a light sensor (Pico 2 W), the array SHALL include `{"n": "light", "u": "%", "v": <pct>}`.

#### Scenario: Collection queried
- **WHEN** a CoAP `GET` is received on `/sensors`
- **THEN** the system returns `2.05 Content` with a SenML Pack JSON array containing all supported sensor metrics (including temperature, humidity, and light on supported boards)
