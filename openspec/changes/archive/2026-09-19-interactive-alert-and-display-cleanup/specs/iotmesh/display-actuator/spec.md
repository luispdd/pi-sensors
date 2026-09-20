## REMOVED Requirements

### Requirement: Temporary Override Timer
**Reason**: Replaced by indefinite message display until acknowledged by physical button.
**Migration**: User acknowledges incoming display alerts by pressing the reset button on GP14.

### Requirement: Timer Reset
**Reason**: Replaced by persistent alert state without timer.
**Migration**: Successive display messages update the alert text and remain until acknowledged.

## ADDED Requirements

### Requirement: Persistent Display and Button Acknowledge
The system SHALL display an incoming `POST /display` message indefinitely until a physical reset button connected to GP14 is pressed.

#### Scenario: Message displayed until button press
- **WHEN** a `POST /display` command is received
- **THEN** the OLED screen shows the custom message continuously until the button on GP14 is pressed

#### Scenario: Button pressed to dismiss message
- **WHEN** an alert message is currently displayed and the button on GP14 is pressed
- **THEN** the system dismisses the message and restores the default sensor metrics screen

### Requirement: Alert LED Indication
The system SHALL illuminate a dedicated alert LED on GP16 whenever an active message alert is displayed, and extinguish the LED when dismissed.

#### Scenario: LED illuminates on message receipt
- **WHEN** a `POST /display` command is received
- **THEN** the alert LED on GP16 turns ON

#### Scenario: LED turns off on button acknowledgement
- **WHEN** the user presses the reset button on GP14 to dismiss the message
- **THEN** the alert LED on GP16 turns OFF
