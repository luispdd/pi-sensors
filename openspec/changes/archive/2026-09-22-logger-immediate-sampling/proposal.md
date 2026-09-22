## Why

When the user starts a sensor data logging session, the system currently delays capturing any readings until after the full 5-minute sampling interval (`SENSOR_LOG_INTERVAL_S = 300`) elapses. If the user stops the session within those first 5 minutes, no data has been buffered, and nothing is written to the SD card. Furthermore, the in-memory buffer limit of 12 entries would discard the initial reading at the 60-minute mark before an auto-flush.

## What Changes

- **Immediate First Sampling**: When transitioning to `ACTIVE` logging mode, the UI updates immediately, and the background logger task immediately captures and buffers the initial reading ($T=0$) for local and discovered remote nodes before beginning the periodic 5-minute sleep cycle.
- **Buffer Capacity Increase to 13**: Expand the per-node in-memory ring buffer limit from 12 to 13 entries to accommodate the initial $T=0$ sample plus the 12 periodic readings up through the 60-minute mark.
- **Uniform Hourly Flush with Sample Retention**: At the 60-minute auto-flush mark, write the first 12 readings ($M_0$ through $M_{55}$) to the daily CSV file on the SD card, while retaining the 13th reading ($M_{60}$) in the buffer as the first sample of the subsequent hour. Manual stops (`stop_and_flush`) continue to flush all buffered readings.

## Capabilities

### New Capabilities
<!-- None -->

### Modified Capabilities
- `core/data-logger`: Updates the session lifecycle requirement to mandate immediate initial measurement buffering, expands the in-memory ring buffer capacity to 13 entries, and defines the hourly auto-flush behavior of writing 12 records while retaining the 13th measurement in memory.

## Impact

- **Affected Code**: `boards/pico-2w/core/state.py` (buffer size check and slice retention), `boards/pico-2w/services/data_logger.py` (`auto_flush_loop` immediate poll and `flush_to_sd` auto-flush slice logic).
- **APIs / Dependencies**: No external API or schema breaking changes; CSV storage format remains identical.
