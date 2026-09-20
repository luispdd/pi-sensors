# Logger Button Specification

## Purpose

Controls the SD card logging session lifecycle via a dedicated second push button on GP13 (Pin 17), providing a five-stage interaction: IDLE → STAGING → CONFIRM → ACTIVE → IDLE, with short-press and long-press detection.

## Requirements

### Requirement: Dedicated logger button on GP13
The system SHALL configure GP13 as an active-LOW input with internal pull-up resistor as the dedicated logger button, independent of the existing button on GP14. The logger button SHALL have no effect on `MODE_SENSOR_DISPLAY`, `MODE_SEMI_SLEEP`, or `MODE_MESSAGE` transitions.

#### Scenario: Logger button initialised
- **WHEN** the system starts
- **THEN** GP13 SHALL be configured as an input with pull-up and polled by the `button_log_task` every 50 ms

### Requirement: Short-press and long-press detection
The system SHALL distinguish between a short press (button released in under 1000 ms) and a long press (button released at or after 1000 ms). The detection SHALL be based on the elapsed time from press-start to release.

#### Scenario: Short press detected
- **WHEN** the logger button is pressed and released in under 1000 ms
- **THEN** the system SHALL trigger the short-press action for the current logger state

#### Scenario: Long press detected
- **WHEN** the logger button is pressed and held for 1000 ms or more before release
- **THEN** the system SHALL trigger the long-press action for the current logger state

### Requirement: IDLE → STAGING transition (short press)
A short press while the logger is in IDLE state SHALL begin the staging phase: the system SHALL attempt NTP sync, then multicast CoAP discovery to find boards advertising temperature or humidity resources, and transition to the CONFIRM state when both complete (success or failure).

#### Scenario: Short press from IDLE
- **WHEN** the logger button is short-pressed while `AppState.logger_state` is `LOGGER_IDLE`
- **THEN** the system SHALL set `AppState.logger_state` to `LOGGER_STAGING`, display `"Preparing..."` on the TFT, start NTP sync, then start CoAP discovery

#### Scenario: STAGING completes — no errors
- **WHEN** NTP sync succeeds and CoAP discovery finishes
- **THEN** the system SHALL set `AppState.logger_state` to `LOGGER_CONFIRM` and display the confirmation screen showing the date/time and discovered boards

#### Scenario: STAGING completes — NTP or discovery error
- **WHEN** NTP sync fails or no boards (including the local board) are usable
- **THEN** the system SHALL set `AppState.logger_state` to `LOGGER_CONFIRM`, populate `AppState.log_error`, and display the error on the confirm screen with only the long-press cancel option available

### Requirement: CONFIRM → ACTIVE transition (short press)
A short press in the CONFIRM state SHALL start the logging session, but only when NTP sync succeeded (no `AppState.log_error` set). If an error is set, the short press SHALL be ignored.

#### Scenario: Short press from CONFIRM — no errors
- **WHEN** the logger button is short-pressed while in `LOGGER_CONFIRM` and `AppState.log_error` is `None`
- **THEN** the system SHALL set `AppState.logger_state` to `LOGGER_ACTIVE`, `AppState.logging_active` to `True`, and restore the normal sensor display with the logging status section appended

#### Scenario: Short press from CONFIRM — errors present
- **WHEN** the logger button is short-pressed while in `LOGGER_CONFIRM` and `AppState.log_error` is set
- **THEN** the short press SHALL be ignored; no state transition SHALL occur

### Requirement: CONFIRM → IDLE cancel (long press)
A long press in the CONFIRM state SHALL cancel the staging result and return to IDLE, clearing any errors and restoring the normal display.

#### Scenario: Long press from CONFIRM
- **WHEN** the logger button is long-pressed while in `LOGGER_CONFIRM`
- **THEN** the system SHALL set `AppState.logger_state` to `LOGGER_IDLE`, clear `AppState.log_error`, and restore the normal sensor display

### Requirement: ACTIVE → flush and IDLE (short press)
A short press while a logging session is active SHALL trigger an immediate flush of all buffered readings to the SD card and end the session.

#### Scenario: Short press from ACTIVE
- **WHEN** the logger button is short-pressed while `AppState.logging_active` is `True`
- **THEN** the system SHALL call `stop_and_flush()` on `DataLogger`, write all buffered rows to the SD card, reset buffers, and set `AppState.logger_state` to `LOGGER_IDLE`
