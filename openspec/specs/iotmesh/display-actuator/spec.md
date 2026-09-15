# Display Actuator Specification

## Purpose

Allows remote CoAP clients to temporarily display a custom message on the device's OLED screen by sending a plain text payload.

## Requirements

### Requirement: Display Actuation
The system SHALL expose a CoAP `POST /display` endpoint that accepts plain text (UTF-8, max 256 bytes) and renders it on the OLED display.

#### Scenario: Actuator receives command
- **WHEN** a CoAP `POST` is received on `/display` with plain text
- **THEN** the system updates the display to show the text and returns `2.04 Changed`

### Requirement: Temporary Override Timer
The system SHALL display the custom message for 60 seconds before reverting to the default sensor metrics display.

#### Scenario: Override expires
- **WHEN** 60 seconds elapse after receiving a `/display` POST
- **THEN** the display reverts to showing sensor metrics

### Requirement: Timer Reset
The system SHALL reset the 60-second timer if a new `/display` POST is received while an override is already active.

#### Scenario: Override refreshed
- **WHEN** an override is active and a new `/display` POST is received
- **THEN** the message updates and the 60-second timer restarts
