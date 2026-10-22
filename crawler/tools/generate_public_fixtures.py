"""Generate deterministic, public-safe crawler fixtures.

The generated files contain no source rows, contact columns, hidden form
state, or original attachment metadata. Run this module from the repository
root to replace the tracked evidence fixtures.
"""

from __future__ import annotations

import re
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path

from openpyxl import Workbook

from crawler.tools.public_hygiene import SYNTHETIC_AUTHOR, SYNTHETIC_MARKER


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "crawler" / "tests" / "fixtures" / "evidence"
_FIXED_DATE = datetime(2026, 1, 1, 0, 0, 0)
_LEGACY_FILES = (
    EVIDENCE / "aqsc-moa" / "2025年第三批名特优新公示表.xlsx",
    EVIDENCE / "aqsc-moa" / "2025年第三批特质农品公示表.xlsx",
    EVIDENCE
    / "cnipa"
    / "国家知识产权局关于对临晋江石榴等58个产品予以地理标志产品认定的公告（第687号）.pdf",
)


def _set_xlsx_metadata(workbook: Workbook) -> None:
    workbook.properties.creator = SYNTHETIC_AUTHOR
    workbook.properties.lastModifiedBy = SYNTHETIC_AUTHOR
    workbook.properties.title = "Synthetic crawler fixture"
    workbook.properties.subject = SYNTHETIC_MARKER
    workbook.properties.description = "No real source rows or personal data"
    workbook.properties.keywords = SYNTHETIC_MARKER
    workbook.properties.created = _FIXED_DATE
    workbook.properties.modified = _FIXED_DATE


def _normalize_xlsx_archive(path: Path) -> None:
    with zipfile.ZipFile(path) as source:
        entries = [
            (info.filename, source.read(info.filename), info.compress_type)
            for info in source.infolist()
        ]
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as target:
        for name, data, compress_type in entries:
            if name == "docProps/core.xml":
                data = re.sub(
                    rb"(<dcterms:modified[^>]*>)[^<]*(</dcterms:modified>)",
                    rb"\g<1>2026-01-01T00:00:00Z\2",
                    data,
                )
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = compress_type
            info.external_attr = 0o600 << 16
            target.writestr(info, data)


