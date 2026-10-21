from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import ROOT
from .content import EDITABLE_FIELDS, apply_input, publish_post
from .markdown import render_markdown
from .models import Post
from .schemas import PostInput, PublishChecklist


LEGACY_POSTS = [
    {
        "slug": "sql-parameterization",
        "kind": "research",
        "title_en": "SQL injection: testing the boundary between data and code",
        "title_vi": "SQL injection: kiểm chứng ranh giới giữa dữ liệu và câu lệnh",
        "abstract_en": "This controlled experiment compares string concatenation and parameter binding in Python’s SQLite interface. Six fixtures cover normal authentication decisions, a legitimate quoted username, and two injection inputs. Both implementations query the same in-memory database. Concatenation produces three correct outcomes, one syntax error, and two authentication bypasses; parameter binding produces all six expected outcomes. These observations illustrate a code–data boundary, not a general security benchmark. The complete input set, executable source, runtime versions, and raw output are provided for reproduction.",
        "summary_vi": "So sánh truy vấn ghép chuỗi và truy vấn tham số hóa trên sáu ca thử có thể tái lập.",
        "platform": "Local lab",
        "machine": "Python / SQLite",
        "difficulty": "Intermediate",
        "evidence_type": "personal",
        "tags": ["Web Security", "SQL Injection", "Python"],
        "cover_url": "/assets/research/sql-results.svg",
        "published_at": "2026-09-15T00:00:00Z",
    },
    {
        "slug": "alert-deduplication",
        "kind": "research",
        "title_en": "Alert deduplication without losing evidence",
        "title_vi": "Khử trùng lặp cảnh báo: giảm nhiễu mà không mất dấu vết",
        "abstract_en": "Alert deduplication can reduce repeated delivery without suppressing distinct security events, but the choice of identity key matters. This deterministic replay constructs eight unique authentication events from two agents and adds four repeated deliveries. A content-based key retains one event, while a source-identity key retains all eight and removes only the four retries. The result is a counterexample to treating identical message text as event identity. This is an offline Python experiment using synthetic Wazuh-inspired records, not a benchmark of Wazuh, a production SOC, or the existing AI-APW project.",
        "summary_vi": "Thử nghiệm tám sự kiện và bốn lần giao lại để phân biệt nội dung giống nhau với cùng một sự kiện.",
        "platform": "Local lab",
        "machine": "Python / JSON",
        "difficulty": "Intermediate",
        "evidence_type": "personal",
        "tags": ["SOC Engineering", "Detection Engineering", "Python"],
        "cover_url": "/assets/research/dedup-results.svg",
        "published_at": "2026-09-18T00:00:00Z",
    },
    {
        "slug": "ai-triage-boundaries",
        "kind": "research",
        "title_en": "AI in the SOC: validating outputs before automation",
        "title_vi": "AI trong SOC: kiểm chứng ranh giới đầu ra trước khi tự động hóa",
        "abstract_en": "This experiment evaluates a deterministic output boundary for an AI-assisted SOC workflow using eight handcrafted response fixtures. The validator enforces exact fields, source-alert binding, strict types, and a minimum priority. Six fixtures are rejected and two are accepted as advisory text. One accepted response contains a malicious instruction in its explanation, demonstrating that schema validity does not imply semantic trust. No model is queried and no action executor is present. The experiment tests application policy behavior, not prompt-injection resistance or model accuracy.",
        "summary_vi": "Kiểm thử ranh giới đầu ra bằng tám mẫu phản hồi để tách dữ liệu hợp lệ khỏi quyết định đáng tin cậy.",
        "platform": "Local lab",
        "machine": "Policy validator",
        "difficulty": "Intermediate",
        "evidence_type": "personal",
        "tags": ["AI Security", "SOC Engineering", "Python"],
        "cover_url": "/assets/research/ai-results.svg",
        "published_at": "2026-09-21T00:00:00Z",
    },
    {
        "slug": "ssrf-url-parser-boundaries",
        "kind": "research",
        "title_en": "SSRF egress filtering: testing URL parser edge cases and DNS resolution",
        "title_vi": "Chống SSRF ở lớp egress: kiểm thử khác biệt phân tích URL và phân giải địa chỉ IP",
        "abstract_en": "Blocking literal localhost strings in user-supplied URLs fails when HTTP clients accept alternate IP encodings, IPv6 loopback, authority userinfo tricks, or internal DNS records. This offline Python experiment compares a naive substring filter against a canonical egress policy across eight test URLs. The substring filter passes only 2/8 cases, whereas canonical parsing with urllib.parse and ipaddress.is_global enforces all 8/8 expected decisions. The note also discusses DNS rebinding TOCTOU gaps and redirect handling.",
        "summary_vi": "Thử nghiệm tám mẫu URL để so sánh bộ lọc chuỗi đơn giản với chính sách kiểm chứng IP chuẩn hóa ở tầng egress.",
        "platform": "Local lab",
        "machine": "Python / urllib & ipaddress",
        "difficulty": "Intermediate",
        "evidence_type": "personal",
        "tags": ["Web Security", "SSRF", "Python"],
        "cover_url": "/assets/research/ssrf-results.svg",
        "published_at": "2026-09-25T00:00:00Z",
    },
    {
        "slug": "jwt-verification-pitfalls",
        "kind": "research",
        "title_en": "Token verification boundaries: algorithm confusion, exp claims, and audience binding",
        "title_vi": "Kiểm chứng token xác thực: từ nhầm lẫn thuật toán đến ràng buộc ngữ cảnh (aud, exp)",
        "abstract_en": "Self-contained tokens carry both cryptographic headers and authorization claims, creating failure modes when verifiers trust unauthenticated header fields or validate signatures without checking service context. Using six deterministic HMAC-SHA256 fixtures, this experiment contrasts a loose decoder with a strict verification policy enforcing an explicit algorithm allowlist, constant-time HMAC comparison, integer expiration bounds, and audience binding. The loose decoder fails on alg:none, expired, and cross-service tokens (3/6), while the strict verifier passes all 6/6 fixtures.",
        "summary_vi": "Đối chiếu bộ giải mã lỏng và bộ xác minh chặt trên sáu mẫu token để kiểm chứng thuật toán, chữ ký và ngữ cảnh dịch vụ.",
        "platform": "Local lab",
        "machine": "Python / HMAC-SHA256",
        "difficulty": "Intermediate",
        "evidence_type": "personal",
        "tags": ["Web Security", "Authentication", "Cryptography", "Python"],
        "cover_url": "/assets/research/jwt-results.svg",
        "published_at": "2026-09-29T00:00:00Z",
    },
    {
        "slug": "sbom-backport-triage",
        "kind": "research",
        "title_en": "Why version-only CVE matching fails on backported Linux packages",
        "title_vi": "Vì sao đối sánh CVE chỉ theo số phiên bản dễ sai lệch trên bản dựng Linux nhúng?",
        "abstract_en": "Embedded Linux distributions built with Yocto/OpenEmbedded frequently remediate CVEs by backporting targeted patches into recipes without incrementing the upstream package version string. In this six-component synthetic experiment, a version-only scanner agrees with actual build exposure in only 2/6 cases—generating false positives on backported packages and host-only build tools while silently skipping components with missing version metadata. Combining version checks with target rootfs reachability and recipe patch provenance resolves all 6/6 triage decisions.",
        "summary_vi": "Mô hình hóa sáu trường hợp gói phần mềm nhúng để so sánh quét CVE theo chuỗi phiên bản với phân loại có ngữ cảnh bản vá.",
        "platform": "Local lab",
        "machine": "Yocto / SBOM model",
        "difficulty": "Intermediate",
        "evidence_type": "personal",
        "tags": ["Supply-Chain Security", "Embedded Linux", "Python"],
        "cover_url": "/assets/research/sbom-results.svg",
        "published_at": "2026-10-03T00:00:00Z",
    },
    {
        "slug": "netfilter-hook-observability",
        "kind": "research",
        "title_en": "Packet filtering order: modeling PREROUTING vs INPUT drops and NFLOG audit visibility",
        "title_vi": "Thứ tự hook trong Netfilter: mô hình hóa điểm chặn gói tin và khả năng quan sát qua NFLOG",
        "abstract_en": "When validating Linux firewall controls, a zero counter on an INPUT drop rule does not always mean traffic failed to arrive; kernel reverse-path filtering or early hooks may drop spoofed frames before they reach INPUT. This simulation evaluates six packet profiles across an INPUT-only logging design versus a dual-hook architecture that records spoofed frames in mangle/PREROUTING (NFLOG group 110) and policy drops in filter/INPUT (NFLOG group 100). Dual-hook logging captures 4/4 dropped flows compared with 2/4 for INPUT-only logging.",
        "summary_vi": "Mô phỏng sáu mẫu gói tin qua các hook Netfilter để giải thích hiện tượng silent drop và cách bố trí nhóm NFLOG.",
        "platform": "Local lab",
        "machine": "Netfilter / NFLOG model",
        "difficulty": "Intermediate",
        "evidence_type": "personal",
        "tags": ["Network Security", "Embedded Linux", "Detection Engineering"],
        "cover_url": "/assets/research/netfilter-results.svg",
        "published_at": "2026-10-06T00:00:00Z",
    },
    {
        "slug": "correlation-window-tradeoffs",
        "kind": "research",
        "title_en": "Brute-force vs low-and-slow: evaluating sliding windows and entity grouping in log correlation",
        "title_vi": "Phát hiện tấn công rải chậm: đánh giá cửa sổ trượt và cách nhóm thực thể trong tương quan log",
        "abstract_en": "Fixed tumbling windows keyed solely by source IP miss authentication bursts that straddle minute boundaries as well as distributed password-spraying attacks where each IP sends only one request. Replaying four synthetic authentication event streams shows that a fixed 60-second per-IP bucket achieves 2/4 accuracy, whereas a sliding 60-second window tracking both per-IP frequency and distinct targeted accounts achieves 4/4 accuracy without triggering on benign user typos.",
        "summary_vi": "Đánh giá bốn kịch bản sự kiện xác thực để so sánh khung cố định theo IP với cửa sổ trượt đa thực thể.",
        "platform": "Local lab",
        "machine": "Correlation engine",
        "difficulty": "Intermediate",
        "evidence_type": "personal",
        "tags": ["SOC Engineering", "Detection Engineering", "Python"],
        "cover_url": "/assets/research/correlation-results.svg",
        "published_at": "2026-10-09T00:00:00Z",
    },
    {
        "slug": "malware-static-triage-limits",
        "kind": "research",
        "title_en": "Static feature triage and packing evasion: why section entropy needs behavioral verification",
        "title_vi": "Giới hạn của đặc trưng tĩnh khi phân loại mẫu nghi ngờ: entropy, đóng gói (packing) và nhu cầu kiểm chứng động",
        "abstract_en": "High Shannon entropy is a classic indicator of packed or encrypted executable sections, but relying on a single entropy threshold produces false positives on benign compressed resources and false negatives on null-padded payloads. Across five deterministic binary section fixtures, an entropy-only rule (H >= 7.2) classifies 3/5 cases accurately. Combining section entropy with import-table density and RWX memory permissions classifies all 5/5 fixtures while highlighting why static triage must pair with dynamic sandbox execution.",
        "summary_vi": "Tính toán Shannon entropy trên năm mẫu vùng dữ liệu nhị phân để chỉ ra giới hạn của ngưỡng đơn lẻ và vai trò của phân tích động.",
        "platform": "Local lab",
        "machine": "Python / Binary heuristics",
        "difficulty": "Intermediate",
        "evidence_type": "personal",
        "tags": ["AI Security", "Malware Analysis", "Python"],
        "cover_url": "/assets/research/entropy-results.svg",
        "published_at": "2026-10-12T00:00:00Z",
    },
    {
        "slug": "htb-appointment",
        "kind": "writeup",
        "title_en": "Appointment: understanding SQL injection authentication bypass",
        "title_vi": "Appointment: hiểu cách SQL injection vượt qua đăng nhập",
        "abstract_en": "This reference walkthrough examines authentication bypass in Hack The Box's Appointment machine. It connects a small, controlled login test to the underlying SQL parsing error, then proposes evidence collection and regression checks. The emphasis is on explaining why an input changes query logic and what would establish a successful fix. The SQL statement is a teaching model, not recovered application source. No live HTB session was executed for this article, and no personal completion or flag is claimed.",
        "summary_vi": "Giải thích cách payload làm thay đổi logic truy vấn, cách thu thập bằng chứng và kiểm tra bản sửa.",
        "platform": "Hack The Box",
        "machine": "Appointment",
        "difficulty": "Very Easy",
        "evidence_type": "reference",
        "tags": ["HTB", "Web Security", "SQL Injection"],
        "cover_url": "/assets/research/htb-appointment-flow.svg",
        "published_at": "2026-08-22T00:00:00Z",
    },
    {
        "slug": "htb-fawn",
        "kind": "writeup",
        "title_en": "Fawn: testing anonymous FTP access",
        "title_vi": "Fawn: kiểm tra quyền truy cập anonymous trên FTP",
        "abstract_en": "Fawn introduces a common file-service exposure: anonymous FTP access to a file that should not be publicly readable. This reference walkthrough separates service discovery, authentication, directory listing, and file retrieval so that each observation supports a specific conclusion. It also distinguishes access control from transport encryption and proposes a focused retest. Commands describe an authorized lab workflow; they are not a transcript of a live HTB session or evidence of the portfolio owner's completion.",
        "summary_vi": "Tách từng kết luận về cổng mở, đăng nhập anonymous, liệt kê thư mục và quyền đọc file.",
        "platform": "Hack The Box",
        "machine": "Fawn",
        "difficulty": "Very Easy",
        "evidence_type": "reference",
        "tags": ["HTB", "FTP", "Access Control"],
        "cover_url": "/assets/research/htb-fawn-flow.svg",
        "published_at": "2026-08-26T00:00:00Z",
    },
    {
        "slug": "htb-redeemer",
        "kind": "writeup",
        "title_en": "Redeemer: unauthenticated Redis data access",
        "title_vi": "Redeemer: khi Redis cho phép đọc dữ liệu từ mạng",
        "abstract_en": "Redeemer provides a starting point for reasoning about exposed Redis services. This reference walkthrough uses service identification, a minimal connectivity check, incremental key discovery, and type-aware retrieval to evaluate unauthenticated data access. It separates network reachability from authorization and explains why successful reads do not imply operating-system compromise. The workflow is based on HTB's machine synopsis and Redis documentation. No live HTB execution, retrieved flag, or personal machine completion is asserted.",
        "summary_vi": "Khảo sát dịch vụ Redis, duyệt key tăng dần và đọc dữ liệu theo đúng kiểu để đánh giá phạm vi truy cập.",
        "platform": "Hack The Box",
        "machine": "Redeemer",
        "difficulty": "Very Easy",
        "evidence_type": "reference",
        "tags": ["HTB", "Redis", "Access Control"],
        "cover_url": "/assets/research/htb-redeemer-flow.svg",
        "published_at": "2026-08-30T00:00:00Z",
    },
    {
        "slug": "htb-archetype",
        "kind": "writeup",
        "title_en": "Archetype: exposed SMB configuration files, MSSQL xp_cmdshell, and credential hygiene",
        "title_vi": "Archetype: lộ file cấu hình trên SMB, quyền thực thi trong MSSQL và bài học quản lý thông tin xác thực",
        "abstract_en": "This reference walkthrough analyzes the attack chain in Hack The Box's retired Archetype machine, where an unauthenticated SMB share exposes an SSIS configuration file containing plaintext database credentials, and the database account holds sysadmin privileges enabling xp_cmdshell execution. The note breaks remediation into four independent control layers: SMB share ACLs, secret storage hygiene, SQL role least privilege, and host-level procedural hardening.",
        "summary_vi": "Phân tích chuỗi lỗi từ thư mục SMB cấu hình lỏng lẻo, lộ mật khẩu trong file cấu hình đến đặc quyền sysadmin trên MSSQL.",
        "platform": "Hack The Box",
        "machine": "Archetype",
        "difficulty": "Easy",
        "evidence_type": "reference",
        "tags": ["HTB", "Network Security", "Access Control"],
        "cover_url": "/assets/research/htb-archetype-flow.svg",
        "published_at": "2026-09-05T00:00:00Z",
    },
    {
        "slug": "htb-vaccine",
        "kind": "writeup",
        "title_en": "Vaccine: from PostgreSQL injection to command execution and sudoers analysis",
        "title_vi": "Vaccine: từ SQL injection trên PostgreSQL đến kiểm tra quyền thực thi lệnh và cấu hình sudo",
        "abstract_en": "This reference walkthrough studies Hack The Box's retired Vaccine machine to illustrate how blast radius expands when defense-in-depth is absent. An unparameterized search query becomes OS command execution because the web application connects as a PostgreSQL superuser capable of running COPY FROM PROGRAM, and local privilege escalation follows from a sudoers rule permitting interactive vi execution. Each stage is paired with a concrete remediation and verification check.",
        "summary_vi": "Khảo sát cách lỗ hổng SQL injection lan rộng thành chiếm quyền máy chủ khi tài khoản DB có quyền superuser và sudoers cấp quyền quá rộng.",
        "platform": "Hack The Box",
        "machine": "Vaccine",
        "difficulty": "Easy",
        "evidence_type": "reference",
        "tags": ["HTB", "Web Security", "SQL Injection"],
        "cover_url": "/assets/research/htb-vaccine-flow.svg",
        "published_at": "2026-09-10T00:00:00Z",
    },
    {
        "slug": "dfir-web-intrusion-timeline",
        "kind": "writeup",
        "title_en": "Reconstructing a web intrusion timeline from access logs, auth events, and persistence artifacts",
        "title_vi": "Dựng lại timeline sự cố web từ access log, nhật ký xác thực và dấu vết duy trì quyền truy cập",
        "abstract_en": "Single-source log review often misses the connection between an initial web exploit and subsequent host persistence. This DFIR lab walkthrough reconstructs a four-stage server intrusion across Nginx access logs, Linux auditd EXECVE records, SSH auth.log events, and cron/authorized_keys filesystem timestamps. It demonstrates UTC normalization, entity pivoting from HTTP requests to worker child processes, and a complete containment and eradication checklist.",
        "summary_vi": "Thực hành liên kết bốn nguồn nhật ký (Nginx, auditd, auth.log và filesystem mtime) để dựng lại toàn bộ chuỗi xâm nhập và lập danh mục khắc phục.",
        "platform": "Local DFIR lab",
        "machine": "Nginx / Linux auth.log",
        "difficulty": "Intermediate",
        "evidence_type": "personal",
        "tags": ["DFIR", "SOC Engineering", "Web Security"],
        "cover_url": "/assets/research/dfir-timeline.svg",
        "published_at": "2026-10-11T00:00:00Z",
    },
]


