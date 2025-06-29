import voluptuous as vol
import logging
from homeassistant import config_entries
from .const import DOMAIN, DB_PATH
from homeassistant.helpers import selector
import sqlite3

_LOGGER = logging.getLogger(__name__)

EVENT_SCHEMA = {
    vol.Required("tendukien"): selector.TextSelector(
        selector.TextSelectorConfig(
            type=selector.TextSelectorType.TEXT
        )
    ),
    vol.Required("loaisukien", default="lunar"): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {"value": "lunar", "label": "Am"},
                {"value": "solar", "label": "Duong"}
            ],
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
    vol.Required("laplai", default="yearly"): selector.SelectSelector(
        selector.SelectSelectorConfig(
            options=[
                {"value": "yearly", "label": "Hang nam"},
                {"value": "monthly", "label": "Hang thang"},
                {"value": "none", "label": "Khong lap"}
            ],
            mode=selector.SelectSelectorMode.DROPDOWN
        )
    ),
    vol.Optional("ngayam"): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=30, mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Optional("thangam"): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=12, mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Optional("namam"): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1900, max=2100, mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Optional("ngayduong"): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=31, mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Optional("thangduong"): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1, max=12, mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Optional("namduong"): selector.NumberSelector(
        selector.NumberSelectorConfig(
            min=1900, max=2100, mode=selector.NumberSelectorMode.BOX
        )
    ),
    vol.Optional("mota"): selector.TextSelector(
        selector.TextSelectorConfig(
            type=selector.TextSelectorType.TEXT,
        )
    ),
}


class AmlichConfigFlow(config_entries.ConfigFlow, domain="amlich"):
    @staticmethod
    def async_get_options_flow(config_entry):
        return AmLichVNOptionsFlow(config_entry)

    async def async_step_user(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title="Âm Lịch VN",
                data={},
            )
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({}),
        )


async def async_get_options_flow(config_entry):
    return AmLichVNOptionsFlow(config_entry)


