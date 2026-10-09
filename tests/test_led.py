from unittest.mock import AsyncMock, MagicMock, patch
import pytest
from homeassistant.exceptions import ServiceValidationError, HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry
from custom_components.led_badge.const import DOMAIN
from custom_components.led_badge.renderer import render
from custom_components.led_badge.protocol import build_header

def show(rows):
    return "\n".join("".join("#" if p else "." for p in r) for r in rows)

async def _setup(hass, addr="AA:BB:CC:DD:EE:01"):
    hass.config.components.add("bluetooth")
    entry = MockConfigEntry(domain=DOMAIN, data={"address": addr}, unique_id=addr)
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry

async def test_send(hass):
    await _setup(hass)
    assert hass.services.has_service(DOMAIN, "send")
    client = MagicMock(); client.write_gatt_char = AsyncMock(); client.disconnect = AsyncMock()
    with patch("custom_components.led_badge.bluetooth.async_ble_device_from_address", return_value=object()), \
         patch("custom_components.led_badge.establish_connection", AsyncMock(return_value=client)), \
         patch("custom_components.led_badge.asyncio.sleep", AsyncMock()):
        await hass.services.async_call(DOMAIN, "send", {
            "brightness": "25",
            "messages": [{"text": "Hi :heart: Welt", "mode": "fixed", "speed": "5", "blink": True},
                         {"text": ":wifi: Äöü", "mode": 1}]}, blocking=True)
    chunks = [c.args[1] for c in client.write_gatt_char.call_args_list]
    payload = b"".join(chunks)
    assert payload[:4] == b"wang"
    assert payload[5] == 0x40
    assert payload[6] == 0b01
    assert payload[8] == (4 << 4) | 4
    assert payload[9] == (3 << 4) | 1
    client.disconnect.assert_awaited()

async def test_too_long(hass):
    await _setup(hass)
    with patch("custom_components.led_badge.bluetooth.async_ble_device_from_address", return_value=object()):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(DOMAIN, "send", {"messages": [{"text": "X" * 2000}]}, blocking=True)

async def test_not_advertising(hass):
    await _setup(hass)
    with patch("custom_components.led_badge.bluetooth.async_ble_device_from_address", return_value=None):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(DOMAIN, "send", {"messages": [{"text": "x"}]}, blocking=True)

async def test_multiple_needs_address(hass):
    await _setup(hass, "AA:BB:CC:DD:EE:01")
    e2 = MockConfigEntry(domain=DOMAIN, data={"address": "AA:BB:CC:DD:EE:02"}, unique_id="AA:BB:CC:DD:EE:02")
    e2.add_to_hass(hass); assert await hass.config_entries.async_setup(e2.entry_id)
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(DOMAIN, "send", {"messages": [{"text": "x"}]}, blocking=True)

async def test_unload_keeps_service(hass):
    entry = await _setup(hass)
    assert await hass.config_entries.async_unload(entry.entry_id)
    assert hass.services.has_service(DOMAIN, "send")

async def test_render(tmp_path):
    for t in ["Hi :heart: Welt", "Dennis :wifi:", "Typ gj Äpfel", ":nope: x", "", "   "]:
        rows = render(t, str(tmp_path))
        assert len(rows) == 11 and len({len(r) for r in rows}) == 1
        print(repr(t)); print(show(rows))

async def test_user_icon(tmp_path):
    from PIL import Image
    d = tmp_path / "led_badge_icons"; d.mkdir()
    img = Image.new("RGBA", (20, 22), (255, 255, 255, 0))
    for x in range(20):
        for y in range(22):
            if (x + y) % 7 == 0: img.putpixel((x, y), (255, 255, 255, 255))
    img.save(d / "diag.png")
    rows = render(":diag:", str(tmp_path))
    print(show(rows))
    assert len(rows[0]) == 1 + 10 + 1

async def test_brightness_levels():
    assert [build_header([1],[4],[0],[0],[0],b)[5] for b in (100, 75, 50, 25, 1)] == [0, 0x10, 0x20, 0x40, 0x40]
