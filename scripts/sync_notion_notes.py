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
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path


NOTION_API = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
PAGE_ID = "344e41c3-0079-8032-bbfd-fcc5365e5ac0"
CHILDREN_BATCH = 90


def _headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def _request(method: str, path: str, token: str, body: dict | None = None) -> dict:
    url = f"{NOTION_API}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, method=method, headers=_headers(token), data=data)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))
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


def markdown_to_blocks(md: str) -> list[dict]:
    lines = md.splitlines()
    blocks: list[dict] = []
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
    body_blocks = markdown_to_blocks(md)
    all_blocks = section_header(args.title) + body_blocks
    written = append_children(args.page_id, token, all_blocks)
    print(f"[notion] appended {written} blocks to page {args.page_id}")


if __name__ == "__main__":
    main()
