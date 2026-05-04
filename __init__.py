"""LED Name Badge (LSLED) – Home Assistant integration."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime

import voluptuous as vol
from bleak.exc import BleakError
from bleak_retry_connector import (
    BleakClientWithServiceCache,
    establish_connection,
)

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from .const import (
    CHARACTERISTIC_UUID,
    CHUNK_SIZE,
    DEFAULT_BRIGHTNESS,
    DEFAULT_MODE,
    DEFAULT_SPEED,
    DOMAIN,
    SERVICE_SEND,
    VALID_MODES,
)
from .protocol import bitmap_to_bytes, build_header, chunkify
from .renderer import render

_LOGGER = logging.getLogger(__name__)

_MODE_NAMES = {
    "left": 0, "right": 1, "up": 2, "down": 3,
    "fixed": 4, "anim": 5, "drop": 6, "curtain": 7, "laser": 8,
}


def _mode(value):
    """Validator: accept either int or symbolic mode name."""
    if isinstance(value, int):
        if value not in VALID_MODES:
            raise vol.Invalid(f"mode must be one of {VALID_MODES}")
        return value
    if isinstance(value, str) and value.lower() in _MODE_NAMES:
        return _MODE_NAMES[value.lower()]
    raise vol.Invalid(
        "mode must be 0..8 or one of: " + ", ".join(_MODE_NAMES)
    )


MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("text"): cv.string,
        vol.Optional("mode", default=DEFAULT_MODE): _mode,
        vol.Optional("speed", default=DEFAULT_SPEED): vol.All(
            int, vol.Range(min=1, max=8)
        ),
        vol.Optional("blink", default=False): cv.boolean,
        vol.Optional("marquee", default=False): cv.boolean,
    }
)

SEND_SCHEMA = vol.Schema(
    {
        vol.Optional("address"): cv.string,
        vol.Required("messages"): vol.All(
            cv.ensure_list, [MESSAGE_SCHEMA], vol.Length(min=1, max=8)
        ),
        vol.Optional("brightness", default=DEFAULT_BRIGHTNESS): vol.All(
            int, vol.Range(min=1, max=100)
        ),
    }
)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Register a configured badge and (once) the send service."""
    address: str = entry.data[CONF_ADDRESS].upper()
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {"address": address}

    if not hass.services.has_service(DOMAIN, SERVICE_SEND):
        async def _handle_send(call: ServiceCall) -> None:
            target = call.data.get("address")
            if not target:
                if not hass.data.get(DOMAIN):
                    raise HomeAssistantError("No LED badge is configured")
                target = next(iter(hass.data[DOMAIN].values()))["address"]

            await _send_to_badge(
                hass,
                target.upper(),
                call.data["messages"],
                call.data["brightness"],
            )

        hass.services.async_register(
            DOMAIN, SERVICE_SEND, _handle_send, schema=SEND_SCHEMA
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Drop a config entry; deregister the service if it was the last one."""
    hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if not hass.data.get(DOMAIN):
        hass.services.async_remove(DOMAIN, SERVICE_SEND)
    return True


async def _send_to_badge(
    hass: HomeAssistant,
    address: str,
    messages: list[dict],
    brightness: int,
) -> None:
    """Render messages and write them to the badge.

    The badge must currently be in BT-transfer mode (top button pressed twice
    until the BT icon appears on the display) — otherwise it does not
    advertise and we cannot connect.
    """
    # Render all messages; encode each into byte-columns
    bitmaps = [render(m["text"]) for m in messages]
    encoded: list[bytes] = []
    lengths: list[int] = []
    for rows in bitmaps:
        data, n_cols = bitmap_to_bytes(rows)
        encoded.append(data)
        lengths.append(n_cols)

    header = build_header(
        lengths=lengths,
        speeds=[m["speed"] for m in messages],
        modes=[m["mode"] for m in messages],
        blinks=[m["blink"] for m in messages],
        marquees=[m["marquee"] for m in messages],
        brightness=brightness,
        timestamp=datetime.now(),
    )
    payload = header + b"".join(encoded)
    chunks = list(chunkify(payload, CHUNK_SIZE))
    _LOGGER.debug(
        "led_badge[%s]: %d B payload → %d chunks",
        address, len(payload), len(chunks),
    )

    # Resolve via HA Bluetooth stack — works through ESPHome BT proxies, too,
    # provided the proxy runs in active mode.
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    if ble_device is None:
        raise HomeAssistantError(
            f"Badge {address} is not advertising. Press the top button on "
            f"the badge twice to enable Bluetooth transfer mode, then retry."
        )

    try:
        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            f"led_badge[{address}]",
            max_attempts=3,
        )
    except (BleakError, asyncio.TimeoutError) as err:
        raise HomeAssistantError(f"Could not connect to badge: {err}") from err

    try:
        for chunk in chunks:
            await client.write_gatt_char(
                CHARACTERISTIC_UUID, chunk, response=False
            )
        # Some firmware variants need a moment before disconnect, otherwise
        # the last chunk may be dropped.
        await asyncio.sleep(0.2)
    except BleakError as err:
        raise HomeAssistantError(f"BLE write failed: {err}") from err
    finally:
        try:
            await client.disconnect()
        except BleakError:
            pass
