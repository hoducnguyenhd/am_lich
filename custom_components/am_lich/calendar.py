"""
Custom calendar platform for Âm Lịch VN (amlichvn).
Cho phép sự kiện trong DB xuất hiện trực tiếp trên giao diện Lịch Home Assistant.
"""
import logging
import sqlite3
from datetime import datetime, timedelta, date
import calendar
from homeassistant.components.calendar import (
    CalendarEntity, CalendarEvent, DOMAIN as CALENDAR_DOMAIN
)
from homeassistant.const import STATE_UNKNOWN
from .const import DOMAIN, DB_PATH

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, config_entry, async_add_entities):
    async_add_entities([AmLichVNCalendar()])

class AmLichVNCalendar(CalendarEntity):
    _attr_has_entity_name = True
    _attr_name = "Sự kiện Âm Lịch VN"
    _attr_unique_id = "amlich_calendar"

    def __init__(self):
        self._events = []
        self._load_events()

    def _load_events(self):
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, tendukien, loaisukien, ngayam, thangam, namam, ngayduong, thangduong, namduong, mota, laplai
                FROM events
                """
            )
            self._events = cursor.fetchall()
            conn.close()
        except Exception as ex:
            _LOGGER.error(f"Không thể đọc events.db: {ex}")
            self._events = []

    async def async_get_events(self, hass, start_date: datetime, end_date: datetime):
        self._load_events()
        result = []
        for row in self._events:
            # Lặp qua từng ngày trong khoảng truy vấn,
            current = start_date.date()
            while current <= end_date.date():
                event_date = self._get_event_date_for_range(row, current)
                if event_date == current:
                    result.append(CalendarEvent(
                        summary=row[1],
                        start=event_date,
                        end=event_date + timedelta(days=1),
                        description=row[9] or "",
                        uid=f"{row[0]}_{event_date.strftime('%Y%m%d')}"
                    ))
                current += timedelta(days=1)
        return result

    async def async_get_event(self, hass, event_id):
        self._load_events()
        for row in self._events:
            if str(row[0]) == str(event_id):
                event_date = self._get_event_date(row, date.today())
                return CalendarEvent(
                    summary=row[1],
                    start=event_date,
                    end=event_date + timedelta(days=1),
                    description=row[9] or "",
                    uid=str(row[0])
                )
        return None

    @property
    def event(self):
        self._load_events()
        today = date.today()
        for row in self._events:
            event_date = self._get_event_date(row, today)
            if event_date == today:
                return CalendarEvent(
                    summary=row[1],
                    start=event_date,
                    end=event_date + timedelta(days=1),
                    description=row[9] or "",
                    uid=str(row[0])
                )
        return None

    def _get_event_date(self, row, ref_date):
        # row: (id, tendukien, loaisukien, ngayam, thangam, namam, ngayduong, thangduong, namduong, mota, laplai)
        try:
            if row[2] == "solar":
                # Dương lịch
                if row[10] == "yearly":
                    # Lặp lại hàng năm
                    month = int(row[7]) if row[7] else None
                    day = int(row[6]) if row[6] else None
                    year = ref_date.year
                    if not month or not day:
                        return None
                    event_date = date(year, month, day)
                    if event_date < ref_date:
                        event_date = date(year + 1, month, day)
                    return event_date
                elif row[10] == "monthly":
                    # Lặp lại hàng tháng
                    day = int(row[6]) if row[6] else None
                    month = ref_date.month
                    year = ref_date.year
                    if not day:
                        return None
                    event_date = date(year, month, day)
                    if event_date < ref_date:
                        month += 1
                        if month > 12:
                            month = 1
                            year += 1
                        event_date = date(year, month, day)
                    return event_date
                else:
                    # Không lặp lại
                    year = int(row[8]) if row[8] else None
                    month = int(row[7]) if row[7] else None
                    day = int(row[6]) if row[6] else None
                    if not year or not month or not day:
                        return None
                    return date(year, month, day)
            else:
                # Âm lịch
                try:
                    from lunarcalendar import Converter, Lunar, Solar
                except ImportError:
                    return None
                lunar_day = int(row[3]) if row[3] else None
                lunar_month = int(row[4]) if row[4] else None
                lunar_year = int(row[5]) if row[5] else ref_date.year
                if not lunar_day or not lunar_month:
                    return None
                if row[10] == "yearly":
                    for offset in [0, 1]:
                        ly = ref_date.year + offset
                        lunar = Lunar(ly, lunar_month, lunar_day, False)
                        solar = Converter.Lunar2Solar(lunar)
                        event_date = date(solar.year, solar.month, solar.day)
                        if event_date >= ref_date:
                            return event_date
                    return None
                elif row[10] == "monthly":
                    solar_today = Solar(ref_date.year, ref_date.month, ref_date.day)
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
                else:
                    lunar = Lunar(lunar_year, lunar_month, lunar_day, False)
                    solar = Converter.Lunar2Solar(lunar)
                    return date(solar.year, solar.month, solar.day)
        except Exception as ex:
            _LOGGER.error(f"Lỗi tính ngày cho sự kiện calendar: {ex}")
            return None

    def _get_event_date_for_range(self, row, ref_date):
        # Logic giống _get_nearest_solar trong sensor.py, nhưng trả về ngày đúng với ref_date nếu trùng
        try:
            if row[2] == "solar":
                day = int(row[6]) if row[6] else None
                month = int(row[7]) if row[7] else None
                year = int(row[8]) if row[8] else None
                # Kiểm tra ngày hợp lệ với tháng/năm hiện tại
                def is_valid_date(y, m, d):
                    try:
                        date(y, m, d)
                        return True
                    except Exception:
                        return False
                if row[10] == "monthly":
                    # Lặp lại hàng tháng: chỉ tạo nếu không chỉ định tháng hoặc tháng đúng
                    if day and ref_date.day == day and is_valid_date(ref_date.year, ref_date.month, day):
                        if not month or ref_date.month == month:
                            return ref_date
                elif row[10] == "yearly":
                    # Lặp lại hàng năm: ngày/tháng trùng và hợp lệ
                    if day and month:
                        if (ref_date.day == day and ref_date.month == month and is_valid_date(ref_date.year, month, day)):
                            return ref_date
                else:
                    # Không lặp lại: ngày/tháng/năm phải trùng và hợp lệ
                    if day and month and year:
                        if (ref_date.day == day and ref_date.month == month and ref_date.year == year and is_valid_date(year, month, day)):
                            return ref_date
            else:
                # Âm lịch (không thay đổi logic)
                try:
                    from lunarcalendar import Converter, Solar
                except ImportError:
                    return None
                lunar_day = int(row[3]) if row[3] else None
                lunar_month = int(row[4]) if row[4] else None
                lunar_year = int(row[5]) if row[5] else None
                solar_today = Solar(ref_date.year, ref_date.month, ref_date.day)
                lunar_today = Converter.Solar2Lunar(solar_today)
                if row[10] == "monthly":
                    if lunar_day and lunar_today.day == lunar_day:
                        return ref_date
                elif row[10] == "yearly":
                    if lunar_day and lunar_month:
                        if lunar_today.day == lunar_day and lunar_today.month == lunar_month:
                            return ref_date
                else:
                    if lunar_day and lunar_month and lunar_year:
                        if lunar_today.day == lunar_day and lunar_today.month == lunar_month and lunar_today.year == lunar_year:
                            return ref_date
        except Exception as ex:
            _LOGGER.error(f"Lỗi tính ngày cho sự kiện calendar (range): {ex}")
            return None
