from __future__ import annotations

import ipaddress
import re
import socket
import time
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import requests


PAGE_ID = re.compile(r"(?<![0-9a-fA-F])([0-9a-fA-F]{32}|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})(?![0-9a-fA-F])")
NOTION_HOSTS = {"notion.so", "www.notion.so", "notion.site", "www.notion.site"}
FILE_HOST_SUFFIXES = (".notion-static.com", ".notionusercontent.com", ".amazonaws.com")


class NotionImportError(ValueError):
    pass


@dataclass
class ImportedPage:
    page_id: str
    title: str
    markdown: str
    warnings: list[str] = field(default_factory=list)


def parse_page_id(value: str) -> str:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if not (hostname in NOTION_HOSTS or hostname.endswith(".notion.site")):
        raise NotionImportError("URL phải thuộc notion.so hoặc notion.site")
    match = PAGE_ID.search(parsed.path)
    if not match:
        raise NotionImportError("Không tìm thấy page ID hợp lệ trong URL Notion")
    raw = match.group(1).replace("-", "").lower()
    return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"


def _markdown_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace("[", "\\[").replace("]", "\\]")


def rich_text(items: list[dict]) -> str:
    result = []
    for item in items:
        value = _markdown_escape(item.get("plain_text", ""))
        annotations = item.get("annotations", {})
        if annotations.get("code"):
            value = f"`{value.replace('`', 'ˋ')}`"
        else:
            if annotations.get("bold"):
                value = f"**{value}**"
            if annotations.get("italic"):
                value = f"*{value}*"
            if annotations.get("strikethrough"):
                value = f"~~{value}~~"
        href = item.get("href")
        if href and href.startswith(("https://", "http://")):
            value = f"[{value}]({href})"
        result.append(value)
    return "".join(result)


def _hostname_is_public(hostname: str) -> bool:
    try:
        addresses = socket.getaddrinfo(hostname, 443, type=socket.SOCK_STREAM)
    except OSError:
        return False
    return bool(addresses) and all(ipaddress.ip_address(item[4][0]).is_global for item in addresses)


def validate_notion_file_url(value: str) -> None:
    parsed = urlparse(value)
    hostname = (parsed.hostname or "").lower()
    if parsed.scheme != "https" or not hostname.endswith(FILE_HOST_SUFFIXES):
        raise NotionImportError("Notion trả về file URL ngoài allowlist")
    if not _hostname_is_public(hostname):
        raise NotionImportError("File URL không trỏ tới địa chỉ Internet công khai")


