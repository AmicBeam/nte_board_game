#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


GRAPHQL_URL = "https://everness.info/api/graphql"
ASSET_BASE_URL = "https://api.everness.info/data/assets"
DEFAULT_CACHE_TTL_S = 3600.0

HEADERS = {
    "Cookie": "locale=zh-Hans",
    "Origin": "https://everness.info",
    "Referer": "https://everness.info/zh-Hans/items",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
    "Content-Type": "application/json",
    "User-Agent": "codex-everness-items/1.0",
}

GET_ITEMS_QUERY = """query GetItems($filter: ItemsFilterInput) {
  items(filter: $filter) {
    id
    name
    icon
    quality
    type_id
    type_icon
    type_custom_id
    description
    context
    sources {
      source_id
      name
      __typename
    }
    __typename
  }
}"""


class EvernessItemsError(RuntimeError):
    pass


def cache_dir() -> Path:
    cache_root = os.environ.get("CODEX_EVERNESS_ITEMS_CACHE_DIR", "").strip()
    if cache_root:
        return Path(cache_root).expanduser()
    tmp_dir = os.environ.get("TMPDIR", "").strip()
    if tmp_dir:
        return Path(tmp_dir).expanduser() / "codex-everness-items"
    return Path("/tmp/codex-everness-items")


def cache_path() -> Path:
    return cache_dir() / "items-zh-Hans.json"


def ssl_context(insecure: bool) -> ssl.SSLContext | None:
    if not insecure:
        return None
    return ssl._create_unverified_context()  # noqa: SLF001


def request_json(payload: dict[str, Any], insecure: bool = False) -> dict[str, Any]:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(GRAPHQL_URL, data=data, headers=HEADERS, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30, context=ssl_context(insecure)) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.URLError as exc:
        raise EvernessItemsError(f"Everness request failed: {exc}") from exc


