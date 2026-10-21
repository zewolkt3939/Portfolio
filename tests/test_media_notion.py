import io

import pytest
from PIL import Image

from portfolio_cms.config import Settings
from portfolio_cms.media import InvalidImage, store_image
from portfolio_cms.notion import NotionImportError, NotionImporter, parse_page_id, rich_text


def test_image_is_reencoded_without_metadata(db, tmp_path):
    source = io.BytesIO()
    image = Image.new("RGB", (80, 50), "#405d47")
    exif = Image.Exif()
    exif[0x010E] = "private caption"
    image.save(source, format="JPEG", exif=exif)
    cfg = Settings(database_url="sqlite://", upload_dir=tmp_path)
    media = store_image(db, source.getvalue(), "../camera.jpg", "Ảnh kết quả", cfg)
    stored = tmp_path / media.disk_path
    with Image.open(stored) as result:
        assert result.format == "WEBP"
        assert not result.getexif()
    assert media.original_name == "camera.jpg"
    assert media.size_bytes <= 8 * 1024 * 1024


def test_invalid_upload_is_rejected(db, tmp_path):
    with pytest.raises(InvalidImage):
        store_image(db, b"not-an-image", "payload.png", settings=Settings(upload_dir=tmp_path))


def test_notion_url_allowlist_and_page_id():
    page_id = parse_page_id("https://www.notion.so/Research-12345678123456781234567812345678")
    assert page_id == "12345678-1234-5678-1234-567812345678"
    with pytest.raises(NotionImportError):
        parse_page_id("https://attacker.example/notion/12345678123456781234567812345678")


def test_notion_block_conversion_marks_unknown_blocks():
    importer = NotionImporter.__new__(NotionImporter)
    importer.warnings = []
    importer._children = lambda _block_id: []
    blocks = [
        {"type": "heading_1", "heading_1": {"rich_text": [{"plain_text": "Mục", "annotations": {}}]}},
        {"type": "paragraph", "paragraph": {"rich_text": [{"plain_text": "Nội dung", "annotations": {"bold": True}}]}},
        {"type": "unsupported_demo", "unsupported_demo": {}},
    ]
    markdown = importer._blocks_to_markdown(blocks)
    assert "## Mục" in markdown
    assert "**Nội dung**" in markdown
    assert "unsupported_demo" in importer.warnings[0]
    assert rich_text([{"plain_text": "x", "annotations": {"code": True}}]) == "`x`"

