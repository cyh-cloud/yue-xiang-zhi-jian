from __future__ import annotations

import json
import logging
from collections.abc import Iterator

import httpx
from flask import Flask, current_app
from flask import has_app_context

from app.agri_skills.ai_context import redact_ai_log
from app.agri_skills.errors import AiUnavailableError


def extract_json_object(content: str) -> str:
    if not isinstance(content, str):
        raise ValueError("AI response content must be a string")

    text = content.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    start = text.find("{")
    if start < 0:
        raise ValueError("AI response does not contain a JSON object")

    decoder = json.JSONDecoder()
    value, end = decoder.raw_decode(text[start:])
    if not isinstance(value, dict):
        raise ValueError("AI response JSON must be an object")
    return text[start : start + end]


def _redact_embedded_json(value):
    if isinstance(value, dict):
        return {
            key: _redact_embedded_json(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact_embedded_json(item) for item in value]
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return value
        if isinstance(parsed, (dict, list)):
            return json.dumps(
                redact_ai_log(parsed),
                ensure_ascii=False,
            )
    return value


class NullAiClient:
    def stream_chat(self, messages: list[dict], *, call_point: str) -> Iterator[str]:
        raise AiUnavailableError("AI service is not configured")

    def complete_json(self, messages: list[dict], *, call_point: str) -> dict:
        raise AiUnavailableError("AI service is not configured")

    def transcribe(self, audio: bytes, filename: str, *, call_point: str) -> str:
        raise AiUnavailableError("AI service is not configured")


class OpenAiCompatibleAiClient:
    def __init__(
        self,
        *,
        api_url: str,
        api_key: str,
        model: str,
        timeout: float,
        transport=None,
    ):
        self.api_url = api_url
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.transport = transport

    def _client(self) -> httpx.Client:
        if self.transport is not None:
            return httpx.Client(
                transport=self.transport,
                timeout=self.timeout,
            )
        return httpx.Client(timeout=self.timeout)

    @staticmethod
    def _log_failure(call_point: str, messages: list[dict]) -> None:
        logger = (
            current_app.logger
            if has_app_context()
            else logging.getLogger(__name__)
        )
        logger.warning(
            "AI call failed for %s: %s",
            call_point,
            _redact_embedded_json(redact_ai_log(messages)),
        )

    def stream_chat(
        self,
        messages: list[dict],
        *,
        call_point: str,
    ) -> Iterator[str]:
        if not self.api_url or not self.api_key:
            raise AiUnavailableError("AI service is not configured")

        try:
            with self._client() as client:
                with client.stream(
                    "POST",
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": True,
                    },
                ) as response:
                    response.raise_for_status()
                    for line in response.iter_lines():
                        if isinstance(line, bytes):
                            line = line.decode("utf-8")
                        if not line.startswith("data: "):
                            continue
                        payload = line[6:]
                        if payload == "[DONE]":
                            break
                        data = json.loads(payload)
                        content = data["choices"][0]["delta"].get("content", "")
                        if content:
                            yield content
        except Exception as exc:
            self._log_failure(call_point, messages)
            raise AiUnavailableError("AI service request failed") from exc

    def complete_json(
        self,
        messages: list[dict],
        *,
        call_point: str,
    ) -> dict:
        if not self.api_url or not self.api_key:
            raise AiUnavailableError("AI service is not configured")

        try:
            with self._client() as client:
                response = client.post(
                    self.api_url,
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    json={
                        "model": self.model,
                        "messages": messages,
                        "stream": False,
                    },
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
                return json.loads(extract_json_object(content))
        except Exception as exc:
            self._log_failure(call_point, messages)
            raise AiUnavailableError("AI service request failed") from exc

    def transcribe(
        self,
        audio: bytes,
        filename: str,
        *,
        call_point: str,
    ) -> str:
        raise AiUnavailableError("ASR endpoint is not configured")


def set_ai_client(app: Flask, client) -> None:
    app.extensions["agri_ai_client"] = client


def get_ai_client():
    return current_app.extensions.get("agri_ai_client", NullAiClient())
