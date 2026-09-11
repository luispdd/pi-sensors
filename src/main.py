"""Main entry point for Raspberry Pi Pico W environmental sensor station.

Orchestrates concurrent asyncio tasks for:
1. Periodic sensor readings (DHT22 & LM393)
2. SSD1306 OLED display updates with telemetry, URL, and request metrics
3. WiFi connection management and automatic keepalive reconnects
4. Asynchronous HTTP web server serving GET /sensors
"""

import config
from display import OLEDDisplay
from network_manager import NetworkManager
from sensors import SensorReader
from state import AppState
from webserver import WebServer

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


async def sensor_task(app_state: AppState, reader: SensorReader):
    """Periodically reads environmental sensors and updates state."""
    while True:
        try:
            data = reader.read_sensors()
            app_state.update_sensors(data)
        except Exception as e:
            print(f"[main] Error in sensor task: {e}")
        await asyncio.sleep(config.SENSOR_READ_INTERVAL_S)


async def display_task(app_state: AppState, oled: OLEDDisplay):
    """Periodically refreshes the OLED screen with current metrics."""
    while True:
        try:
            oled.update(
                temp=app_state.temperature_c,
                hum=app_state.humidity_pct,
                light_state=app_state.light,
                ip=app_state.ip_address,
                wifi_status=app_state.wifi_status,
                requests_served=app_state.requests_served,
                config_error=app_state.config_error,
            )
        except Exception as e:
            print(f"[main] Error in display task: {e}")
        await asyncio.sleep(config.DISPLAY_REFRESH_INTERVAL_S)


async def network_task(app_state: AppState, net_mgr: NetworkManager):
    """Manages WiFi connection lifecycle and updates network state."""
    if config.WIFI_CONFIG_ERROR:
        app_state.wifi_status = "config_error"
        app_state.config_error = config.WIFI_CONFIG_ERROR
        print(f"[main] WiFi disabled due to configuration error: {config.WIFI_CONFIG_ERROR}")
        while True:
            await asyncio.sleep(30.0)

    # Initial connection attempt
    app_state.wifi_status = "connecting"
    connected = await net_mgr.connect(timeout_s=15)
    if connected:
        app_state.wifi_status = "connected"
        app_state.ip_address = net_mgr.get_ip()
    else:
        app_state.wifi_status = "disconnected"

    # Keepalive loop
    while True:
        try:
            if not net_mgr.is_connected():
                app_state.wifi_status = "connecting"
                app_state.ip_address = None
                print("[main] WiFi disconnected, attempting reconnection...")
                connected = await net_mgr.connect(timeout_s=12)
                if connected:
                    app_state.wifi_status = "connected"
                    app_state.ip_address = net_mgr.get_ip()
                else:
                    app_state.wifi_status = "disconnected"
                    await asyncio.sleep(config.WIFI_RETRY_INTERVAL_S)
            else:
                app_state.wifi_status = "connected"
                app_state.ip_address = net_mgr.get_ip()
                await asyncio.sleep(5.0)
        except Exception as e:
            print(f"[main] Error in network task: {e}")
            await asyncio.sleep(5.0)


async def server_task(app_state: AppState):
    """Starts and runs the asynchronous HTTP server."""
    server = WebServer(app_state, host="0.0.0.0", port=config.HTTP_PORT)
    await server.start()
    while True:
        await asyncio.sleep(3600)


async def main():
    print("=== Raspberry Pi Pico W Sensor Station ===")
    app_state = AppState()

    # Hardware & services initialization
    oled = OLEDDisplay()
    oled.show_splash("Pico Station", "Initializing...")

    reader = SensorReader()
    # Perform immediate initial sensor reading
    init_data = reader.read_sensors()
    app_state.update_sensors(init_data)

    net_mgr = NetworkManager()

    print("[main] Spawning concurrent background tasks...")
    # Spawn background coroutines
    t_sensors = asyncio.create_task(sensor_task(app_state, reader))
    t_display = asyncio.create_task(display_task(app_state, oled))
    t_network = asyncio.create_task(network_task(app_state, net_mgr))
    t_server = asyncio.create_task(server_task(app_state))

    # Keep main coroutine alive
    await asyncio.gather(t_sensors, t_display, t_network, t_server)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[main] Program interrupted by user. Exiting cleanly.")
