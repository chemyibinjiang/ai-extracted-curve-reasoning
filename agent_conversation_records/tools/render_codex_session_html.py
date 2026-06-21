from __future__ import annotations

import base64
import csv
import hashlib
import html
import json
import os
import argparse
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any
from urllib.parse import unquote

from PIL import Image


SESSION_SHORT_NAMES = {
    "019e5a99-d4b4-7b33-9c00-74b8d0f6c184": "s1",
    "019eb222-0283-7721-a3de-1c69905a9035": "s2",
}

OUT_ROOT = Path(__file__).resolve().parents[1]
TRANSCRIPT_DIR = OUT_ROOT / "rendered_transcripts"
IMAGE_ROOT = TRANSCRIPT_DIR / "assets"
LEGACY_IMAGE_ROOT = OUT_ROOT / "extracted_images"
MANIFEST_PATH = OUT_ROOT / "export_manifest.csv"
IMAGE_MANIFEST_PATH = OUT_ROOT / "image_manifest.csv"
FILE_MANIFEST_PATH = OUT_ROOT / "linked_file_manifest.csv"
CHECKSUM_PATH = OUT_ROOT / "checksums_sha256.csv"
README_PATH = OUT_ROOT / "README.md"

MAX_DISPLAY_IMAGE_DIMENSION = 2400
DATA_URI_RE = re.compile(r"^data:(image/[a-zA-Z0-9.+-]+);base64,(.*)$", re.DOTALL)
MARKDOWN_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")
MARKDOWN_LINK_RE = re.compile(r"(?<!!)\[([^\]]+)\]\(([^)\n]+)\)")
MARKDOWN_ANY_LINK_RE = re.compile(r"(!?)\[([^\]]*)\]\(([^)\n]+)\)")
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".svg"}
FENCED_CODE_RE = re.compile(r"```([A-Za-z0-9_+.-]*)\n?(.*?)```", re.DOTALL)
INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
WINDOWS_USER_PATH_RE = re.compile(r"[A-Za-z]:[\\/]+Users[\\/]+[^\\/\s\])>\"']+", re.IGNORECASE)
POSIX_USER_PATH_RE = re.compile(r"/Users/[^/\s\])>\"']+", re.IGNORECASE)


def path_variants(path: Path) -> set[str]:
    text = str(path)
    variants = {text, text.replace("\\", "/")}
    try:
        resolved = str(path.resolve())
        variants.add(resolved)
        variants.add(resolved.replace("\\", "/"))
    except Exception:
        pass
    return variants


def public_path_replacements() -> list[tuple[str, str]]:
    home = Path.home()
    repo_root = OUT_ROOT.parent
    replacements: list[tuple[Path, str]] = [
        (repo_root, "[PUBLIC_REPO]"),
        (home / "Desktop" / "LSV_paper" / "LSV_agent_analysis", "[ANALYSIS_WORKSPACE]"),
        (home / "Desktop" / "LSV_paper", "[PROJECT_WORKSPACE]"),
        (home / ".codex" / "sessions", "[CODEX_SESSION_LOGS]"),
        (home, "[USER_HOME]"),
    ]
    pairs: list[tuple[str, str]] = []
    for path, label in replacements:
        for variant in path_variants(path):
            pairs.append((variant, label))
    pairs.sort(key=lambda item: len(item[0]), reverse=True)
    return pairs


def sanitize_public_text(value: Any) -> str:
    text = "" if value is None else str(value)
    for needle, replacement in public_path_replacements():
        text = text.replace(needle, replacement)
    text = WINDOWS_USER_PATH_RE.sub("[USER_HOME]", text)
    text = POSIX_USER_PATH_RE.sub("[USER_HOME]", text)
    return text


def public_path_label(value: Any) -> str:
    return sanitize_public_text(value)


