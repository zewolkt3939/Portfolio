from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .markdown import render_markdown
from .models import Post, PostRevision, Tag
from .schemas import PostInput, PublishChecklist


EDITABLE_FIELDS = (
    "slug", "kind", "title_vi", "title_en", "summary_vi", "abstract_en",
    "body_markdown_vi", "platform", "machine", "difficulty", "evidence_type", "cover_url",
)


def tag_slug(name: str) -> str:
    value = unicodedata.normalize("NFKD", name.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")[:60] or "tag"


def snapshot(post: Post) -> dict:
    return {
        **{field: getattr(post, field) for field in EDITABLE_FIELDS},
        "body_html_cached": post.body_html_cached,
        "toc": json.loads(post.toc_json or "[]"),
        "reading_minutes": post.reading_minutes,
        "tags": [{"name": tag.name, "slug": tag.slug} for tag in post.tags],
        "published_at": post.published_at.isoformat() if post.published_at else None,
        "updated_at": post.updated_at.isoformat() if post.updated_at else None,
    }


def content_hash(data: dict) -> str:
    stable = {key: value for key, value in data.items() if key not in {"published_at", "updated_at"}}
    return hashlib.sha256(json.dumps(stable, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def set_tags(db: Session, post: Post, names: list[str]) -> None:
    tags = []
    for name in names:
        slug = tag_slug(name)
        tag = db.scalar(select(Tag).where(Tag.slug == slug))
        if not tag:
            tag = Tag(slug=slug, name=name)
            db.add(tag)
        tags.append(tag)
    post.tags = tags


def apply_input(db: Session, post: Post, data: PostInput, editor_id: str | None, reason: str = "save") -> Post:
    if post.published_at and post.slug != data.slug:
        raise ValueError("Không thể đổi slug sau lần publish đầu tiên để giữ URL ổn định")
    existing = db.scalar(select(Post).where(Post.slug == data.slug))
    if existing and existing is not post:
        raise ValueError("Slug này đã được sử dụng")
    rendered = render_markdown(data.body_markdown_vi)
    for field in EDITABLE_FIELDS:
        setattr(post, field, getattr(data, field))
    post.body_html_cached = rendered.html
    post.toc_json = json.dumps(rendered.toc, ensure_ascii=False)
    post.reading_minutes = rendered.reading_minutes
    set_tags(db, post, data.tags)
    post.updated_at = datetime.now(timezone.utc)
    db.flush()
    data_snapshot = snapshot(post)
    post.content_hash = content_hash(data_snapshot)
    db.add(PostRevision(post_id=post.id, editor_id=editor_id, reason=reason, snapshot=json.dumps(data_snapshot, ensure_ascii=False)))
    db.commit()
    db.refresh(post)
    return post


def publish_post(db: Session, post: Post, editor_id: str | None, checklist: PublishChecklist) -> Post:
    if post.kind == "writeup" and not all((checklist.retired_or_permitted, checklist.redacted, checklist.sources_checked)):
        raise ValueError("Write-up cần hoàn thành đủ checklist trước khi publish")
    if not post.tags:
        raise ValueError("Bài viết cần ít nhất một tag")
    now = datetime.now(timezone.utc)
    if not post.published_at:
        post.published_at = now
    post.updated_at = now
    published = snapshot(post)
    published["published_at"] = post.published_at.isoformat()
    published["updated_at"] = now.isoformat()
    post.content_hash = content_hash(published)
    post.published_content_hash = post.content_hash
    post.published_snapshot = json.dumps(published, ensure_ascii=False)
    post.status = "published"
    db.add(PostRevision(post_id=post.id, editor_id=editor_id, reason="publish", snapshot=json.dumps(published, ensure_ascii=False)))
    db.commit()
    db.refresh(post)
    return post


def restore_revision(db: Session, post: Post, revision: PostRevision, editor_id: str | None) -> Post:
    data = json.loads(revision.snapshot)
    payload = PostInput(**{**data, "tags": [tag["name"] if isinstance(tag, dict) else tag for tag in data.get("tags", [])]})
    return apply_input(db, post, payload, editor_id, reason="restore")


def public_snapshot(post: Post) -> dict | None:
    if post.status != "published" or not post.published_snapshot:
        return None
    data = json.loads(post.published_snapshot)
    data["id"] = post.id
    return data
