"""LED Name Badge (LSLED) – Home Assistant integration."""
from __future__ import annotations

import asyncio
from datetime import datetime
import logging
from typing import Any

from bleak.exc import BleakError
from bleak_retry_connector import BleakClientWithServiceCache, establish_connection
import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import dt as dt_util

from .const import (
    CHARACTERISTIC_UUID,
    CHUNK_SIZE,
    DEFAULT_BRIGHTNESS,
    DEFAULT_MODE,
    DEFAULT_SPEED,
    DISPLAY_HEIGHT,
    DOMAIN,
    MODE_NAMES,
    SERVICE_SEND,
    VALID_MODES,
)
from .protocol import (
    HEADER_SIZE,
    MAX_PAYLOAD_BYTES,
    bitmap_to_bytes,
    build_header,
    chunkify,
)
from .renderer import render

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)

DATA_ADDRESSES = "addresses"
DATA_LOCKS = "locks"


def _mode(value: Any) -> int:
    """Validator: accept an int, a numeric string or a symbolic mode name."""
    if isinstance(value, str):
        value = value.strip().lower()
        if value in MODE_NAMES:
            return MODE_NAMES[value]
        if value.isdigit():
            value = int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        if value not in VALID_MODES:
            raise vol.Invalid(f"mode must be one of {VALID_MODES}")
        return value
    raise vol.Invalid("mode must be 0..8 or one of: " + ", ".join(MODE_NAMES))


MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("text"): cv.string,
        vol.Optional("mode", default=DEFAULT_MODE): _mode,
        vol.Optional("speed", default=DEFAULT_SPEED): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=8)
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
            vol.Coerce(int), vol.Range(min=1, max=100)
        ),
    }
)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the send action once for the whole integration."""
    hass.data.setdefault(DOMAIN, {DATA_ADDRESSES: {}, DATA_LOCKS: {}})

    async def _handle_send(call: ServiceCall) -> None:
        addresses: dict[str, str] = hass.data[DOMAIN][DATA_ADDRESSES]
        target = call.data.get("address")
        if target:
            target = target.strip().upper()
        elif not addresses:
            raise ServiceValidationError("No LED badge is configured")
        elif len(set(addresses.values())) > 1:
            raise ServiceValidationError(
                "Several LED badges are configured, please set 'address' to "
                "one of: " + ", ".join(sorted(set(addresses.values())))
            )
        else:
            target = next(iter(addresses.values()))

        lock = hass.data[DOMAIN][DATA_LOCKS].setdefault(target, asyncio.Lock())
        async with lock:
            await _send_to_badge(
                hass, target, call.data["messages"], call.data["brightness"]
            )

    hass.services.async_register(
        DOMAIN, SERVICE_SEND, _handle_send, schema=SEND_SCHEMA
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Remember the address of a configured badge."""
    hass.data[DOMAIN][DATA_ADDRESSES][entry.entry_id] = entry.data[
        CONF_ADDRESS
    ].upper()
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Forget a configured badge."""
    hass.data[DOMAIN][DATA_ADDRESSES].pop(entry.entry_id, None)
    return True


def _build_payload(
    messages: list[dict[str, Any]],
    brightness: int,
    timestamp: datetime,
    config_dir: str,
) -> bytes:
    """Render all messages and build the complete payload (runs in executor)."""
    encoded: list[bytes] = []
    lengths: list[int] = []
    for message in messages:
        data, n_cols = bitmap_to_bytes(render(message["text"], config_dir))
        encoded.append(data)
        lengths.append(n_cols)

    header = build_header(
        lengths=lengths,
        speeds=[m["speed"] for m in messages],
        modes=[m["mode"] for m in messages],
        blinks=[m["blink"] for m in messages],
        marquees=[m["marquee"] for m in messages],
        brightness=brightness,
        timestamp=timestamp,
    )
    return header + b"".join(encoded)


async def _send_to_badge(
    hass: HomeAssistant,
    address: str,
    messages: list[dict[str, Any]],
    brightness: int,
) -> None:
    """Render messages and write them to the badge.

    The badge must currently be in BT-transfer mode (top button pressed twice
    until the BT icon appears on the display), otherwise it does not
    advertise and we cannot connect.
    """
    # Rendering loads fonts and icon files from disk -> executor
    payload = await hass.async_add_executor_job(
        _build_payload,
        messages,
        brightness,
        dt_util.now(),
        hass.config.config_dir,
    )
    if len(payload) > MAX_PAYLOAD_BYTES:
        max_cols = (MAX_PAYLOAD_BYTES - HEADER_SIZE) // DISPLAY_HEIGHT
        used_cols = (len(payload) - HEADER_SIZE) // DISPLAY_HEIGHT
        raise ServiceValidationError(
            f"The messages are too long for the badge ({used_cols * 8} px "
            f"wide, the badge stores at most about {max_cols * 8} px). "
            "Please shorten the text."
        )

    chunks = list(chunkify(payload, CHUNK_SIZE))
    _LOGGER.debug(
        "led_badge[%s]: %d B payload -> %d chunks",
        address,
        len(payload),
        len(chunks),
    )

    # Resolve via HA Bluetooth stack - works through ESPHome BT proxies, too,
    # provided the proxy runs in active mode.
    ble_device = bluetooth.async_ble_device_from_address(
        hass, address, connectable=True
    )
    if ble_device is None:
        raise HomeAssistantError(
            f"Badge {address} is not advertising. Press the top button on "
            "the badge twice to enable Bluetooth transfer mode, then retry."
        )

    try:
        client = await establish_connection(
            BleakClientWithServiceCache,
            ble_device,
            f"led_badge[{address}]",
            max_attempts=3,
        )
    except (BleakError, TimeoutError) as err:
        raise HomeAssistantError(f"Could not connect to badge: {err}") from err

    try:
        for chunk in chunks:
            await client.write_gatt_char(CHARACTERISTIC_UUID, chunk, response=False)
        # Some firmware variants need a moment before disconnect, otherwise
        # the last chunk may be dropped.
        await asyncio.sleep(0.2)
    except (BleakError, TimeoutError) as err:
        raise HomeAssistantError(f"BLE write failed: {err}") from err
    finally:
        try:
            await client.disconnect()
        except (BleakError, TimeoutError):
            pass
