## ADDED Requirements

### Requirement: DETAILS_MODE SD File Listing View (pico-2w)
In DETAILS_MODE the pico-2w TFT display SHALL show a paginated listing of files from `/sd/sensor-data/`. The file list SHALL be fetched fresh from the SD card every time the system enters DETAILS_MODE. Each page SHALL display as many filenames as fit on screen, sorted alphanumerically. When additional files exist beyond the current page, the last visible line SHALL display `<Next page>`. When no further files exist, `<Next page>` SHALL NOT be shown.

#### Scenario: File list is refreshed on DETAILS_MODE entry
- **WHEN** the system transitions into DETAILS_MODE
- **THEN** the system SHALL mount the SD card, read the contents of `/sd/sensor-data/`, cache the sorted list, and unmount.

#### Scenario: First page is displayed on DETAILS_MODE entry
- **WHEN** DETAILS_MODE is entered and the file list has been loaded
- **THEN** the display SHALL show the first page of filenames starting at index 0.

#### Scenario: Next page shown when overflow exists
- **WHEN** the number of files exceeds the per-page capacity
- **THEN** the last line of the current page SHALL read `<Next page>`.

#### Scenario: Secondary button advances page
- **WHEN** the secondary button (GP13) is short-pressed while in DETAILS_MODE
- **THEN** the display SHALL advance to the next page of filenames, wrapping back to the first page after the last.

#### Scenario: No next page indicator on last page
- **WHEN** all files fit on the current page or the last page is displayed
- **THEN** `<Next page>` SHALL NOT appear.

#### Scenario: SD card absent or mount fails
- **WHEN** the SD card cannot be mounted when entering DETAILS_MODE
- **THEN** the display SHALL show an error message (e.g., `SD: unavailable`) and the file list SHALL be empty.

### Requirement: STATUS_MODE Layout with PIR Activity (pico-2w)
The STATUS_MODE view on the TFT SHALL include a PIR activity line as the second displayed line, immediately after the primary telemetry line (temperature / humidity / light). All subsequent lines (network status, CoAP route, requests served, last caller, and the logging section when active) SHALL shift down by one line spacing to accommodate the PIR line.

#### Scenario: PIR activity line is rendered in STATUS_MODE
- **WHEN** the system is in STATUS_MODE and the TFT is on
- **THEN** the second line of the display SHALL show PIR motion activity (e.g., `PIR: <value>%`), with `--` shown when the value is unavailable.

## MODIFIED Requirements

### Requirement: Pico 2 W Primary Button Interaction
The primary button (GP14, active-LOW, pull-up) SHALL implement the mode-transition contract defined in `core/display-modes`:
- Short press in STATUS_MODE → DETAILS_MODE.
- Short press in DETAILS_MODE → STATUS_MODE.
- Long press (≥ 1000 ms) from any active mode → SEMI_SLEEP (previous mode saved).
- Any press from SEMI_SLEEP → restore previous mode and wake display.
- Short press in MESSAGE_MODE → discard message, restore previous mode.

#### Scenario: Short press toggles between STATUS_MODE and DETAILS_MODE
- **WHEN** the primary button is short-pressed while in STATUS_MODE or DETAILS_MODE
- **THEN** the system SHALL transition to the other mode without blanking the TFT display.

#### Scenario: Long press enters SEMI_SLEEP
- **WHEN** the primary button is held for ≥ 1000 ms in STATUS_MODE or DETAILS_MODE
- **THEN** the system SHALL enter SEMI_SLEEP and blank the TFT display.

#### Scenario: Any press restores from SEMI_SLEEP
- **WHEN** the primary button is pressed while in SEMI_SLEEP
- **THEN** the system SHALL restore the previous mode and turn on the TFT display.

### Requirement: Pico 2 W Secondary Button Interaction
The secondary button (GP13, active-LOW, pull-up) SHALL behave differently depending on the current mode:
- In STATUS_MODE: the button SHALL continue to drive the data logger lifecycle (IDLE → CONFIRM → ACTIVE and associated transitions) unchanged.
- In DETAILS_MODE: short press SHALL advance the SD file listing to the next page; long press SHALL have no effect.
- In all other modes (SEMI_SLEEP, MESSAGE_MODE): the button SHALL be ignored.

#### Scenario: Secondary button runs logger lifecycle in STATUS_MODE
- **WHEN** the secondary button is short-pressed while in STATUS_MODE and the logger is IDLE
- **THEN** the system SHALL begin the logger staging process (unchanged behaviour).

#### Scenario: Secondary button advances file page in DETAILS_MODE
- **WHEN** the secondary button is short-pressed while in DETAILS_MODE
- **THEN** the file listing SHALL advance to the next page (wrapping to first after last).

#### Scenario: Secondary button ignored outside STATUS_MODE and DETAILS_MODE
- **WHEN** the secondary button is pressed while in SEMI_SLEEP or MESSAGE_MODE
- **THEN** the system SHALL take no action.
