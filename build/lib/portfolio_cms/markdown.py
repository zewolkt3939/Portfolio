from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

import nh3
from bs4 import BeautifulSoup
from markdown_it import MarkdownIt
from mdit_py_plugins.footnote import footnote_plugin


ALLOWED_TAGS = {
    "a", "blockquote", "br", "code", "div", "em", "figcaption", "figure",
    "h2", "h3", "h4", "hr", "img", "li", "ol", "p", "pre", "span",
    "strong", "table", "tbody", "td", "th", "thead", "tr", "ul",
}
ALLOWED_ATTRIBUTES = {
    "a": {"href", "title", "rel", "target"},
    "code": {"class"},
    "div": {"class"},
    "figure": {"class"},
    "h2": {"id"}, "h3": {"id"}, "h4": {"id"},
    "img": {"src", "alt", "title", "width", "height", "loading"},
    "span": {"class", "lang"},
}


@dataclass(frozen=True)
class RenderedMarkdown:
    html: str
    toc: list[dict[str, str | int]]
    reading_minutes: int


def slugify_heading(value: str, used: set[str]) -> str:
    normalized = unicodedata.normalize("NFKD", value.replace("đ", "d").replace("Đ", "D"))
    ascii_value = normalized.encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_value).strip("-") or "section"
    candidate = slug
    suffix = 2
    while candidate in used:
        candidate = f"{slug}-{suffix}"
        suffix += 1
    used.add(candidate)
    return candidate


def render_markdown(source: str) -> RenderedMarkdown:
    parser = MarkdownIt("gfm-like", {"html": False, "linkify": True, "typographer": True})
    parser.use(footnote_plugin)
    rendered = parser.render(source)
    soup = BeautifulSoup(rendered, "html.parser")
    toc: list[dict[str, str | int]] = []
    used: set[str] = set()
    for heading in soup.find_all(["h2", "h3", "h4"]):
        title = heading.get_text(" ", strip=True)
        anchor = slugify_heading(title, used)
        heading["id"] = anchor
        toc.append({"id": anchor, "title": title, "level": int(heading.name[1])})
    for paragraph in list(soup.find_all("p")):
        if not paragraph.find("img"):
            continue
        caption = paragraph.find_next_sibling("p")
        if not caption or not re.match(r"^(Hình|Figure)\s+\d+[.:]", caption.get_text(" ", strip=True), re.I):
            continue
        figure = soup.new_tag("figure")
        figure["class"] = "article-figure"
        paragraph.wrap(figure)
        caption.name = "figcaption"
        figure.append(caption.extract())
    for image in soup.find_all("img"):
        image["loading"] = "lazy"
    for link in soup.find_all("a"):
        href = link.get("href", "")
        if href.startswith(("http://", "https://")):
            link["target"] = "_blank"
            link["rel"] = "noreferrer noopener"
    cleaned = nh3.clean(
        str(soup),
        tags=ALLOWED_TAGS,
        attributes=ALLOWED_ATTRIBUTES,
        url_schemes={"http", "https", "mailto"},
        link_rel=None,
    )
    words = re.findall(r"\b\w+\b", BeautifulSoup(cleaned, "html.parser").get_text(" "))
    return RenderedMarkdown(cleaned, toc, max(1, round(len(words) / 220)))