def is_probably_local_path_reference(value: str) -> bool:
    stripped = value.strip().strip("<>`'\"")
    return bool(
        stripped.startswith("file:///")
        or re.match(r"^/?[A-Za-z]:[\\/]", stripped)
        or re.match(r"^/mnt/[a-zA-Z]/", stripped)
        or re.match(r"^/Users/[^/]+/", stripped)
    )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def text_from_content(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    parts: list[str] = []
    for item in content:
        if isinstance(item, dict) and item.get("type") in {"input_text", "output_text", "text", "summary_text"}:
            parts.append(item.get("text") or "")
    return "\n".join(part for part in parts if part)


def normalize_local_image_path(url: str) -> Path | None:
    path = normalize_local_path(url)
    if path is None or path.suffix.lower() not in IMAGE_SUFFIXES:
        return None
    return path


def normalize_local_path(url: str) -> Path | None:
    value = unquote(url.strip().strip("<>"))
    value = value.strip("`'\"")
    if value.startswith("file:///"):
        value = value[len("file:///") :]
    if value.startswith("/C:/") or value.startswith("/D:/") or value.startswith("/Z:/"):
        value = value[1:]
    if re.match(r"^/mnt/[a-zA-Z]/", value):
        drive = value[5].upper()
        value = f"{drive}:/" + value[7:]
    posix_home = re.match(r"^/Users/[^/]+/(.*)$", value)
    if posix_home:
        value = str(Path.home() / posix_home.group(1))
    value = value.replace("/", "\\")
    if not re.match(r"^[A-Za-z]:\\", value):
        return None
    path = Path(value)
    if not path.exists():
        match = re.match(r"^(.+\.[A-Za-z0-9_+-]+):\d+$", value)
        if match:
            candidate = Path(match.group(1))
            if candidate.exists():
                path = candidate
    return path


def relative_to_transcript(path: Path) -> str:
    return Path(os.path.relpath(path, TRANSCRIPT_DIR)).as_posix()


def image_dimensions(path: Path) -> tuple[int | None, int | None, str]:
    if path.suffix.lower() == ".svg":
        return None, None, "svg"
    try:
        with Image.open(path) as image:
            return image.width, image.height, image.mode
    except Exception:
        return None, None, "unreadable"


def make_browser_display_copy(source_path: Path, out_path: Path) -> dict[str, Any]:
    if source_path.suffix.lower() == ".svg":
        shutil.copy2(source_path, out_path)
        width, height, mode = image_dimensions(out_path)
        return {"display_width": width, "display_height": height, "display_mode": mode, "resized": False}

    with Image.open(source_path) as image:
        image.load()
        source_width, source_height = image.size
        resized = False

        if image.mode in {"RGBA", "LA"}:
            background = Image.new("RGBA", image.size, (255, 255, 255, 255))
            background.alpha_composite(image.convert("RGBA"))
            image = background.convert("RGB")
        elif image.mode not in {"RGB", "L"}:
            image = image.convert("RGB")

        max_dimension = max(image.size)
        if max_dimension > MAX_DISPLAY_IMAGE_DIMENSION:
            scale = MAX_DISPLAY_IMAGE_DIMENSION / max_dimension
            new_size = (max(1, round(image.width * scale)), max(1, round(image.height * scale)))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            resized = True

        save_kwargs: dict[str, Any] = {}
        if out_path.suffix.lower() == ".png":
            save_kwargs = {"optimize": True}
        elif out_path.suffix.lower() in {".jpg", ".jpeg"}:
            save_kwargs = {"quality": 92, "optimize": True}
        image.save(out_path, **save_kwargs)
        return {
            "source_width": source_width,
            "source_height": source_height,
            "display_width": image.width,
            "display_height": image.height,
            "display_mode": image.mode,
            "resized": resized,
        }


def copy_linked_image(
    source_path: Path,
    image_dir: Path,
    session_id: str,
    source_map: dict[str, str],
    image_rows: list[dict[str, Any]],
) -> str | None:
    if not source_path.exists():
        return None
    resolved = str(source_path.resolve())
    key = resolved.lower()
    if key in source_map:
        return source_map[key]

    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:12]
    linked_dir = image_dir / "f"
    linked_dir.mkdir(parents=True, exist_ok=True)
    out_path = linked_dir / f"img_{len(image_rows) + 1:04d}_{digest}{source_path.suffix.lower()}"
    source_width, source_height, source_mode = image_dimensions(source_path)
    display_info = make_browser_display_copy(source_path, out_path)
    rel = relative_to_transcript(out_path)
    source_map[key] = rel
    image_rows.append(
        {
            "session_id": session_id,
            "kind": "linked_local_figure",
            "source_path": public_path_label(resolved),
            "output_path": str(out_path.relative_to(OUT_ROOT)),
            "relative_link": rel,
            "source_bytes": source_path.stat().st_size,
            "output_bytes": out_path.stat().st_size,
            "source_width": source_width,
            "source_height": source_height,
            "source_mode": source_mode,
            "display_width": display_info.get("display_width"),
            "display_height": display_info.get("display_height"),
            "display_mode": display_info.get("display_mode"),
            "resized": display_info.get("resized", False),
            "status": "ok",
        }
    )
    return rel


