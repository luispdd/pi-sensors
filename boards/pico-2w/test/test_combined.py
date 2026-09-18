"""
test_combined.py — Shared SPI0 bus validation for pi-screen-camera
===================================================================
Covers tasks 4.1 and 4.2:
  4.1  TFT → SD → TFT single cycle: green fill, write file, blue fill
       Verifies no display corruption and file is readable after bus switch.
  4.2  TFT → SD → TFT repeated 5 times in a loop.
       Verifies bus stability across multiple transitions.

PREREQUISITE — sdcard must be installed at /lib/sdcard.py.
  Via mip (Pico W): import mip; mip.install('sdcard')

Run from the Pico REPL or Thonny after uploading src/ to the board root (/):
    exec(open('/test/test_combined.py').read())

Or with mpremote:
    mpremote run src/test/test_combined.py

Expected output on success:
    --- Combined SPI bus validation ---

    [4.1] Cycle 1/1
      TFT: green fill ... OK
      SD:  writing /sd/combined.txt ... OK
      SD:  reading back ... OK
      TFT: blue fill ... OK

    [PASS] 4.1  Single TFT->SD->TFT cycle complete, no contention

    [4.2] Running 5 cycles...
      Cycle 1/5 ... OK
      Cycle 2/5 ... OK
      Cycle 3/5 ... OK
      Cycle 4/5 ... OK
      Cycle 5/5 ... OK

    [PASS] 4.2  5 cycles complete, bus stable, file readable throughout
    All combined bus tests passed.

SPI bus arbitration rules enforced here (spec: hardware/spi-bus):
  - Only one CS active at a time (TFT_CS XOR SD_CS LOW)
  - Speed set to SPI_SPEED_TFT before TFT access
  - Speed set to SPI_SPEED_SD_DATA after SD init
  - TFT_CS HIGH during all SD transactions
  - SD_CS HIGH during all TFT transactions
"""

import sys
import os
import time

# ── path setup ───────────────────────────────────────────────────────────────
# Ensure root (/) and src/ are in sys.path so config.py and lib/ are importable
for p in ('', '/', '/lib', '..', 'src', '/src', 'src/lib', '/src/lib'):
    if p not in sys.path:
        sys.path.insert(0, p)

from machine import SPI, Pin
from settings import config
import sdcard
from ST7735 import TFT
from sysfont import sysfont

# ── helpers ──────────────────────────────────────────────────────────────────

def _pass(task, msg):
    print(f'\n[PASS] {task}  {msg}')

def _fail(task, msg, exc=None):
    print(f'\n[FAIL] {task}  {msg}')
    if exc:
        print(f'       {type(exc).__name__}: {exc}')
    sys.exit(1)

# ── shared hardware init ─────────────────────────────────────────────────────
# Both CS pins start HIGH (idle) — spec: spi-bus / both CS lines idle high

tft_cs_pin = Pin(config.TFT_CS, Pin.OUT, value=1)
sd_cs_pin  = Pin(config.SD_CS,  Pin.OUT, value=1)

# Single SPI0 instance — speed will be switched per device
spi = SPI(
    config.SPI_BUS,
    baudrate=config.SPI_SPEED_TFT,
    polarity=0,
    phase=0,
    sck=Pin(config.SPI_SCK),
    mosi=Pin(config.SPI_MOSI),
    miso=Pin(config.SPI_MISO),
)

# ── bus-switch helpers ───────────────────────────────────────────────────────

def use_tft():
    """Switch SPI0 to TFT speed. SD_CS stays HIGH. TFT driver owns CS."""
    sd_cs_pin(1)                              # deassert SD first
    spi.init(baudrate=config.SPI_SPEED_TFT)    # spec: spi-bus / TFT speed

def use_sd():
    """Switch SPI0 to SD data speed. TFT_CS stays HIGH. SD owns CS."""
    tft_cs_pin(1)                                # deassert TFT first
    spi.init(baudrate=config.SPI_SPEED_SD_DATA)   # spec: spi-bus / SD data speed

