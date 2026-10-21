import pytest
from pydantic import ValidationError

from portfolio_cms.markdown import render_markdown
from portfolio_cms.schemas import PostInput
from tests.helpers import post_input


def test_markdown_sanitizes_html_and_dangerous_urls():
    rendered = render_markdown(
        "## Tiêu đề\n\n<script>alert(1)</script>\n\n[x](javascript:alert(1))\n\n[nguồn](https://owasp.org)"
    )
    assert "<script" not in rendered.html
    assert 'href="javascript:' not in rendered.html
    assert 'rel="noreferrer noopener"' in rendered.html
    assert rendered.toc == [{"id": "tieu-de", "title": "Tiêu đề", "level": 2}]


def test_duplicate_headings_get_stable_unique_ids():
    rendered = render_markdown("## Kết quả\n\nA\n\n## Kết quả\n\nB")
    assert [item["id"] for item in rendered.toc] == ["ket-qua", "ket-qua-2"]


def test_image_caption_becomes_semantic_figure():
    rendered = render_markdown("![Biểu đồ](/assets/test.webp)\n\nHình 1. Kết quả kiểm thử.")
    assert '<figure class="article-figure">' in rendered.html
    assert "<figcaption>Hình 1. Kết quả kiểm thử.</figcaption>" in rendered.html


def test_slug_and_tags_are_normalized():
    payload = post_input()
    data = payload.model_dump()
    data["slug"] = "  Valid-Slug  "
    data["tags"] = [" Web Security ", "web security", "SQL  Injection"]
    parsed = PostInput(**data)
    assert parsed.slug == "valid-slug"
    assert parsed.tags == ["Web Security", "SQL Injection"]


def test_slug_rejects_paths():
    data = post_input().model_dump()
    data["slug"] = "../research/admin"
    with pytest.raises(ValidationError):
        PostInput(**data)
