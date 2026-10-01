## ADDED Requirements

### Requirement: DETAILS_MODE Sensor Summary View (pico-1w)
In DETAILS_MODE the pico-1w OLED display SHALL render a summary table with one line per registered metric showing the current value, session minimum, and session maximum. The first line SHALL be a header label. Metrics are shown in the order: temperature, humidity. A fourth line SHALL be left blank as a reserved placeholder.

#### Scenario: DETAILS_MODE renders temperature and humidity stats
- **WHEN** the system is in DETAILS_MODE and the OLED is on
- **THEN** the display SHALL show rows in the format `<key>: <cur> <min> <max>` truncated to MAX_LINE_LEN, with `--` substituted for any None values.

#### Scenario: DETAILS_MODE shows placeholder for future sensor
- **WHEN** the system is in DETAILS_MODE
- **THEN** a fourth data row SHALL be blank, reserving space for a future sensor metric.

## MODIFIED Requirements

### Requirement: Pico 1 W Primary Button Interaction
The primary button (GP14, active-LOW, pull-up) SHALL implement the mode-transition contract defined in `core/display-modes`:
- Short press in STATUS_MODE → DETAILS_MODE.
- Short press in DETAILS_MODE → STATUS_MODE.
- Long press (≥ 1000 ms) from any active mode → SEMI_SLEEP (previous mode saved).
- Any press from SEMI_SLEEP → restore previous mode and wake display.
- Short press in MESSAGE_MODE → discard message, restore previous mode.

#### Scenario: Short press toggles between STATUS_MODE and DETAILS_MODE
- **WHEN** the primary button is short-pressed while in STATUS_MODE or DETAILS_MODE
- **THEN** the system SHALL transition to the other mode without blanking the display.

#### Scenario: Long press enters SEMI_SLEEP
- **WHEN** the primary button is held for ≥ 1000 ms in STATUS_MODE or DETAILS_MODE
- **THEN** the system SHALL enter SEMI_SLEEP and blank the OLED display.

#### Scenario: Any press restores from SEMI_SLEEP
- **WHEN** the primary button is pressed while in SEMI_SLEEP
- **THEN** the system SHALL restore the previous mode and turn on the OLED display.
