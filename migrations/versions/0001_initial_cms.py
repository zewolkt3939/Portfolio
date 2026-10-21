"""Initial portfolio CMS schema."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial_cms"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("admin_users", sa.Column("id", sa.String(36), primary_key=True), sa.Column("username", sa.String(80), nullable=False), sa.Column("password_hash", sa.Text(), nullable=False), sa.Column("totp_secret_encrypted", sa.Text(), nullable=False), sa.Column("recovery_codes_json", sa.Text(), nullable=False), sa.Column("is_active", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_login_at", sa.DateTime(timezone=True)))
    op.create_index("ix_admin_users_username", "admin_users", ["username"], unique=True)
    op.create_table("posts", sa.Column("id", sa.String(36), primary_key=True), sa.Column("slug", sa.String(120), nullable=False), sa.Column("status", sa.String(16), nullable=False), sa.Column("kind", sa.String(16), nullable=False), sa.Column("title_vi", sa.String(240), nullable=False), sa.Column("title_en", sa.String(240)), sa.Column("summary_vi", sa.Text(), nullable=False), sa.Column("abstract_en", sa.Text(), nullable=False), sa.Column("body_markdown_vi", sa.Text(), nullable=False), sa.Column("body_html_cached", sa.Text(), nullable=False), sa.Column("toc_json", sa.Text(), nullable=False), sa.Column("platform", sa.String(80)), sa.Column("machine", sa.String(120)), sa.Column("difficulty", sa.String(40)), sa.Column("evidence_type", sa.String(32), nullable=False), sa.Column("source_kind", sa.String(24), nullable=False), sa.Column("notion_page_id", sa.String(36)), sa.Column("cover_url", sa.String(500)), sa.Column("reading_minutes", sa.Integer(), nullable=False), sa.Column("content_hash", sa.String(64), nullable=False), sa.Column("published_content_hash", sa.String(64)), sa.Column("published_snapshot", sa.Text()), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False), sa.Column("published_at", sa.DateTime(timezone=True)), sa.CheckConstraint("status IN ('draft', 'published', 'archived')", name="ck_posts_status"), sa.CheckConstraint("kind IN ('research', 'writeup')", name="ck_posts_kind"), sa.CheckConstraint("evidence_type IN ('personal', 'reference')", name="ck_posts_evidence_type"), sa.UniqueConstraint("notion_page_id"))
    op.create_index("ix_posts_slug", "posts", ["slug"], unique=True)
    op.create_index("ix_posts_status", "posts", ["status"])
    op.create_index("ix_posts_kind", "posts", ["kind"])
    op.create_table("tags", sa.Column("id", sa.String(36), primary_key=True), sa.Column("slug", sa.String(60), nullable=False), sa.Column("name", sa.String(80), nullable=False))
    op.create_index("ix_tags_slug", "tags", ["slug"], unique=True)
    op.create_table("post_tags", sa.Column("post_id", sa.String(36), sa.ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True), sa.Column("tag_id", sa.String(36), sa.ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True))
    op.create_table("post_revisions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("post_id", sa.String(36), sa.ForeignKey("posts.id", ondelete="CASCADE"), nullable=False), sa.Column("editor_id", sa.String(36), sa.ForeignKey("admin_users.id")), sa.Column("reason", sa.String(32), nullable=False), sa.Column("snapshot", sa.Text(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_post_revisions_post_id", "post_revisions", ["post_id"])
    op.create_index("ix_post_revisions_created_at", "post_revisions", ["created_at"])
    op.create_table("media", sa.Column("id", sa.String(36), primary_key=True), sa.Column("public_url", sa.String(500), nullable=False, unique=True), sa.Column("disk_path", sa.String(500), nullable=False, unique=True), sa.Column("original_name", sa.String(255), nullable=False), sa.Column("mime_type", sa.String(60), nullable=False), sa.Column("size_bytes", sa.Integer(), nullable=False), sa.Column("sha256", sa.String(64), nullable=False), sa.Column("width", sa.Integer(), nullable=False), sa.Column("height", sa.Integer(), nullable=False), sa.Column("alt_vi", sa.String(500), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_media_sha256", "media", ["sha256"])
    op.create_table("admin_sessions", sa.Column("id", sa.String(36), primary_key=True), sa.Column("user_id", sa.String(36), sa.ForeignKey("admin_users.id", ondelete="CASCADE"), nullable=False), sa.Column("token_hash", sa.String(64), nullable=False), sa.Column("authenticated", sa.Boolean(), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False), sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_admin_sessions_user_id", "admin_sessions", ["user_id"])
    op.create_index("ix_admin_sessions_token_hash", "admin_sessions", ["token_hash"], unique=True)
    op.create_index("ix_admin_sessions_expires_at", "admin_sessions", ["expires_at"])
    op.create_table("login_attempts", sa.Column("id", sa.String(36), primary_key=True), sa.Column("subject_hash", sa.String(64), nullable=False), sa.Column("successful", sa.Boolean(), nullable=False), sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_login_attempts_subject_hash", "login_attempts", ["subject_hash"])
    op.create_index("ix_login_attempts_attempted_at", "login_attempts", ["attempted_at"])


def downgrade() -> None:
    for table in ("login_attempts", "admin_sessions", "media", "post_revisions", "post_tags", "tags", "posts", "admin_users"):
        op.drop_table(table)