def copy_linked_file(
    source_path: Path,
    image_dir: Path,
    source_map: dict[str, str],
    file_rows: list[dict[str, Any]],
    session_id: str,
) -> str | None:
    if not source_path.exists() or not source_path.is_file():
        return None
    resolved = str(source_path.resolve())
    key = resolved.lower()
    if key in source_map:
        return source_map[key]

    suffix = source_path.suffix.lower() or ".dat"
    digest = hashlib.sha256(resolved.encode("utf-8")).hexdigest()[:12]
    file_dir = image_dir / "files"
    file_dir.mkdir(parents=True, exist_ok=True)
    out_path = file_dir / f"file_{len(file_rows) + 1:04d}_{digest}{suffix}"
    shutil.copy2(source_path, out_path)
    rel = relative_to_transcript(out_path)
    source_map[key] = rel
    file_rows.append(
        {
            "session_id": session_id,
            "source_path": public_path_label(resolved),
            "output_path": str(out_path.relative_to(OUT_ROOT)),
            "relative_link": rel,
            "source_bytes": source_path.stat().st_size,
            "output_bytes": out_path.stat().st_size,
            "extension": suffix,
            "status": "ok",
        }
    )
    return rel


def extract_embedded_image(data_uri: str, image_dir: Path, session_id: str, stem: str, image_rows: list[dict[str, Any]]) -> str | None:
    match = DATA_URI_RE.match(data_uri)
    if not match:
        return None
    mime, payload = match.groups()
    ext = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }.get(mime.lower(), ".bin")
    image_dir.mkdir(parents=True, exist_ok=True)
    raw_path = image_dir / f"raw_{len(image_rows) + 1:04d}{ext}"
    out_path = image_dir / f"img_{len(image_rows) + 1:04d}{ext}"
    raw_path.write_bytes(base64.b64decode(payload))
    source_width, source_height, source_mode = image_dimensions(raw_path)
    display_info = make_browser_display_copy(raw_path, out_path)
    raw_path.unlink(missing_ok=True)
    rel = relative_to_transcript(out_path)
    image_rows.append(
        {
            "session_id": session_id,
            "kind": "embedded_input_image",
            "source_path": "embedded data URI",
            "output_path": str(out_path.relative_to(OUT_ROOT)),
            "relative_link": rel,
            "source_bytes": "",
            "output_bytes": out_path.stat().st_size,
            "source_width": source_width,
            "source_height": source_height,
            "source_mode": source_mode,
            "display_width": display_info.get("display_width"),
            "display_height": display_info.get("display_height"),
            "display_mode": display_info.get("display_mode"),
            "resized": display_info.get("resized", False),
            "status": "ok",
        }
    )
    return rel


def data_uri_from_content_item(item: dict[str, Any]) -> str | None:
    for key in ("image_url", "url", "data"):
        value = item.get(key)
        if isinstance(value, str) and value.startswith("data:image/"):
            return value
    return None


def message_images(content: Any, image_dir: Path, session_id: str, message_index: int, image_rows: list[dict[str, Any]]) -> list[str]:
    if not isinstance(content, list):
        return []
    paths: list[str] = []
    image_index = 1
    for item in content:
        if not isinstance(item, dict) or item.get("type") != "input_image":
            continue
        data_uri = data_uri_from_content_item(item)
        if not data_uri:
            continue
        rel = extract_embedded_image(data_uri, image_dir, session_id, f"{session_id}_msg{message_index:05d}_img{image_index:02d}", image_rows)
        if rel:
            paths.append(rel)
            image_index += 1
    return paths


def rewrite_local_markdown_image_refs(
    text: str,
    image_dir: Path,
    session_id: str,
    source_map: dict[str, str],
    image_rows: list[dict[str, Any]],
    missing_refs: list[str],
) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        alt, url = match.groups()
        source_path = normalize_local_image_path(url)
        if source_path is None:
            return match.group(0)
        rel = copy_linked_image(source_path, image_dir, session_id, source_map, image_rows)
        if rel is None:
            missing_refs.append(str(source_path))
            return match.group(0)
        count += 1
        return f"![{alt}]({rel})"

    return MARKDOWN_IMAGE_RE.sub(replace, text), count


def rewrite_local_markdown_file_refs(
    text: str,
    image_dir: Path,
    session_id: str,
    image_source_map: dict[str, str],
    file_source_map: dict[str, str],
    image_rows: list[dict[str, Any]],
    file_rows: list[dict[str, Any]],
    missing_refs: list[str],
) -> tuple[str, int]:
    count = 0

    def replace(match: re.Match[str]) -> str:
        nonlocal count
        label, url = match.groups()
        source_path = normalize_local_path(url)
        if source_path is None:
            return match.group(0)
        if source_path.suffix.lower() in IMAGE_SUFFIXES:
            rel = copy_linked_image(source_path, image_dir, session_id, image_source_map, image_rows)
        else:
            rel = copy_linked_file(source_path, image_dir, file_source_map, file_rows, session_id)
        if rel is None:
            missing_refs.append(str(source_path))
            return match.group(0)
        count += 1
        return f"[{label}]({rel})"

    return MARKDOWN_LINK_RE.sub(replace, text), count


