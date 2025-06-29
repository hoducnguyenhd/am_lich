from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.const import STATE_UNKNOWN
from .amlich_core import query_date
import logging
import sqlite3
from .const import DB_PATH
import os
import voluptuous as vol
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

DOMAIN = "amlich"
INPUT_TEXT_ENTITY = "input_text.tracuu"


def ensure_events_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tendukien TEXT,
            loaisukien TEXT,
            ngayam REAL,
            thangam REAL,
            namam REAL,
            ngayduong REAL,
            thangduong REAL,
            namduong REAL,
            mota TEXT,
            laplai TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def ensure_events_db_exists():
    if not os.path.exists(DB_PATH):
        ensure_events_table()


def parse_float_or_none(val):
    try:
        if val is None or val == "":
            return None
        return float(val)
    except Exception:
        return None


def format_int_if_possible(val):
    if val is None:
        return ""
    if isinstance(val, float) and val.is_integer():
        return str(int(val))
    return str(val)


class AmLichEventSensor(SensorEntity):
    def __init__(self, row):
        self._id = row[0]
        self._tendukien = row[1]
        self._loaisukien = row[2]
        self._ngayam = parse_float_or_none(row[3])
        self._thangam = parse_float_or_none(row[4])
        self._namam = parse_float_or_none(row[5])
        self._ngayduong = parse_float_or_none(row[6])
        self._thangduong = parse_float_or_none(row[7])
        self._namduong = parse_float_or_none(row[8])
        self._mota = row[9]
        self._laplai = row[10]
        _LOGGER.warning(
            f"[DEBUG amlich] id={self._id} tendukien={self._tendukien} "
            f"loaisukien={self._loaisukien} ngayam={self._ngayam} "
            f"({type(self._ngayam)}) thangam={self._thangam} "
            f"({type(self._thangam)}) namam={self._namam} "
            f"({type(self._namam)}) ngayduong={self._ngayduong} "
            f"({type(self._ngayduong)}) thangduong={self._thangduong} "
            f"({type(self._thangduong)}) namduong={self._namduong} "
            f"({type(self._namduong)})"
        )
        self._attr_unique_id = f"amlich_{self._id}"
        self._attr_name = self._tendukien
        self._attr_icon = "mdi:calendar"
        self._state = STATE_UNKNOWN
        self._attr_extra_state_attributes = self._build_attrs()

    def _build_attrs(self):
        # Hiển thị ngày/tháng/năm không có .0 nếu là số nguyên
        if self._loaisukien == "solar":
            ngay = format_int_if_possible(self._ngayduong)
            thang = format_int_if_possible(self._thangduong)
            nam = format_int_if_possible(self._namduong)
            if nam:
                ngay_su_kien = f"{ngay}/{thang}/{nam}"
            else:
                ngay_su_kien = f"{ngay}/{thang}"
        else:
            ngay = format_int_if_possible(self._ngayam)
            thang = format_int_if_possible(self._thangam)
            nam = format_int_if_possible(self._namam)
            if nam:
                ngay_su_kien = f"{ngay}/{thang}/{nam}"
            else:
                ngay_su_kien = f"{ngay}/{thang}"
        attrs = {
            "ngay_su_kien": ngay_su_kien,
            "loai_su_kien": (
                "Duong Lich" if self._loaisukien == "solar" else "Am Lich"
            ),
            "mo_ta": self._mota,
            "laplai": self._laplai
        }
        return attrs

    def _get_nearest_solar(self):
        from datetime import date
        today = date.today()
        try:
            if self._loaisukien == "solar":
                if not self._ngayduong:
                    return None
                sd = int(self._ngayduong)
                if self._laplai == "monthly":
                    month = today.month
                    year = today.year
                    if today.day > sd:
                        month += 1
                        if month > 12:
                            month = 1
                            year += 1
                    return date(year, month, sd)
                elif self._laplai == "yearly":
                    if not self._thangduong:
                        return None
                    month = int(self._thangduong)
                    day = int(self._ngayduong)
                    year = today.year
                    event_date = date(year, month, day)
                    if event_date < today:
                        event_date = date(year+1, month, day)
                    return event_date
                else:
                    if not self._namduong or not self._thangduong:
                        return None
                    year = int(self._namduong)
                    month = int(self._thangduong)
                    day = int(self._ngayduong)
                    return date(year, month, day)
            else:
                try:
                    from lunarcalendar import Converter, Lunar, Solar
                except ImportError:
                    return None
                if not self._ngayam:
                    return None
                lunar_day = int(self._ngayam)
                lunar_month = int(self._thangam) if self._thangam else None
                lunar_year = int(self._namam) if self._namam else today.year
                if self._laplai == "monthly":
                    solar_today = Solar(today.year, today.month, today.day)
                    lunar_today = Converter.Solar2Lunar(solar_today)
                    am_thang = lunar_today.month
                    am_nam = lunar_today.year
                    if lunar_today.day > lunar_day:
                        am_thang += 1
                        if am_thang > 12:
                            am_thang = 1
                            am_nam += 1
                    lunar = Lunar(am_nam, am_thang, lunar_day, False)
                    solar = Converter.Lunar2Solar(lunar)
                    return date(solar.year, solar.month, solar.day)
                elif self._laplai == "yearly":
                    if not lunar_month:
                        return None
                    for offset in [0, 1]:
                        ly = today.year + offset
                        lunar = Lunar(ly, lunar_month, lunar_day, False)
                        solar = Converter.Lunar2Solar(lunar)
                        event_date = date(solar.year, solar.month, solar.day)
                        if event_date >= today:
                            return event_date
                    lunar = Lunar(
                        today.year + 1, lunar_month, lunar_day, False
                    )
                    solar = Converter.Lunar2Solar(lunar)
                    return date(solar.year, solar.month, solar.day)
                else:
                    if not lunar_month:
                        return None
                    lunar = Lunar(lunar_year, lunar_month, lunar_day, False)
                    solar = Converter.Lunar2Solar(lunar)
                    return date(solar.year, solar.month, solar.day)
        except Exception as ex:
            _LOGGER.error(
                "Loi tinh ngay duong gan nhat cho su kien %s: %s",
                self._tendukien,
                ex,
            )
            return None

    def _get_nearest_solar_str(self):
        event_date = self._get_nearest_solar()
        if event_date:
            return event_date.strftime("%d/%m/%Y")
        return ""

    @property
    def state(self):
        from datetime import date
        event_date = self._get_nearest_solar()
        if event_date:
            today = date.today()
            days_left = (event_date - today).days
            return (
                f"Sắp tới {event_date.strftime('%d/%m/%Y')} - "
                f"còn {days_left} ngày"
            )
        return STATE_UNKNOWN

    async def async_update(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, tendukien, loaisukien, ngayam, thangam, namam, "
                "ngayduong, thangduong, namduong, mota, laplai FROM events "
                "WHERE id=?",
                (self._id,)
            )
            row = cursor.fetchone()
            conn.close()
            if row:
                self._tendukien = row[1]
                self._loaisukien = row[2]
                self._ngayam = parse_float_or_none(row[3])
                self._thangam = parse_float_or_none(row[4])
                self._namam = parse_float_or_none(row[5])
                self._ngayduong = parse_float_or_none(row[6])
                self._thangduong = parse_float_or_none(row[7])
                self._namduong = parse_float_or_none(row[8])
                self._mota = row[9]
                self._laplai = row[10]
                self._attr_name = self._tendukien
                self._attr_extra_state_attributes = self._build_attrs()
        except Exception as ex:
            _LOGGER.error(f"Lỗi reload DB cho sensor {self._id}: {ex}")

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, "amlich_events")},
            "name": "Âm lịch VN",
            "manufacturer": "amlich",
            "model": "Sự kiện Âm/Dương lịch"
        }


