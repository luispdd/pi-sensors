"""Main entry point for Raspberry Pi Pico W environmental sensor station.

Orchestrates concurrent asyncio tasks for:
1. Periodic sensor readings (DHT22)
2. SSD1306 OLED display updates with telemetry, route, and request metrics
3. WiFi connection management and automatic keepalive reconnects
4. Asynchronous HTTP web server serving GET /info
5. Asynchronous IoTMesh CoAP server
6. Reset button monitoring and alert LED output
"""

from settings import config
from hardware.controls import AlertLED, Button
from hardware.display import OLEDDisplay
from services.network_manager import NetworkManager
from hardware.sensors import SensorReader, get_sensor_reader
from core.state import AppState, MODE_SENSOR_DISPLAY, MODE_SEMI_SLEEP, MODE_MESSAGE
from services.webserver import WebServer
from services.coap_server import CoapServer
from services.ntp_service import sync_ntp, get_utc_iso_timestamp, NTPTracker

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


async def sensor_task(app_state: AppState, reader: SensorReader):
    """Periodically reads environmental sensors and updates state."""
    while True:
        try:
            if app_state.mode != MODE_SEMI_SLEEP:
                prev_errors = reader.read_errors
                data = reader.read_sensors()
                if reader.read_errors == prev_errors and app_state.ntp_synced:
                    data["timestamp"] = get_utc_iso_timestamp()
                    reader.last_timestamp = data["timestamp"]
                else:
                    data["timestamp"] = reader.last_timestamp
                app_state.update_sensors(data)
                await asyncio.sleep(config.SENSOR_READ_INTERVAL_S)
            else:
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[main] Error in sensor task: {e}")
            await asyncio.sleep(config.SENSOR_READ_INTERVAL_S)


async def display_task(app_state: AppState, oled: OLEDDisplay):
    """Periodically refreshes the OLED screen with current metrics."""
    while True:
        try:
            if app_state.mode != MODE_SEMI_SLEEP:
                oled.update_from_state(app_state)
                await asyncio.sleep(config.DISPLAY_REFRESH_INTERVAL_S)
            else:
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[main] Error in display task: {e}")
            await asyncio.sleep(config.DISPLAY_REFRESH_INTERVAL_S)


async def button_task(app_state: AppState, button: Button, led: AlertLED, oled: OLEDDisplay = None):
    """Monitors the reset button and controls the alert LED."""
    while True:
        try:
            # Sync LED state with active message mode or pending message
            led.set(app_state.mode == MODE_MESSAGE or app_state.has_pending_message())

            if button.was_pressed():
                # Button pressed transition edge
                if app_state.mode == MODE_SENSOR_DISPLAY:
                    print("[main] Button pressed: entering semi-sleep")
                    app_state.enter_semi_sleep()
                    if oled is not None:
                        oled.power_off()
                    led.off()
                elif app_state.mode == MODE_SEMI_SLEEP:
                    if app_state.has_pending_message():
                        print("[main] Button pressed: showing pending message")
                        msg = app_state.pending_message
                        app_state.enter_message_mode(msg)
                        led.on()
                    else:
                        print("[main] Button pressed: resuming sensor display")
                        app_state.enter_sensor_mode()
                        led.off()
                elif app_state.mode == MODE_MESSAGE:
                    print("[main] Button pressed: clearing message, resuming sensor display")
                    app_state.enter_sensor_mode()
                    led.off()
        except Exception as e:
            print(f"[main] Error in button task: {e}")
        await asyncio.sleep(0.05)


