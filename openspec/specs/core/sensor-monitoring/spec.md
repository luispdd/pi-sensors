# Sensor Monitoring Specification

## Purpose

Provides periodic environmental telemetry by acquiring ambient temperature and relative humidity measurements from connected sensors.

## Requirements

### Requirement: Periodic DHT22 sensor readings
The system SHALL sample temperature (in Celsius) and relative humidity (percentage) from the DHT22 sensor on GP15 at regular intervals of at least 1 second when the display mode is `MODE_SENSOR_DISPLAY` or `MODE_MESSAGE`. When the mode is `MODE_SEMI_SLEEP`, continuous periodic sampling SHALL be suspended.

#### Scenario: Successful measurement reading
- **WHEN** the sampling timer triggers, the DHT22 signal is intact, and the mode is `MODE_SENSOR_DISPLAY` or `MODE_MESSAGE`
- **THEN** valid numeric values for temperature and humidity SHALL be cached for display and HTTP/CoAP serving

#### Scenario: Sensor read failure handling
- **WHEN** reading the DHT22 fails due to checksum errors or timing timeout
- **THEN** the system SHALL retain the last known valid values and increment a read error counter without crashing the execution loop

#### Scenario: Continuous sampling suspended in SEMI_SLEEP
- **WHEN** the mode is `MODE_SEMI_SLEEP`
- **THEN** the periodic sensor sampling loop SHALL be idle and SHALL NOT read the DHT22

### Requirement: On-Demand Sensor Reads in SEMI_SLEEP
When the mode is `MODE_SEMI_SLEEP`, the system SHALL perform a single synchronous DHT22 read before responding to any of the following requests: HTTP `GET /info`, CoAP `GET /sensors`, CoAP `GET /sensors/temperature`, CoAP `GET /sensors/humidity`. The read result SHALL update the cached values before the response is sent.

#### Scenario: On-demand read for HTTP /info during SEMI_SLEEP
- **WHEN** an HTTP `GET /info` is received and the mode is `MODE_SEMI_SLEEP`
- **THEN** the system SHALL read the DHT22 synchronously, update cached sensor values, and include the fresh values in the JSON response

#### Scenario: On-demand read for CoAP sensor endpoints during SEMI_SLEEP
- **WHEN** a CoAP `GET` is received on `/sensors`, `/sensors/temperature`, or `/sensors/humidity` and the mode is `MODE_SEMI_SLEEP`
- **THEN** the system SHALL read the DHT22 synchronously, update cached sensor values, and include the fresh values in the CoAP response

#### Scenario: No on-demand read in active modes
- **WHEN** a sensor request arrives and the mode is `MODE_SENSOR_DISPLAY` or `MODE_MESSAGE`
- **THEN** the system SHALL respond with the most recently cached values without triggering an additional DHT22 read
