## Context

Existing IoTMesh nodes (`boards/pico-1w`, `boards/pico-2w`) run MicroPython and act as passive CoAP servers on UDP port 5683. The Pico 2 W buffers readings and writes daily CSV logs to SD card storage, exposing them through `GET /log?cursor=<c>&size=<s>`. The controller is the first active node in the system, responsible for discovering LAN nodes, synchronizing logs into SQLite, and serving an HTTP API.

See `proposal.md` for motivation and `specs/core/controller/spec.md` for behavioral requirements.

## Goals / Non-Goals

**Goals:**
- Implement a modular, asynchronous CPython backend in `controller/backend/` (`config.py`, `db.py`, `coap_client.py`, `poller.py`, `api.py`).
- Store sensor readings dynamically using SQLite `JSON` metrics (`metrics JSON`), supporting any sensor type without database migrations.
- Provide a thread/task-safe `sync_now()` function protected by an `asyncio.Lock`, accessible both by the automated 300s background loop and via `POST /api/sync`.
- Expose a clean HTTP REST API for cURL-driven operations (discover, sync, display proxy, query readings, status).

**Non-Goals:**
- Building the Angular frontend application or serving frontend static assets (deferred to an upcoming phase).
- Multi-process scaling or external database engines (Postgres/Redis) — SQLite WAL is optimal for this single-controller topology.
- Modifying firmware or specs on existing `boards/*`.

## Decisions

### Decision 1: Dynamic Sensor Schema using SQLite JSON
- **Choice**: Store telemetry in a `readings` table with `timestamp TEXT`, `device_id TEXT`, and `metrics JSON NOT NULL`, indexed with a unique constraint on `(timestamp, device_id)`.
- **Rationale**: Nodes like `pico-1w` only provide temperature/humidity; `pico-2w` provides light; future nodes will introduce barometric pressure, VOCs, or battery level. Storing dynamic JSON payloads avoids brittle schema migrations while enabling SQLite's native `json_extract()` for queries.
- **Alternatives Considered**:
  - *Fixed columns (`temp`, `hum`, `light`)*: Rejected because adding new sensors requires schema alterations and leaves sparse columns.
  - *Entity-Attribute-Value (EAV)*: Rejected due to 4x-5x row multiplication and high query complexity when reconstituting snapshots.

### Decision 2: Async CoAP Client Architecture in `controller/backend/coap_client.py`
- **Choice**: Implement an asynchronous UDP CoAP client directly inside `controller/backend/coap_client.py` using Python's standard `asyncio.DatagramProtocol` or `socket` integration.
- **Rationale**: By tailoring the client directly to IoTMesh's CoAP profile (RFC 7252 Confirmable/Non-Confirmable GET/POST, CoRE Link Format parsing, and subnet broadcast/multicast), we avoid heavyweight external bindings while ensuring protocol compatibility with the MicroPython nodes.
- **Alternatives Considered**:
  - *Reusing `boards/pico-2w/services/coap_server.py`*: Rejected because `pico-2w` relies on MicroPython-specific modules (`microcoapy`, `usocket`).
  - *`aiocoap` package*: Viable, but standard asyncio UDP sockets provide zero-dependency simplicity and total control over broadcast/multicast socket options across Linux platforms.

### Decision 3: Poller Synchronization and Concurrency Architecture
- **Choice**: Decouple the synchronization worker into a `PollerService` with a `sync_now()` method guarded by `asyncio.Lock`.
- **Rationale**: When an operator executes `curl -X POST http://localhost:8000/api/sync`, the system can immediately run the catch-up loop without waiting for the 5-minute timer. If a sync is already executing, the lock prevents double-polling or duplicate network bursts.
- **Alternatives Considered**:
  - *Coupled timer loop*: Poller runs only on a timer, requiring manual triggers to just set a flag and wait for the next tick. Rejected because operators want immediate feedback on "Sync now".

### Decision 4: HTTP Framework Selection
- **Choice**: `aiohttp.web` (or `FastAPI` / `Starlette`).
- **Rationale**: `aiohttp.web` integrates seamlessly into Python's native `asyncio` event loop, allowing the HTTP server, the background poller task, and the UDP CoAP client to run co-operatively in a single process without threading overhead.

### Decision 5: Package Management and Environment Orchestration with uv
- **Choice**: Use `uv` for virtual environment creation, dependency resolution, lockfile management (`pyproject.toml` / `uv.lock`), and execution (`uv run`).
- **Rationale**: `uv` provides blazing-fast reproducible dependency installations, robust environment isolation, and avoids `pip` version drift or global contamination on Linux and development hosts.
- **Alternatives Considered**:
  - *Standard `pip` and `venv`*: Functional but significantly slower, lacking deterministic lockfile management by default.
  - *Poetry / Pipenv*: Heavier tools with more friction and slower resolution.

## Risks / Trade-offs

- **[UDP packet loss during log catch-up burst]** &rarr; *Mitigation*: The CoAP client implements retry logic with exponential backoff on unacknowledged requests.
- **[Long catch-up sync blocking the event loop]** &rarr; *Mitigation*: The poller processes paginated batches of 50 rows and calls `await asyncio.sleep(0)` between pages to yield control back to HTTP requests.
- **[Network broadcast restrictions on certain routers]** &rarr; *Mitigation*: The discovery mechanism sends probes to both IPv4 multicast `224.0.1.187` and subnet broadcast (`x.x.x.255` and `255.255.255.255`), and allows direct target IP specification in API requests.