def _write_xlsx(path: Path, rows: list[list[object]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Sheet1"
    for row in rows:
        sheet.append(row)
    _set_xlsx_metadata(workbook)
    buffer = BytesIO()
    workbook.save(buffer)
    path.write_bytes(buffer.getvalue())
    _normalize_xlsx_archive(path)


def _pdf_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def build_pdf(
    pages: list[list[str] | str],
    *,
    author: str = SYNTHETIC_AUTHOR,
    title: str = "Synthetic crawler fixture",
    subject: str = SYNTHETIC_MARKER,
    keywords: str = SYNTHETIC_MARKER,
    creator: str = SYNTHETIC_AUTHOR,
    producer: str = SYNTHETIC_AUTHOR,
) -> bytes:
    """Build a small, text-extractable PDF without third-party layout tools."""
    page_texts = [
        [page] if isinstance(page, str) else list(page)
        for page in pages
    ]
    objects: dict[int, bytes] = {}
    page_ids = []
    next_id = 5
    for lines in page_texts:
        page_id = next_id
        content_id = next_id + 1
        next_id += 2
        page_ids.append(page_id)
        content = ["BT", "/F1 12 Tf", "14 TL", "50 750 Td"]
        for line in lines:
            content.append(f"({_pdf_escape(line)}) Tj")
            content.append("T*")
        content.append("ET")
        stream = "\n".join(content).encode("ascii", errors="replace")
        objects[content_id] = (
            f"<< /Length {len(stream)} >>\nstream\n".encode("ascii")
            + stream
            + b"\nendstream"
        )
        objects[page_id] = (
            f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            f"/Resources << /Font << /F1 3 0 R >> >> "
            f"/Contents {content_id} 0 R >>"
        ).encode("ascii")

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objects[2] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode(
        "ascii"
    )
    objects[3] = b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"
    objects[4] = (
        "<< "
        f"/Title ({_pdf_escape(title)}) "
        f"/Author ({_pdf_escape(author)}) "
        f"/Subject ({_pdf_escape(subject)}) "
        f"/Keywords ({_pdf_escape(keywords)}) "
        f"/Creator ({_pdf_escape(creator)}) "
        f"/Producer ({_pdf_escape(producer)}) "
        "/CreationDate (D:20260101000000+08'00') "
        "/ModDate (D:20260101000000+08'00') "
        ">>"
    ).encode("ascii", errors="replace")

    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for object_id in range(1, max(objects) + 1):
        offsets.append(len(output))
        output.extend(f"{object_id} 0 obj\n".encode("ascii"))
        output.extend(objects[object_id])
        output.extend(b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(offsets)}\n".encode("ascii"))
    output.extend(b"0000000000 65535 f\r\n")
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n\r\n".encode("ascii"))
    output.extend(
        (
            f"trailer\n<< /Size {len(offsets)} /Root 1 0 R /Info 4 0 R >>\n"
            f"startxref\n{xref}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(output)


def _html(title: str, body: str, *, job_title: str | None = None) -> str:
    title_block = (
        f'<div class="job-name">{job_title}</div>' if job_title else ""
    )
    return (
        "<!doctype html>\n"
        "<html><head>"
        '<meta charset="utf-8">'
        '<meta name="fixture-origin" content="synthetic-fixture">'
        f"<title>{title}</title>"
        "</head><body>"
        f"{title_block}{body}"
        "</body></html>\n"
    )


def generate_public_fixtures(root: Path = EVIDENCE) -> None:
    root = Path(root)
    (root / "aqsc-moa").mkdir(parents=True, exist_ok=True)
    (root / "cnipa").mkdir(parents=True, exist_ok=True)
    (root / "nongmuhr").mkdir(parents=True, exist_ok=True)
    (root / "nzrc").mkdir(parents=True, exist_ok=True)
    (root / "weather").mkdir(parents=True, exist_ok=True)
    for path in _LEGACY_FILES:
        if path.exists():
            path.unlink()

    _write_xlsx(
        root / "aqsc-moa" / "synthetic-mtyx-sample.xlsx",
        [
            ["Synthetic 名特优新 fixture"],
            ["序号", "省份", "县域", "证书编号", "产品名称", "获证单位", "生产规模", "主要生产经营单位"],
            [1, "示例省", "示例县", "SYN-MTYX-001", "示例鲅鱼圈鸡蛋", "示例获证单位甲", "10 公顷", "示例经营主体甲"],
            [2, "示例省", "示例县", "SYN-MTYX-002", "示例安溪毛蟹", "示例获证单位乙", "20 公顷", "示例经营主体乙"],
            [3, "示例省", "示例县", "SYN-MTYX-003", "示例仪征紫菜薹", "示例获证单位丙", "30 公顷", "示例经营主体丙"],
            [4, "示例省", "示例县", "SYN-MTYX-004", "示例贝母", "示例获证单位丁", "40 公顷", "示例经营主体丁"],
        ],
    )
    _write_xlsx(
        root / "aqsc-moa" / "synthetic-tepinongpin-sample.xlsx",
        [
            ["Synthetic 特质农品 fixture"],
            ["序号", "省份", "县域", "产品全称", "申请单位全称", "生产规模"],
            [1, "示例省", "示例县", "示例丹参", "示例申请单位甲", "10 公顷"],
            [2, "示例省", "示例县", "示例鱼腥草", "示例申请单位乙", "20 公顷"],
            [3, "示例省", "示例县", "示例螺丝椒", "示例申请单位丙", "30 公顷"],
            [4, "示例省", "示例县", "示例普通苹果", "示例申请单位丁", "40 公顷"],
        ],
    )

    (root / "cnipa" / "synthetic-announcement-687.pdf").write_bytes(
        build_pdf(
            [
                [
                    "SYNTHETIC-FIXTURE",
                    "Attachment 1",
                    "Synthetic geographical indication product information",
                    "Seq Product Name Province Applicant Origin Scope Remarks",
                    "1",
                    "Sample Pomegranate",
                    "Example Province",
                    "Example Applicant",
                    "Example Origin Scope",
                ],
                [
                    "SYNTHETIC-FIXTURE",
                    "Seq Product Name Province Applicant Origin Scope Remarks",
                    "2",
                    "Sample Tea",
                    "Example Province",
                    "Example Applicant",
                    "Example Origin Scope",
                ],
            ]
        )
    )

    (root / "nongmuhr" / "employ-view-13519.html").write_text(
        _html(
            "示例农业企业招聘",
            "<h1 class=\"job-name\">示例农艺师 招聘</h1>"
            "<p>示例农业企业公开岗位摘要。</p>",
        ),
        encoding="utf-8",
        newline="\n",
    )
    (root / "nongmuhr" / "employ-view-13520.html").write_text(
        _html(
            "示例农业企业招聘",
            "<h1 class=\"job-name\">示例养殖员 招聘</h1>"
            "<p>示例农业企业公开岗位摘要。</p>",
        ),
        encoding="utf-8",
        newline="\n",
    )
    (root / "nzrc" / "job-detail-8235500.html").write_text(
        _html(
            "示例农业科技招聘",
            '<h1><a href="/company/companys/90001.html">'
            "示例农业科技有限公司</a></h1>"
            "<h2>招聘职位：示例种植技术员</h2>"
            "<p>示例公开岗位摘要。</p>",
            job_title="示例种植技术员",
        ),
        encoding="utf-8",
        newline="\n",
    )
    (root / "nzrc" / "job-detail-8240109.html").write_text(
        _html(
            "示例农业科技招聘",
            '<h1><a href="/company/companys/90002.html">'
            "示例农业服务有限公司</a></h1>"
            "<h2>招聘职位：示例农业技术员</h2>"
            "<p>示例公开岗位摘要。</p>",
            job_title="示例农业技术员",
        ),
        encoding="utf-8",
        newline="\n",
    )

    (root / "weather" / "sk-beijing.json").write_text(
        'var dataSK={"nameen":"beijing","cityname":"北京",'
        '"city":"101010100","temp":"6.1","tempf":"43",'
        '"WD":"西风","wde":"W","WS":"1级","wse":"2km\\/h",'
        '"SD":"89%","sd":"89%","qy":"1017","njd":"18km",'
        '"time":"00:45","rain":"0","rain24h":"0","aqi":"23",'
        '"aqi_pm25":"23","weather":"晴","weathere":"Sunny",'
        '"weathercode":"d00","limitnumber":"不限行",'
        '"date":"10月19日(星期一)"}\n',
        encoding="utf-8",
        newline="\n",
    )
    (root / "weather" / "sk-beijing.response-headers.txt").write_text(
        "content-type: application/json\n",
        encoding="utf-8",
        newline="\n",
    )


if __name__ == "__main__":
    generate_public_fixtures()
    print(f"generated synthetic fixtures under {EVIDENCE}")
