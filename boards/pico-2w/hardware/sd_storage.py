"""SD card storage management using MicroPython's sdcard driver and os.mount with SPI arbitration."""

import os
from settings import config

try:
    from machine import Pin
except ImportError:
    Pin = None

try:
    import sdcard
except ImportError:
    try:
        from lib import sdcard
    except ImportError:
        sdcard = None

CSV_HEADER = "timestamp,device_id,temperature_c,humidity_pct,light_pct\n"


class SDStorage:
    """Manages mounting, directory creation, CSV writing, and unmounting for SD card storage."""

    def __init__(
        self,
        spi=None,
        tft_cs=None,
        sd_cs_pin=config.SD_CS,
        mount_point="/sd",
        baudrate=config.SPI_SPEED_SD_DATA,
    ):
        self.spi = spi
        self.mount_point = mount_point
        self.baudrate = baudrate
        self._mounted = False
        self._sd = None

        # Setup TFT CS pin reference for SPI bus arbitration
        if isinstance(tft_cs, int):
            self.tft_cs = Pin(tft_cs, Pin.OUT, value=1) if Pin is not None else None
        else:
            self.tft_cs = tft_cs

        # Setup SD CS pin
        if Pin is not None and sd_cs_pin is not None:
            self.sd_cs = Pin(sd_cs_pin, Pin.OUT, value=1)
        else:
            self.sd_cs = None

    def _acquire_bus(self):
        """Sets TFT_CS HIGH and updates SPI frequency to SD data baudrate."""
        if self.tft_cs is not None:
            try:
                self.tft_cs.value(1)
            except Exception:
                pass
        if self.spi is not None:
            try:
                self.spi.init(baudrate=self.baudrate)
            except Exception:
                pass

    def mount(self):
        """Mounts the SD card filesystem at self.mount_point.

        Raises OSError or Exception if card missing or mount fails.
        """
        if self._mounted:
            return True

        if self.spi is None or self.sd_cs is None or sdcard is None:
            raise OSError("Hardware or driver missing for SD card")

        self._acquire_bus()
        self._sd = sdcard.SDCard(self.spi, self.sd_cs)
        vfs = os.VfsFat(self._sd)
        os.mount(vfs, self.mount_point)
        self._mounted = True
        return True

    def unmount(self):
        """Unmounts the SD card filesystem if currently mounted."""
        if not self._mounted:
            return
        try:
            os.umount(self.mount_point)
        except Exception:
            pass
        finally:
            self._mounted = False
            self._sd = None
            if self.sd_cs is not None:
                try:
                    self.sd_cs.value(1)
                except Exception:
                    pass

    def ensure_dir(self, path):
        """Creates directory and necessary parent directories on the mounted filesystem.

        e.g., path = "/sd/sensor-data"
        """
        parts = [p for p in path.split("/") if p]
        current = ""
        if path.startswith("/"):
            current = "/"
        for part in parts:
            current = current + ("" if current == "/" else "/") + part
            try:
                os.mkdir(current)
            except OSError:
                # Directory already exists or cannot be created
                pass

    def open_daily_file(self, date_str, device_id=None):
        """Opens /sd/sensor-data/<date_str>.csv in append mode.

        Writes the CSV header if the file is newly created (size == 0).
        Returns the open file handle.
        """
        # Support flexible argument order if called as (device_id, date_str)
        if device_id is not None:
            if isinstance(device_id, str) and len(device_id) == 10 and device_id[4] == "-" and device_id[7] == "-":
                date_str = device_id

        dir_path = f"{self.mount_point}{config.LOG_SD_ROOT}"
        self.ensure_dir(dir_path)
        file_path = f"{dir_path}/{date_str}.csv"

        # Check if file exists and has content
        file_exists = False
        try:
            stat = os.stat(file_path)
            if stat[6] > 0:  # stat[6] is st_size in MicroPython
                file_exists = True
        except OSError:
            file_exists = False

        f = open(file_path, "a")
        if not file_exists:
            f.write(CSV_HEADER)
            f.flush()
        return f

    def write_rows(self, file_handle, rows):
        """Writes rows (iterable of dicts with ts, device_id, temp, hum) as CSV lines and flushes.

        Each row dict or tuple is expected to have:
        - ts: ISO-8601 string
        - device_id: string
        - temp: float/int or None
        - hum: float/int or None
        """
        for r in rows:
            if isinstance(r, dict):
                ts = r.get("ts", "")
                dev_id = r.get("device_id", "")
                temp = r.get("temp", "")
                hum = r.get("hum", "")
                light = r.get("light", "")
            else:
                # tuple/list fallback: (ts, dev_id, temp, hum, [light])
                ts, dev_id, temp, hum = r[0], r[1], r[2], r[3]
                light = r[4] if len(r) > 4 else ""

            temp_str = f"{temp:.1f}" if isinstance(temp, (int, float)) else (str(temp) if temp is not None else "")
            hum_str = f"{hum:.1f}" if isinstance(hum, (int, float)) else (str(hum) if hum is not None else "")
            light_str = f"{light:.1f}" if isinstance(light, (int, float)) else (str(light) if light is not None else "")
            file_handle.write(f"{ts},{dev_id},{temp_str},{hum_str},{light_str}\n")
        file_handle.flush()

    def flush_buffers(self, buffers, date_str):
        """Mounts SD, writes rows to the unified daily file <date_str>.csv, and unmounts.

        buffers can be:
        - A list of row dicts/tuples (already sorted)
        - A dict {device_id: [rows]}
        Returns True on success, or raises Exception on failure.
        """
        self.mount()
        try:
            if isinstance(buffers, list):
                rows_to_write = buffers
            elif isinstance(buffers, dict):
                rows_to_write = []
                for device_id, rows in buffers.items():
                    for r in rows:
                        if isinstance(r, dict) and "device_id" not in r:
                            r_copy = dict(r)
                            r_copy["device_id"] = device_id
                            rows_to_write.append(r_copy)
                        else:
                            rows_to_write.append(r)
                rows_to_write.sort(key=lambda r: (r.get("ts", "") if isinstance(r, dict) else r[0], r.get("device_id", "") if isinstance(r, dict) else r[1]))
            else:
                rows_to_write = []

            if rows_to_write:
                f = self.open_daily_file(date_str)
                try:
                    self.write_rows(f, rows_to_write)
                finally:
                    f.close()
            return True
        finally:
            self.unmount()
