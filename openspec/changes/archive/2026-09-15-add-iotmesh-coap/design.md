## Context

The Pico W currently runs a `uasyncio` HTTP server to serve sensor telemetry on port 80. To implement the IoTMesh Service Spec, we need to add a UDP CoAP server alongside it on port 5683. MicroPython on the `rp2350`/`rp2040` (with the `cyw43` driver) has known multicast reliability issues, so UDP broadcast (`255.255.255.255:5683`) is used for CoRE Link Format discovery.

## Goals / Non-Goals

**Goals:**
- Serve CoAP endpoints concurrently with the existing HTTP server.
- Intercept the OLED display rendering logic in `display.py` without blocking the main event loop.

**Non-Goals:**
- Completely removing the HTTP webserver (this will be an optional cleanup task later).
- Adding persistent storage for custom display messages across reboots.

## Decisions

**1. CoAP Library Integration:**
- **Decision:** Use `microCoAPy`.
- **Rationale:** The spec explicitly recommends it for MicroPython. We will integrate its listening loop into the root `main.py` using `uasyncio` (if `microCoAPy` provides async support) or a non-blocking `select`/`poll` loop within an async task to ensure it coexists nicely with the HTTP server.

**2. Discovery Binding:**
- **Decision:** Bind the CoAP server to `0.0.0.0:5683`.
- **Rationale:** This allows the node to receive both unicast CoAP requests (for sensors) and broadcast UDP packets (`255.255.255.255:5683`) for CoRE Link discovery.

**3. Display Override State Machine:**
- **Decision:** Add a `display_override_text` string and `display_override_expires_at` timestamp to the shared `AppState` in `state.py`.
- **Rationale:** `display.py` already checks `AppState` to render the screen. By adding the override state there, `display.py` can simply check if `ticks_ms()` is less than `display_override_expires_at` and draw the override text instead of the sensor metrics. The CoAP `POST /display` endpoint just updates these two fields in `AppState`.

## Risks / Trade-offs

- **[Risk] Increased memory footprint** → Mitigation: Run garbage collection (`gc.collect()`) periodically and consider disabling debug logging in `microCoAPy` as recommended for constrained environments like the ESP8266.
- **[Risk] Main loop blocking** → Mitigation: Ensure the UDP socket recv loop is non-blocking or awaited properly via `uasyncio`.
