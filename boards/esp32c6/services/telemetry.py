"""Periodic telemetry sampling service for registered sensors."""

from settings import config
from core.state import MODE_SEMI_SLEEP
from services.ntp_service import get_utc_iso_timestamp

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


async def run_sensor_task(app_state, interval_s=getattr(config, "SENSOR_READ_INTERVAL_S", 2.5)):
    """Periodically samples registered sensors in active modes."""
    # Warm-up delay after boot
    await asyncio.sleep(2.0)
    while True:
        try:
            if app_state.mode != MODE_SEMI_SLEEP:
                ts = get_utc_iso_timestamp() if app_state.ntp_synced else None
                app_state.read_registered_sensors(timestamp=ts)
                await asyncio.sleep(interval_s)
            else:
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[telemetry] Error in sensor task: {e}")
            await asyncio.sleep(interval_s)