def fetch_items(no_cache: bool = False, insecure: bool = False) -> list[dict[str, Any]]:
    path = cache_path()
    if not no_cache and path.exists():
        age_s = time.time() - path.stat().st_mtime
        if age_s <= DEFAULT_CACHE_TTL_S:
            return json.loads(path.read_text(encoding="utf-8"))["items"]

    payload = {
        "operationName": "GetItems",
        "variables": {},
        "extensions": {
            "clientLibrary": {
                "name": "@apollo/client",
                "version": "4.0.12",
            },
        },
        "query": GET_ITEMS_QUERY,
    }
    body = request_json(payload, insecure=insecure)
    items = body.get("data", {}).get("items")
    if not isinstance(items, list):
        raise EvernessItemsError(f"Unexpected Everness response: {body}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"fetched_at": time.time(), "items": items}, ensure_ascii=False), encoding="utf-8")
    return items


def normalize_icon_url(icon: str | None, ext: str = "webp") -> str:
    if not icon:
        return ""
    normalized = icon.replace("\\", "/")
    has_ext = bool(re.search(r"\.[a-z0-9]+$", normalized, flags=re.I))
    clean_ext = ext.lstrip(".")
    if normalized.startswith("/Game/UI/") or normalized.startswith("/Game/UI_Icon/"):
        if has_ext:
            normalized = re.sub(r"\.[a-z0-9]+$", "", normalized, flags=re.I)
        rel = re.sub(r"^/Game/UI_Icon/", "", normalized)
        rel = re.sub(r"^/Game/UI/", "", rel)
        rel = rel.lstrip("/")
        return f"{ASSET_BASE_URL}/{rel}.{clean_ext}"
    if normalized.startswith("http://") or normalized.startswith("https://"):
        return normalized if has_ext else f"{normalized}.{clean_ext}"
    return normalized if has_ext else f"{normalized}.{clean_ext}"


def text_blob(item: dict[str, Any]) -> str:
    return "\n".join(str(item.get(key) or "") for key in ("name", "description", "context"))


def compact_text(value: Any, limit: int = 240) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    return text if len(text) <= limit else text[: limit - 1] + "…"


def find_items(items: list[dict[str, Any]], query: str | None, item_id: str | None, limit: int) -> list[dict[str, Any]]:
    if item_id:
        needle = item_id.lower()
        matches = [item for item in items if str(item.get("id", "")).lower() == needle]
        if matches:
            return matches[:limit]
    if not query:
        return items[:limit]
    terms = [term.lower() for term in re.split(r"\s+", query.strip()) if term.strip()]
    if not terms:
        return items[:limit]
    scored: list[tuple[int, dict[str, Any]]] = []
    for item in items:
        blob = text_blob(item).lower()
        name = str(item.get("name") or "").lower()
        item_id_text = str(item.get("id") or "").lower()
        if not all(term in blob or term in item_id_text for term in terms):
            continue
        score = 0
        for term in terms:
            if term == name or term == item_id_text:
                score += 100
            elif term in name:
                score += 50
            elif term in item_id_text:
                score += 30
            else:
                score += 10
        scored.append((score, item))
    scored.sort(key=lambda row: (-row[0], str(row[1].get("name") or "")))
    return [item for _, item in scored[:limit]]


def explicit_links(target: dict[str, Any], items: list[dict[str, Any]], limit: int = 20) -> dict[str, list[dict[str, Any]]]:
    target_name = str(target.get("name") or "").strip()
    target_text = "\n".join(str(target.get(key) or "") for key in ("description", "context"))
    direct = []
    reverse = []
    for item in items:
        name = str(item.get("name") or "").strip()
        if not name or item.get("id") == target.get("id"):
            continue
        if len(name) >= 2 and name in target_text:
            direct.append(item)
        if target_name and target_name in "\n".join(str(item.get(key) or "") for key in ("description", "context")):
            reverse.append(item)
    return {"explicit_mentions": direct[:limit], "mentioned_by": reverse[:limit]}


def output_record(item: dict[str, Any], items: list[dict[str, Any]] | None = None, include_links: bool = False) -> dict[str, Any]:
    record = {
        "id": item.get("id"),
        "name": item.get("name"),
        "quality": item.get("quality"),
        "type_custom_id": item.get("type_custom_id"),
        "type_id": item.get("type_id"),
        "type_icon": item.get("type_icon"),
        "icon": item.get("icon"),
        "icon_url": normalize_icon_url(item.get("icon")),
        "description": item.get("description") or "",
        "context": item.get("context") or "",
        "sources": item.get("sources") or [],
    }
    if include_links and items is not None:
        record["links"] = {
            key: [
                {
                    "id": linked.get("id"),
                    "name": linked.get("name"),
                    "type_custom_id": linked.get("type_custom_id"),
                    "context": linked.get("context") or "",
                }
                for linked in value
            ]
            for key, value in explicit_links(item, items).items()
        }
    return record


def render_markdown(records: list[dict[str, Any]]) -> str:
    chunks = []
    for record in records:
        chunks.append(f"## {record['name']} ({record['id']})")
        chunks.append(f"- 类型：{record.get('type_custom_id') or record.get('type_id') or '未知'}")
        chunks.append(f"- 品质：{record.get('quality') or '未知'}")
        chunks.append(f"- 图标：{record.get('icon_url') or '无'}")
        if record.get("context"):
            chunks.append(f"- 用途：{compact_text(record['context'], 500)}")
        if record.get("description"):
            chunks.append(f"- 描述：{compact_text(record['description'], 500)}")
        sources = [src.get("name") or src.get("source_id") for src in record.get("sources", []) if src]
        if sources:
            chunks.append(f"- 来源：{', '.join(str(src) for src in sources)}")
        links = record.get("links")
        if links:
            direct = links.get("explicit_mentions") or []
            reverse = links.get("mentioned_by") or []
            chunks.append("- 显式关联：" + (", ".join(f"{item['name']}({item['id']})" for item in direct) if direct else "无"))
            chunks.append("- 被这些道具提及：" + (", ".join(f"{item['name']}({item['id']})" for item in reverse) if reverse else "无"))
        chunks.append("")
    return "\n".join(chunks).rstrip() + "\n"


def safe_filename(name: str, fallback: str) -> str:
    base = name.strip() or fallback
    base = re.sub(r"[\\/:*?\"<>|]", "_", base)
    base = re.sub(r"\s+", " ", base).strip()
    return base or fallback


def download_icons(records: list[dict[str, Any]], output_dir: Path, insecure: bool = False) -> list[dict[str, str]]:
    output_dir.mkdir(parents=True, exist_ok=True)
    downloaded = []
    for record in records:
        url = record.get("icon_url") or normalize_icon_url(record.get("icon"))
        if not url:
            continue
        filename = safe_filename(str(record.get("name") or ""), str(record.get("id") or "item")) + ".webp"
        output_path = output_dir / filename
        req = urllib.request.Request(url, headers={"User-Agent": HEADERS["User-Agent"]})
        try:
            with urllib.request.urlopen(req, timeout=30, context=ssl_context(insecure)) as resp:
                content_type = resp.headers.get("content-type", "")
                data = resp.read()
        except urllib.error.URLError as exc:
            raise EvernessItemsError(f"Icon download failed for {record.get('name')}: {exc}") from exc
        if "image" not in content_type.lower() and not data.startswith(b"RIFF"):
            raise EvernessItemsError(f"Icon URL did not return an image for {record.get('name')}: {url}")
        output_path.write_bytes(data)
        downloaded.append({"name": str(record.get("name") or ""), "url": url, "path": str(output_path)})
    return downloaded


def list_types(items: list[dict[str, Any]]) -> str:
    counts: dict[str, int] = {}
    for item in items:
        key = str(item.get("type_custom_id") or item.get("type_id") or "unknown")
        counts[key] = counts.get(key, 0) + 1
    return "\n".join(f"{key}\t{count}" for key, count in sorted(counts.items())) + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fetch Everness item data and icons.")
    parser.add_argument("--name", help="Search item name/description/context.")
    parser.add_argument("--search", help="Search item name/description/context with space-separated terms.")
    parser.add_argument("--id", dest="item_id", help="Exact item id.")
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--links", action="store_true", help="Include explicit description/context item links.")
    parser.add_argument("--download-icons", metavar="DIR", help="Download matched item icons into DIR.")
    parser.add_argument("--format", choices=["markdown", "json"], default="markdown")
    parser.add_argument("--list-types", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--insecure", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    query = args.name or args.search
    try:
        items = fetch_items(no_cache=args.no_cache, insecure=args.insecure)
        if args.list_types:
            sys.stdout.write(list_types(items))
            return 0
        matches = find_items(items, query=query, item_id=args.item_id, limit=max(1, args.limit))
        records = [output_record(item, items=items, include_links=args.links) for item in matches]
        if args.download_icons:
            downloaded = download_icons(records, Path(args.download_icons), insecure=args.insecure)
            if args.format == "json":
                sys.stdout.write(json.dumps({"items": records, "downloaded": downloaded}, ensure_ascii=False, indent=2) + "\n")
            else:
                sys.stdout.write(render_markdown(records))
                sys.stdout.write("\nDownloaded icons:\n")
                for row in downloaded:
                    sys.stdout.write(f"- {row['name']}: {row['path']}\n")
            return 0
        if args.format == "json":
            sys.stdout.write(json.dumps({"items": records}, ensure_ascii=False, indent=2) + "\n")
        else:
            sys.stdout.write(render_markdown(records))
        return 0
    except EvernessItemsError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
