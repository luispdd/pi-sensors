## ADDED Requirements

### Requirement: Logging status section on TFT during active session
When `AppState.logging_active` is `True`, the system SHALL render a logging status section in the lower area of the TFT display below the standard telemetry content. The section SHALL show: a horizontal divider, active board IDs (truncated to up to 7 characters each, prefixed with `LOG`, wrapping across up to two lines if needed to fit the 20-character screen width, allowing multiple board IDs such as `LOG pico-2w pico-1w` to render on a single line), the total buffered reading count, and the last NTP sync time.

#### Scenario: Logging status section rendered during active session
- **WHEN** `AppState.logging_active` is `True` and the display refreshes in `MODE_SENSOR_DISPLAY`
- **THEN** the lower area of the TFT SHALL show: a divider line, the board-list line(s) (prefixed with `LOG`, fitting on one line when total length <= 20 characters, wrapping to a second line only if needed), a buffered-count line (e.g. `Buf: 12 reads`), and the last NTP time line (e.g. `NTP: 10:04 UTC`)

#### Scenario: Logging status section absent when session inactive
- **WHEN** `AppState.logging_active` is `False`
- **THEN** the TFT SHALL render the standard layout without any logging section

### Requirement: Removal of title header to maximize screen space
The telemetry display SHALL omit the static title header (`Pico 2 W IoTMesh`) and its separator line, starting telemetry and network metrics directly from the top of the display to maximize vertical space and cleanly fit telemetry, requests, caller information, and the logging status section without overflow.

#### Scenario: Screen space optimized
- **WHEN** the standard status screen is displayed
- **THEN** telemetry data starts near y=8, followed by network status, requests served, and last caller, allowing the logging status section to fit within the 160-pixel display height without requiring a separate compact layout mode

### Requirement: LOGGER_CONFIRM screen takes over the TFT
When `AppState.logger_state` is `LOGGER_CONFIRM`, the system SHALL replace the standard sensor display with a full-screen confirmation layout showing: the page title `LOGGER SETUP`, the current UTC date and time from NTP, the list of discovered boards (one per line, prefixed with `*`), and the available user options (`[click] START` and `[hold] CANCEL`). If an error is present in `AppState.log_error`, the error SHALL replace the board list and only the cancel option SHALL be shown.

#### Scenario: Confirm screen rendered — no errors
- **WHEN** `AppState.logger_state` is `LOGGER_CONFIRM` and `AppState.log_error` is `None`
- **THEN** the TFT SHALL show the LOGGER SETUP title, the NTP date/time, discovered board names, and both START and CANCEL options

#### Scenario: Confirm screen rendered — with errors
- **WHEN** `AppState.logger_state` is `LOGGER_CONFIRM` and `AppState.log_error` is set
- **THEN** the TFT SHALL show the LOGGER SETUP title, the error message in red, and only the CANCEL option

### Requirement: LOGGER_STAGING transitional display
When `AppState.logger_state` is `LOGGER_STAGING`, the system SHALL display a transitional status on the TFT indicating that NTP sync and discovery are in progress.

#### Scenario: Staging progress shown
- **WHEN** `AppState.logger_state` is `LOGGER_STAGING`
- **THEN** the TFT SHALL show a message such as `"Preparing..."` or `"Scanning..."` replacing the standard content

### Requirement: Log error display on normal screen
When `AppState.log_error` is set during an active session (e.g. SD card failure), the error string SHALL appear in the logging status section in place of the NTP time line, rendered in red.

#### Scenario: SD error shown in logging section
- **WHEN** `AppState.logging_active` is `True` and `AppState.log_error` is set
- **THEN** the error string SHALL be shown in the logging status section on the TFT in red, replacing the NTP time line
