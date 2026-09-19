from __future__ import annotations

import ipaddress
import os
import socket
from pathlib import Path, PureWindowsPath
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
from flask import current_app, has_app_context

from app.teacher_console.errors import ProviderValidationError


ALLOWED_MEDIA_SOURCE_TYPES = {"local_upload", "external_url"}
ALLOWED_VIDEO_EXTENSIONS = {".mp4": "video/mp4", ".webm": "video/webm"}
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


def _resolved_public_addresses(parsed) -> list:
    host = parsed.hostname
    if not host:
        raise _media_error(
            "媒体地址不可访问",
            code="media_reference_unreachable",
            media_url=parsed.geturl(),
            reason="missing_host",
        )

    try:
        direct_ip = ipaddress.ip_address(host)
    except ValueError:
        direct_ip = None

    if direct_ip is not None:
        addresses = [direct_ip]
    else:
        try:
            address_infos = socket.getaddrinfo(
                host,
                parsed.port,
                type=socket.SOCK_STREAM,
            )
        except (OSError, UnicodeError) as error:
            raise _media_error(
                "媒体地址不可访问",
                code="media_reference_unreachable",
                media_url=parsed.geturl(),
                reason="unresolved",
            ) from error
        addresses = [
            ipaddress.ip_address(address_info[4][0])
            for address_info in address_infos
        ]

    if not addresses or any(not address.is_global for address in addresses):
        raise _media_error(
            "媒体地址不可访问",
            code="media_reference_unreachable",
            media_url=parsed.geturl(),
            reason="non_public_address",
        )
    return addresses


def _validate_local_media_url(media_url: str) -> str:
    parsed = urlsplit(media_url)
    filename = parsed.path.removeprefix(LOCAL_MEDIA_URL_PREFIX)
    windows_path = PureWindowsPath(filename)
    if (
        parsed.scheme
        or parsed.netloc
        or parsed.query
        or parsed.fragment
        or not parsed.path.startswith(LOCAL_MEDIA_URL_PREFIX)
        or not filename
        or "/" in filename
        or "\\" in filename
        or ":" in filename
        or filename in {".", ".."}
        or windows_path.drive
        or windows_path.root
        or windows_path.is_absolute()
        or len(windows_path.parts) != 1
        or windows_path.name != filename
        or Path(filename).suffix.lower() not in ALLOWED_VIDEO_EXTENSIONS
    ):
        raise _media_error(
            "本地视频地址无效",
            code="media_reference_invalid",
            media_source_type="local_upload",
        )
    return filename


def course_media_path(filename: str) -> Path:
    filename = _validate_local_media_url(
        f"{LOCAL_MEDIA_URL_PREFIX}{filename}"
    )
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


def save_course_video(file_storage, teacher_id: int) -> dict:
    filename = str(file_storage.filename or "")
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_VIDEO_EXTENSIONS:
        raise _media_error(
            "视频仅支持 MP4 或 WebM",
            code="media_reference_invalid",
            media_source_type="local_upload",
        )

    file_storage.stream.seek(0, os.SEEK_END)
    size = file_storage.stream.tell()
    file_storage.stream.seek(0)
    if size <= 0 or size > current_app.config["MAX_VIDEO_UPLOAD_BYTES"]:
        raise _media_error(
            "视频文件大小超出限制",
            code="media_reference_invalid",
            media_source_type="local_upload",
            size_bytes=size,
            max_size_bytes=current_app.config["MAX_VIDEO_UPLOAD_BYTES"],
        )

    stored_name = f"{teacher_id}-{uuid4().hex}{suffix}"
    destination = course_media_path(stored_name)
    destination.parent.mkdir(parents=True, exist_ok=True)
    file_storage.save(destination)
    return {
        "media_source_type": "local_upload",
        "media_url": f"{LOCAL_MEDIA_URL_PREFIX}{stored_name}",
        "size_bytes": size,
    }


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
        parsed_url = urlsplit(normalized_url)
        if check_remote:
            _resolved_public_addresses(parsed_url)
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

    media_path = course_media_path(filename)
    if not media_path.is_file() or not os.access(media_path, os.R_OK):
        raise _media_error(
            "媒体地址不可访问",
            code="media_reference_unreachable",
            media_url=normalized_url,
        )
    return normalized_url
