from __future__ import annotations

from math import ceil

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..publications import filter_posts, public_post, published_posts


router = APIRouter(prefix="/api/v1", tags=["public"])


def _api_item(item: dict, include_body: bool = False) -> dict:
    result = {
        key: item.get(key)
        for key in (
            "slug", "kind", "title_vi", "title_en", "summary_vi", "abstract_en",
            "platform", "machine", "difficulty", "evidence_type", "cover_url",
            "reading_minutes", "tags", "published_at", "updated_at",
        )
    }
    if include_body:
        result["html_vi"] = item.get("body_html_cached")
        result["toc"] = item.get("toc", [])
    return result


@router.get("/posts")
def list_posts(
    q: str = Query(default="", max_length=120),
    tag: str = Query(default="", max_length=80),
    kind: str = Query(default="", pattern=r"^(|research|writeup)$"),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
):
    page_size = 12
    items = filter_posts(published_posts(db), q=q, tag=tag, kind=kind)
    total_pages = max(1, ceil(len(items) / page_size))
    page = min(page, total_pages)
    start = (page - 1) * page_size
    return {
        "items": [_api_item(item) for item in items[start : start + page_size]],
        "page": page,
        "page_size": page_size,
        "pages": total_pages,
        "total": len(items),
    }


@router.get("/posts/{slug}")
def get_post(slug: str, db: Session = Depends(get_db)):
    item = public_post(db, slug)
    if not item:
        raise HTTPException(status_code=404, detail="Post not found")
    return _api_item(item, include_body=True)

