"""Main entry point for Waveshare ESP32-C6-Zero environmental sensor station."""

from settings import config
from core.state import AppState
from hardware.sensors.dht22 import create_sensor as create_dht22
from hardware.led import get_status_led, run_led_task
from hardware.ui import UIController
from services.network_manager import NetworkManager, run_network_task
from services.webserver import run_webserver_task
from services.coap_server import run_coap_task
from services.ntp_service import run_ntp_task
from services.telemetry import run_sensor_task

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


async def memory_task(interval_s=5):
    """Periodic garbage collection to prevent heap fragmentation on ESP32-C6."""
    import gc
    while True:
        await asyncio.sleep(interval_s)
        gc.collect()


async def main():
    print("=== Waveshare ESP32-C6-Zero Station ===")
    app_state = AppState()

    # Hardware & UI initialization
    led = get_status_led()
    led.set_status("boot")

    ui = UIController(app_state)
    ui.show_splash("ESP32-C6 Node", "Initializing...")

    # Register modular sensors
    app_state.register_sensor(create_dht22(pin=config.PIN_DHT22))

    net_mgr = NetworkManager()

    print("[main] Spawning concurrent service tasks...")
    await asyncio.gather(
        run_sensor_task(app_state),
        ui.run_display_task(app_state),
        ui.run_button_task(app_state),
        run_led_task(app_state, led),
        run_network_task(app_state, net_mgr),
        run_webserver_task(app_state),
        run_coap_task(app_state),
        run_ntp_task(app_state),
        memory_task(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[main] Interrupted by user. Exiting cleanly.")
