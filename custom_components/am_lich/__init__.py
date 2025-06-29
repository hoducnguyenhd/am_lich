import os
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.const import CONF_PATH
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
from homeassistant.helpers.event import async_track_time_change  # noqa
from homeassistant.core import callback  # noqa
import logging
import traceback
import asyncio
from .const import AMLICH_ICS_PATH

_LOGGER = logging.getLogger(__name__)

DOMAIN = "amlich"

CONFIG_SCHEMA = vol.Schema({
    vol.Required(DOMAIN): vol.Schema({
        vol.Optional('api_key', default=""): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    _LOGGER.debug("[amlich] Bắt đầu async_setup")
    try:
        # Không lấy ics_path từ config nữa, dùng const
        api_key = config[DOMAIN].get('api_key') if DOMAIN in config else None
        ics_path = AMLICH_ICS_PATH
        _LOGGER.debug(
            f"Cấu hình: ics_path={ics_path}, api_key={'****' if api_key else 'None'}"
        )

        # Kiểm tra đường dẫn ICS
        if not ics_path:
            _LOGGER.error("Đường dẫn ICS không được cung cấp")
            return False

        # Kiểm tra file tồn tại và quyền (chạy trong executor)
        def check_file():
            try:
                if not os.path.exists(ics_path):
                    _LOGGER.error(f"File ICS không tồn tại: {ics_path}")
                    return False
                if not os.path.isfile(ics_path):
                    _LOGGER.error(f"Đường dẫn ICS không phải file: {ics_path}")
                    return False
                with open(ics_path, 'r', encoding='utf-8') as f:
                    content = f.read(1024)
                    if not content.strip():
                        _LOGGER.error(f"File ICS rỗng: {ics_path}")
                        return False
                size = os.path.getsize(ics_path)
                _LOGGER.debug(
                    f"File ICS {ics_path} có thể đọc, kích thước: {size} bytes"
                )
                return True
            except Exception as e:
                _LOGGER.error(
                    f"Lỗi khi kiểm tra file ICS {ics_path}: {str(e)}"
                )
                return False

        if not await hass.async_add_executor_job(check_file):
            return False

        # Lưu cấu hình
        hass.data.setdefault(DOMAIN, {})
        hass.data[DOMAIN] = {'ics_path': ics_path, 'api_key': api_key}
        _LOGGER.debug("Đã lưu cấu hình vào hass.data")

        # Kiểm tra import amlich_core
        try:
            from .amlich_core import load_ics_file, set_api_key
        except ImportError as e:
            _LOGGER.error(f"Lỗi import amlich_core: {str(e)}")
            return False

        # Đặt API key
        try:
            await hass.async_add_executor_job(set_api_key, api_key)
            _LOGGER.debug("Đã đặt API key")
        except Exception as e:
            _LOGGER.error(f"Lỗi khi đặt API key: {str(e)}")
            return False

        # Tải file ICS
        try:
            if not await hass.async_add_executor_job(load_ics_file, ics_path):
                _LOGGER.error("Không thể tải file ICS")
                return False
            _LOGGER.debug("Đã tải file ICS thành công")
        except Exception as e:
            _LOGGER.error(f"Lỗi khi tải file ICS: {str(e)}")
            return False

        # KHÔNG forward entry ở đây! Để Home Assistant tự gọi async_setup_entry.

        # Đăng ký service reload_ics
        async def reload_ics_service(call):
            _LOGGER.debug("Gọi service reload_ics")
            try:
                if not await hass.async_add_executor_job(load_ics_file, ics_path):
                    _LOGGER.error("Không thể làm mới dữ liệu ICS")
                    return
                _LOGGER.debug("Đã làm mới dữ liệu ICS")
                sensor_entity_id = "sensor.tra_cuu_su_kien"
                if sensor_entity_id in hass.states.async_entity_ids():
                    await hass.helpers.entity_component.async_update_entity(
                        sensor_entity_id
                    )
                    _LOGGER.debug(f"Đã cập nhật sensor {sensor_entity_id}")
                else:
                    _LOGGER.warning(
                        f"Sensor {sensor_entity_id} chưa được khởi tạo"
                    )
            except Exception as e:
                _LOGGER.error(f"Lỗi khi thực thi reload_ics: {str(e)}")
                raise

        hass.services.async_register(DOMAIN, "reload_ics", reload_ics_service)
        _LOGGER.debug("Đã đăng ký service reload_ics")

        # Tự động tạo helper input_text.tracuu nếu chưa có
        input_text_entity_id = "input_text.tracuu"
        if input_text_entity_id not in hass.states.async_entity_ids():
            _LOGGER.info(
                "Chưa có helper input_text.tracuu, sẽ thử tạo tự động..."
            )
            try:
                # Gọi service input_text.set_value để tạo entity.
                # Nếu helper input_text đã được khai báo trong YAML thì sẽ thành công.
                await hass.services.async_call(
                    "input_text", "set_value",
                    {"entity_id": input_text_entity_id, "value": ""},
                    blocking=True
                )
                _LOGGER.info(
                    "Đã gọi service input_text.set_value cho input_text.tracuu."
                )
                _LOGGER.info(
                    "Nếu entity chưa tồn tại, hãy tạo helper input_text.tracuu "
                    "qua UI hoặc YAML."
                )
            except Exception as e:
                _LOGGER.warning(
                    f"Không thể tự động tạo input_text.tracuu: {str(e)}."
                )
                _LOGGER.warning(
                    "Vui lòng tạo helper input_text.tracuu qua UI hoặc YAML."
                )
        else:
            _LOGGER.info("Đã phát hiện helper input_text.tracuu.")

        _LOGGER.info("Thiết lập component amlich thành công")
        return True

    except Exception as e:
        _LOGGER.error(f"Lỗi nghiêm trọng khi thiết lập amlich: {str(e)}")
        _LOGGER.error(f"Traceback: {traceback.format_exc()}")
        return False


async def async_setup_entry(hass, entry):
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {}
    await hass.config_entries.async_forward_entry_setups(
        entry, ["sensor", "calendar", "switch"]
    )

    # Đăng ký callback để cập nhật dữ liệu mỗi ngày lúc 0h
    @callback
    async def midnight_update(now):
        _LOGGER.info("AmLichVN: Đang cập nhật dữ liệu lúc 0h")

    async_track_time_change(
        hass,
        midnight_update,
        hour=0,
        minute=0,
        second=10,
    )

    # Đăng ký service để reload entry (có thể gọi từ code khác)
    async def reload_entry_service(call):
        _LOGGER.info("AmLichVN: Reloading config entry by service")
        await hass.config_entries.async_reload(entry.entry_id)

    hass.services.async_register(DOMAIN, "reload_entry", reload_entry_service)

    return True


async def async_unload_entry(hass, entry):
    await hass.config_entries.async_forward_entry_unload(entry, "calendar")
    return await hass.config_entries.async_forward_entry_unload(
        entry, "sensor"
    )
