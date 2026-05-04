"""Constants for the LED Badge integration."""
from __future__ import annotations

DOMAIN = "led_badge"

# BLE Service & Characteristic UUIDs of the LSLED badge
SERVICE_UUID = "0000fee0-0000-1000-8000-00805f9b34fb"
CHARACTERISTIC_UUID = "0000fee1-0000-1000-8000-00805f9b34fb"

# Display geometry (LSLED 11x44)
DISPLAY_HEIGHT = 11
DISPLAY_WIDTH = 44
CHUNK_SIZE = 16  # BLE writes are 16-byte chunks

# Service names
SERVICE_SEND = "send"

# Animation modes (matching the reverse-engineered firmware protocol)
MODE_LEFT = 0     # scroll left  – use this for long text
MODE_RIGHT = 1
MODE_UP = 2
MODE_DOWN = 3
MODE_FIXED = 4    # static, no animation
MODE_ANIM = 5
MODE_DROP = 6
MODE_CURTAIN = 7
MODE_LASER = 8

VALID_MODES = list(range(9))

DEFAULT_MODE = MODE_LEFT
DEFAULT_SPEED = 4
DEFAULT_BRIGHTNESS = 100
