from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import ROOT
from .content import EDITABLE_FIELDS, apply_input, publish_post
from .markdown import render_markdown
from .models import Post
from .schemas import PostInput, PublishChecklist


LEGACY_POSTS = [
    {
        "slug": "sql-parameterization", "kind": "research", "title_en": "SQL injection: testing the boundary between data and code",
        "title_vi": "SQL injection: kiểm chứng ranh giới giữa dữ liệu và câu lệnh",
        "abstract_en": "This controlled experiment compares string concatenation and parameter binding in Python’s SQLite interface. Six fixtures cover normal authentication decisions, a legitimate quoted username, and two injection inputs. Both implementations query the same in-memory database. Concatenation produces three correct outcomes, one syntax error, and two authentication bypasses; parameter binding produces all six expected outcomes. These observations illustrate a code–data boundary, not a general security benchmark. The complete input set, executable source, runtime versions, and raw output are provided for reproduction.",
        "summary_vi": "So sánh truy vấn ghép chuỗi và truy vấn tham số hóa trên sáu ca thử có thể tái lập.",
        "platform": "Local lab", "machine": "Python / SQLite", "difficulty": "Intermediate", "evidence_type": "personal",
        "tags": ["Web Security", "SQL Injection", "Python"], "cover_url": "/assets/research/sql-results.svg",
    },
    {
        "slug": "alert-deduplication", "kind": "research", "title_en": "Alert deduplication without losing evidence",
        "title_vi": "Khử trùng lặp cảnh báo: giảm nhiễu mà không mất dấu vết",
        "abstract_en": "Alert deduplication can reduce repeated delivery without suppressing distinct security events, but the choice of identity key matters. This deterministic replay constructs eight unique authentication events from two agents and adds four repeated deliveries. A content-based key retains one event, while a source-identity key retains all eight and removes only the four retries. The result is a counterexample to treating identical message text as event identity. This is an offline Python experiment using synthetic Wazuh-inspired records, not a benchmark of Wazuh, a production SOC, or the existing AI-APW project.",
        "summary_vi": "Thử nghiệm tám sự kiện và bốn lần giao lại để phân biệt nội dung giống nhau với cùng một sự kiện.",
        "platform": "Local lab", "machine": "Python / JSON", "difficulty": "Intermediate", "evidence_type": "personal",
        "tags": ["SOC Engineering", "Detection Engineering", "Python"], "cover_url": "/assets/research/dedup-results.svg",
    },
    {
        "slug": "ai-triage-boundaries", "kind": "research", "title_en": "AI in the SOC: validating outputs before automation",
        "title_vi": "AI trong SOC: kiểm chứng ranh giới đầu ra trước khi tự động hóa",
        "abstract_en": "This experiment evaluates a deterministic output boundary for an AI-assisted SOC workflow using eight handcrafted response fixtures. The validator enforces exact fields, source-alert binding, strict types, and a minimum priority. Six fixtures are rejected and two are accepted as advisory text. One accepted response contains a malicious instruction in its explanation, demonstrating that schema validity does not imply semantic trust. No model is queried and no action executor is present. The experiment tests application policy behavior, not prompt-injection resistance or model accuracy.",
        "summary_vi": "Kiểm thử ranh giới đầu ra bằng tám mẫu phản hồi để tách dữ liệu hợp lệ khỏi quyết định đáng tin cậy.",
        "platform": "Local lab", "machine": "Policy validator", "difficulty": "Intermediate", "evidence_type": "personal",
        "tags": ["AI Security", "SOC Engineering", "Python"], "cover_url": "/assets/research/ai-results.svg",
    },
    {
        "slug": "htb-appointment", "kind": "writeup", "title_en": "Appointment: understanding SQL injection authentication bypass",
        "title_vi": "Appointment: hiểu cách SQL injection vượt qua đăng nhập",
        "abstract_en": "This reference walkthrough examines authentication bypass in Hack The Box's Appointment machine. It connects a small, controlled login test to the underlying SQL parsing error, then proposes evidence collection and regression checks. The emphasis is on explaining why an input changes query logic and what would establish a successful fix. The SQL statement is a teaching model, not recovered application source. No live HTB session was executed for this article, and no personal completion or flag is claimed.",
        "summary_vi": "Giải thích cách payload làm thay đổi logic truy vấn, cách thu thập bằng chứng và kiểm tra bản sửa.",
        "platform": "Hack The Box", "machine": "Appointment", "difficulty": "Very Easy", "evidence_type": "reference",
        "tags": ["HTB", "Web Security", "SQL Injection"], "cover_url": None,
    },
    {
        "slug": "htb-fawn", "kind": "writeup", "title_en": "Fawn: testing anonymous FTP access",
        "title_vi": "Fawn: kiểm tra quyền truy cập anonymous trên FTP",
        "abstract_en": "Fawn introduces a common file-service exposure: anonymous FTP access to a file that should not be publicly readable. This reference walkthrough separates service discovery, authentication, directory listing, and file retrieval so that each observation supports a specific conclusion. It also distinguishes access control from transport encryption and proposes a focused retest. Commands describe an authorized lab workflow; they are not a transcript of a live HTB session or evidence of the portfolio owner's completion.",
        "summary_vi": "Tách từng kết luận về cổng mở, đăng nhập anonymous, liệt kê thư mục và quyền đọc file.",
        "platform": "Hack The Box", "machine": "Fawn", "difficulty": "Very Easy", "evidence_type": "reference",
        "tags": ["HTB", "FTP", "Access Control"], "cover_url": None,
    },
    {
        "slug": "htb-redeemer", "kind": "writeup", "title_en": "Redeemer: unauthenticated Redis data access",
        "title_vi": "Redeemer: khi Redis cho phép đọc dữ liệu từ mạng",
        "abstract_en": "Redeemer provides a starting point for reasoning about exposed Redis services. This reference walkthrough uses service identification, a minimal connectivity check, incremental key discovery, and type-aware retrieval to evaluate unauthenticated data access. It separates network reachability from authorization and explains why successful reads do not imply operating-system compromise. The workflow is based on HTB's machine synopsis and Redis documentation. No live HTB execution, retrieved flag, or personal machine completion is asserted.",
        "summary_vi": "Khảo sát dịch vụ Redis, duyệt key tăng dần và đọc dữ liệu theo đúng kiểu để đánh giá phạm vi truy cập.",
        "platform": "Hack The Box", "machine": "Redeemer", "difficulty": "Very Easy", "evidence_type": "reference",
        "tags": ["HTB", "Redis", "Access Control"], "cover_url": None,
    },
]


