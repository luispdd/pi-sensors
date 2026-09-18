## MODIFIED Requirements

### Requirement: Display Actuation
The system SHALL expose a CoAP `POST /display` endpoint that accepts plain text (UTF-8, max 256 bytes).

The behaviour on receipt depends on the current display mode:
- If the mode is `MODE_SENSOR_DISPLAY`: the system SHALL transition to `MODE_MESSAGE`, show the text on the connected display, turn the alert LED on (if wired), and return `2.04 Changed`.
- If the mode is `MODE_SEMI_SLEEP`: the system SHALL store the text as a pending message, turn the alert LED on (if wired) to signal a waiting notification, keep the display off, and return `2.04 Changed`. The display SHALL NOT show the message until the user presses the button (if wired) or the mode transitions.
- If the mode is `MODE_MESSAGE`: the system SHALL replace the displayed text with the new payload and return `2.04 Changed`.

#### Scenario: Actuator receives command
- **WHEN** a CoAP `POST` is received on `/display` with plain text
- **THEN** the system SHALL process the actuation command and return `2.04 Changed`

#### Scenario: Actuation in SENSOR_DISPLAY mode
- **WHEN** a CoAP `POST` is received on `/display` with plain text and the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the system SHALL transition to `MODE_MESSAGE`, show the text on the connected display, turn the LED on (if wired), and return `2.04 Changed`

#### Scenario: Actuation in SEMI_SLEEP mode
- **WHEN** a CoAP `POST` is received on `/display` with plain text and the mode is `MODE_SEMI_SLEEP`
- **THEN** the system SHALL store the payload as `pending_message`, turn the LED on (if wired), leave the display off, and return `2.04 Changed`

#### Scenario: Actuation in MESSAGE mode
- **WHEN** a CoAP `POST` is received on `/display` with plain text and the mode is `MODE_MESSAGE`
- **THEN** the system SHALL replace the displayed text with the new payload and return `2.04 Changed`

### Requirement: Button-Driven Mode Cycle
When a physical button is wired, pressing it SHALL cycle the display mode. On boards without a button wired, mode transitions SHALL only occur via CoAP commands.

- `MODE_SENSOR_DISPLAY` + button → `MODE_SEMI_SLEEP` (display off, LED off)
- `MODE_SEMI_SLEEP` + button, no pending message → `MODE_SENSOR_DISPLAY` (display resumes)
- `MODE_SEMI_SLEEP` + button, pending message present → `MODE_MESSAGE` (pending message shown, LED remains on)
- `MODE_MESSAGE` + button → `MODE_SENSOR_DISPLAY` (message cleared, LED off)

#### Scenario: Button pressed in SENSOR_DISPLAY mode
- **WHEN** the button is pressed while the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the system SHALL transition to `MODE_SEMI_SLEEP`, clear and power off the display, and turn the LED off

#### Scenario: Button pressed in SEMI_SLEEP with no pending message
- **WHEN** the button is pressed while the mode is `MODE_SEMI_SLEEP` and no pending message exists
- **THEN** the system SHALL transition to `MODE_SENSOR_DISPLAY` and resume normal display refresh

#### Scenario: Button pressed in SEMI_SLEEP with a pending message
- **WHEN** the button is pressed while the mode is `MODE_SEMI_SLEEP` and a pending message is stored
- **THEN** the system SHALL transition to `MODE_MESSAGE`, show the pending message on the display, and keep the LED on

#### Scenario: Button pressed in MESSAGE mode
- **WHEN** the button is pressed while the mode is `MODE_MESSAGE`
- **THEN** the system SHALL clear the message and pending message, turn the LED off, and transition to `MODE_SENSOR_DISPLAY`

#### Scenario: No button wired
- **WHEN** the board has no physical button connected
- **THEN** mode transitions SHALL only occur via CoAP `POST /display` commands and the system SHALL remain in the current mode until a CoAP command changes it
