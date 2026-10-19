import hashlib
import json
import re
import threading
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any


CHINA_TZ = timezone(timedelta(hours=8))
DEFAULT_CACHE_TTL_SECONDS = 15 * 60


class WeatherRuntimeCache:
    """Small in-memory TTL cache for runtime weather DTOs."""

    def __init__(
        self,
        ttl_seconds=DEFAULT_CACHE_TTL_SECONDS,
        *,
        clock=None,
        max_entries=128,
    ):
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self.ttl_seconds = ttl_seconds
        self.max_entries = max(1, int(max_entries))
        self._clock = clock or time.monotonic
        self._items = {}
        self._lock = threading.Lock()

    def get_or_load(self, key, loader):
        now = self._clock()
        with self._lock:
            cached = self._items.get(key)
            if cached is not None and cached[0] > now:
                return cached[1]
            if cached is not None:
                self._items.pop(key, None)

        value = loader()
        with self._lock:
            if len(self._items) >= self.max_entries:
                oldest = min(
                    self._items,
                    key=lambda item_key: self._items[item_key][0],
                )
                self._items.pop(oldest, None)
            self._items[key] = (now + self.ttl_seconds, value)
        return value

    def clear(self):
        with self._lock:
            self._items.clear()

    def __len__(self):
        with self._lock:
            return len(self._items)


@dataclass(frozen=True)
class WeatherSource:
    source_id: str
    name: str
    home_url: str
    endpoint_template: str
    free_tier: str
    quota_text: str
    attribution_text: str
    license_or_usage: str
    license_url: str
    is_free_tier: bool = True
    paid_plans_allowed: bool = False
    historical_storage_allowed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class WeatherComCnDTO:
    source_id: str
    city_code: str
    city_name: str
    city_slug: str | None
    temperature_c: float | None
    temperature_f: float | None
    condition_text: str | None
    condition_code: str | None
    wind_direction: str | None
    wind_direction_code: str | None
    wind_level: str | None
    wind_speed: str | None
    humidity: str | None
    humidity_raw: str | None
    pressure_hpa: float | None
    visibility: str | None
    rain_current: float | None
    rain_24h: float | None
    aqi: int | None
    aqi_pm25: int | None
    observed_at: str
    observed_date_raw: str | None
    observed_time_raw: str | None
    fetched_at: str
    source_url: str
    content_hash: str
    content_version: str
    header_sha256: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


