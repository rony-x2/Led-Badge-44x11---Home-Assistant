from unittest.mock import patch, MagicMock
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from custom_components.led_badge.const import DOMAIN

def info(addr, name):
    m = MagicMock(); m.address = addr; m.name = name; return m

async def test_user_flow(hass):
    hass.config.components.add("bluetooth")
    with patch("custom_components.led_badge.config_flow.async_discovered_service_info", return_value=[info("AA:BB:CC:DD:EE:01","LSLED"), info("11:22:33:44:55:66","Other")]):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
        assert r["type"] is FlowResultType.FORM
        r = await hass.config_entries.flow.async_configure(r["flow_id"], {"address": "AA:BB:CC:DD:EE:01"})
    assert r["type"] is FlowResultType.CREATE_ENTRY and r["data"] == {"address": "AA:BB:CC:DD:EE:01"}

async def test_user_flow_none(hass):
    hass.config.components.add("bluetooth")
    with patch("custom_components.led_badge.config_flow.async_discovered_service_info", return_value=[]):
        r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert r["type"] is FlowResultType.ABORT and r["reason"] == "no_devices_found"

async def test_bt_flow(hass):
    hass.config.components.add("bluetooth")
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_BLUETOOTH}, data=info("AA:BB:CC:DD:EE:02","LSLED"))
    assert r["type"] is FlowResultType.FORM and r["step_id"] == "bluetooth_confirm"
    r = await hass.config_entries.flow.async_configure(r["flow_id"], {})
    assert r["type"] is FlowResultType.CREATE_ENTRY
