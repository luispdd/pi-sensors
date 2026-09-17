## MODIFIED Requirements

### Requirement: Display Actuation
The system SHALL expose a CoAP `POST /display` endpoint that accepts plain text (UTF-8, max 256 bytes).

The behaviour on receipt depends on the current display mode:
- If the mode is `MODE_SENSOR_DISPLAY`: the system SHALL transition to `MODE_MESSAGE`, show the text on the OLED, turn the alert LED on, and return `2.04 Changed`.
- If the mode is `MODE_SEMI_SLEEP`: the system SHALL store the text as a pending message, turn the alert LED on to signal a waiting notification, keep the OLED off, and return `2.04 Changed`. The display SHALL NOT show the message until the user presses the button.
- If the mode is `MODE_MESSAGE`: the system SHALL replace the displayed text with the new payload and return `2.04 Changed`.

#### Scenario: Actuator receives command
- **WHEN** a CoAP `POST` is received on `/display` with plain text
- **THEN** the system SHALL process the actuation command and return `2.04 Changed`

#### Scenario: Actuation in SENSOR_DISPLAY mode
- **WHEN** a CoAP `POST` is received on `/display` with plain text and the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the system SHALL transition to `MODE_MESSAGE`, show the text on the OLED, turn the LED on, and return `2.04 Changed`

#### Scenario: Actuation in SEMI_SLEEP mode
- **WHEN** a CoAP `POST` is received on `/display` with plain text and the mode is `MODE_SEMI_SLEEP`
- **THEN** the system SHALL store the payload as `pending_message`, turn the LED on, leave the OLED off, and return `2.04 Changed`

#### Scenario: Actuation in MESSAGE mode
- **WHEN** a CoAP `POST` is received on `/display` with plain text and the mode is `MODE_MESSAGE`
- **THEN** the system SHALL replace the displayed text with the new payload and return `2.04 Changed`

### Requirement: Button-Driven Mode Cycle
The physical button on GP14 (active-LOW with internal pull-up) SHALL cycle the display mode on each press edge according to the following rules:

- `MODE_SENSOR_DISPLAY` + button → `MODE_SEMI_SLEEP` (display off, LED off)
- `MODE_SEMI_SLEEP` + button, no pending message → `MODE_SENSOR_DISPLAY` (display resumes)
- `MODE_SEMI_SLEEP` + button, pending message present → `MODE_MESSAGE` (pending message shown, LED remains on)
- `MODE_MESSAGE` + button → `MODE_SENSOR_DISPLAY` (message cleared, LED off)

#### Scenario: Button pressed in SENSOR_DISPLAY mode
- **WHEN** the button is pressed while the mode is `MODE_SENSOR_DISPLAY`
- **THEN** the system SHALL transition to `MODE_SEMI_SLEEP`, clear and power off the OLED, and turn the LED off

#### Scenario: Button pressed in SEMI_SLEEP with no pending message
- **WHEN** the button is pressed while the mode is `MODE_SEMI_SLEEP` and no pending message exists
- **THEN** the system SHALL transition to `MODE_SENSOR_DISPLAY` and resume normal display refresh

#### Scenario: Button pressed in SEMI_SLEEP with a pending message
- **WHEN** the button is pressed while the mode is `MODE_SEMI_SLEEP` and a pending message is stored
- **THEN** the system SHALL transition to `MODE_MESSAGE`, show the pending message on the OLED, and keep the LED on

#### Scenario: Button pressed in MESSAGE mode
- **WHEN** the button is pressed while the mode is `MODE_MESSAGE`
- **THEN** the system SHALL clear the message and pending message, turn the LED off, and transition to `MODE_SENSOR_DISPLAY`

## REMOVED Requirements

### Requirement: Temporary Override Timer
**Reason**: Replaced by the button-driven mode cycle. Messages now persist until the user acknowledges them with a button press; time-based auto-dismissal is removed.
**Migration**: No external API change. The `POST /display` endpoint and response code are unchanged.

### Requirement: Timer Reset
**Reason**: The 60-second timer mechanism is removed alongside the Temporary Override Timer requirement.
**Migration**: Sending a new `POST /display` while in `MODE_MESSAGE` still replaces the displayed text; the button is now the only dismissal mechanism.
