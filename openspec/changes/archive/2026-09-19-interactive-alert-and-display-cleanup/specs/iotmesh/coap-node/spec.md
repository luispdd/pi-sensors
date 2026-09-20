## MODIFIED Requirements

### Requirement: CoRE Link Discovery
The system SHALL respond to `GET /.well-known/core` requests with a CoRE Link Format payload enumerating its identity, sensors (temperature and humidity only), and actuator endpoints.

#### Scenario: Discovery request received
- **WHEN** a CoAP `GET` is received on `/.well-known/core`
- **THEN** the system returns `2.05 Content` with the CoRE Link Format string without light sensor links

### Requirement: Individual Sensor Endpoints
The system SHALL expose `GET /sensors/temperature` and `GET /sensors/humidity`, returning SenML JSON payloads.

#### Scenario: Sensor queried
- **WHEN** a CoAP `GET` is received on `/sensors/temperature`
- **THEN** the system returns `2.05 Content` with SenML JSON containing the `temperature` reading

### Requirement: Sensor Collection Endpoint
The system SHALL expose `GET /sensors` returning a SenML Pack (JSON array) containing temperature and humidity readings.

#### Scenario: Collection queried
- **WHEN** a CoAP `GET` is received on `/sensors`
- **THEN** the system returns `2.05 Content` with a SenML Pack JSON array containing temperature and humidity

## ADDED Requirements

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
