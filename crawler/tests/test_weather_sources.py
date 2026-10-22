import json
import unittest
from datetime import datetime, timezone
from pathlib import Path

from crawler.pipeline.sources.weather_sources import (
    WEATHER_SOURCES,
    WeatherRuntimeCache,
    parse_weather_com_cn,
)


ROOT = Path(__file__).resolve().parents[1]
BEIJING_RAW = ROOT / "tests" / "fixtures" / "evidence" / "weather" / "sk-beijing.json"
BEIJING_HEADERS = (
    ROOT
    / "tests"
    / "fixtures"
    / "evidence"
    / "weather"
    / "sk-beijing.response-headers.txt"
)
BEIJING_URL = "https://d1.weather.com.cn/sk_2d/101010100.html"


class WeatherSourcesTest(unittest.TestCase):
    def test_free_sources_have_independent_ids_and_quota_metadata(self):
        source_ids = {source.source_id for source in WEATHER_SOURCES}

        self.assertEqual(
            source_ids,
            {"weather", "open-meteo", "qweather"},
        )
        for source in WEATHER_SOURCES:
            self.assertEqual(source.is_free_tier, True)
            self.assertFalse(source.paid_plans_allowed)
            self.assertFalse(source.historical_storage_allowed)
            self.assertTrue(source.quota_text)
            self.assertTrue(source.attribution_text)
            self.assertTrue(source.license_or_usage)

    def test_weather_com_cn_data_sk_becomes_runtime_dto(self):
        fetched_at = datetime(2026, 10, 19, 1, 10, tzinfo=timezone.utc)

        dto = parse_weather_com_cn(
            BEIJING_RAW.read_text(encoding="utf-8"),
            source_url=BEIJING_URL,
            fetched_at=fetched_at,
        )

        self.assertEqual(dto.source_id, "weather")
        self.assertEqual(dto.city_code, "101010100")
        self.assertEqual(dto.city_name, "北京")
        self.assertEqual(dto.temperature_c, 6.1)
        self.assertEqual(dto.condition_text, "晴")
        self.assertEqual(dto.observed_at, "2026-10-19T00:45:00+08:00")
        self.assertEqual(dto.fetched_at, "2026-10-19T09:10:00+08:00")
        self.assertEqual(dto.source_url, BEIJING_URL)
        self.assertNotIn("headers", dto.to_dict())

    def test_header_hash_does_not_change_content_version(self):
        fetched_at = datetime(2026, 10, 19, 1, 10, tzinfo=timezone.utc)
        body = BEIJING_RAW.read_text(encoding="utf-8")
        first_headers = BEIJING_HEADERS.read_text(encoding="utf-8")
        second_headers = first_headers + "\ndate: later\n"

        first = parse_weather_com_cn(
            body,
            source_url=BEIJING_URL,
            fetched_at=fetched_at,
            response_headers=first_headers,
        )
        second = parse_weather_com_cn(
            body,
            source_url=BEIJING_URL,
            fetched_at=fetched_at,
            response_headers=second_headers,
        )

        self.assertEqual(first.content_hash, second.content_hash)
        self.assertNotEqual(first.header_sha256, second.header_sha256)
        self.assertEqual(first.content_version, first.content_hash)

    def test_source_metadata_is_json_serializable(self):
        payload = [source.to_dict() for source in WEATHER_SOURCES]

        encoded = json.dumps(payload, ensure_ascii=False)

        self.assertIn('"source_id": "weather"', encoded)
        self.assertNotIn("weather-com-cn", encoded)
        self.assertIn("open-meteo", encoded)
        self.assertIn("qweather", encoded)

    def test_runtime_cache_reuses_dto_until_ttl_expires(self):
        now = [100.0]
        loads = []
        cache = WeatherRuntimeCache(
            ttl_seconds=60,
            clock=lambda: now[0],
        )

        def load():
            loads.append(now[0])
            return {"temperature_c": 20 + len(loads)}

        first = cache.get_or_load("weather:101010100", load)
        second = cache.get_or_load("weather:101010100", load)
        now[0] += 61
        third = cache.get_or_load("weather:101010100", load)

        self.assertIs(first, second)
        self.assertEqual(first, {"temperature_c": 21})
        self.assertEqual(third, {"temperature_c": 22})
        self.assertEqual(loads, [100.0, 161.0])


if __name__ == "__main__":
    unittest.main()
