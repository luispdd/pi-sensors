## MODIFIED Requirements

### Requirement: Periodic DHT22 sensor readings
The system SHALL sample measurements from all registered sensor modules in the dynamic sensor registry (including ambient temperature, relative humidity from DHT22, and ambient light percentage where equipped) at regular intervals according to each sensor's configured sampling interval when the display mode is `MODE_SENSOR_DISPLAY` or `MODE_MESSAGE`. When the mode is `MODE_SEMI_SLEEP`, continuous periodic sampling SHALL be suspended.

The system SHALL synchronize its clock via NTP on boot and periodically. Each sampled reading SHALL include a UTC ISO-8601 timestamp (`YYYY-MM-DDTHH:MM:SS`) reflecting the exact time the reading was taken. This timestamp SHALL be included in all HTTP and CoAP responses serving the sensor data. If NTP synchronization has never succeeded, the system SHALL omit the timestamp or return `null`.

#### Scenario: Successful measurement reading
- **WHEN** the sampling timer triggers for registered sensors, hardware signals are intact, and the mode is `MODE_SENSOR_DISPLAY` or `MODE_MESSAGE`
- **THEN** valid numeric values for all connected sensors, along with the current UTC timestamp, SHALL be cached in `AppState` for display and HTTP/CoAP serving

#### Scenario: Sensor read failure handling
- **WHEN** reading any registered sensor fails due to communication errors, checksum mismatches, or timeout after driver-level transient retry attempts
- **THEN** the system SHALL retain the last known valid values (including their original timestamp) for that sensor and increment a read error counter without crashing the execution loop

#### Scenario: Continuous sampling suspended in SEMI_SLEEP
- **WHEN** the mode is `MODE_SEMI_SLEEP`
- **THEN** the periodic sensor sampling loop SHALL be idle and SHALL NOT read connected sensors

### Requirement: On-Demand Sensor Reads in SEMI_SLEEP
When the mode is `MODE_SEMI_SLEEP`, the system SHALL perform a synchronous read of all registered sensors before responding to any of the following requests: HTTP `GET /info`, CoAP `GET /sensors`, or CoAP `GET /sensors/<metric_key>` (such as `/sensors/temperature`, `/sensors/humidity`, `/sensors/light`). The read result, including the freshly generated UTC timestamp, SHALL update the cached values before the response is sent.

#### Scenario: On-demand read for HTTP /info during SEMI_SLEEP
- **WHEN** an HTTP `GET /info` is received and the mode is `MODE_SEMI_SLEEP`
- **THEN** the system SHALL read connected sensors synchronously, update cached sensor values and timestamp in `AppState`, and include the fresh values in the JSON response

#### Scenario: On-demand read for CoAP sensor endpoints during SEMI_SLEEP
- **WHEN** a CoAP `GET` is received on `/sensors` or `/sensors/<metric_key>` and the mode is `MODE_SEMI_SLEEP`
- **THEN** the system SHALL read connected sensors synchronously, update cached sensor values and timestamp in `AppState`, and include the fresh values in the CoAP response

#### Scenario: No on-demand read in active modes
- **WHEN** a sensor request arrives and the mode is `MODE_SENSOR_DISPLAY` or `MODE_MESSAGE`
- **THEN** the system SHALL respond with the most recently cached values and timestamp without triggering an additional sensor read
