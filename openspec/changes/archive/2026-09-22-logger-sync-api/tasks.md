## 1. Sensor Nodes (pico-1w)

- [x] 1.1 Add NTP synchronization capability to `boards/pico-1w/main.py` using `services.ntp_service` and verify it syncs time successfully on boot
- [x] 1.2 Update the DHT22 polling loop to generate a UTC ISO-8601 timestamp at the exact moment of sampling, and verify the timestamp is cached alongside `temperature_c` and `humidity_pct`
- [x] 1.3 Update the CoAP `/sensors` response to include the cached timestamp in the SenML JSON payload, and verify via `coap-client` that the timestamp is returned

## 2. Data Logger (pico-2w) Storage

- [x] 2.1 Update `boards/pico-2w/hardware/sd_storage.py`'s `open_daily_file` method to use `YYYY-MM-DD.csv` instead of `YYYY-MM-DD-<device-id>.csv`, and verify a unified file is created
- [x] 2.2 Update `boards/pico-2w/services/data_logger.py` to extract timestamps from the incoming CoAP/HTTP sensor payloads instead of generating them locally, and verify the buffer holds the remote timestamp
- [x] 2.3 Modify `DataLogger.flush_to_sd()` to aggregate all `buffers` into a single list and apply `.sort(key=lambda r: (r['ts'], r['device_id']))` before calling `sd_storage.flush_buffers()`, and verify the resulting SD file is strictly ordered

## 3. Data Logger (pico-2w) Sync API

- [x] 3.1 Implement a `cursor` parsing utility that splits `filename:line_number` and finds the next sequential file using `os.listdir()` alphabetically, and verify it correctly identifies the next file
- [x] 3.2 Add `GET /log` endpoint to `boards/pico-2w/services/coap_server.py` that accepts `cursor` (optional) and `size` (mandatory) parameters, and verify it returns a 4.00 Bad Request if `size` is missing
- [x] 3.3 Implement the file reading logic in the `/log` endpoint to open the target file, skip to the line, and yield up to `size` lines, updating the `next_cursor`, and verify via `coap-client` that pagination across files works flawlessly