def classify_note(role: str, text: str) -> str:
    if role != "user":
        return "message"
    stripped = text.strip()
    if stripped.startswith("<environment_context>"):
        return "context"
    if stripped.startswith("<turn_aborted>"):
        return "interruption"
    return "message"


def parse_session(path: Path, session_id: str) -> dict[str, Any]:
    image_dir = IMAGE_ROOT / SESSION_SHORT_NAMES.get(session_id, session_id[:8])
    if image_dir.exists() and image_dir.resolve().is_relative_to(IMAGE_ROOT.resolve()):
        shutil.rmtree(image_dir)

    messages: list[dict[str, Any]] = []
    session_meta: list[dict[str, Any]] = []
    payload_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    tool_counts: Counter[str] = Counter()
    source_map: dict[str, str] = {}
    missing_refs: list[str] = []
    image_rows: list[dict[str, Any]] = []
    linked_ref_count = 0
    compacted_count = 0
    line_count = 0

    with path.open("r", encoding="utf-8", errors="replace") as f:
        for line_no, line in enumerate(f, start=1):
            line_count = line_no
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            timestamp = obj.get("timestamp", "")
            outer_type = obj.get("type")
            payload = obj.get("payload") or {}

            if outer_type == "session_meta":
                session_meta.append(
                    {
                        "line": line_no,
                        "id": payload.get("id"),
                        "forked_from_id": payload.get("forked_from_id"),
                        "timestamp": payload.get("timestamp"),
                        "cwd": public_path_label(payload.get("cwd")),
                        "originator": payload.get("originator"),
                        "cli_version": payload.get("cli_version"),
                    }
                )
                continue

            if outer_type == "compacted":
                compacted_count += 1
                replacement = payload.get("replacement_history") or []
                summary = public_path_label(payload.get("message") or f"Compaction event containing {len(replacement)} replacement history item(s).")
                messages.append({"timestamp": timestamp, "line": line_no, "role": "compaction", "kind": "compaction", "text": summary, "images": []})
                continue

            if outer_type != "response_item":
                continue

            payload_type = payload.get("type", "")
            payload_counts[payload_type] += 1

            if payload_type == "message":
                role = payload.get("role", "")
                role_counts[role] += 1
                if role not in {"user", "assistant"}:
                    continue
                content = payload.get("content")
                text = text_from_content(content)
                images = message_images(content, image_dir, session_id, len(messages) + 1, image_rows)
                text, added = rewrite_local_markdown_image_refs(text, image_dir, session_id, source_map, image_rows, missing_refs)
                linked_ref_count += added
                if text or images:
                    messages.append(
                        {
                            "timestamp": timestamp,
                            "line": line_no,
                            "role": role,
                            "kind": classify_note(role, text),
                            "text": text,
                            "images": images,
                        }
                    )
            elif payload_type in {"function_call", "custom_tool_call", "tool_search_call", "web_search_call"}:
                name = payload.get("name") or payload.get("tool_name") or payload.get("server") or "unknown"
                tool_counts[str(name)] += 1

    return {
        "session_id": session_id,
            "source_path": public_path_label(path),
        "source_size_bytes": path.stat().st_size,
        "source_sha256": sha256_file(path),
        "line_count": line_count,
        "session_meta": session_meta,
        "payload_counts": dict(payload_counts),
        "role_counts": dict(role_counts),
        "tool_counts": dict(tool_counts),
        "compacted_count": compacted_count,
        "messages": messages,
        "embedded_image_count": sum(1 for row in image_rows if row["kind"] == "embedded_input_image"),
        "linked_local_image_reference_count": linked_ref_count,
        "linked_local_image_unique_count": len(source_map),
        "missing_local_image_refs": sorted(set(missing_refs)),
        "image_rows": image_rows,
    }


def render_inline_markdown(text: str, convert_breaks: bool = True) -> str:
    code_chunks: list[str] = []

    def protect_code(match: re.Match[str]) -> str:
        token = f"\uE000CODE{len(code_chunks)}\uE001"
        code_chunks.append(f"<code>{html.escape(sanitize_public_text(match.group(1)))}</code>")
        return token

    protected = INLINE_CODE_RE.sub(protect_code, sanitize_public_text(text))
    rendered = render_inline_no_code(protected)
    for index, code_html in enumerate(code_chunks):
        rendered = rendered.replace(f"\uE000CODE{index}\uE001", code_html)
    return rendered.replace("\n", "<br>\n") if convert_breaks else rendered