def read_legacy_post(metadata: dict) -> PostInput:
    source = ROOT / "seeds/posts" / f"{metadata['slug']}.md"
    body_markdown = source.read_text(encoding="utf-8").strip()
    return PostInput(
        slug=metadata["slug"], kind=metadata["kind"], title_vi=metadata["title_vi"],
        title_en=metadata["title_en"], summary_vi=metadata["summary_vi"], abstract_en=metadata["abstract_en"],
        body_markdown_vi=body_markdown, platform=metadata["platform"], machine=metadata["machine"],
        difficulty=metadata["difficulty"], evidence_type=metadata["evidence_type"],
        cover_url=metadata["cover_url"], tags=metadata["tags"],
    )


def _matches(post: Post, data: PostInput) -> bool:
    fields_match = all(getattr(post, field) == getattr(data, field) for field in EDITABLE_FIELDS)
    rendered_matches = post.body_html_cached == render_markdown(data.body_markdown_vi).html
    return fields_match and rendered_matches and sorted(tag.name for tag in post.tags) == sorted(data.tags)


def seed_legacy_posts(db: Session) -> tuple[int, int, int]:
    created = updated = skipped = 0
    published_at = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
    checklist = PublishChecklist(retired_or_permitted=True, redacted=True, sources_checked=True)
    for metadata in LEGACY_POSTS:
        data = read_legacy_post(metadata)
        post = db.scalar(select(Post).where(Post.slug == data.slug))
        if post and post.status == "published" and _matches(post, data):
            skipped += 1
            continue
        if not post:
            post = Post(
                slug=data.slug, title_vi=data.title_vi, summary_vi=data.summary_vi,
                abstract_en=data.abstract_en, body_markdown_vi=data.body_markdown_vi, body_html_cached="",
            )
            db.add(post)
            created += 1
        else:
            updated += 1
        apply_input(db, post, data, None, reason="legacy-seed")
        post.source_kind = "legacy"
        post.published_at = published_at
        publish_post(db, post, None, checklist)
    return created, updated, skipped
