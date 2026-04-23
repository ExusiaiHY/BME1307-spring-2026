"""Append a markdown note to the BME1307 Notion project-log page.

Usage:
    NOTION_TOKEN=... python scripts/sync_notion_notes.py \
        --markdown docs/notion_2026_04_23_notes.md \
        --title "2026-04-23 同步: Part 1 + Part 2(含 BUSAT)"

Prints how many blocks were appended. Notion caps /children POSTs at
100 blocks, so we chunk.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2026-03-11"
PAGE_ID = "344e41c3-0079-8032-bbfd-fcc5365e5ac0"
CHILDREN_BATCH = 90


def _headers(token: str, content_type: str | None = "application/json") -> dict:
    headers = {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _request(
    method: str,
    path: str,
    token: str,
    body: dict | bytes | None = None,
    content_type: str | None = "application/json",
) -> dict:
    url = f"{NOTION_API}{path}"
    data = json.dumps(body).encode("utf-8") if isinstance(body, dict) else body
    req = urllib.request.Request(url, method=method, headers=_headers(token, content_type), data=data)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = resp.read()
            if not payload:
                return {}
            return json.loads(payload.decode("utf-8"))
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"Notion API {method} {path} failed ({e.code}): {detail}")


def _text(content: str, annotations: dict | None = None) -> dict:
    node: dict = {"type": "text", "text": {"content": content, "link": None}}
    if annotations:
        node["annotations"] = annotations
    return node


_INLINE_PATTERN = re.compile(
    r"(\*\*(?P<bold>[^*]+)\*\*)"
    r"|(\*(?P<ital>[^*]+)\*)"
    r"|(`(?P<code>[^`]+)`)"
)
_IMAGE_PATTERN = re.compile(r"^!\[(?P<alt>[^\]]*)\]\((?P<src>[^)]+)\)$")


def parse_rich_text(raw: str) -> list[dict]:
    """Turn a single markdown line into Notion rich_text objects."""
    if not raw:
        return []
    nodes: list[dict] = []
    cursor = 0
    for m in _INLINE_PATTERN.finditer(raw):
        if m.start() > cursor:
            nodes.append(_text(raw[cursor:m.start()]))
        if m.group("bold") is not None:
            nodes.append(_text(m.group("bold"), {"bold": True}))
        elif m.group("ital") is not None:
            nodes.append(_text(m.group("ital"), {"italic": True}))
        elif m.group("code") is not None:
            nodes.append(_text(m.group("code"), {"code": True}))
        cursor = m.end()
    if cursor < len(raw):
        nodes.append(_text(raw[cursor:]))
    return nodes or [_text(raw)]


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": parse_rich_text(text)},
    }


def _heading(level: int, text: str) -> dict:
    key = f"heading_{min(level, 3)}"
    return {"object": "block", "type": key, key: {"rich_text": parse_rich_text(text)}}


def _bullet(text: str) -> dict:
    return {
        "object": "block",
        "type": "bulleted_list_item",
        "bulleted_list_item": {"rich_text": parse_rich_text(text)},
    }


def _numbered(text: str) -> dict:
    return {
        "object": "block",
        "type": "numbered_list_item",
        "numbered_list_item": {"rich_text": parse_rich_text(text)},
    }


def _quote(text: str) -> dict:
    return {"object": "block", "type": "quote", "quote": {"rich_text": parse_rich_text(text)}}


def _divider() -> dict:
    return {"object": "block", "type": "divider", "divider": {}}


def _code(lines: list[str], lang: str) -> dict:
    return {
        "object": "block",
        "type": "code",
        "code": {
            "rich_text": [_text("\n".join(lines))],
            "language": lang or "plain text",
        },
    }


def _callout(text: str, emoji: str = "📌") -> dict:
    return {
        "object": "block",
        "type": "callout",
        "callout": {
            "rich_text": parse_rich_text(text),
            "icon": {"type": "emoji", "emoji": emoji},
            "color": "default",
        },
    }


def _table(rows: list[list[str]]) -> dict:
    if not rows:
        return _paragraph("")
    width = max(len(r) for r in rows)
    normalized = [r + [""] * (width - len(r)) for r in rows]
    table_rows = [
        {
            "object": "block",
            "type": "table_row",
            "table_row": {"cells": [parse_rich_text(cell) for cell in row]},
        }
        for row in normalized
    ]
    return {
        "object": "block",
        "type": "table",
        "table": {
            "table_width": width,
            "has_column_header": True,
            "has_row_header": False,
            "children": table_rows,
        },
    }


def _image_external(url: str, caption: str) -> dict:
    return {
        "object": "block",
        "type": "image",
        "image": {
            "type": "external",
            "external": {"url": url},
            "caption": parse_rich_text(caption),
        },
    }


def _image_file_upload(file_upload_id: str, caption: str) -> dict:
    return {
        "object": "block",
        "type": "image",
        "image": {
            "type": "file_upload",
            "file_upload": {"id": file_upload_id},
            "caption": parse_rich_text(caption),
        },
    }


def _multipart_body(field_name: str, file_path: Path, content_type: str) -> tuple[bytes, str]:
    boundary = f"----CodexNotion{int(time.time() * 1000)}"
    file_bytes = file_path.read_bytes()
    parts = [
        f"--{boundary}\r\n".encode("utf-8"),
        (
            f'Content-Disposition: form-data; name="{field_name}"; '
            f'filename="{file_path.name}"\r\n'
        ).encode("utf-8"),
        f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"),
        file_bytes,
        b"\r\n",
        f"--{boundary}--\r\n".encode("utf-8"),
    ]
    return b"".join(parts), f"multipart/form-data; boundary={boundary}"


def _upload_file(file_path: Path, token: str, cache: dict[Path, str]) -> str:
    resolved = file_path.resolve()
    if resolved in cache:
        return cache[resolved]

    mime = mimetypes.guess_type(resolved.name)[0] or "application/octet-stream"
    created = _request(
        "POST",
        "/file_uploads",
        token,
        {
            "mode": "single_part",
            "filename": resolved.name,
            "content_type": mime,
        },
    )
    upload_id = created["id"]
    body, content_type = _multipart_body("file", resolved, mime)
    _request("POST", f"/file_uploads/{upload_id}/send", token, body=body, content_type=content_type)

    for _ in range(20):
        status = _request("GET", f"/file_uploads/{upload_id}", token)
        state = status.get("status")
        if state == "uploaded":
            cache[resolved] = upload_id
            return upload_id
        if state in {"failed", "expired"}:
            raise SystemExit(f"Notion file upload failed for {resolved}: status={state}")
        time.sleep(0.5)
    raise SystemExit(f"Timed out waiting for Notion file upload: {resolved}")


def _resolve_image_target(target: str, markdown_path: Path) -> Path:
    raw = Path(target)
    if raw.is_absolute():
        return raw
    return (markdown_path.parent / raw).resolve()


def _image_block(target: str, caption: str, markdown_path: Path, token: str, cache: dict[Path, str]) -> dict:
    if re.match(r"^https?://", target):
        return _image_external(target, caption)

    file_path = _resolve_image_target(target, markdown_path)
    if not file_path.exists():
        raise SystemExit(f"Image path not found: {target} (resolved to {file_path})")
    upload_id = _upload_file(file_path, token, cache)
    return _image_file_upload(upload_id, caption)


_NOTION_CODE_LANGS = {
    "python", "javascript", "typescript", "bash", "shell", "sh", "yaml",
    "json", "html", "css", "sql", "markdown", "matlab", "c", "c++", "java",
    "plain text",
}


def _normalize_lang(lang: str) -> str:
    lang = (lang or "").strip().lower()
    if lang == "sh":
        return "shell"
    return lang if lang in _NOTION_CODE_LANGS else "plain text"


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def _split_table_row(line: str) -> list[str]:
    cells = line.strip().strip("|").split("|")
    return [c.strip() for c in cells]


def markdown_to_blocks(md: str, markdown_path: Path, token: str) -> list[dict]:
    lines = md.splitlines()
    blocks: list[dict] = []
    upload_cache: dict[Path, str] = {}
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        if stripped.startswith("```"):
            lang = _normalize_lang(stripped[3:].strip())
            j = i + 1
            code_lines: list[str] = []
            while j < n and not lines[j].lstrip().startswith("```"):
                code_lines.append(lines[j])
                j += 1
            blocks.append(_code(code_lines, lang))
            i = j + 1
            continue

        if set(stripped) <= {"-"} and len(stripped) >= 3:
            blocks.append(_divider())
            i += 1
            continue

        if stripped.startswith("#"):
            m = re.match(r"^(#{1,6})\s+(.*)$", stripped)
            if m:
                level = len(m.group(1))
                blocks.append(_heading(level, m.group(2).strip()))
                i += 1
                continue

        if stripped.startswith("> "):
            blocks.append(_quote(stripped[2:].strip()))
            i += 1
            continue

        m = _IMAGE_PATTERN.match(stripped)
        if m:
            blocks.append(
                _image_block(
                    target=m.group("src").strip(),
                    caption=m.group("alt").strip(),
                    markdown_path=markdown_path,
                    token=token,
                    cache=upload_cache,
                )
            )
            i += 1
            continue

        if _is_table_row(line):
            table_rows: list[list[str]] = []
            while i < n and _is_table_row(lines[i]):
                row = _split_table_row(lines[i])
                is_separator = all(re.match(r"^:?-{2,}:?$", c) for c in row if c)
                if not is_separator:
                    table_rows.append(row)
                i += 1
            blocks.append(_table(table_rows))
            continue

        m = re.match(r"^(\s*)[-*+]\s+(.*)$", line)
        if m:
            blocks.append(_bullet(m.group(2).strip()))
            i += 1
            continue

        m = re.match(r"^(\s*)\d+\.\s+(.*)$", line)
        if m:
            blocks.append(_numbered(m.group(2).strip()))
            i += 1
            continue

        blocks.append(_paragraph(stripped))
        i += 1

    return blocks


def append_children(page_id: str, token: str, blocks: list[dict]) -> int:
    total = 0
    for start in range(0, len(blocks), CHILDREN_BATCH):
        chunk = blocks[start:start + CHILDREN_BATCH]
        _request("PATCH", f"/blocks/{page_id}/children", token, {"children": chunk})
        total += len(chunk)
        time.sleep(0.25)
    return total


def section_header(title: str) -> list[dict]:
    return [
        _divider(),
        _heading(2, title),
        _callout("本条记录由 sync_notion_notes.py 从 docs/ 直接追加。", emoji="🗒️"),
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--markdown", type=Path, required=True)
    parser.add_argument("--title", type=str, required=True)
    parser.add_argument("--page-id", type=str, default=PAGE_ID)
    args = parser.parse_args()

    token = os.environ.get("NOTION_TOKEN")
    if not token:
        raise SystemExit("NOTION_TOKEN environment variable is required")
    md = args.markdown.read_text(encoding="utf-8")
    body_blocks = markdown_to_blocks(md, markdown_path=args.markdown.resolve(), token=token)
    all_blocks = section_header(args.title) + body_blocks
    written = append_children(args.page_id, token, all_blocks)
    print(f"[notion] appended {written} blocks to page {args.page_id}")


if __name__ == "__main__":
    main()