def render_inline_no_code(text: str) -> str:
    rendered = html.escape(sanitize_public_text(text))
    rendered = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", rendered, flags=re.DOTALL)
    rendered = re.sub(r"__(.+?)__", r"<strong>\1</strong>", rendered, flags=re.DOTALL)
    rendered = re.sub(r"~~(.+?)~~", r"<del>\1</del>", rendered, flags=re.DOTALL)
    return rendered


def is_table_separator(line: str) -> bool:
    stripped = line.strip()
    if not (stripped.startswith("|") and stripped.endswith("|")):
        return False
    cells = [cell.strip() for cell in stripped.strip("|").split("|")]
    return bool(cells) and all(re.fullmatch(r":?-{3,}:?", cell or "") for cell in cells)


def render_table(lines: list[str]) -> str:
    rows = [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in lines]
    header = rows[0]
    body = rows[2:]
    html_rows = [
        "<table class=\"md-table\"><thead><tr>"
        + "".join(f"<th>{render_inline_markdown(cell, convert_breaks=False)}</th>" for cell in header)
        + "</tr></thead><tbody>"
    ]
    for row in body:
        html_rows.append(
            "<tr>"
            + "".join(f"<td>{render_inline_markdown(cell, convert_breaks=False)}</td>" for cell in row)
            + "</tr>"
        )
    html_rows.append("</tbody></table>")
    return "".join(html_rows)


def render_normal_markdown(text: str) -> str:
    lines = text.splitlines()
    out: list[str] = []
    buffer: list[str] = []

    def flush_buffer() -> None:
        if buffer:
            out.append(render_inline_markdown("\n".join(buffer)))
            buffer.clear()

    i = 0
    while i < len(lines):
        if i + 1 < len(lines) and lines[i].strip().startswith("|") and is_table_separator(lines[i + 1]):
            flush_buffer()
            table_lines = [lines[i], lines[i + 1]]
            i += 2
            while i < len(lines) and lines[i].strip().startswith("|"):
                table_lines.append(lines[i])
                i += 1
            out.append(render_table(table_lines))
            continue
        buffer.append(lines[i])
        i += 1
    flush_buffer()
    return "<br>\n".join(part for part in out if part)


def render_markdown_text_preserving_links(text: str) -> str:
    chunks: list[str] = []
    pos = 0
    for match in FENCED_CODE_RE.finditer(text):
        chunks.append(render_markdown_links_and_inline(text[pos : match.start()]))
        language = html.escape(match.group(1))
        code = html.escape(sanitize_public_text(match.group(2).rstrip("\n")))
        lang_class = f" class=\"language-{language}\"" if language else ""
        chunks.append(f"<pre><code{lang_class}>{code}</code></pre>")
        pos = match.end()
    chunks.append(render_markdown_links_and_inline(text[pos:]))
    return "".join(chunks)


def render_markdown_links_and_inline(text: str) -> str:
    chunks: list[str] = []
    pos = 0
    for match in MARKDOWN_ANY_LINK_RE.finditer(text):
        chunks.append(render_normal_markdown(text[pos : match.start()]))
        bang, label, url = match.groups()
        label_text = render_inline_markdown(label or "Linked figure", convert_breaks=False)
        alt_text = html.escape(sanitize_public_text(label or "Linked figure"))
        url_text = html.escape(url)
        if bang:
            if is_probably_local_path_reference(url) and normalize_local_path(url) is None:
                chunks.append(
                    '<figure class="linked-figure missing-figure">'
                    f"<figcaption>{label_text} (local figure reference unavailable in public transcript)</figcaption>"
                    "</figure>"
                )
            else:
                chunks.append(
                    f'<figure class="linked-figure"><a href="{url_text}"><img decoding="async" src="{url_text}" alt="{alt_text}"></a>'
                    f"<figcaption>{label_text}</figcaption></figure>"
                )
        elif normalize_local_path(url) is not None:
            local_path = normalize_local_path(url)
            display_label = label
            if any(marker in label for marker in ("C:\\", "C:/", "/C:", "/Users/", "/mnt/")) and local_path is not None:
                display_label = local_path.name or local_path.parent.name
            chunks.append(f'<span class="local-file-ref">{html.escape(sanitize_public_text(display_label))}</span>')
        else:
            safe_url = "#" if is_probably_local_path_reference(url) else url_text
            chunks.append(f'<a href="{safe_url}">{label_text}</a>')
        pos = match.end()
    chunks.append(render_normal_markdown(text[pos:]))
    return "".join(chunks)


