## ADDED Requirements

### Requirement: JSON HTTP endpoint /info
The system SHALL serve an HTTP GET endpoint at `/info` responding with valid JSON containing environmental measurements and system telemetry.

#### Scenario: Successful GET /info request
- **WHEN** a client performs an HTTP `GET /info` request
- **THEN** the system increments the request counter and returns HTTP 200 with JSON telemetry
