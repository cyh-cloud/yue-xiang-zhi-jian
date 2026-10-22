"""Source adapters that normalize fixture or saved source data for the pipeline."""

from . import cass_linguistics, fiveajob
from .dialect_org import parse_detail
from .weather_sources import (
    WEATHER_SOURCES,
    WeatherComCnDTO,
    WeatherSource,
    parse_weather_com_cn,
)

__all__ = [
    "WEATHER_SOURCES",
    "WeatherComCnDTO",
    "WeatherSource",
    "cass_linguistics",
    "fiveajob",
    "parse_detail",
    "parse_weather_com_cn",
]