def render_public_markdown_text(text: str) -> str:
    def replace(match: re.Match[str]) -> str:
        bang, label, url = match.groups()
        if not is_probably_local_path_reference(url):
            return match.group(0)
        local_path = normalize_local_path(url)
        if local_path is not None:
            display_label = local_path.name or label or "local file"
        else:
            display_label = label or "local file"
        display_label = sanitize_public_text(display_label)
        if bang:
            return f"**{display_label}** *(local figure reference not exported)*"
        return f"**{display_label}**"

    return sanitize_public_text(MARKDOWN_ANY_LINK_RE.sub(replace, text))


def render_html(parsed: dict[str, Any]) -> str:
    tool_rows = "".join(
        f"<tr><td>{html.escape(name)}</td><td>{count}</td></tr>"
        for name, count in sorted(parsed["tool_counts"].items(), key=lambda x: (-x[1], x[0]))[:20]
    )

    cards: list[str] = []
    for i, message in enumerate(parsed["messages"], start=1):
        role = message["role"]
        kind = message["kind"]
        label = {"user": "User", "assistant": "Assistant", "compaction": "Compaction"}.get(role, role.title())
        css_role = "assistant" if role == "assistant" else "user" if role == "user" else "context"
        if kind in {"context", "interruption", "compaction"}:
            css_role = "context"
            label = kind.title()
        image_html = ""
        for rel in message["images"]:
            image_html += (
                f'<figure class="embedded-figure"><a href="{html.escape(rel)}"><img decoding="async" '
                f'src="{html.escape(rel)}" alt="Extracted image from message {i}"></a>'
                f"<figcaption>Extracted image from message {i}</figcaption></figure>"
            )
        cards.append(
            f'<article class="message {css_role}" id="m{i}">'
            f'<header><span class="role">{label}</span><span class="time">{html.escape(message["timestamp"])}</span>'
            f'<span class="line">JSONL line {message["line"]}</span></header>'
            f'<div class="body">{render_markdown_text_preserving_links(message["text"])}{image_html}</div>'
            "</article>"
        )

    css = """
body { margin: 0; font-family: Arial, Helvetica, sans-serif; color: #172033; background: #f6f8fb; line-height: 1.48; }
.page { max-width: 1220px; margin: 0 auto; padding: 28px 32px 64px; }
h1 { margin: 0 0 8px; font-size: 30px; }
h2 { margin-top: 34px; border-bottom: 1px solid #d9e0ea; padding-bottom: 8px; }
.subtitle, .small { color: #5e6a7d; }
.notice { background: #fff8e7; border: 1px solid #f1d48a; border-radius: 8px; padding: 12px 14px; margin: 18px 0; }
.summary-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(205px, 1fr)); gap: 12px; margin: 18px 0; }
.metric { background: white; border: 1px solid #dfe6ef; border-radius: 8px; padding: 12px 14px; box-shadow: 0 1px 2px rgba(13,35,67,.04); }
.metric .value { display: block; font-weight: 700; font-size: 20px; color: #0f3f7a; }
.metric .label { display: block; font-size: 13px; color: #66738a; }
table { border-collapse: collapse; width: 100%; background: white; margin: 12px 0 20px; }
th, td { border: 1px solid #dfe6ef; padding: 8px 10px; vertical-align: top; font-size: 13px; }
th { background: #eef3f8; text-align: left; }
.md-table { margin: 10px 0 14px; }
.md-table th, .md-table td { font-size: 13px; }
.message { background: white; border: 1px solid #dfe6ef; border-left: 6px solid #8793a5; border-radius: 8px; margin: 14px 0; overflow: hidden; box-shadow: 0 1px 2px rgba(13,35,67,.04); }
.message.user { border-left-color: #1d64b7; }
.message.assistant { border-left-color: #147a5a; }
.message.context { border-left-color: #8c6a00; background: #fffdf7; }
.message header { display: flex; gap: 12px; align-items: baseline; flex-wrap: wrap; padding: 9px 12px; background: #f7f9fc; border-bottom: 1px solid #e6edf5; }
.message.context header { background: #fff7dd; }
.role { font-weight: 700; }
.time, .line { color: #637188; font-size: 12px; }
.body { padding: 13px 14px; overflow-wrap: anywhere; font-size: 14px; }
figure { margin: 12px 0 18px; }
figure img { display: block; width: auto; max-width: 100%; max-height: none; border: 1px solid #cfd8e5; border-radius: 6px; background: white; }
figcaption { font-size: 12px; color: #66738a; margin-top: 5px; }
a { color: #155db8; }
.local-file-ref { color: #155db8; font-weight: 700; overflow-wrap: anywhere; }
.local-file-ref::before { content: "["; color: #7b8798; }
.local-file-ref::after { content: "]"; color: #7b8798; }
code, pre { font-family: Consolas, "Courier New", monospace; }
code { background: #eef3f8; border: 1px solid #d9e3ef; border-radius: 4px; padding: 0 4px; }
pre { background: #0f172a; color: #e5edf8; padding: 12px 14px; border-radius: 6px; overflow-x: auto; white-space: pre; }
pre code { background: transparent; border: 0; padding: 0; color: inherit; }
"""

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Codex session transcript: {html.escape(parsed["session_id"])}</title>
<style>{css}</style>
</head>
<body>
<main class="page">
<h1>Codex session transcript: {html.escape(parsed["session_id"])}</h1>
<p class="subtitle">Readable transcript rendered from the local Codex JSONL session log.</p>
<div class="notice">This HTML focuses on user/assistant-visible messages and discussion figures. Developer/system prompts and full tool payloads are omitted from the readable view; the raw JSONL record is identified by session ID and SHA-256 checksum without exposing private local paths.</div>
<section class="summary-grid">
<div class="metric"><span class="value">{parsed["line_count"]:,}</span><span class="label">JSONL lines</span></div>
<div class="metric"><span class="value">{len(parsed["messages"]):,}</span><span class="label">rendered messages/notes</span></div>
<div class="metric"><span class="value">{parsed["embedded_image_count"]:,}</span><span class="label">embedded images extracted</span></div>
<div class="metric"><span class="value">{parsed["linked_local_image_unique_count"]:,}</span><span class="label">linked local figures exported</span></div>
<div class="metric"><span class="value">{parsed["source_size_bytes"] / (1024 * 1024):.1f} MB</span><span class="label">raw log size</span></div>
</section>
<h2>Raw Log Provenance</h2>
<table><tr><th>Source JSONL</th><td>{html.escape(public_path_label(parsed["source_path"]))}</td></tr><tr><th>SHA-256</th><td><code>{html.escape(parsed["source_sha256"])}</code></td></tr></table>
<h2>Tool Activity Summary</h2>
<p class="small">Tool calls are counted for provenance but not expanded in the readable transcript.</p>
<table><tr><th>Tool</th><th>Calls</th></tr>{tool_rows}</table>
<h2>Conversation</h2>
{''.join(cards)}
</main>
</body>
</html>
"""


def render_markdown(parsed: dict[str, Any]) -> str:
    lines = [
        f"# Codex session transcript: {parsed['session_id']}",
        "",
        f"- Source JSONL: `{public_path_label(parsed['source_path'])}`",
        f"- SHA-256: `{parsed['source_sha256']}`",
        f"- Rendered messages/notes: {len(parsed['messages']):,}",
        f"- Embedded images extracted: {parsed['embedded_image_count']:,}",
        f"- Linked local image references exported: {parsed['linked_local_image_reference_count']:,}",
        f"- Unique linked local figures exported: {parsed['linked_local_image_unique_count']:,}",
        "",
        "## Conversation",
        "",
    ]
    for i, message in enumerate(parsed["messages"], start=1):
        label = message["role"].title()
        if message["kind"] in {"context", "interruption", "compaction"}:
            label = message["kind"].title()
        lines.extend([f"### {i}. {label}", "", f"`{message['timestamp']}` - JSONL line `{message['line']}`", "", render_public_markdown_text(message["text"]), ""])
        for rel in message["images"]:
            lines.extend([f"![Extracted image from message {i}]({rel})", ""])
    return "\n".join(lines)


def write_readme(rows: list[dict[str, Any]]) -> None:
    text = """# Agent Conversation Records