def read_legacy_post(metadata: dict) -> PostInput:
    filename = f"{metadata['slug']}.md"
    candidates = (
        Path.cwd() / "seeds" / "posts" / filename,
        ROOT / "seeds" / "posts" / filename,
    )
    source = next((candidate for candidate in candidates if candidate.is_file()), None)
    if source is None:
        checked = ", ".join(str(candidate) for candidate in candidates)
        raise FileNotFoundError(f"Legacy seed file {filename} was not found. Checked: {checked}")
    body_markdown = source.read_text(encoding="utf-8").strip()
    return PostInput(
        slug=metadata["slug"], kind=metadata["kind"], title_vi=metadata["title_vi"],
        title_en=metadata["title_en"], summary_vi=metadata["summary_vi"], abstract_en=metadata["abstract_en"],
        body_markdown_vi=body_markdown, platform=metadata["platform"], machine=metadata["machine"],
        difficulty=metadata["difficulty"], evidence_type=metadata["evidence_type"],
        cover_url=metadata["cover_url"], tags=metadata["tags"],
    )


def _matches(post: Post, data: PostInput, target_published_at: datetime) -> bool:
    fields_match = all(getattr(post, field) == getattr(data, field) for field in EDITABLE_FIELDS)
    rendered_matches = post.body_html_cached == render_markdown(data.body_markdown_vi).html
    pub_matches = post.published_at is not None and post.published_at.replace(tzinfo=timezone.utc) == target_published_at
    return fields_match and rendered_matches and pub_matches and sorted(tag.name for tag in post.tags) == sorted(data.tags)


def seed_legacy_posts(db: Session) -> tuple[int, int, int]:
    created = updated = skipped = 0
    default_published_at = datetime(2026, 9, 15, 0, 0, tzinfo=timezone.utc)
    checklist = PublishChecklist(retired_or_permitted=True, redacted=True, sources_checked=True)
    for metadata in LEGACY_POSTS:
        data = read_legacy_post(metadata)
        raw_pub = metadata.get("published_at")
        published_at = datetime.fromisoformat(raw_pub.replace("Z", "+00:00")) if raw_pub else default_published_at
        post = db.scalar(select(Post).where(Post.slug == data.slug))
        if post and post.status == "published" and _matches(post, data, published_at):
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