class AmlichSensor(SensorEntity):
    """Sensor tra cứu sự kiện."""

    def __init__(self, hass: HomeAssistant):
        self._hass = hass
        self._state = "Không có dữ liệu"
        self._attributes = {
            "output": "Không có dữ liệu",
            "is_lunar": False,
            "lunar_date": None,  # Lưu ngày âm lịch dạng DD/MM/YYYY
            "events": []
        }
        self._attr_name = "Tra Cứu Sự Kiện"
        self._attr_unique_id = f"{DOMAIN}_su_kien_sensor"
        self._attr_should_poll = False
        self._attr_device_info = {
            "identifiers": {(DOMAIN, "amlich_events")},
            "name": "Âm lịch VN",
            "manufacturer": "amlich",
            "model": "Sự kiện Âm/Dương lịch"
        }
        _LOGGER.debug("Đã khởi tạo instance AmlichSensor")

    async def async_added_to_hass(self):
        """Gọi khi sensor được thêm vào Home Assistant."""
        _LOGGER.debug("Gọi async_added_to_hass cho sensor.tra_cuu_su_kien")
        try:
            @callback
            def input_text_changed(event):
                new_state = event.data.get("new_state")
                if new_state is None or new_state.state == STATE_UNKNOWN:
                    return
                query = new_state.state.strip()
                if query:
                    _LOGGER.debug(f"Xử lý truy vấn: {query}")

                    async def handle_query():
                        # Đọc trạng thái switch use_humor (chỉ dùng switch)
                        use_humor = False
                        humor_entity = self._hass.states.get("switch.use_humor")
                        if humor_entity:
                            use_humor = humor_entity.state == "on"
                        result = await query_date(
                            self._hass, query, use_humor=use_humor
                        )
                        self._attributes = {
                            "output": result.get("output", "Không có dữ liệu"),
                            "date": result.get("date"),
                            "range": result.get("range"),
                            "is_lunar": result.get("is_lunar", False),
                            # Đảm bảo chứa năm (DD/MM/YYYY)
                            "lunar_date": result.get("lunar_date"),
                            "events": result.get("events", []),
                            "use_humor": use_humor
                        }
                        self._state = result.get(
                            "output", "Không có dữ liệu"
                        )[:255]
                        self.async_write_ha_state()
                    self._hass.async_create_task(handle_query())

            async_track_state_change_event(
                self._hass,
                [
                    INPUT_TEXT_ENTITY,
                    "switch.amlich_use_humor_switch",
                    "switch.use_humor"
                ],
                input_text_changed
            )
            _LOGGER.debug(
                f"Đã đăng ký lắng nghe {INPUT_TEXT_ENTITY}, "
                "switch.amlich_use_humor_switch và switch.use_humor"
            )

            input_state = self._hass.states.get(INPUT_TEXT_ENTITY)
            humor_entity = self._hass.states.get("switch.use_humor")
            use_humor = humor_entity and humor_entity.state == "on"
            if (
                input_state
                and input_state.state
                and input_state.state != STATE_UNKNOWN
            ):
                result = await query_date(
                    self._hass, input_state.state.strip(), use_humor=use_humor
                )
                self._attributes = {
                    "output": result.get("output", "Không có dữ liệu"),
                    "date": result.get("date"),
                    "range": result.get("range"),
                    "is_lunar": result.get("is_lunar", False),
                    # Đảm bảo chứa năm (DD/MM/YYYY)
                    "lunar_date": result.get("lunar_date"),
                    "events": result.get("events", []),
                    "use_humor": use_humor
                }
                self._state = result.get("output", "Không có dữ liệu")[:255]
                self.async_write_ha_state()
                _LOGGER.debug(
                    "Đã cập nhật state ban đầu cho sensor.tra_cuu_su_kien"
                )
        except Exception as e:
            _LOGGER.error(f"Lỗi trong async_added_to_hass: {str(e)}")

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes


