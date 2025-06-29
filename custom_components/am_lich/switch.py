"""
Dummy switch platform file for amlich custom component.
This file is required so Home Assistant can import the 'switch' platform.
All switch logic is handled in sensor.py.
"""

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
import logging
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class AmlichUseHumorSwitch(SwitchEntity):
    """Switch use_humor tự động, đúng chuẩn switch Home Assistant."""
    def __init__(self, hass: HomeAssistant):
        _LOGGER.debug("[DEBUG] Khởi tạo AmlichUseHumorSwitch")
        self._hass = hass
        self._attr_name = "Use Humor"
        self._attr_unique_id = "use_humor"
        self._attr_should_poll = False
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "amlich_events")},
            "name": "Âm lịch VN",
            "manufacturer": "amlich",
            "model": "Sự kiện Âm/Dương lịch"
        }
        self._state = False
        _LOGGER.debug(f"[DEBUG] AmlichUseHumorSwitch unique_id: {self._attr_unique_id}, device_info: {self._attr_device_info}")

    @property
    def is_on(self):
        _LOGGER.debug(f"[DEBUG] is_on called, state: {self._state}")
        return self._state

    async def async_added_to_hass(self):
        _LOGGER.debug("[DEBUG] AmlichUseHumorSwitch đã được thêm vào Home Assistant")

    async def async_turn_on(self, **kwargs):
        _LOGGER.debug("[DEBUG] async_turn_on called")
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        _LOGGER.debug("[DEBUG] async_turn_off called")
        self._state = False
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        return {}

def get_switch_entities(hass):
    return [AmlichUseHumorSwitch(hass)]

async def async_setup_entry(hass, config_entry, async_add_entities):
    _LOGGER.debug("[DEBUG] Bắt đầu async_setup_entry cho switch amlich")
    switches = get_switch_entities(hass)
    async_add_entities(switches, True)
    _LOGGER.debug("[DEBUG] Đã gọi xong async_add_entities cho switch")
