"""
test_tft.py — TFT display validation script for pi-screen-camera
=================================================================
Covers tasks 3.1, 3.2, 3.3:
  3.1  SPI0 init at 20 MHz, ST7735 initr() — no exception
  3.2  fill(RED) — screen goes solid red; MADCTL/colour order check
  3.3  fill(BLACK) then text "Hello Pico!" at (10,10) in white

Run from the Pico REPL or Thonny after copying src/ to the board root (/):
    exec(open('/test/test_tft.py').read())

Or with mpremote:
    mpremote run src/test/test_tft.py

Expected output on success:
    [PASS] 3.1  TFT init OK (no exception during initr)
    >>> Look at the screen: it should be solid RED. <<<
    Press Enter when ready (or Ctrl-C to abort)...
    [PASS] 3.2  fill(RED) sent — confirmed by you
    [PASS] 3.3  Text "Hello Pico!" rendered at (10,10)
    All TFT tests passed.

Troubleshooting:
  3.1 blank / no response:
    - Verify RESET (GP21), DC (GP20), TFT_CS (GP17) wiring.
    - The driver's _reset() uses 500us pulses; some modules need longer.
      If blank: add time.sleep_ms(120) after initr() and retry.
  3.2 wrong colour (e.g. blue instead of red):
    - The MADCTL byte controls RGB vs BGR.  Try tft.rgb(False) for BGR.
    - Update config.TFT_MADCTL in src/config.py with the confirmed value.
  3.2 image shifted (garbage strip on one edge):
    - Set offset: tft._offset[0] = 2; tft._offset[1] = 1
    - Use initb2() instead of initr() if using a blue-tab module.
    - Update config.py with confirmed colstart/rowstart values.
  3.3 text invisible: ensure foreground != background colour.
"""

import sys
import time

# ── path setup ───────────────────────────────────────────────────────────────
# Ensure root (/) and src/ are in sys.path so config.py and lib/ are importable
for p in ('', '/', '/lib', '..', 'src', '/src', 'src/lib', '/src/lib'):
    if p not in sys.path:
        sys.path.insert(0, p)

from machine import SPI, Pin
from settings import config
from ST7735 import TFT, TFTBGR, TFTRGB
from sysfont import sysfont

# ── helpers ──────────────────────────────────────────────────────────────────

def _pass(task, msg):
    print(f'[PASS] {task}  {msg}')

def _fail(task, msg, exc=None):
    print(f'[FAIL] {task}  {msg}')
    if exc:
        print(f'       {type(exc).__name__}: {exc}')
    sys.exit(1)

def _prompt(msg):
    """Pause for user visual confirmation.  Ctrl-C aborts."""
    print(f'\n>>> {msg} <<<')
    try:
        input('Press Enter when ready (or Ctrl-C to abort)...')
    except KeyboardInterrupt:
        print('\nAborted.')
        sys.exit(1)

# ── task 3.1 — init SPI0 at 20 MHz, apply RESET, call initr() ───────────────

print('--- TFT display validation ---')

# Hold SD_CS HIGH throughout all TFT tests (spec: spi-bus / CS exclusivity)
sd_cs = Pin(config.SD_CS, Pin.OUT, value=1)

# SPI0 at 20 MHz for TFT pixel writes (spec: spi-bus / per-device speed)
spi = SPI(
    config.SPI_BUS,
    baudrate=config.SPI_SPEED_TFT,
    polarity=0,
    phase=0,
    sck=Pin(config.SPI_SCK),
    mosi=Pin(config.SPI_MOSI),
    miso=Pin(config.SPI_MISO),
)

# Note: the TFT constructor takes GPIO *numbers*, not Pin objects.
# It creates the DC, RESET, and CS pins internally.
# The RESET pulse (≥10 ms, spec: tft-display req 1) is applied inside
# initr() via _reset().  We add an extra 10 ms sleep after init to be safe
# with modules that need a longer settle time.
try:
    tft = TFT(spi, config.TFT_DC, config.TFT_RESET, config.TFT_CS)
    tft.initr()                 # applies RESET + full register init sequence
    time.sleep_ms(10)           # safety settle for slow modules
    _pass('3.1', 'TFT init OK (no exception during initr)')
except Exception as e:
    _fail('3.1', 'initr() raised an exception — check wiring (DC, RESET, CS)', e)

# ── task 3.2 — fill screen RED, ask user to visually confirm ─────────────────

# Start with RGB mode (matches TFT.RED = 0xF800 RGB565 definition).
# If the screen shows blue instead of red, change to tft.rgb(False) and
# update config.TFT_MADCTL = 0x08 (TFTBGR) in src/config.py.
tft.rgb(True)   # True = RGB (config.TFT_MADCTL placeholder = 0x00)

try:
    RED = TFT.RED   # 0xF800 in RGB565 — pure red
    tft.fill(RED)
except Exception as e:
    _fail('3.2', 'fill(RED) raised an exception', e)

_prompt(
    'Look at the screen: it should be solid RED.\n'
    '  - If BLUE: run tft.rgb(False) and update config.TFT_MADCTL = 0x08\n'
    '  - If shifted: set tft._offset[0]=2; tft._offset[1]=1 and re-run fill'
)
_pass('3.2', 'fill(RED) sent — confirmed by you')

# ── task 3.3 — fill BLACK, render text "Hello Pico!" at (10,10) in WHITE ────

try:
    tft.fill(TFT.BLACK)
    time.sleep_ms(50)

    # text(pos, string, color, font, size=1)
    # pos is (x, y); WHITE = TFT.WHITE (0xFFFF in RGB565)
    tft.text((10, 10), 'Hello Pico!', TFT.WHITE, sysfont, 1)

except Exception as e:
    _fail('3.3', 'text() raised an exception', e)

_prompt(
    'Screen should be BLACK with "Hello Pico!" in WHITE at top-left.\n'
    '  - If shifted: set tft._offset[0]=2; tft._offset[1]=1, re-run test\n'
    '  - If invisible: check colour values (WHITE=0xFFFF, BLACK=0x0000)'
)
_pass('3.3', 'Text "Hello Pico!" rendered at (10,10)')

# ── summary ──────────────────────────────────────────────────────────────────

print()
print('All TFT tests passed.')
print()
print('ACTION REQUIRED: Update src/config.py with confirmed values:')
print('  TFT_MADCTL = 0x00  # RGB (or 0x08 if BGR swap was needed)')
print('  # colstart/rowstart offset: set tft._offset if image was shifted')
