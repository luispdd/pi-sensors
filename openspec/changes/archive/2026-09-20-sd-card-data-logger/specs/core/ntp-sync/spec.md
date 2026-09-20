## Purpose

Synchronises the board's real-time clock from a freely available internet NTP service to provide accurate UTC wall-clock timestamps for logged sensor data.

## ADDED Requirements

### Requirement: NTP sync on session arm
The system SHALL attempt an NTP sync using MicroPython's built-in `ntptime` module each time the user arms a new logging session (first button press on the logger button). The sync SHALL complete before the staging discovery phase proceeds. If the sync fails, the system SHALL record the failure in `AppState.log_error` and remain in the staging error state, blocking session confirmation.

#### Scenario: Successful NTP sync
- **WHEN** the user arms the logger and WiFi is connected
- **THEN** the system SHALL call `ntptime.settime()`, update `AppState.log_ntp_time_str` with the resulting UTC time string (format `HH:MM UTC`), and proceed to CoAP discovery

#### Scenario: NTP sync fails — no WiFi
- **WHEN** the user arms the logger and WiFi is not connected or NTP host is unreachable
- **THEN** the system SHALL set `AppState.log_error` to `"NTP: no WiFi"` or `"NTP: timeout"`, display the error on the TFT confirm screen, and allow only a long-press cancel to exit

#### Scenario: NTP sync fails — timeout
- **WHEN** `ntptime.settime()` raises an `OSError` due to timeout
- **THEN** the system SHALL set `AppState.log_error` to `"NTP: timeout"` and block session start

### Requirement: Nightly re-sync
The system SHALL re-sync NTP once per day at midnight UTC while a logging session is active, ensuring timestamps remain accurate across long sessions and day-boundary file rollovers are named correctly.

#### Scenario: Midnight re-sync while session active
- **WHEN** a logging session is active and the UTC date changes (midnight crossed)
- **THEN** the system SHALL attempt an NTP re-sync; on success it SHALL update `AppState.log_ntp_time_str`; on failure it SHALL log a warning but SHALL NOT terminate the session

### Requirement: NTP error display
If NTP sync fails at session arm time, the error SHALL be shown on the TFT staging/confirm screen. The normal sensor display SHALL not be interrupted for NTP errors that occur during a nightly re-sync.

#### Scenario: Arm-time NTP error shown on confirm screen
- **WHEN** NTP fails during session arm
- **THEN** the TFT confirm screen SHALL show the error string and display only the cancel option

#### Scenario: Nightly re-sync error is silent
- **WHEN** a nightly NTP re-sync fails while a session is active
- **THEN** the system SHALL not interrupt the display or the session; the failure SHALL be logged to serial only