# ── TFT init (once, before cycling) ─────────────────────────────────────────

use_tft()
tft = TFT(spi, config.TFT_DC, config.TFT_RESET, config.TFT_CS)
try:
    tft.initr()
    time.sleep_ms(10)
except Exception as e:
    _fail('setup', 'TFT initr() failed — check wiring', e)

tft.rgb(True)   # RGB mode; change to False and update config.TFT_MADCTL if colors wrong

# ── combined cycle helper ────────────────────────────────────────────────────

COMBINED_PATH    = '/sd/combined.txt'
COMBINED_CONTENT = 'combined test ok\n'

def run_cycle(cycle_num, total):
    """
    One full TFT → SD → TFT arbitration cycle.
    Returns True on success, raises on any failure.
    """
    label = f'  Cycle {cycle_num}/{total}'

    # ── TFT: green fill (SD_CS stays HIGH) ───────────────────────────────
    use_tft()
    print(f'{label} ... ', end='')
    try:
        tft.fill(TFT.GREEN)
    except Exception as e:
        print('FAIL')
        raise RuntimeError(f'TFT green fill failed: {e}') from e

    # ── SD: mount, write, read, unmount (TFT_CS stays HIGH) ──────────────
    use_sd()
    try:
        sd = sdcard.SDCard(spi, sd_cs_pin)
        os.mount(sd, '/sd')
    except Exception as e:
        print('FAIL')
        raise RuntimeError(f'SD mount failed: {e}') from e

    try:
        with open(COMBINED_PATH, 'w') as f:
            f.write(COMBINED_CONTENT)
        with open(COMBINED_PATH, 'r') as f:
            readback = f.read()
        if readback != COMBINED_CONTENT:
            raise ValueError(f'Content mismatch: {repr(readback)}')
    except Exception as e:
        os.umount('/sd')
        print('FAIL')
        raise RuntimeError(f'SD file operation failed: {e}') from e

    try:
        os.umount('/sd')
    except Exception:
        pass  # not fatal

    # ── TFT: blue fill (SD_CS stays HIGH) ────────────────────────────────
    use_tft()
    try:
        tft.fill(TFT.BLUE)
    except Exception as e:
        print('FAIL')
        raise RuntimeError(f'TFT blue fill failed: {e}') from e

    print('OK')
    return True

# ── task 4.1 — single TFT → SD → TFT cycle ──────────────────────────────────

print('--- Combined SPI bus validation ---')
print()
print('[4.1] Cycle 1/1')

try:
    run_cycle(1, 1)
    _pass('4.1', 'Single TFT->SD->TFT cycle complete, no contention')
except Exception as e:
    _fail('4.1', str(e))

# ── task 4.2 — 5 repeated cycles ─────────────────────────────────────────────

REPEAT = 5
print()
print(f'[4.2] Running {REPEAT} cycles...')

for i in range(1, REPEAT + 1):
    try:
        run_cycle(i, REPEAT)
    except Exception as e:
        _fail('4.2', f'Failed on cycle {i}/{REPEAT}: {e}')

# Final read to confirm file is still intact after all cycles
use_sd()
try:
    sd = sdcard.SDCard(spi, sd_cs_pin)
    os.mount(sd, '/sd')
    with open(COMBINED_PATH, 'r') as f:
        final = f.read()
    os.umount('/sd')
    if final != COMBINED_CONTENT:
        _fail('4.2', f'Final file read mismatch after {REPEAT} cycles: {repr(final)}')
except Exception as e:
    _fail('4.2', f'Final SD read failed after {REPEAT} cycles', e)

_pass('4.2', f'{REPEAT} cycles complete, bus stable, file readable throughout')

# ── summary ──────────────────────────────────────────────────────────────────

# Leave display showing white text as a visual "tests passed" indicator
use_tft()
tft.fill(TFT.BLACK)
tft.text((4, 4),  'Bus test', TFT.GREEN, sysfont, 1)
tft.text((4, 16), 'PASSED', TFT.GREEN, sysfont, 2)

print()
print('All combined bus tests passed.')