class AmLichVNOptionsFlow(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        # Khởi tạo options flow cho AmLichVN
        self.config_entry = config_entry
        self._selected_event_id = None
        self._db_path = None

    async def async_step_init(self, user_input=None):
        # Bước khởi tạo: hiển thị menu chính
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "manage_events": "Quản lý sự kiện"
            }
        )

    async def async_step_manage_events(self, user_input=None):
        # Bước quản lý sự kiện: chọn, thêm hoặc sửa sự kiện
        events = self._load_events()
        options = []
        # Hiển thị tiếng Việt cho tất cả label dropdown
        for row in events:
            options.append({
                "value": str(row[0]),
                "label": row[1]
            })
        options.append({
            "value": "add_new",
            "label": "Thêm sự kiện mới"
        })
        schema = {
            vol.Required("event_id"): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=options,
                    mode=selector.SelectSelectorMode.DROPDOWN
                )
            )
        }
        if user_input is not None:
            event_id = user_input["event_id"]
            if event_id == "add_new":
                return await self.async_step_add_event()
            else:
                self._selected_event_id = int(event_id)
                return await self.async_step_edit_event()
        return self.async_show_form(
            step_id="manage_events",
            data_schema=vol.Schema(schema),
            errors=None
        )

    async def async_step_confirm_delete(self, user_input=None):
        # Bước xác nhận xóa sự kiện
        schema = {
            vol.Required("confirm", default=False): selector.BooleanSelector()
        }
        errors = {}
        if user_input is not None:
            if user_input.get("confirm"):
                # Thực hiện xóa sự kiện
                if self._selected_event_id:
                    conn = sqlite3.connect(DB_PATH)
                    cursor = conn.cursor()
                    cursor.execute(
                        "DELETE FROM events WHERE id=?",
                        (self._selected_event_id,)
                    )
                    conn.commit()
                    conn.close()
                    self._reload_integration()
                return self.async_create_entry(title="", data={})
            else:
                # Nếu không xác nhận, quay lại menu chính
                return await self.async_step_init()
        return self.async_show_form(
            step_id="confirm_delete",
            data_schema=vol.Schema(schema),
            errors=errors
        )

    def _reload_integration(self):
        # Gọi service reload_entry sau khi thêm/sửa/xóa sự kiện
        hass = self.hass if hasattr(self, "hass") else None
        if hass:
            hass.async_create_task(
                hass.services.async_call(
                    "amlich", "reload_entry", {}, blocking=False
                )
            )

    async def async_step_add_event(self, user_input=None):
        # Bước thêm sự kiện mới
        errors = {}
        loaisukien = None
        if user_input is not None:
            loaisukien = user_input.get("loaisukien")
        else:
            loaisukien = "lunar"
        schema = self._build_event_schema(loaisukien, user_input)
        if user_input is not None:
            try:
                self._insert_event(self._filter_event_data(user_input))
                self._reload_integration()
                return self.async_create_entry(title="", data={})
            except Exception as ex:
                errors["base"] = "add_failed"
                _LOGGER.error(f"Lỗi thêm sự kiện: {ex}")
        return self.async_show_form(
            step_id="add_event",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    async def async_step_edit_event(self, user_input=None):
        # Bước sửa sự kiện đã chọn
        errors = {}
        self._events = self._load_events()
        event = None
        for row in self._events:
            if row[0] == self._selected_event_id:
                event = row
                break
        if not event:
            errors["base"] = "not_found"
            return self.async_show_form(
                step_id="init",
                data_schema=vol.Schema({}),
                errors=errors
            )
        initial = self._event_to_dict(event)
        loaisukien = user_input.get("loaisukien") if user_input else initial.get("loaisukien", "lunar")
        schema = self._build_event_schema(loaisukien, initial, user_input)
        if user_input is not None:
            if user_input.get("delete", False):
                return await self.async_step_confirm_delete()
            try:
                self._update_event(self._selected_event_id, self._filter_event_data(user_input, initial))
                self._reload_integration()
                return self.async_create_entry(title="", data={})
            except Exception as ex:
                errors["base"] = "edit_failed"
                _LOGGER.error(f"Lỗi sửa sự kiện: {ex}")
        return self.async_show_form(
            step_id="edit_event",
            data_schema=vol.Schema(schema),
            errors=errors,
        )

    def _build_event_schema(self, loaisukien, initial=None, user_input=None):
        # Xây dựng schema cho form thêm/sửa sự kiện
        laplai_val = (user_input or initial or {}).get("laplai", "yearly")
        schema = {}
        def get_val(key):
            # Lấy giá trị mặc định cho trường nhập liệu
            val = None
            if user_input is not None and key in user_input:
                val = user_input[key]
            elif initial is not None and key in initial:
                val = initial[key]
            if val is None or val == "":
                return ""
            try:
                fval = float(val)
                if fval.is_integer():
                    return str(int(fval))
                return str(fval)
            except Exception:
                return str(val)
        schema[vol.Required("tendukien", default=get_val("tendukien"))] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        )
        schema[vol.Required("loaisukien", default=get_val("loaisukien") or "lunar")] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": "lunar", "label": "Âm"},
                    {"value": "solar", "label": "Dương"}
                ],
                mode=selector.SelectSelectorMode.DROPDOWN
            )
        )
        schema[vol.Required("laplai", default=laplai_val)] = selector.SelectSelector(
            selector.SelectSelectorConfig(
                options=[
                    {"value": "yearly", "label": "Hàng năm"},
                    {"value": "monthly", "label": "Hàng tháng"},
                    {"value": "none", "label": "Không lặp"}
                ],
                mode=selector.SelectSelectorMode.DROPDOWN
            )
        )
        for field, label in [("ngay", "Ngày"), ("thang", "Tháng"), ("nam", "Năm")]:
            schema[vol.Optional(field, default=get_val(field))] = selector.TextSelector(
                selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
            )
        schema[vol.Optional("mota", default=get_val("mota"))] = selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.TEXT)
        )
        if initial is not None:
            schema[vol.Optional("delete")] = selector.BooleanSelector()
        return schema

    def _filter_event_data(self, data, initial=None):
        # Lấy dữ liệu từ form, chuyển đổi về dict chuẩn để lưu DB
        def clean(key):
            val = data.get(key, None)
            if val is None or (isinstance(val, str) and val.strip() == ""):
                return None
            try:
                fval = float(val)
                if fval.is_integer():
                    return int(fval)
                return fval
            except Exception:
                return val
        loaisukien = data.get("loaisukien")
        result = {
            "tendukien": clean("tendukien"),
            "loaisukien": loaisukien,
            "laplai": data.get("laplai"),
            "mota": clean("mota"),
        }
        if loaisukien == "lunar":
            result["ngayam"] = clean("ngay")
            result["thangam"] = clean("thang")
            result["namam"] = clean("nam")
            result["ngayduong"] = None
            result["thangduong"] = None
            result["namduong"] = None
        elif loaisukien == "solar":
            result["ngayam"] = None
            result["thangam"] = None
            result["namam"] = None
            result["ngayduong"] = clean("ngay")
            result["thangduong"] = clean("thang")
            result["namduong"] = clean("nam")
        else:
            result["ngayam"] = None
            result["thangam"] = None
            result["namam"] = None
            result["ngayduong"] = None
            result["thangduong"] = None
            result["namduong"] = None
        return result

    def _event_to_dict(self, row):
        # Chuyển dữ liệu từ DB về dict cho form
        if row[2] == "lunar":
            return {
                "tendukien": row[1],
                "loaisukien": row[2],
                "ngay": row[3],
                "thang": row[4],
                "nam": row[5],
                "mota": row[9],
                "laplai": row[10],
            }
        else:
            return {
                "tendukien": row[1],
                "loaisukien": row[2],
                "ngay": row[6],
                "thang": row[7],
                "nam": row[8],
                "mota": row[9],
                "laplai": row[10],
            }

    def _load_events(self):
        # Đảm bảo file DB và bảng events tồn tại trước khi truy vấn
        from .sensor import ensure_events_db_exists
        ensure_events_db_exists()
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, tendukien, loaisukien, ngayam, thangam, namam,
                ngayduong, thangduong, namduong, mota, laplai
                FROM events
                """
            )
            rows = cursor.fetchall()
            conn.close()
            return rows
        except Exception as ex:
            _LOGGER.error(f"Khong the doc events.db: {ex}")
            return []

    def _update_event(self, event_id, data):
        # Cập nhật sự kiện trong DB
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        update_fields = [
            "tendukien", "loaisukien",
            "ngayam", "thangam", "namam",
            "ngayduong", "thangduong", "namduong",
            "mota", "laplai"
        ]
        values = []
        for field in update_fields:
            v = data.get(field, None)
            if v == "" or v is None:
                values.append(None)
            elif field in ["ngayam", "thangam", "namam", "ngayduong", "thangduong", "namduong"]:
                try:
                    values.append(float(v))
                except Exception:
                    values.append(None)
            else:
                values.append(v)
        values.append(event_id)
        cursor.execute(
            """
            UPDATE events SET
                tendukien=?, loaisukien=?, ngayam=?, thangam=?, namam=?,
                ngayduong=?, thangduong=?, namduong=?, mota=?,
                laplai=?
            WHERE id=?
            """,
            tuple(values),
        )
        conn.commit()
        conn.close()

    def _insert_event(self, data):
        # Đảm bảo file DB và bảng events tồn tại trước khi thêm
        from .sensor import ensure_events_db_exists
        ensure_events_db_exists()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO events (
                tendukien, loaisukien,
                ngayam, thangam, namam,
                ngayduong, thangduong, namduong,
                mota, laplai
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                data.get("tendukien"),
                data.get("loaisukien"),
                data.get("ngayam"),
                data.get("thangam"),
                data.get("namam"),
                data.get("ngayduong"),
                data.get("thangduong"),
                data.get("namduong"),
                data.get("mota"),
                data.get("laplai"),
            ),
        )
        conn.commit()
        conn.close()