WEATHER_SOURCES = (
    WeatherSource(
        source_id="weather",
        name="中国天气网",
        home_url="https://www.weather.com.cn/",
        endpoint_template=(
            "https://d1.weather.com.cn/sk_2d/{city_code}.html"
        ),
        free_tier="网页运行时辅助接口，免费访问，无正式 API 合同",
        quota_text="无公开 SLA 或配额，按城市低频按需请求，单轮缓存 15 至 30 分钟",
        attribution_text="中国天气网 www.weather.com.cn",
        license_or_usage="未发现 API 复用许可，仅限非商业竞赛参考，上线前需确认授权",
        license_url="https://www.weather.com.cn/",
    ),
    WeatherSource(
        source_id="open-meteo",
        name="Open-Meteo",
        home_url="https://open-meteo.com/",
        endpoint_template=(
            "https://api.open-meteo.com/v1/forecast"
            "?latitude={latitude}&longitude={longitude}&current=temperature_2m"
        ),
        free_tier="非商业免费层，无需 API Key",
        quota_text="免费层限流以官方文档为准，按城市批量请求并缓存，避免逐任务调用",
        attribution_text="Weather data by Open-Meteo.com",
        license_or_usage="Open-Meteo 免费层允许非商业使用，必须保留来源署名",
        license_url="https://open-meteo.com/en/license",
    ),
    WeatherSource(
        source_id="qweather",
        name="和风天气",
        home_url="https://www.qweather.com/",
        endpoint_template=(
            "https://devapi.qweather.com/v7/weather/now"
            "?location={location}&key={api_key}"
        ),
        free_tier="免费开发版，需 API Key，不接付费套餐",
        quota_text="免费开发版每日调用量以控制台额度为准，按城市缓存，不在循环中重试",
        attribution_text="和风天气 QWeather",
        license_or_usage="只使用免费开发版和免费数据，商业或付费能力不在范围内",
        license_url="https://dev.qweather.com/docs/configuration/",
    ),
)


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_none(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def _parse_data_sk(body: str) -> dict[str, Any]:
    match = re.search(r"var\s+dataSK\s*=\s*(\{.*\})\s*;?\s*$", body, re.DOTALL)
    if not match:
        raise ValueError("weather.com.cn response does not contain var dataSK")
    payload = json.loads(match.group(1))
    if not isinstance(payload, dict):
        raise ValueError("weather.com.cn dataSK is not an object")
    return payload


def _parse_observed_at(
    date_raw: str | None,
    time_raw: str | None,
    fetched_at: datetime,
) -> str:
    if not date_raw or not time_raw:
        return fetched_at.astimezone(CHINA_TZ).isoformat()
    match = re.fullmatch(
        r"(\d{1,2})月(\d{1,2})日(?:[（(](?:周|星期)([一二三四五六日天])[）)])?",
        date_raw.strip(),
    )
    time_match = re.fullmatch(r"(\d{1,2}):(\d{2})", time_raw.strip())
    if not match or not time_match:
        return fetched_at.astimezone(CHINA_TZ).isoformat()

    month, day = int(match.group(1)), int(match.group(2))
    hour, minute = int(time_match.group(1)), int(time_match.group(2))
    local_fetch = fetched_at.astimezone(CHINA_TZ)
    year = local_fetch.year
    observed_date = date(year, month, day)

    # The source omits the year. A December response fetched in January belongs
    # to the previous year, and a January response fetched in December belongs
    # to the next year.
    if observed_date - local_fetch.date() > timedelta(days=180):
        observed_date = date(year - 1, month, day)
    elif local_fetch.date() - observed_date > timedelta(days=180):
        observed_date = date(year + 1, month, day)

    observed = datetime.combine(observed_date, time(hour, minute), tzinfo=CHINA_TZ)
    if observed - local_fetch > timedelta(hours=2):
        observed -= timedelta(days=1)
    return observed.isoformat()


def parse_weather_com_cn(
    body: str,
    *,
    source_url: str,
    fetched_at: datetime,
    response_headers: str | None = None,
) -> WeatherComCnDTO:
    payload = _parse_data_sk(body)
    city_code = str(payload.get("city") or "")
    if not city_code:
        raise ValueError("weather.com.cn dataSK is missing city")

    local_fetched_at = fetched_at.astimezone(CHINA_TZ).isoformat()
    humidity_raw = payload.get("SD")
    humidity = humidity_raw.rstrip("%") if isinstance(humidity_raw, str) else None
    content_hash = _sha256_text(body)

    return WeatherComCnDTO(
        source_id="weather",
        city_code=city_code,
        city_name=str(payload.get("cityname") or ""),
        city_slug=payload.get("nameen"),
        temperature_c=_float_or_none(payload.get("temp")),
        temperature_f=_float_or_none(payload.get("tempf")),
        condition_text=payload.get("weather"),
        condition_code=payload.get("weathercode"),
        wind_direction=payload.get("WD"),
        wind_direction_code=payload.get("wde"),
        wind_level=payload.get("WS"),
        wind_speed=payload.get("wse"),
        humidity=humidity,
        humidity_raw=humidity_raw,
        pressure_hpa=_float_or_none(payload.get("qy")),
        visibility=payload.get("njd"),
        rain_current=_float_or_none(payload.get("rain")),
        rain_24h=_float_or_none(payload.get("rain24h")),
        aqi=_int_or_none(payload.get("aqi")),
        aqi_pm25=_int_or_none(payload.get("aqi_pm25")),
        observed_at=_parse_observed_at(
            payload.get("date"),
            payload.get("time"),
            fetched_at,
        ),
        observed_date_raw=payload.get("date"),
        observed_time_raw=payload.get("time"),
        fetched_at=local_fetched_at,
        source_url=source_url,
        content_hash=content_hash,
        content_version=content_hash,
        header_sha256=(
            _sha256_text(response_headers)
            if response_headers is not None
            else None
        ),
    )
