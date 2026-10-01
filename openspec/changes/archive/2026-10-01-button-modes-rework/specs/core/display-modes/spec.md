## Purpose

Defines the four-mode display interaction model shared across all boards, the button press semantics that govern mode transitions, and the previous-mode restore contract that allows SEMI_SLEEP and MESSAGE_MODE to return to the interrupted mode on exit.

## ADDED Requirements

### Requirement: Four-Mode Display Model
The system SHALL support exactly four display modes: STATUS_MODE (0), SEMI_SLEEP (1), MESSAGE_MODE (2), and DETAILS_MODE (3). Each mode is identified by an integer constant stored in `AppState.mode`.

#### Scenario: Mode constants are defined
- **WHEN** the application initialises
- **THEN** `MODE_SENSOR_DISPLAY` (0), `MODE_SEMI_SLEEP` (1), `MODE_MESSAGE` (2), and `MODE_DETAILS` (3) SHALL be defined and accessible to all UI and state modules.

### Requirement: Primary Button Mode Transitions
The primary button (active-LOW, internal pull-up) SHALL control mode transitions according to the following rules, applied at the moment of release detection:

- **Long press (≥ 1000 ms)**: From any active mode (STATUS_MODE, DETAILS_MODE, or MESSAGE_MODE) the system SHALL save the current mode as the previous mode and transition to SEMI_SLEEP, blanking the display.
- **Any press from SEMI_SLEEP**: The system SHALL restore the previous mode, turn the display on, and resume rendering.
- **Short press in STATUS_MODE**: The system SHALL transition to DETAILS_MODE without altering the display power state.
- **Short press in DETAILS_MODE**: The system SHALL transition to STATUS_MODE without altering the display power state.
- **Short press in MESSAGE_MODE**: The system SHALL discard the current message, restore the previous mode, and resume rendering in that mode.

#### Scenario: Long press enters SEMI_SLEEP from STATUS_MODE
- **WHEN** the primary button is held for ≥ 1000 ms while in STATUS_MODE
- **THEN** the system SHALL save STATUS_MODE as previous mode, transition to SEMI_SLEEP, and blank the display.

#### Scenario: Long press enters SEMI_SLEEP from DETAILS_MODE
- **WHEN** the primary button is held for ≥ 1000 ms while in DETAILS_MODE
- **THEN** the system SHALL save DETAILS_MODE as previous mode, transition to SEMI_SLEEP, and blank the display.

#### Scenario: Any press wakes from SEMI_SLEEP
- **WHEN** the primary button is pressed (short or long) while in SEMI_SLEEP
- **THEN** the system SHALL restore the previous mode and turn the display on.

#### Scenario: Short press cycles STATUS_MODE to DETAILS_MODE
- **WHEN** the primary button is released after a short press (< 1000 ms) while in STATUS_MODE
- **THEN** the system SHALL transition to DETAILS_MODE.

#### Scenario: Short press cycles DETAILS_MODE to STATUS_MODE
- **WHEN** the primary button is released after a short press (< 1000 ms) while in DETAILS_MODE
- **THEN** the system SHALL transition to STATUS_MODE.

#### Scenario: Short press in MESSAGE_MODE restores previous mode
- **WHEN** the primary button is released after a short press while in MESSAGE_MODE
- **THEN** the system SHALL clear the message, transition to the saved previous mode, and resume rendering in that mode.

### Requirement: Previous-Mode Restore Contract
The system SHALL maintain a `_previous_mode` field in `AppState` initialised to `MODE_SENSOR_DISPLAY`. This field SHALL be updated whenever the system enters SEMI_SLEEP or MESSAGE_MODE, recording the mode that was active at the time of entry.

#### Scenario: Previous mode is saved on SEMI_SLEEP entry
- **WHEN** the system transitions into SEMI_SLEEP (via long press)
- **THEN** `AppState._previous_mode` SHALL hold the mode that was active immediately before the transition.

#### Scenario: Previous mode is saved on MESSAGE_MODE entry
- **WHEN** an external message causes the system to enter MESSAGE_MODE
- **THEN** `AppState._previous_mode` SHALL hold the mode that was active immediately before the message arrived.

### Requirement: MESSAGE_MODE Interruption Behaviour
Externally triggered messages (CoAP, network) SHALL immediately switch the display to MESSAGE_MODE, saving the current mode as previous. The message SHALL remain visible until the primary button is short-pressed, at which point the previous mode is restored.

#### Scenario: External message interrupts STATUS_MODE
- **WHEN** a message is received while in STATUS_MODE
- **THEN** the system SHALL save STATUS_MODE, enter MESSAGE_MODE, and display the message immediately.

#### Scenario: External message interrupts DETAILS_MODE
- **WHEN** a message is received while in DETAILS_MODE
- **THEN** the system SHALL save DETAILS_MODE, enter MESSAGE_MODE, and display the message immediately.

### Requirement: Per-Metric Session Min/Max Tracking
The system SHALL track boot-scoped minimum and maximum values for each registered sensor metric. On each metric update the system SHALL compare the new value against the stored min and max and update them accordingly. Both SHALL be initialised to `None` and set to the first received value.

#### Scenario: Min/max initialises on first reading
- **WHEN** a metric receives its first non-None value after boot
- **THEN** both `min` and `max` for that metric SHALL be set to that value.

#### Scenario: Min updates on lower value
- **WHEN** a metric update is received with a value lower than the current stored min
- **THEN** the stored min SHALL be updated to the new value.

#### Scenario: Max updates on higher value
- **WHEN** a metric update is received with a value higher than the current stored max
- **THEN** the stored max SHALL be updated to the new value.
