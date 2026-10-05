"""NTP time synchronization service using MicroPython's built-in ntptime module."""

import time

try:
    import ntptime
except ImportError:
    ntptime = None


def get_utc_time_str():
    """Returns the current UTC time as 'HH:MM UTC' string from time.localtime()."""
    try:
        t = time.localtime()
        return f"{t[3]:02d}:{t[4]:02d} UTC"
    except Exception:
        return "--:-- UTC"


def get_utc_date_str():
    """Returns the current UTC date as 'YYYY-MM-DD' string from time.localtime()."""
    try:
        t = time.localtime()
        return f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}"
    except Exception:
        return "1970-01-01"


def format_iso_timestamp(secs=None):
    """Formats epoch seconds (or current RTC time) into UTC ISO-8601 string 'YYYY-MM-DDTHH:MM:SS'."""
    try:
        t = time.localtime(secs) if secs is not None else time.localtime()
        return f"{t[0]:04d}-{t[1]:02d}-{t[2]:02d}T{t[3]:02d}:{t[4]:02d}:{t[5]:02d}"
    except Exception:
        return "1970-01-01T00:00:00"


def get_utc_iso_timestamp():
    """Returns the current UTC ISO-8601 string 'YYYY-MM-DDTHH:MM:SS'."""
    return format_iso_timestamp()


def sync_ntp(host=None):
    """Synchronises the internal RTC using ntptime.settime().

    Returns (True, 'HH:MM UTC') on success,
    or (False, error_str) on failure/OSError.
    """
    if ntptime is None:
        return (False, "NTP: not supported")

    if host:
        try:
            ntptime.host = host
        except Exception:
            pass

    try:
        ntptime.settime()
        time_str = get_utc_time_str()
        return (True, time_str)
    except OSError as e:
        err_msg = str(e).lower()
        if "timeout" in err_msg or "timed out" in err_msg or getattr(e, "errno", None) == 110:
            return (False, "NTP: timeout")
        return (False, "NTP: no WiFi")
    except Exception as e:
        return (False, f"NTP: error")


class NTPTracker:
    """Tracks midnight crossing and triggers nightly NTP re-sync."""

    def __init__(self):
        try:
            self._last_sync_day = time.localtime()[2]
        except Exception:
            self._last_sync_day = None

    def check_and_resync(self, app_state=None):
        """Checks if UTC day (day of month) has changed.

        If changed, attempts sync_ntp().
        On success, updates app_state.log_ntp_time_str if app_state is provided.
        Returns True if a resync was attempted, False otherwise.
        """
        try:
            current_day = time.localtime()[2]
        except Exception:
            return False

        if self._last_sync_day is None:
            self._last_sync_day = current_day
            return False

        if current_day != self._last_sync_day:
            print(f"[ntp] UTC date changed from day {self._last_sync_day} to {current_day}, re-syncing NTP...")
            self._last_sync_day = current_day
            success, result = sync_ntp()
            if success:
                print(f"[ntp] Midnight re-sync successful: {result}")
                if app_state is not None:
                    app_state.log_ntp_time_str = result
            else:
                print(f"[ntp] Warning: Midnight re-sync failed ({result}); session continues.")
            return True

        return False


async def run_ntp_task(app_state, sync_interval_s=300):
    """Maintains board internal timestamp by ticking every second, and synchronizes NTP periodically (default every 5 minutes)."""
    try:
        import uasyncio as asyncio
    except ImportError:
        import asyncio

    last_sync = 0
    # Anchor initial time if needed
    if getattr(app_state, "_current_epoch", None) is None:
        try:
            if hasattr(app_state, "set_time"):
                app_state.set_time(time.time(), synced=False)
        except Exception:
            pass

    while True:
        try:
            now = time.time()
            if getattr(app_state, "wifi_status", None) == "connected":
                if not getattr(app_state, "ntp_synced", False) or (now - last_sync >= sync_interval_s):
                    success, res = sync_ntp()
                    if success:
                        last_sync = time.time()
                        if hasattr(app_state, "set_time"):
                            app_state.set_time(last_sync, synced=True)
                        if hasattr(app_state, "log_ntp_time_str"):
                            app_state.log_ntp_time_str = res
                        print(f"[ntp] NTP sync successful ({res}), anchor epoch: {last_sync}")
                        # Take periodic measurement aligned with NTP sync
                        if hasattr(app_state, "read_registered_sensors"):
                            try:
                                app_state.read_registered_sensors()
                            except Exception as e:
                                print(f"[ntp] Error taking aligned sensor reading: {e}")
                    else:
                        print(f"[ntp] NTP sync failed: {res}")

            # Internal execution loop ticks the timestamp by 1 second on each tick
            if hasattr(app_state, "tick_timestamp"):
                app_state.tick_timestamp(1)

            await asyncio.sleep(1.0)
        except Exception as e:
            print(f"[ntp] Error in timekeeper task: {e}")
            await asyncio.sleep(1.0)

