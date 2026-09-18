## MODIFIED Requirements

### Requirement: Individual Sensor Endpoints
The system SHALL expose `GET /sensors/temperature` and `GET /sensors/humidity`, returning SenML JSON payloads. On boards where a sensor is not yet connected, the corresponding SenML `v` field SHALL be `null`.

#### Scenario: Sensor queried with hardware present
- **WHEN** a CoAP `GET` is received on `/sensors/temperature` and the sensor is connected
- **THEN** the system returns `2.05 Content` with SenML JSON containing the numeric `temperature` reading

#### Scenario: Sensor queried with no hardware
- **WHEN** a CoAP `GET` is received on `/sensors/temperature` and no temperature sensor is connected
- **THEN** the system returns `2.05 Content` with SenML JSON where `v` is `null`

### Requirement: Sensor Collection Endpoint
The system SHALL expose `GET /sensors` returning a SenML Pack (JSON array) containing all sensor readings. On boards where sensors are not connected, readings SHALL have `null` values.

#### Scenario: Collection queried
- **WHEN** a CoAP `GET` is received on `/sensors`
- **THEN** the system returns `2.05 Content` with a SenML Pack JSON array

## REMOVED Requirements

### Requirement: Individual Sensor Endpoints (light)
**Reason**: The LM393 light sensor was deprecated in a prior change. The `GET /sensors/light` endpoint is no longer exposed.
**Migration**: Remove any client code querying `GET /sensors/light`. Use `GET /sensors` for the full sensor collection.
