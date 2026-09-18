"""
test_sd.py — SD card validation script for pi-screen-camera
============================================================
Covers tasks 2.1, 2.2, 2.3:
  2.1  SPI0 init at 400 kHz, SD card mount — no exception
  2.2  os.listdir('/sd') returns a list
  2.3  Write and read back a test file — confirms FAT write/read roundtrip

PREREQUISITE — install the sdcard driver first (confirmed finding: it is NOT
built into MicroPython firmware on the Pico 2 W):

  Option A — via mip over WiFi (Pico W):
    import mip; mip.install('sdcard')
    # installs to /lib/sdcard.py

  Option B — manual upload via Thonny or mpremote:
    URL: https://raw.githubusercontent.com/micropython/micropython-lib/master/micropython/drivers/storage/sdcard/sdcard.py
    Upload to: /lib/sdcard.py

Run from the Pico REPL or Thonny after copying src/ to the board root (/):
    exec(open('/test/test_sd.py').read())

Or run directly with mpremote:
    mpremote run src/test/test_sd.py

Expected output on success:
    [PASS] 2.1  SD card mounted at /sd
    [PASS] 2.2  os.listdir('/sd') -> [...]
    [PASS] 2.3  FAT write/read roundtrip OK
    All SD tests passed.

Troubleshooting:
  - If 2.1 fails with OSError on SDCard init: check wiring (GP22=SD_CS,
    GP16=MISO, GP18=SCK, GP19=MOSI).  If MISO floats, add a 10 kΩ
    pull-up resistor from GP16 to 3V3 and retry.
  - If 2.1 fails at os.mount: ensure SD card is FAT16/FAT32 (not exFAT).
    Cards >32 GB are often exFAT; reformat as FAT32.
  - If 2.3 fails on read: re-check card is not write-protected.
"""

import sys
import os

# ── path setup ──────────────────────────────────────────────────────────────
# Ensure root (/) and src/ are in sys.path so config.py and lib/ are importable
for p in ('', '/', '/lib', '..', 'src', '/src', 'src/lib', '/src/lib'):
    if p not in sys.path:
        sys.path.insert(0, p)

from machine import SPI, Pin
from settings import config

# ── helpers ──────────────────────────────────────────────────────────────────

def _pass(task, msg):
    print(f'[PASS] {task}  {msg}')

def _fail(task, msg, exc=None):
    print(f'[FAIL] {task}  {msg}')
    if exc:
        print(f'       {type(exc).__name__}: {exc}')
    sys.exit(1)

# ── task 2.1 — init SPI0 at 400 kHz, mount SD card ─────────────────────────

print('--- SD card validation ---')

# Hold TFT_CS HIGH throughout all SD tests (spec: spi-bus / CS exclusivity)
tft_cs = Pin(config.TFT_CS, Pin.OUT, value=1)

# SPI0 at ≤400 kHz for card identification phase (spec: sd-card req 1)
spi = SPI(
    config.SPI_BUS,
    baudrate=config.SPI_SPEED_SD_INIT,
    polarity=0,
    phase=0,
    sck=Pin(config.SPI_SCK),
    mosi=Pin(config.SPI_MOSI),
    miso=Pin(config.SPI_MISO),
)

try:
    import sdcard
    sd = sdcard.SDCard(spi, Pin(config.SD_CS))
    os.mount(sd, '/sd')
    _pass('2.1', 'SD card mounted at /sd')
except Exception as e:
    _fail('2.1', 'SD card mount failed — see troubleshooting notes above', e)

# ── task 2.2 — os.listdir('/sd') returns a list ──────────────────────────────

try:
    entries = os.listdir('/sd')
    _pass('2.2', f'os.listdir(\'/sd\') -> {entries}')
except Exception as e:
    _fail(
        '2.2',
        'os.listdir failed — if MISO floats, add 10 kΩ pull-up on GP16 to 3V3',
        e,
    )

# ── task 2.3 — FAT write/read roundtrip ─────────────────────────────────────

TEST_PATH    = '/sd/test.txt'
TEST_CONTENT = 'pi-screen-camera ok\n'

try:
    with open(TEST_PATH, 'w') as f:
        f.write(TEST_CONTENT)
except Exception as e:
    _fail('2.3', f'Write to {TEST_PATH} failed', e)

try:
    with open(TEST_PATH, 'r') as f:
        readback = f.read()
except Exception as e:
    _fail('2.3', f'Read from {TEST_PATH} failed', e)

if readback == TEST_CONTENT:
    _pass('2.3', 'FAT write/read roundtrip OK')
else:
    _fail(
        '2.3',
        f'Content mismatch!\n  wrote:  {repr(TEST_CONTENT)}\n  read:   {repr(readback)}',
    )

# ── summary ──────────────────────────────────────────────────────────────────

# Unmount cleanly so later tests or REPL sessions can re-mount
try:
    os.umount('/sd')
except Exception:
    pass  # not fatal if unmount fails (already unmounted)

print()
print('All SD tests passed.')
