"""
test_sd_to_tft.py — SD card file browser displayed on TFT
==========================================================
Task 4.3 integration test: mount SD, read root directory, unmount SD,
then display results on the TFT screen. All SD activity completes before
any TFT rendering begins — the two devices never share the bus concurrently.

Display behaviour:
  - SD mounted OK + files found  -> list filenames, one per line
  - SD mounted OK + empty root   -> centred "Empty card" message in yellow
  - SD mount failed               -> "SD Error" header + short reason in red

The 128x160 screen at font size 1 (5x8 px glyphs, +1 px spacing = 6px wide,
9px tall) fits:
  - 21 characters per line  (128 / 6 = 21.3)
  - 17 lines                (160 / 9 = 17.7)

If more than 17 entries exist, the list is truncated and a scroll indicator
"(+N more)" is shown on the last line.

PREREQUISITE — sdcard must be installed at /lib/sdcard.py.
  Via mip (Pico W): import mip; mip.install('sdcard')

Run from Thonny or mpremote (after copying src/ to the board root /):
    exec(open('/test/test_sd_to_tft.py').read())
    mpremote run src/test/test_sd_to_tft.py
"""

import sys
import os
import time

# ── path setup ───────────────────────────────────────────────────────────────
# Ensure root (/) and src/ are in sys.path so config.py and lib/ are importable
for p in ('', '/', '/lib', '..', 'src', '/src', 'src/lib', '/src/lib'):
    if p not in sys.path:
        sys.path.insert(0, p)

try:
    from machine import SPI, Pin
except ImportError:
    import unittest
    raise unittest.SkipTest("MicroPython hardware test (skipped on host)")
from settings import config
import sdcard
from ST7735 import TFT
from sysfont import sysfont

# ── display layout constants ─────────────────────────────────────────────────
FONT_W      = sysfont['Width']   # 5 px
FONT_H      = sysfont['Height']  # 8 px
CHAR_W      = FONT_W + 1         # 6 px (driver adds 1 px spacing between chars)
LINE_H      = FONT_H + 1         # 9 px (1 px gap between lines)
MAX_CHARS   = config.TFT_WIDTH  // CHAR_W   # 21 chars
MAX_LINES   = config.TFT_HEIGHT // LINE_H   # 17 lines
HEADER_LINES = 1                          # one header line at top

# ── shared hardware init (both CS idle HIGH) ─────────────────────────────────
tft_cs_pin = Pin(config.TFT_CS, Pin.OUT, value=1)
sd_cs_pin  = Pin(config.SD_CS,  Pin.OUT, value=1)

spi = SPI(
    config.SPI_BUS,
    baudrate=config.SPI_SPEED_SD_INIT,   # start slow for SD init
    polarity=0,
    phase=0,
    sck=Pin(config.SPI_SCK),
    mosi=Pin(config.SPI_MOSI),
    miso=Pin(config.SPI_MISO),
)

# ── helpers ──────────────────────────────────────────────────────────────────

def truncate(name, max_chars):
    """Truncate a filename to fit within max_chars, adding '>' if cut."""
    if len(name) <= max_chars:
        return name
    return name[:max_chars - 1] + '>'

def tft_println(tft, row, text, color):
    """Render one line of text at the given row index (0-based)."""
    y = row * LINE_H
    tft.text((0, y), text, color, sysfont, 1)

# ── phase 1: SD — mount, read, unmount (TFT untouched) ──────────────────────
# TFT_CS stays HIGH the entire time (spec: spi-bus / CS exclusivity)

print('Mounting SD card...')
sd_entries  = None   # list[str] on success, None on error
sd_error    = None   # str on failure

tft_cs_pin(1)        # assert TFT idle
spi.init(baudrate=config.SPI_SPEED_SD_INIT)

try:
    sd = sdcard.SDCard(spi, sd_cs_pin)
    os.mount(sd, '/sd')

    # Switch to higher speed after init for the directory read
    spi.init(baudrate=config.SPI_SPEED_SD_DATA)

    sd_entries = os.listdir('/sd')

    try:
        os.umount('/sd')
    except Exception:
        pass   # unmount failure is non-fatal — data already captured

    print(f'SD OK: {len(sd_entries)} entries')

except Exception as e:
    sd_error = str(e)[:MAX_CHARS]   # truncate to fit on screen
    print(f'SD error: {e}')
    try:
        os.umount('/sd')
    except Exception:
        pass

# ── phase 2: TFT — render results (SD untouched) ────────────────────────────
# SD_CS stays HIGH the entire time (spec: spi-bus / CS exclusivity)

sd_cs_pin(1)         # assert SD idle
spi.init(baudrate=config.SPI_SPEED_TFT)

tft = TFT(spi, config.TFT_DC, config.TFT_RESET, config.TFT_CS)
tft.initr()
time.sleep_ms(10)
tft.rgb(True)        # RGB mode; flip to False + update config.TFT_MADCTL if colours wrong

tft.fill(TFT.BLACK)

if sd_error is not None:
    # ── error state ──────────────────────────────────────────────────────────
    tft_println(tft, 0, 'SD Error', TFT.RED)
    # Split error into MAX_CHARS chunks across remaining lines
    err_full = sd_error
    row = 1
    while err_full and row < MAX_LINES:
        tft_println(tft, row, err_full[:MAX_CHARS], TFT.RED)
        err_full = err_full[MAX_CHARS:]
        row += 1

elif len(sd_entries) == 0:
    # ── empty card ───────────────────────────────────────────────────────────
    # Centre "Empty card" vertically and horizontally
    msg   = 'Empty card'
    msg_x = (config.TFT_WIDTH - len(msg) * CHAR_W) // 2
    msg_y = (config.TFT_HEIGHT // 2) - (LINE_H // 2)
    tft.text((msg_x, msg_y), msg, TFT.YELLOW, sysfont, 1)

else:
    # ── file listing ─────────────────────────────────────────────────────────
    # Header
    header = 'SD Files'
    tft_println(tft, 0, header, TFT.CYAN)

    # Draw a thin separator line under the header
    tft.hline((0, LINE_H - 1), config.TFT_WIDTH, TFT.CYAN)

    available_lines = MAX_LINES - HEADER_LINES
    entries_to_show = sd_entries[:available_lines]
    overflow        = len(sd_entries) - len(entries_to_show)

    # Reserve last line for overflow indicator if needed
    if overflow > 0:
        entries_to_show = sd_entries[:available_lines - 1]
        overflow        = len(sd_entries) - len(entries_to_show)

    for i, name in enumerate(entries_to_show):
        row   = HEADER_LINES + i
        color = TFT.WHITE
        tft_println(tft, row, truncate(name, MAX_CHARS), color)

    if overflow > 0:
        last_row = HEADER_LINES + len(entries_to_show)
        indicator = truncate(f'(+{overflow} more)', MAX_CHARS)
        tft_println(tft, last_row, indicator, TFT.GRAY)

print('Display updated.')
