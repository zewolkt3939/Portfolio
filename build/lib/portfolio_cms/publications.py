from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from .content import public_snapshot
from .models import Post


def published_posts(db: Session) -> list[dict]:
    """Return immutable public snapshots, newest first."""
    rows = db.scalars(select(Post).where(Post.status == "published")).all()
    items = [snapshot for row in rows if (snapshot := public_snapshot(row))]
    return sorted(items, key=lambda item: item.get("published_at") or "", reverse=True)


def filter_posts(
    items: list[dict], q: str = "", tag: str = "", kind: str = "", platform: str = "", difficulty: str = ""
) -> list[dict]:
    query = q.strip().casefold()
    tag_query = tag.strip().casefold()
    result = []
    for item in items:
        if kind and item.get("kind") != kind:
            continue
        if platform and (item.get("platform") or "").casefold() != platform.casefold():
            continue
        if difficulty and (item.get("difficulty") or "").casefold() != difficulty.casefold():
            continue
        tag_values = {
            value.casefold()
            for tag_item in item.get("tags", [])
            for value in (tag_item.get("name", ""), tag_item.get("slug", ""))
        }
        if tag_query and tag_query not in tag_values:
            continue
        haystack = " ".join(
            str(item.get(key) or "")
            for key in ("title_vi", "title_en", "summary_vi", "abstract_en", "platform", "machine")
        ).casefold()
        if query and query not in haystack and query not in " ".join(tag_values):
            continue
        result.append(item)
    return result


def public_post(db: Session, slug: str) -> dict | None:
    row = db.scalar(select(Post).where(Post.slug == slug, Post.status == "published"))
    return public_snapshot(row) if row else None


def display_date(value: str | None, locale: str) -> str:
    if not value:
        return ""
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.strftime("%d.%m.%Y" if locale == "vi" else "%d %b %Y")
