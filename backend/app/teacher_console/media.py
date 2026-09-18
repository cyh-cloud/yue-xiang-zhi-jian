from __future__ import annotations

import os
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from flask import current_app, has_app_context

from app.teacher_console.errors import ProviderValidationError


ALLOWED_MEDIA_SOURCE_TYPES = {"local_upload", "external_url"}
ALLOWED_VIDEO_SUFFIXES = {".mp4", ".webm"}
LOCAL_MEDIA_URL_PREFIX = "/media/teacher-courses/"
REMOTE_CHECK_TIMEOUT_SECONDS = 5.0


def _media_error(message: str, *, code: str, **details) -> ProviderValidationError:
    return ProviderValidationError(
        message,
        code=code,
        details=details,
    )


def _validate_external_url(media_url: str) -> None:
    parsed = urlsplit(media_url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        raise _media_error(
            "媒体地址格式无效",
            code="media_reference_invalid",
            media_source_type="external_url",
        )


def _validate_local_media_url(media_url: str) -> str:
    parsed = urlsplit(media_url)
    filename = parsed.path.removeprefix(LOCAL_MEDIA_URL_PREFIX)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(LOCAL_MEDIA_URL_PREFIX)
        or not filename
        or "/" in filename
        or Path(filename).suffix.lower() not in ALLOWED_VIDEO_SUFFIXES
    ):
        raise _media_error(
            "本地视频地址无效",
            code="media_reference_invalid",
            media_source_type="local_upload",
        )
    return filename


def _local_media_path(filename: str) -> Path:
    configured_root = (
        current_app.config.get("COURSE_MEDIA_ROOT")
        if has_app_context()
        else None
    )
    if configured_root:
        root = Path(configured_root)
    elif has_app_context():
        root = (
            Path(current_app.root_path).parents[1]
            / "uploads"
            / "teacher-courses"
        )
    else:
        raise _media_error(
            "媒体地址不可访问",
            code="media_reference_unreachable",
            media_source_type="local_upload",
        )
    return root / filename


def validate_media_reference(
    media_source_type,
    media_url,
    *,
    transport=None,
    check_remote=False,
) -> str:
    source_type = (
        media_source_type.strip()
        if isinstance(media_source_type, str)
        else ""
    )
    if source_type not in ALLOWED_MEDIA_SOURCE_TYPES:
        raise _media_error(
            "媒体来源类型无效",
            code="media_source_type_invalid",
            field="media_source_type",
        )

    normalized_url = media_url.strip() if isinstance(media_url, str) else ""
    if not normalized_url:
        raise _media_error(
            "媒体地址不能为空",
            code="media_reference_invalid",
            field="media_url",
        )

    if source_type == "external_url":
        _validate_external_url(normalized_url)
        if not check_remote:
            return normalized_url

        try:
            with httpx.Client(
                transport=transport,
                timeout=REMOTE_CHECK_TIMEOUT_SECONDS,
                follow_redirects=False,
            ) as client:
                response = client.head(normalized_url)
        except httpx.HTTPError as error:
            raise _media_error(
                "媒体地址不可访问",
                code="media_reference_unreachable",
                media_url=normalized_url,
                reason=type(error).__name__,
            ) from error

        if not 200 <= response.status_code < 400:
            raise _media_error(
                "媒体地址不可访问",
                code="media_reference_unreachable",
                media_url=normalized_url,
                status_code=response.status_code,
            )
        return normalized_url

    filename = _validate_local_media_url(normalized_url)
    if not check_remote:
        return normalized_url

    media_path = _local_media_path(filename)
    if not media_path.is_file() or not os.access(media_path, os.R_OK):
        raise _media_error(
            "媒体地址不可访问",
            code="media_reference_unreachable",
            media_url=normalized_url,
        )
    return normalized_url