class NotionImporter:
    def __init__(self, token: str, version: str, save_image):
        if not token:
            raise NotionImportError("Chưa cấu hình NOTION_API_TOKEN")
        self.client = requests.Session()
        self.client.headers.update({"Authorization": f"Bearer {token}", "Notion-Version": version})
        self.save_image = save_image
        self.warnings: list[str] = []

    def close(self):
        self.client.close()

    def _get(self, path: str, params: dict | None = None) -> dict:
        for _attempt in range(3):
            response = self.client.get(f"https://api.notion.com{path}", params=params, timeout=20, allow_redirects=False)
            if response.status_code != 429:
                break
            time.sleep(min(float(response.headers.get("retry-after", "1")), 5))
        if response.status_code == 404:
            raise NotionImportError("Page không tồn tại hoặc chưa được share cho integration")
        if response.status_code >= 400:
            raise NotionImportError(f"Notion API trả về lỗi {response.status_code}")
        return response.json()

    def _children(self, block_id: str) -> list[dict]:
        results, cursor = [], None
        while True:
            params = {"page_size": 100}
            if cursor:
                params["start_cursor"] = cursor
            payload = self._get(f"/v1/blocks/{block_id}/children", params)
            results.extend(payload.get("results", []))
            if not payload.get("has_more"):
                return results
            cursor = payload.get("next_cursor")

    def _download(self, url: str) -> bytes:
        for _ in range(4):
            validate_notion_file_url(url)
            response = requests.get(url, timeout=20, allow_redirects=False)
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            if response.status_code >= 400:
                raise NotionImportError(f"Không tải được ảnh Notion ({response.status_code})")
            if len(response.content) > 8 * 1024 * 1024:
                raise NotionImportError("Ảnh Notion vượt quá giới hạn 8 MB")
            return response.content
        raise NotionImportError("Ảnh Notion chuyển hướng quá nhiều lần")

    def _image(self, block: dict) -> str:
        value = block["image"]
        caption = rich_text(value.get("caption", [])) or "Hình minh họa"
        if value.get("type") != "file":
            self.warnings.append("External image chưa được nhập; hãy upload thủ công trước khi publish.")
            return f"> [Cần nhập ảnh ngoài: {caption}]\n"
        url = value["file"]["url"]
        data = self._download(url)
        media = self.save_image(data, f"notion-{block['id']}.image", caption)
        return f"![{caption}]({media.public_url})\n"

    def _blocks_to_markdown(self, blocks: list[dict], depth: int = 0) -> str:
        lines: list[str] = []
        for block in blocks:
            kind = block.get("type", "unsupported")
            value = block.get(kind, {})
            text = rich_text(value.get("rich_text", []))
            if kind == "paragraph":
                lines.append(text)
            elif kind.startswith("heading_"):
                level = min(int(kind[-1]) + 1, 4)
                lines.append(f"{'#' * level} {text}")
            elif kind == "bulleted_list_item":
                lines.append(f"{'  ' * depth}- {text}")
            elif kind == "numbered_list_item":
                lines.append(f"{'  ' * depth}1. {text}")
            elif kind == "to_do":
                lines.append(f"- [{'x' if value.get('checked') else ' '}] {text}")
            elif kind == "quote":
                lines.append("\n".join(f"> {line}" for line in text.splitlines()))
            elif kind == "callout":
                lines.append(f"> **Ghi chú:** {text}")
            elif kind == "code":
                language = value.get("language", "text")
                lines.append(f"```{language}\n{text}\n```")
            elif kind == "divider":
                lines.append("---")
            elif kind == "equation":
                lines.append(f"`{value.get('expression', '')}`")
            elif kind == "image":
                try:
                    lines.append(self._image(block))
                except NotionImportError as exc:
                    self.warnings.append(str(exc))
                    lines.append("> [Ảnh Notion chưa nhập được]")
            elif kind in {"bookmark", "link_preview", "embed"}:
                url = value.get("url", "")
                lines.append(f"[{url}]({url})" if url.startswith(("http://", "https://")) else "")
            elif kind == "table":
                rows = self._children(block["id"])
                cells = [[rich_text(cell) for cell in row.get("table_row", {}).get("cells", [])] for row in rows]
                if cells:
                    lines.append("| " + " | ".join(cells[0]) + " |")
                    lines.append("| " + " | ".join("---" for _ in cells[0]) + " |")
                    lines.extend("| " + " | ".join(row) + " |" for row in cells[1:])
            elif kind not in {"column", "column_list", "toggle", "synced_block"}:
                self.warnings.append(f"Block Notion chưa hỗ trợ: {kind}")
            if block.get("has_children") and kind != "table":
                nested = self._blocks_to_markdown(self._children(block["id"]), depth + 1)
                if nested:
                    lines.append(nested)
        return "\n\n".join(line for line in lines if line.strip())

    def import_page(self, url: str) -> ImportedPage:
        page_id = parse_page_id(url)
        page = self._get(f"/v1/pages/{page_id}")
        title = "Untitled Notion page"
        for prop in page.get("properties", {}).values():
            if prop.get("type") == "title":
                title = "".join(item.get("plain_text", "") for item in prop.get("title", [])).strip() or title
                break
        markdown = self._blocks_to_markdown(self._children(page_id)).strip()
        if not markdown:
            raise NotionImportError("Page Notion không có nội dung có thể nhập")
        return ImportedPage(page_id=page_id, title=title, markdown=markdown, warnings=self.warnings)