This folder contains readable HTML/Markdown renderings of the two Codex sessions used for the dataset-augmented AI-agent analysis.

The raw Codex JSONL files are archived as `raw_codex_session_jsonl.zip`. The readable HTML/Markdown files are public-safe renderings for inspection, while `export_manifest.csv` and `checksums_sha256.csv` record the session ID, file size, line count, and SHA-256 checksum for each raw log.

Private workstation paths are replaced with placeholders in the public renderings:

- `[PUBLIC_REPO]`: this public repository root.
- `[ANALYSIS_WORKSPACE]`: local working folder used by the analysis agents.
- `[PROJECT_WORKSPACE]`: local project workspace used during manuscript preparation.
- `[CODEX_SESSION_LOGS]`: local Codex raw session log directory.
- `[USER_HOME]`: local user home directory.

Local figure references that appeared in the conversation are exported into `rendered_transcripts/assets/` and rewritten as relative links. Large raster figures are converted into browser-friendly display copies with white backgrounds and capped dimensions; the original source figures remain preserved in the raw analysis archive.

Ordinary local file references to CSV, Python, Markdown, PDF, or other analysis files are rendered as blue non-clickable local-file references. They are intentionally not copied into the HTML package, because the full raw analysis folder is preserved separately in the raw archive.

## Rendered Sessions

