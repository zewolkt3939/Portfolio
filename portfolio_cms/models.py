from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


post_tags = Table(
    "post_tags",
    Base.metadata,
    Column("post_id", String(36), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", String(36), ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class Post(Base):
    __tablename__ = "posts"
    __table_args__ = (
        CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_posts_status"),
        CheckConstraint("kind IN ('research', 'writeup')", name="ck_posts_kind"),
        CheckConstraint("evidence_type IN ('personal', 'reference')", name="ck_posts_evidence_type"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    status: Mapped[str] = mapped_column(String(16), default="draft", index=True)
    kind: Mapped[str] = mapped_column(String(16), default="writeup", index=True)
    title_vi: Mapped[str] = mapped_column(String(240))
    title_en: Mapped[str | None] = mapped_column(String(240), nullable=True)
    summary_vi: Mapped[str] = mapped_column(Text)
    abstract_en: Mapped[str] = mapped_column(Text)
    body_markdown_vi: Mapped[str] = mapped_column(Text)
    body_html_cached: Mapped[str] = mapped_column(Text)
    toc_json: Mapped[str] = mapped_column(Text, default="[]")
    platform: Mapped[str | None] = mapped_column(String(80), nullable=True)
    machine: Mapped[str | None] = mapped_column(String(120), nullable=True)
    difficulty: Mapped[str | None] = mapped_column(String(40), nullable=True)
    evidence_type: Mapped[str] = mapped_column(String(32), default="reference")
    source_kind: Mapped[str] = mapped_column(String(24), default="authored")
    notion_page_id: Mapped[str | None] = mapped_column(String(36), nullable=True, unique=True)
    cover_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    reading_minutes: Mapped[int] = mapped_column(Integer, default=1)
    content_hash: Mapped[str] = mapped_column(String(64), default="")
    published_content_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    published_snapshot: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    tags: Mapped[list[Tag]] = relationship(secondary=post_tags, back_populates="posts", lazy="selectin")
    revisions: Mapped[list[PostRevision]] = relationship(
        back_populates="post", cascade="all, delete-orphan", order_by="PostRevision.created_at.desc()"
    )

    @property
    def has_unpublished_changes(self) -> bool:
        return self.status == "published" and self.content_hash != self.published_content_hash


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    slug: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(80))
    posts: Mapped[list[Post]] = relationship(secondary=post_tags, back_populates="tags")


class PostRevision(Base):
    __tablename__ = "post_revisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    post_id: Mapped[str] = mapped_column(String(36), ForeignKey("posts.id", ondelete="CASCADE"), index=True)
    editor_id: Mapped[str | None] = mapped_column(String(36), ForeignKey("admin_users.id"), nullable=True)
    reason: Mapped[str] = mapped_column(String(32), default="save")
    snapshot: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    post: Mapped[Post] = relationship(back_populates="revisions")


class Media(Base):
    __tablename__ = "media"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    public_url: Mapped[str] = mapped_column(String(500), unique=True)
    disk_path: Mapped[str] = mapped_column(String(500), unique=True)
    original_name: Mapped[str] = mapped_column(String(255))
    mime_type: Mapped[str] = mapped_column(String(60))
    size_bytes: Mapped[int] = mapped_column(Integer)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    alt_vi: Mapped[str] = mapped_column(String(500), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AdminUser(Base):
    __tablename__ = "admin_users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(Text)
    totp_secret_encrypted: Mapped[str] = mapped_column(Text)
    recovery_codes_json: Mapped[str] = mapped_column(Text, default="[]")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AdminSession(Base):
    __tablename__ = "admin_sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("admin_users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    authenticated: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    user: Mapped[AdminUser] = relationship()


class LoginAttempt(Base):
    __tablename__ = "login_attempts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    subject_hash: Mapped[str] = mapped_column(String(64), index=True)
    successful: Mapped[bool] = mapped_column(Boolean, default=False)
    attempted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
