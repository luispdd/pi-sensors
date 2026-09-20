# CoAP Node Specification

## Purpose

Provides a CoAP server that responds to CoRE Link Format discovery requests and serves sensor data formatted as SenML JSON.

## Requirements

### Requirement: CoAP UDP Binding
The system SHALL bind a UDP socket on port 5683 to listen for CoAP messages, including unicast, broadcast (`255.255.255.255`), and IPv4 multicast (`224.0.1.187`) destinations.

#### Scenario: Bind successfully
- **WHEN** the system initializes network services
- **THEN** it successfully starts listening on UDP port 5683

### Requirement: CoAP IPv4 Multicast Group Membership
The system SHALL join the CoAP all-nodes IPv4 multicast group `224.0.1.187` (RFC 7252 §12.8) after binding the UDP socket, so that it receives multicast discovery requests from other nodes on the local network.

The join SHALL be attempted using `IP_ADD_MEMBERSHIP` with `INADDR_ANY` as the interface address. If the underlying network stack does not support this socket option (e.g. some MicroPython builds), the join SHALL fail gracefully with a log message and the server SHALL continue operating on unicast and broadcast only.

#### Scenario: Multicast join succeeds
- **WHEN** the CoAP server starts and `IP_ADD_MEMBERSHIP` is available
- **THEN** the board joins `224.0.1.187` and logs `[coap] Joined multicast group 224.0.1.187`
- **AND** the board responds to `GET coap://224.0.1.187/.well-known/core` requests

#### Scenario: Multicast join not supported
- **WHEN** the CoAP server starts and `IP_ADD_MEMBERSHIP` is not available on the platform
- **THEN** the board logs `[coap] Multicast join skipped (not supported): <reason>`
- **AND** the server continues listening on unicast and broadcast

### Requirement: CoRE Link Discovery
The system SHALL respond to `GET /.well-known/core` requests with a CoRE Link Format payload enumerating its identity, sensors (temperature and humidity only), and actuator endpoints.

#### Scenario: Discovery request received
- **WHEN** a CoAP `GET` is received on `/.well-known/core`
- **THEN** the system returns `2.05 Content` with the CoRE Link Format string without light sensor links

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

### Requirement: Node Discovery Cache and Caller Resolution
The system SHALL maintain a cache of known network node identities discovered via CoRE Link Format probes. Upon receiving a `POST /display` request from a caller IP, the system SHALL check the cache, trigger a discovery probe if the caller IP is absent, and resolve the caller's device ID or fall back to the last IP octet.

#### Scenario: Caller found in cache
- **WHEN** a `POST /display` arrives from an IP already recorded in the discovery cache
- **THEN** the system resolves and records the caller's device ID for display

#### Scenario: Caller missing from cache but responds to probe
- **WHEN** a `POST /display` arrives from an unknown IP and the discovery probe receives a response
- **THEN** the system updates the cache and records the discovered device ID for display

#### Scenario: Caller missing from cache and does not respond to probe
- **WHEN** a `POST /display` arrives from an unknown IP and discovery probe does not find a device ID
- **THEN** the system records the last octet of the caller's IP address for display