"""
    for row in rows:
        sid = row["session_id"]
        text += f"- `{sid}`: `rendered_transcripts/{sid}.html`\n"
    README_PATH.write_text(text, encoding="utf-8")


def clean_output_dirs() -> None:
    for folder in [TRANSCRIPT_DIR, LEGACY_IMAGE_ROOT]:
        if folder.exists() and folder.resolve().is_relative_to(OUT_ROOT.resolve()):
            shutil.rmtree(folder)
    TRANSCRIPT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_ROOT.mkdir(parents=True, exist_ok=True)


def parse_session_args() -> dict[str, Path]:
    parser = argparse.ArgumentParser(
        description="Render selected local Codex JSONL sessions into public-safe HTML/Markdown transcripts."
    )
    parser.add_argument(
        "--session",
        action="append",
        required=True,
        metavar="SESSION_ID=JSONL_PATH",
        help="Session ID and local JSONL path. Repeat once per session.",
    )
    args = parser.parse_args()

    sessions: dict[str, Path] = {}
    for item in args.session:
        if "=" not in item:
            raise SystemExit(f"Invalid --session value: {item!r}; expected SESSION_ID=JSONL_PATH")
        session_id, source = item.split("=", 1)
        session_id = session_id.strip()
        source_path = Path(source.strip().strip('"'))
        if not session_id:
            raise SystemExit(f"Invalid --session value: {item!r}; missing session ID")
        sessions[session_id] = source_path
    return sessions


def main() -> None:
    sessions = parse_session_args()
    clean_output_dirs()
    manifest_rows: list[dict[str, Any]] = []
    checksum_rows: list[dict[str, str]] = []
    all_image_rows: list[dict[str, Any]] = []

    for session_id, source_path in sessions.items():
        if not source_path.exists():
            raise FileNotFoundError(source_path)
        parsed = parse_session(source_path, session_id)
        all_image_rows.extend(parsed["image_rows"])
        html_path = TRANSCRIPT_DIR / f"{session_id}.html"
        md_path = TRANSCRIPT_DIR / f"{session_id}.md"
        html_path.write_text(render_html(parsed), encoding="utf-8")
        md_path.write_text(render_markdown(parsed), encoding="utf-8")
        manifest_rows.append(
            {
                "session_id": session_id,
                "source_jsonl": public_path_label(parsed["source_path"]),
                "source_size_bytes": parsed["source_size_bytes"],
                "source_sha256": parsed["source_sha256"],
                "jsonl_line_count": parsed["line_count"],
                "rendered_message_count": len(parsed["messages"]),
                "embedded_image_count": parsed["embedded_image_count"],
                "linked_local_image_reference_count": parsed["linked_local_image_reference_count"],
                "linked_local_image_unique_count": parsed["linked_local_image_unique_count"],
                "missing_local_image_ref_count": len(parsed["missing_local_image_refs"]),
                "html_transcript": str(html_path.relative_to(OUT_ROOT)),
                "markdown_transcript": str(md_path.relative_to(OUT_ROOT)),
            }
        )
        checksum_rows.extend(
            [
                {"path": public_path_label(parsed["source_path"]), "sha256": parsed["source_sha256"], "kind": "raw_jsonl"},
                {"path": str(html_path.relative_to(OUT_ROOT)), "sha256": sha256_file(html_path), "kind": "rendered_html"},
                {"path": str(md_path.relative_to(OUT_ROOT)), "sha256": sha256_file(md_path), "kind": "rendered_markdown"},
            ]
        )

    with MANIFEST_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(manifest_rows[0].keys()))
        writer.writeheader()
        writer.writerows(manifest_rows)
    with IMAGE_MANIFEST_PATH.open("w", newline="", encoding="utf-8") as f:
        fieldnames = [
            "session_id",
            "kind",
            "source_path",
            "output_path",
            "relative_link",
            "source_bytes",
            "output_bytes",
            "source_width",
            "source_height",
            "source_mode",
            "display_width",
            "display_height",
            "display_mode",
            "resized",
            "status",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(all_image_rows)
    with CHECKSUM_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["path", "sha256", "kind"])
        writer.writeheader()
        writer.writerows(checksum_rows)
    write_readme(manifest_rows)
    print(f"Wrote {len(manifest_rows)} transcript set(s) to {OUT_ROOT}")
    print(f"Exported {len(all_image_rows)} unique display image(s)")


if __name__ == "__main__":
    main()