async def network_task(app_state: AppState, net_mgr: NetworkManager):
    """Manages WiFi connection lifecycle and updates network state."""
    if config.WIFI_CONFIG_ERROR:
        app_state.update_wifi("config_error", config_error=config.WIFI_CONFIG_ERROR)
        print(f"[main] WiFi disabled due to configuration error: {config.WIFI_CONFIG_ERROR}")
        while True:
            await asyncio.sleep(30.0)

    # Initial connection attempt
    app_state.update_wifi("connecting")
    connected = await net_mgr.connect(timeout_s=15)
    if connected:
        app_state.update_wifi("connected", ip=net_mgr.get_ip())
    else:
        app_state.update_wifi("disconnected")

    # Keepalive loop
    while True:
        try:
            if not net_mgr.is_connected():
                app_state.update_wifi("connecting")
                print("[main] WiFi disconnected, attempting reconnection...")
                connected = await net_mgr.connect(timeout_s=12)
                if connected:
                    app_state.update_wifi("connected", ip=net_mgr.get_ip())
                else:
                    app_state.update_wifi("disconnected")
                    await asyncio.sleep(config.WIFI_RETRY_INTERVAL_S)
            else:
                app_state.update_wifi("connected", ip=net_mgr.get_ip())
                await asyncio.sleep(5.0)
        except Exception as e:
            print(f"[main] Error in network task: {e}")
            await asyncio.sleep(5.0)


async def server_task(app_state: AppState, reader: SensorReader = None):
    """Starts and runs the asynchronous HTTP server."""
    server = WebServer(app_state, reader=reader, host="0.0.0.0", port=config.HTTP_PORT)
    await server.start()
    while True:
        await asyncio.sleep(3600)


async def coap_task(app_state: AppState, reader: SensorReader = None):
    """Starts and runs the asynchronous IoTMesh CoAP server."""
    try:
        # Wait until WiFi is connected before binding UDP socket
        while app_state.wifi_status != "connected":
            await asyncio.sleep(0.5)

        print(f"[main] WiFi connected, starting CoAP server on port {config.COAP_PORT}...")
        server = CoapServer(app_state, reader=reader, port=config.COAP_PORT)
        server.start()
        await server.run()
    except Exception as e:
        print(f"[main] Error in coap_task: {e}")


async def ntp_task(app_state: AppState):
    """Synchronizes NTP clock on boot once WiFi is connected, and periodically."""
    ntp_tracker = NTPTracker()
    while True:
        try:
            if app_state.wifi_status == "connected":
                if not app_state.ntp_synced:
                    success, res = sync_ntp()
                    if success:
                        app_state.ntp_synced = True
                        print(f"[ntp] Initial NTP sync successful: {res}")
                    else:
                        print(f"[ntp] Initial NTP sync failed: {res}")
                else:
                    ntp_tracker.check_and_resync(app_state)
            await asyncio.sleep(10.0 if not app_state.ntp_synced else 60.0)
        except Exception as e:
            print(f"[main] Error in ntp task: {e}")
            await asyncio.sleep(30.0)


async def main():
    print("=== Raspberry Pi Pico W Sensor Station ===")
    app_state = AppState()

    # Hardware & services initialization
    oled = OLEDDisplay()
    oled.show_splash("Pico Station", "Initializing...")

    button = Button(config.PIN_BUTTON)
    led = AlertLED(config.PIN_LED_ALERT)

    reader = get_sensor_reader()
    # Perform immediate initial sensor reading
    init_data = reader.read_sensors()
    if app_state.ntp_synced:
        init_data["timestamp"] = get_utc_iso_timestamp()
    app_state.update_sensors(init_data)

    net_mgr = NetworkManager()

    print("[main] Spawning concurrent background tasks...")
    # Spawn background coroutines
    t_sensors = asyncio.create_task(sensor_task(app_state, reader))
    t_display = asyncio.create_task(display_task(app_state, oled))
    t_network = asyncio.create_task(network_task(app_state, net_mgr))
    t_server = asyncio.create_task(server_task(app_state, reader))
    t_coap = asyncio.create_task(coap_task(app_state, reader))
    t_button = asyncio.create_task(button_task(app_state, button, led, oled))
    t_ntp = asyncio.create_task(ntp_task(app_state))

    # Keep main coroutine alive
    await asyncio.gather(t_sensors, t_display, t_network, t_server, t_coap, t_button, t_ntp)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[main] Program interrupted by user. Exiting cleanly.")
