## Why

Currently, IoTMesh nodes (`boards/*`) act as passive servers responding to CoAP and HTTP requests, with Pico 2 W buffering and persisting telemetry to SD card logs. To aggregate, monitor, and interact with the mesh network, an active controller is needed to autonomously discover nodes, synchronize persistent historical logs into a central database, and expose a manageable HTTP control interface for operators and future web dashboards.

## What Changes

- Introduce the initial Python controller backend in `controller/backend/`.
- Implement asynchronous CoAP network discovery for IoTMesh nodes via LAN broadcast and multicast probes (`.well-known/core`).
- Implement a data synchronizer and poller that connects to logger nodes advertising `rt="data-sync"`, synchronizes log records using cursor-based pagination (`GET /log?cursor=<c>&size=<s>`), and maintains a 5-minute background polling cadence.
- Implement an on-demand sync trigger (`sync_now()`) protected by concurrency locks so synchronization can be executed immediately via API without colliding with scheduled polling.
- Implement an SQLite database layer storing dynamic sensor metrics as JSON payloads (allowing arbitrary future sensor metrics without schema migrations), tracking sync cursors per logger, and caching node status.
- Implement an HTTP REST API allowing operators to trigger discovery, execute syncs, query historical telemetry, inspect node status, and proxy actuation commands (`POST /display`) to boards using `curl`.
- Defer the Angular frontend application to an upcoming phase.

## Capabilities

### New Capabilities
- `core/controller`: Active IoTMesh controller backend providing CoAP node discovery, cursor-based log synchronization, dynamic SQLite telemetry storage, and an HTTP management API.

### Modified Capabilities
<!-- None: No existing board or core capability requirements are altered. Existing nodes remain passive CoAP servers. -->

## Impact

- **New Files**: `controller/backend/` containing `config.py`, `db.py`, `coap_client.py`, `poller.py`, and `api.py`.
- **Dependencies & Tooling**: Python 3.10+ managed via `uv` (using `pyproject.toml` or `uv pip`), with `aiohttp` (or `fastapi`/`uvicorn`) and asynchronous networking for CoAP.
- **Git / Repo**: Root `.gitignore` updated to ignore `.venv`, `controller/backend/__pycache__/`, and `controller/.venv`.
- **APIs**: New local HTTP endpoints exposed on port 8000 for cURL-driven control and data retrieval.
