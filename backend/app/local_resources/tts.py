from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

import httpx
from flask import Flask, current_app

from app.local_resources.constants import DIALECTS
from app.local_resources.errors import (
    LocalResourceAiUnavailableError,
    LocalResourceValidationError,
)


VOICE_CONFIG = {
    "yue": "AI_TTS_VOICE_YUE",
    "hak": "AI_TTS_VOICE_HAKKA",
    "nan": "AI_TTS_VOICE_TEOCHEW",
}


@dataclass(frozen=True)
class TtsAudio:
    content: bytes
    content_type: str


class TtsClient(Protocol):
    def synthesize(
        self,
        text: str,
        language_code: str,
        voice_code: str,
        *,
        call_point: str,
    ) -> TtsAudio: ...


class OpenAiCompatibleTtsClient:
    def __init__(self, *, api_url, api_key, model, timeout, transport=None):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.transport = transport

    def _client(self):
        kwargs = {"timeout": self.timeout}
        if self.transport is not None:
            kwargs["transport"] = self.transport
        return httpx.Client(**kwargs)

    def synthesize(self, text, language_code, voice_code, *, call_point):
        del call_point
        if not self.api_url or not self.api_key or not self.model:
            raise LocalResourceAiUnavailableError()
        try:
            with self._client() as client:
                response = client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "input": text,
                        "voice": voice_code,
                        "language": language_code,
                        "response_format": "mp3",
                    },
                )
                response.raise_for_status()
                content_type = response.headers.get(
                    "content-type",
                    "",
                ).split(";")[0].strip().lower()
                if not response.content or not content_type.startswith("audio/"):
                    raise LocalResourceAiUnavailableError()
                return TtsAudio(
                    content=response.content,
                    content_type=content_type,
                )
        except LocalResourceAiUnavailableError:
            raise
        except Exception as error:
            raise LocalResourceAiUnavailableError() from error


def set_local_tts_client(app: Flask, client: TtsClient) -> None:
    app.extensions["local_resource_tts_client"] = client


def get_local_tts_client() -> TtsClient:
    client = current_app.extensions.get("local_resource_tts_client")
    if client is None:
        raise LocalResourceAiUnavailableError()
    return client


def synthesize_dialect(dialect_code: str, text: str) -> TtsAudio:
    if dialect_code not in DIALECTS:
        raise LocalResourceValidationError(
            "方言代码不正确",
            details={"dialect_code": "不支持"},
        )
    normalized = str(text or "").strip()
    if not normalized:
        raise LocalResourceAiUnavailableError()
    voice_key = VOICE_CONFIG[dialect_code]
    voice = str(current_app.config.get(voice_key, "")).strip()
    if not voice:
        raise LocalResourceAiUnavailableError()
    try:
        audio = get_local_tts_client().synthesize(
            normalized,
            dialect_code,
            voice,
            call_point="local_resources_dialect_tts",
        )
    except LocalResourceAiUnavailableError:
        raise
    except Exception as error:
        raise LocalResourceAiUnavailableError() from error
    content_type = str(
        getattr(audio, "content_type", "")
    ).split(";")[0].strip().lower()
    content = getattr(audio, "content", None)
    if (
        not isinstance(content, bytes)
        or not content
        or not content_type.startswith("audio/")
    ):
        raise LocalResourceAiUnavailableError()
    return TtsAudio(content=content, content_type=content_type)
