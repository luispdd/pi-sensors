# CoAP Node Specification

## Purpose

Provides a CoAP server that responds to CoRE Link Format discovery requests and serves sensor data formatted as SenML JSON.

## Requirements

### Requirement: CoAP UDP Binding
The system SHALL bind a UDP socket on port 5683 to listen for CoAP messages, including both unicast and broadcast (`255.255.255.255`) destinations.

#### Scenario: Bind successfully
- **WHEN** the system initializes network services
- **THEN** it successfully starts listening on UDP port 5683

### Requirement: CoRE Link Discovery
The system SHALL respond to `GET /.well-known/core` requests with a CoRE Link Format payload enumerating its identity, sensors, and actuator endpoints.

#### Scenario: Discovery request received
- **WHEN** a CoAP `GET` is received on `/.well-known/core`
- **THEN** the system returns `2.05 Content` with the CoRE Link Format string

### Requirement: Identity Endpoint
The system SHALL expose device identity at `GET /id` returning a JSON object with `id` and `type` fields.

#### Scenario: Identity queried
- **WHEN** a CoAP `GET` is received on `/id`
- **THEN** the system returns `2.05 Content` with the identity JSON

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
