## 1. Project Setup and Environment Configuration

- [x] 1.1 Create `controller/backend/` directory structure, initialize Python project environment with `uv` (`pyproject.toml`), and update root `.gitignore` for `.venv`, `controller/.venv`, and `__pycache__`; verify environment creation using `uv sync` or `uv run`.
- [x] 1.2 Implement `controller/backend/config.py` defining controller identity (`id="controller-01"`), HTTP port (8000), CoAP port (5683), discovery targets, and polling interval; verify by running a quick import check.

## 2. Dynamic SQLite Telemetry Storage

- [x] 2.1 Implement `controller/backend/db.py` creating SQLite tables for `readings` (with `metrics JSON` and `UNIQUE(timestamp, device_id)`), `sync_state`, and `nodes`; verify schema creation with a standalone test script.
- [x] 2.2 Add database helper functions in `db.py` for inserting dynamic readings, updating logger cursors, registering discovered nodes, and querying readings with `device_id`, `since`, and `limit` filters; verify with unit test assertions.

## 3. Asynchronous CoAP Client & Discovery

- [x] 3.1 Implement `controller/backend/coap_client.py` for async CoAP packet serialization, message parsing (RFC 7252), and socket communication; verify with unit tests on message encoding/decoding.
- [x] 3.2 Implement LAN discovery in `coap_client.py` sending broadcast and multicast (`224.0.1.187`) `.well-known/core` probes and parsing CoRE Link Format payloads into node capability dictionaries; verify with mock responses.
- [x] 3.3 Implement `GET /log?cursor=...&size=...` and `POST /display` client methods in `coap_client.py` with timeout and retry logic; verify against simulated endpoint responses.

## 4. Poller Service & On-Demand Synchronization

- [x] 4.1 Implement `PollerService` in `controller/backend/poller.py` with `sync_now()` guarded by `asyncio.Lock` to execute sequential catch-up bursts against discovered loggers and ingest dynamic records into SQLite; verify with a multi-page mock sync test.
- [x] 4.2 Implement the automated 300-second background cadence loop in `poller.py` with startup, periodic trigger, and cancellation handling; verify task lifecycle behavior.

## 5. HTTP Management REST API (Curl-Ready)

- [x] 5.1 Implement `controller/backend/api.py` exposing `GET /api/status`, `GET /api/nodes`, and `POST /api/discover`; verify via `curl http://localhost:8000/api/status` and `curl -X POST http://localhost:8000/api/discover`.
- [x] 5.2 Implement `POST /api/sync` and `GET /api/readings` in `api.py` returning dynamic JSON metrics; verify via `curl -X POST http://localhost:8000/api/sync` and `curl "http://localhost:8000/api/readings?limit=10"`.
- [x] 5.3 Implement `POST /api/display` proxying actuator messages to target nodes in `api.py`; verify via `curl -X POST http://localhost:8000/api/display -d '{"target":"...","message":"test"}'`.
- [x] 5.4 Implement the unified entrypoint in `controller/backend/main.py` launching both the HTTP web server and the background poller with graceful shutdown handling; verify startup and shutdown cleanly using `uv run`.
