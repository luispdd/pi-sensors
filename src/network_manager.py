"""WiFi network management for Raspberry Pi Pico W."""

import config

try:
    import uasyncio as asyncio
except ImportError:
    import asyncio

try:
    import network
except ImportError:
    network = None


class NetworkManager:
    def __init__(
        self,
        ssid=config.WIFI_SSID,
        password=config.WIFI_PASSWORD,
        retry_interval=getattr(config, "WIFI_RETRY_INTERVAL_S", 10),
    ):
        self.ssid = ssid
        self.password = password
        self.retry_interval = retry_interval
        self.wlan = None
        self.status = "config_error" if config.WIFI_CONFIG_ERROR else "disconnected"
        self.ip_address = None

        if network is not None and not config.WIFI_CONFIG_ERROR:
            try:
                self.wlan = network.WLAN(network.STA_IF)
                self.wlan.active(True)
            except Exception as e:
                print(f"[network] Initialization error: {e}")

    def is_connected(self):
        """Checks if WiFi is currently connected with a valid IP."""
        if self.wlan is not None:
            try:
                return self.wlan.isconnected()
            except Exception:
                return False
        return False

    def get_ip(self):
        """Returns the current IP address or None."""
        if self.is_connected():
            try:
                self.ip_address = self.wlan.ifconfig()[0]
                return self.ip_address
            except Exception:
                pass
        return None

    def get_status(self):
        """Returns the current connection status string."""
        if config.WIFI_CONFIG_ERROR:
            return "config_error"
        if self.is_connected():
            return "connected"
        return self.status

    async def connect(self, timeout_s=15):
        """Attempts non-blocking WiFi connection up to timeout_s seconds.

        Returns True if connected, False otherwise.
        """
        if config.WIFI_CONFIG_ERROR:
            print(f"[network] WiFi connection aborted: {config.WIFI_CONFIG_ERROR}")
            self.status = "config_error"
            return False

        if self.wlan is None:
            print("[network] WLAN interface not available (simulation mode).")
            self.status = "disconnected"
            return False

        if self.is_connected():
            self.status = "connected"
            self.ip_address = self.wlan.ifconfig()[0]
            return True

        self.status = "connecting"
        print(f"[network] Connecting to WiFi SSID '{self.ssid}'...")
        try:
            self.wlan.connect(self.ssid, self.password)
        except Exception as e:
            print(f"[network] Connect command error: {e}")

        # Poll connection asynchronously so other tasks can run
        waited = 0.0
        while waited < timeout_s:
            if self.is_connected():
                self.ip_address = self.wlan.ifconfig()[0]
                self.status = "connected"
                print(f"[network] Connected! Assigned IP: {self.ip_address}")
                return True
            await asyncio.sleep(0.5)
            waited += 0.5

        self.status = "disconnected"
        print(f"[network] Connection timed out after {timeout_s}s.")
        return False

    async def keepalive_loop(self):
        """Continuous background task to ensure WiFi stays connected."""
        while True:
            if config.WIFI_CONFIG_ERROR:
                self.status = "config_error"
                await asyncio.sleep(self.retry_interval)
                continue

            if not self.is_connected():
                print("[network] WiFi link down, attempting reconnect...")
                self.status = "connecting"
                await self.connect(timeout_s=15)
                if not self.is_connected():
                    self.status = "disconnected"
                    await asyncio.sleep(self.retry_interval)
            else:
                self.status = "connected"
                self.ip_address = self.wlan.ifconfig()[0]
                await asyncio.sleep(5.0)
