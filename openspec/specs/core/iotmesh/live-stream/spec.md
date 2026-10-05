# Live Stream Specification

## Purpose

Defines how any sensor-capable board streams its readings on demand to an MQTT broker, so the controller can show near-live data without changing the regular logger sync. The behaviour is identical on every board, regardless of how many boards exist.

## Requirements

### Requirement: Live Stream CoAP Resource
Every sensor-capable board SHALL advertise a `/live` resource in its `.well-known/core` with `rt="live-stream"` and `if="actuator"`, and SHALL accept `POST /live/start` and `POST /live/stop`.

#### Scenario: Resource is discoverable
- **WHEN** a client requests `.well-known/core` from a board
- **THEN** the response SHALL include `</live>;rt="live-stream";if="actuator"`

### Requirement: Live Start
`POST /live/start` SHALL carry a JSON body `{"broker": "<ip>:<port>", "rate_ms": <n>}`. A board that is not live SHALL connect to the given broker as an MQTT client and publish its current readings to the topic `iotmesh/<device_id>/live` every `rate_ms` milliseconds, until stopped or powered off. Each message SHALL contain the board's internal timestamp, which is actively advanced by the board's internal loop (incrementing the timestamp on each loop execution by the elapsed interval, e.g. adding 1 second every 1-second loop tick) with periodic NTP synchronization (e.g. 5 minutes). The board SHALL NOT make ad-hoc timestamp fetches or invoke external time lookups on every sensor read or live publication.

#### Scenario: Start from idle
- **WHEN** a board that is not live receives a valid `POST /live/start`
- **THEN** it SHALL return `2.04 Changed`, connect to the broker and begin publishing at `rate_ms`

#### Scenario: Board internal timestamp in live messages
- **WHEN** a board publishes live samples at `rate_ms`
- **THEN** each sample SHALL include the board's internal timestamp actively advanced by its internal execution loop (anchored by periodic NTP sync) and current sensor metrics, without calling ad-hoc external time lookups on each sample

#### Scenario: Start with same rate while live
- **WHEN** a board that is already live at `rate_ms = N` receives `POST /live/start` with `rate_ms = N`
- **THEN** it SHALL ignore the request, keep publishing without interruption and return `2.04 Changed`

#### Scenario: Start with a different rate while live
- **WHEN** a board that is already live receives `POST /live/start` with a different `rate_ms`
- **THEN** it SHALL continue publishing at the new `rate_ms`

#### Scenario: Invalid start body
- **WHEN** `POST /live/start` has a missing or malformed body or a non-positive `rate_ms`
- **THEN** the board SHALL return `4.00 Bad Request` and SHALL NOT change its live state

#### Scenario: Broker unreachable
- **WHEN** the board cannot reach the broker
- **THEN** it SHALL NOT crash or block its other services, and a missed sample SHALL NOT be retried or backfilled

### Requirement: Live Stop
`POST /live/stop` SHALL stop publishing and disconnect from the broker. It SHALL be a no-op on a board that is not live.

#### Scenario: Stop while live
- **WHEN** a live board receives `POST /live/stop`
- **THEN** it SHALL stop publishing, disconnect from the broker and return `2.04 Changed`

#### Scenario: Stop while idle
- **WHEN** a board that is not live receives `POST /live/stop`
- **THEN** it SHALL return `2.04 Changed` and change nothing

### Requirement: Live Mode Is Ephemeral
Live state SHALL NOT be persisted. A board SHALL NOT resume live publishing after a reboot, and live publishing SHALL NOT affect the board's regular logging or sync behaviour.

#### Scenario: Reboot while live
- **WHEN** a live board reboots
- **THEN** it SHALL start idle and publish nothing until it receives a new `POST /live/start`