async def async_setup_platform(
    hass: HomeAssistant,
    config,
    async_add_entities: AddEntitiesCallback,
    discovery_info=None
):
    """Thiết lập sensor."""
    _LOGGER.debug("Bắt đầu khởi tạo sensor.tra_cuu_su_kien")
    try:
        sensor = AmlichSensor(hass)
        async_add_entities([sensor])
        _LOGGER.info("Đã thêm sensor.tra_cuu_su_kien vào Home Assistant")
        # Tích hợp các sensor sự kiện từ DB
        ensure_events_db_exists()
        sensors = []
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, tendukien, loaisukien, ngayam, thangam, namam, "
                "ngayduong, thangduong, namduong, mota, laplai FROM events"
            )
            rows = cursor.fetchall()
            conn.close()
            for row in rows:
                sensors.append(AmLichEventSensor(row))
        except Exception as ex:
            _LOGGER.error(f"Khong the doc events.db: {ex}")
        if sensors:
            async_add_entities(sensors, True)
    except Exception as e:
        _LOGGER.error(f"Lỗi khi khởi tạo sensor.tra_cuu_su_kien: {str(e)}")
        raise


async def async_setup_entry(hass, config_entry, async_add_entities):
    _LOGGER.debug("[DEBUG] Bắt đầu async_setup_entry cho amlich")
    ensure_events_table()  # Đảm bảo luôn có bảng events trước khi truy vấn
    sensors = [AmlichSensor(hass)]
    _LOGGER.debug("[DEBUG] Chuẩn bị gọi async_add_entities cho sensor tra cứu")
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, tendukien, loaisukien, ngayam, thangam, namam, "
            "ngayduong, thangduong, namduong, mota, laplai FROM events"
        )
        rows = cursor.fetchall()
        conn.close()
        for row in rows:
            sensors.append(AmLichEventSensor(row))
        _LOGGER.debug(f"[DEBUG] Đã thêm {len(rows)} AmLichEventSensor vào danh sách entity")
    except Exception as ex:
        _LOGGER.error(f"[DEBUG] Khong the doc events.db: {ex}")
    _LOGGER.debug(f"[DEBUG] Gọi async_add_entities với tổng số entity: {len(sensors)}")
    async_add_entities(sensors, True)
    _LOGGER.debug("[DEBUG] Đã gọi xong async_add_entities")
