"""Live MQTT publisher service for Waveshare ESP32-C6-Zero."""

import json

try:
    import uasyncio as asyncio
    _sleep_ms = asyncio.sleep_ms
except (ImportError, AttributeError):
    import asyncio
    async def _sleep_ms(ms):
        await asyncio.sleep(ms / 1000.0)


def _default_mqtt_client_factory(client_id, host, port):
    from umqtt.simple import MQTTClient
    return MQTTClient(client_id, host, port=port)


class LivePublisher:
    """Manages ephemeral, on-demand live streaming of sensor telemetry to MQTT broker."""

    def __init__(self, app_state, client_factory=None):
        self.app_state = app_state
        self.client_factory = client_factory or _default_mqtt_client_factory

        self.is_live = False
        self.broker = None
        self.broker_host = None
        self.broker_port = 1883
        self.rate_ms = None

        self._client = None
        self._task = None

    def start(self, broker: str, rate_ms: int) -> bool:
        """Starts or adjusts live MQTT publishing at the specified rate in milliseconds."""
        if not broker or not isinstance(broker, str) or rate_ms is None or isinstance(rate_ms, bool) or not isinstance(rate_ms, int) or rate_ms <= 0:
            return False

        if ":" in broker:
            parts = broker.split(":", 1)
            host = parts[0]
            try:
                port = int(parts[1])
            except ValueError:
                port = 1883
        else:
            host = broker
            port = 1883

        # Scenario: Start with same rate while live -> ignore request, keep publishing without interruption
        if self.is_live and self.rate_ms == rate_ms and self.broker_host == host and self.broker_port == port:
            return True

        # Scenario: Start with a different rate while live -> continue publishing at the new rate_ms
        if self.is_live:
            broker_changed = (self.broker_host != host or self.broker_port != port)
            self.rate_ms = rate_ms
            self.broker = broker
            self.broker_host = host
            self.broker_port = port
            if broker_changed and self._client is not None:
                try:
                    self._client.disconnect()
                except Exception:
                    pass
                self._client = None
            return True

        # Scenario: Start from idle -> connect to broker and begin publishing at rate_ms
        self.is_live = True
        self.broker = broker
        self.broker_host = host
        self.broker_port = port
        self.rate_ms = rate_ms
        try:
            if hasattr(asyncio, "get_running_loop"):
                loop = asyncio.get_running_loop()
                self._task = loop.create_task(self._publish_loop())
            else:
                self._task = asyncio.create_task(self._publish_loop())
        except RuntimeError:
            self._task = None
        return True

    def stop(self) -> bool:
        """Stops live publishing and disconnects from the broker. No-op if not live."""
        if not self.is_live:
            return True

        self.is_live = False
        if self._task is not None:
            self._task.cancel()
            self._task = None

        if self._client is not None:
            try:
                self._client.disconnect()
            except Exception:
                pass
            self._client = None

        self.broker = None
        self.broker_host = None
        self.broker_port = 1883
        self.rate_ms = None
        return True

    def _collect_payload(self) -> str:
        """Extracts node's timestamp and registered sensor metrics as JSON string."""
        ts = getattr(self.app_state, "timestamp", None)
        if not ts:
            try:
                from services.ntp_service import get_utc_iso_timestamp
                ts = get_utc_iso_timestamp()
            except Exception:
                ts = None

        metrics = {}
        if hasattr(self.app_state, "get_all_metrics"):
            for k, m in self.app_state.get_all_metrics().items():
                val = m.get("val") if isinstance(m, dict) else m
                if val is not None:
                    metrics[k] = val
        else:
            for k in ("temperature", "humidity", "motion", "noise"):
                val = self.app_state.get_metric_val(k)
                if val is not None:
                    metrics[k] = val

        return json.dumps({
            "timestamp": ts,
            "metrics": metrics,
        })

    async def _publish_loop(self):
        """Asynchronous publisher loop executed while is_live is True."""
        device_id = getattr(self.app_state, "device_id", "esp32c6")
        topic = f"iotmesh/{device_id}/live"

        while self.is_live:
            try:
                if self._client is None:
                    try:
                        self._client = self.client_factory(device_id, self.broker_host, self.broker_port)
                        self._client.connect()
                    except Exception as e:
                        print(f"[live] MQTT connect error to {self.broker_host}:{self.broker_port}: {e}")
                        self._client = None

                if self._client is not None:
                    payload = self._collect_payload()
                    try:
                        self._client.publish(topic, payload)
                    except Exception as e:
                        print(f"[live] MQTT publish error: {e}")
                        try:
                            self._client.disconnect()
                        except Exception:
                            pass
                        self._client = None
            except Exception as e:
                print(f"[live] Error in live publish iteration: {e}")

            try:
                sleep_duration = self.rate_ms if self.rate_ms and self.rate_ms > 0 else 1000
                await _sleep_ms(sleep_duration)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(1)
