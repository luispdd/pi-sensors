## MODIFIED Requirements

### Requirement: Periodic DHT22 sensor readings
The system SHALL sample temperature (in Celsius) and relative humidity (percentage) from the DHT22 sensor on GP15, and on boards equipped with the ADA2748 sensor (Pico 2 W), SHALL sample ambient light percentage (`light_pct`) from GP26 (ADC0), at regular intervals of at least 1 second when the display mode is `MODE_SENSOR_DISPLAY` or `MODE_MESSAGE`. When the mode is `MODE_SEMI_SLEEP`, continuous periodic sampling SHALL be suspended.

The system SHALL synchronize its clock via NTP on boot and periodically. Each sampled reading SHALL include a UTC ISO-8601 timestamp (`YYYY-MM-DDTHH:MM:SS`) reflecting the exact time the reading was taken. This timestamp SHALL be included in all HTTP and CoAP responses serving the sensor data. If NTP synchronization has never succeeded, the system SHALL omit the timestamp or return `null`.

#### Scenario: Successful measurement reading
- **WHEN** the sampling timer triggers, sensor signals are intact, and the mode is `MODE_SENSOR_DISPLAY` or `MODE_MESSAGE`
- **THEN** valid numeric values for temperature and humidity, ambient light percentage (on supported boards), along with the current UTC timestamp, SHALL be cached for display and HTTP/CoAP serving

#### Scenario: Sensor read failure handling
- **WHEN** reading any sensor fails due to checksum errors, timing timeout, or ADC read errors
- **THEN** the system SHALL retain the last known valid values (including their original timestamp) and increment a read error counter without crashing the execution loop

#### Scenario: Continuous sampling suspended in SEMI_SLEEP
- **WHEN** the mode is `MODE_SEMI_SLEEP`
- **THEN** the periodic sensor sampling loop SHALL be idle and SHALL NOT read connected sensors

### Requirement: On-Demand Sensor Reads in SEMI_SLEEP
When the mode is `MODE_SEMI_SLEEP`, the system SHALL perform a single synchronous sensor read (including DHT22 and any connected light sensor) before responding to any of the following requests: HTTP `GET /info`, CoAP `GET /sensors`, CoAP `GET /sensors/temperature`, CoAP `GET /sensors/humidity`, CoAP `GET /sensors/light`. The read result, including the freshly generated UTC timestamp, SHALL update the cached values before the response is sent.

#### Scenario: On-demand read for HTTP /info during SEMI_SLEEP
- **WHEN** an HTTP `GET /info` is received and the mode is `MODE_SEMI_SLEEP`
- **THEN** the system SHALL read connected sensors synchronously, update cached sensor values (including `light_pct`) and timestamp, and include the fresh values in the JSON response

#### Scenario: On-demand read for CoAP sensor endpoints during SEMI_SLEEP
- **WHEN** a CoAP `GET` is received on `/sensors`, `/sensors/temperature`, `/sensors/humidity`, or `/sensors/light` and the mode is `MODE_SEMI_SLEEP`
- **THEN** the system SHALL read connected sensors synchronously, update cached sensor values (including `light_pct`) and timestamp, and include the fresh values in the CoAP response

#### Scenario: No on-demand read in active modes
- **WHEN** a sensor request arrives and the mode is `MODE_SENSOR_DISPLAY` or `MODE_MESSAGE`
- **THEN** the system SHALL respond with the most recently cached values and timestamp without triggering an additional sensor read
