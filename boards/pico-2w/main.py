"""Main entry point for Raspberry Pi Pico 2 W board."""

from settings import config
from core.state import AppState
from hardware.sensors.dht22 import create_sensor as create_dht22
from hardware.sensors.light import create_sensor as create_light
from hardware.ui import UIController
from hardware.sd_storage import SDStorage
from services.network_manager import NetworkManager, run_network_task
from services.webserver import run_webserver_task
from services.coap_server import CoapServer, run_coap_task
from services.data_logger import DataLogger
from services.ntp_service import run_ntp_task
from services.telemetry import run_sensor_task

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


async def main():
    print("=== Raspberry Pi Pico 2 W Node ===")
    app_state = AppState()

    # Hardware & UI initialization
    ui = UIController(app_state)
    ui.show_splash("Pico 2W Station", "Initializing...")

    # Register modular sensors
    app_state.register_sensor(create_dht22(pin=config.PIN_DHT22))
    app_state.register_sensor(create_light(pin=getattr(config, "PIN_LIGHT_ADC", 26), light_scale=getattr(config, "LIGHT_SCALE_FACTOR", 4.0)))
    app_state.read_registered_sensors()

    # SD Storage and CoAP Server for DataLogger
    sd_storage = SDStorage(spi=ui.spi, tft_cs=getattr(ui.tft, "cs", config.TFT_CS))
    coap_server = CoapServer(app_state, sd_storage=sd_storage, port=config.COAP_PORT)
    data_logger = DataLogger(app_state, sd_storage, coap_server)

    net_mgr = NetworkManager()

    print("[main] Spawning concurrent service tasks...")
    await asyncio.gather(
        run_sensor_task(app_state),
        ui.run_display_task(app_state),
        ui.run_button_task(app_state, data_logger=data_logger),
        run_network_task(app_state, net_mgr),
        run_webserver_task(app_state),
        run_coap_task(app_state, coap_server=coap_server),
        run_ntp_task(app_state),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[main] Program interrupted by user. Exiting cleanly.")
