import tempfile
import unittest
from pathlib import Path

import httpx

from app import create_app
from app.local_resources.errors import LocalResourceAiUnavailableError
from app.local_resources.tts import (
    OpenAiCompatibleTtsClient,
    set_local_tts_client,
    synthesize_dialect,
)


class LocalResourceTtsTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "test.db"),
                "AI_API_KEY": "shared-key",
                "AI_TTS_URL": "https://tts.example.test/speech",
                "AI_TTS_MODEL": "dialect-tts",
                "AI_TTS_VOICE_YUE": "voice-yue",
                "AI_TTS_VOICE_HAKKA": "voice-hak",
                "AI_TTS_VOICE_TEOCHEW": "voice-nan",
                "AI_TTS_TIMEOUT_SECONDS": 5,
            }
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_dialect_voice_mapping_and_http_contract(self):
        captured = {}

        def handler(request: httpx.Request) -> httpx.Response:
            captured["request"] = request
            return httpx.Response(
                200,
                content=b"ID3audio",
                headers={"content-type": "audio/mpeg"},
                request=request,
            )

        client = OpenAiCompatibleTtsClient(
            api_url="https://tts.example.test/speech",
            api_key="shared-key",
            model="dialect-tts",
            timeout=5,
            transport=httpx.MockTransport(handler),
        )
        set_local_tts_client(self.app, client)
        with self.app.app_context():
            audio = synthesize_dialect("hak", "你好")
        request = captured["request"]
        self.assertEqual(audio.content, b"ID3audio")
        self.assertEqual(audio.content_type, "audio/mpeg")
        self.assertIn(b'"language":"hak"', request.content)
        self.assertIn(b'"voice":"voice-hak"', request.content)
        self.assertIn(
            b'"response_format":"mp3"',
            request.content,
        )

    def test_missing_voice_and_empty_audio_are_unavailable(self):
        self.app.config["AI_TTS_VOICE_YUE"] = ""
        with self.app.app_context():
            with self.assertRaises(LocalResourceAiUnavailableError):
                synthesize_dialect("yue", "你好")

    def test_non_audio_response_is_unavailable(self):
        class BadClient:
            def synthesize(self, **kwargs):
                from app.local_resources.tts import TtsAudio
                return TtsAudio(content=b"not-audio", content_type="text/plain")

        set_local_tts_client(self.app, BadClient())
        with self.app.app_context():
            with self.assertRaises(LocalResourceAiUnavailableError):
                synthesize_dialect("nan", "你好")


if __name__ == "__main__":
    unittest.main()
