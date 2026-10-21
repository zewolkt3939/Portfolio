from portfolio_cms.models import Post
from portfolio_cms.schemas import PostInput


def post_input(slug: str = "sample-note", kind: str = "research") -> PostInput:
    return PostInput(
        slug=slug,
        kind=kind,
        title_vi="Ghi chép kiểm thử có thể tái lập",
        title_en="A reproducible security test",
        summary_vi="Tóm tắt rõ câu hỏi, bằng chứng và giới hạn của thử nghiệm.",
        abstract_en="This controlled note records its method, evidence, limitations, and a focused remediation retest.",
        body_markdown_vi="## Phương pháp\n\nDữ liệu tổng hợp được chạy trong local lab.\n\n## Kết quả\n\nKhông chứa dữ liệu nhạy cảm.",
        platform="Local lab",
        machine=None,
        difficulty="Intermediate",
        evidence_type="personal" if kind == "research" else "reference",
        cover_url=None,
        tags=["Web Security", "Testing"],
    )


def new_post(data: PostInput) -> Post:
    return Post(
        slug=data.slug,
        title_vi=data.title_vi,
        summary_vi=data.summary_vi,
        abstract_en=data.abstract_en,
        body_markdown_vi=data.body_markdown_vi,
        body_html_cached="",
    )

