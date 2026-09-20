"""Main entry point for Raspberry Pi Pico 2 W board.

Orchestrates concurrent asyncio tasks for:
1. Periodic sensor readings (stub reader)
2. ST7735 TFT display updates with telemetry, route, and request metrics
3. WiFi connection management and automatic keepalive reconnects
4. Asynchronous HTTP web server serving GET /info
5. Asynchronous IoTMesh CoAP server
6. Button monitoring and alert LED output (stubs)
"""

from settings import config
from hardware.controls import AlertLED, Button, ButtonLog
from hardware.display import TFTDisplay, OLEDDisplay
from hardware.sd_storage import SDStorage
from services.network_manager import NetworkManager
from hardware.sensors import SensorReader, get_sensor_reader
from core.state import (
    AppState,
    MODE_SENSOR_DISPLAY,
    MODE_SEMI_SLEEP,
    MODE_MESSAGE,
    LOGGER_IDLE,
    LOGGER_STAGING,
    LOGGER_CONFIRM,
    LOGGER_ACTIVE,
)
from services.webserver import WebServer
from services.coap_server import CoapServer
from services.data_logger import DataLogger

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio


async def sensor_task(app_state: AppState, reader: SensorReader):
    """Periodically reads environmental sensors and updates state."""
    while True:
        try:
            if app_state.mode != MODE_SEMI_SLEEP:
                data = reader.read_sensors()
                app_state.update_sensors(data)
                await asyncio.sleep(config.SENSOR_READ_INTERVAL_S)
            else:
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[main] Error in sensor task: {e}")
            await asyncio.sleep(config.SENSOR_READ_INTERVAL_S)


async def display_task(app_state: AppState, display: TFTDisplay):
    """Periodically refreshes the TFT screen with current metrics."""
    while True:
        try:
            if app_state.mode != MODE_SEMI_SLEEP:
                display.update_from_state(app_state)
                await asyncio.sleep(config.DISPLAY_REFRESH_INTERVAL_S)
            else:
                await asyncio.sleep(0.1)
        except Exception as e:
            print(f"[main] Error in display task: {e}")
            await asyncio.sleep(config.DISPLAY_REFRESH_INTERVAL_S)


async def button_task(app_state: AppState, button: Button, led: AlertLED, display: TFTDisplay = None):
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
                    if display is not None:
                        display.power_off()
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


async def button_log_task(app_state: AppState, button_log: ButtonLog, data_logger: DataLogger, display: TFTDisplay = None):
    """Monitors the dedicated data logger button (GP13) and dispatches lifecycle events."""
    active_flush_loop_task = None

    while True:
        try:
            rel = button_log.release_type()
            if rel is not None:
                current_logger_state = app_state.logger_state

                if current_logger_state == LOGGER_IDLE:
                    if rel == "short":
                        print("[main] Logger button: IDLE -> short-press, running staging...")
                        asyncio.create_task(data_logger.run_staging())

                elif current_logger_state == LOGGER_CONFIRM:
                    if rel == "short":
                        if not app_state.log_error:
                            print("[main] Logger button: CONFIRM -> short-press, starting session...")
                            data_logger.start_session()
                            if active_flush_loop_task is None or active_flush_loop_task.done():
                                active_flush_loop_task = asyncio.create_task(data_logger.auto_flush_loop())
                        else:
                            print("[main] Logger button: short-press ignored due to staging error.")
                    elif rel == "long":
                        print("[main] Logger button: CONFIRM -> long-press, canceling to IDLE...")
                        app_state.clear_logger_error()
                        app_state.logger_state = LOGGER_IDLE

                elif current_logger_state == LOGGER_ACTIVE:
                    if rel == "short":
                        print("[main] Logger button: ACTIVE -> short-press, stopping and flushing...")
                        asyncio.create_task(data_logger.stop_and_flush())

            await asyncio.sleep(0.05)
        except Exception as e:
            print(f"[main] Error in button_log_task: {e}")
            await asyncio.sleep(0.05)


async def server_task(app_state: AppState, reader: SensorReader = None):
    """Starts and runs the asynchronous HTTP server."""
    server = WebServer(app_state, reader=reader, host="0.0.0.0", port=config.HTTP_PORT)
    await server.start()
    while True:
        await asyncio.sleep(3600)


async def coap_task(app_state: AppState, coap_server: CoapServer = None, reader: SensorReader = None):
    """Starts and runs the asynchronous IoTMesh CoAP server."""
    try:
        # Wait until WiFi is connected before binding UDP socket
        while app_state.wifi_status != "connected":
            await asyncio.sleep(0.5)

        print(f"[main] WiFi connected, starting CoAP server on port {config.COAP_PORT}...")
        server = coap_server if coap_server is not None else CoapServer(app_state, reader=reader, port=config.COAP_PORT)
        server.start()
        await server.run()
    except Exception as e:
        print(f"[main] Error in coap_task: {e}")


async def main():
    print("=== Raspberry Pi Pico 2 W Node ===")
    app_state = AppState()

    # Hardware & services initialization
    display = TFTDisplay()
    display.show_splash("Pico 2W Station", "Initializing...")

    button = Button(config.PIN_BUTTON)
    button_log = ButtonLog(config.PIN_BUTTON_LOG)
    led = AlertLED(config.PIN_LED_ALERT)

    reader = get_sensor_reader()
    init_data = reader.read_sensors()
    app_state.update_sensors(init_data)

    # SD Storage and CoAP Server for DataLogger
    sd_storage = SDStorage(spi=display.spi, tft_cs=getattr(display.tft, "cs", config.TFT_CS))
    coap_server = CoapServer(app_state, reader=reader, port=config.COAP_PORT)
    data_logger = DataLogger(app_state, sd_storage, coap_server)

    net_mgr = NetworkManager()

    print("[main] Spawning concurrent background tasks...")
    # Spawn background coroutines
    t_sensors = asyncio.create_task(sensor_task(app_state, reader))
    t_display = asyncio.create_task(display_task(app_state, display))
    t_network = asyncio.create_task(network_task(app_state, net_mgr))
    t_server = asyncio.create_task(server_task(app_state, reader))
    t_coap = asyncio.create_task(coap_task(app_state, coap_server=coap_server, reader=reader))
    t_button = asyncio.create_task(button_task(app_state, button, led, display))
    t_button_log = asyncio.create_task(button_log_task(app_state, button_log, data_logger, display))

    # Keep main coroutine alive
    await asyncio.gather(t_sensors, t_display, t_network, t_server, t_coap, t_button, t_button_log)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[main] Program interrupted by user. Exiting cleanly.")
