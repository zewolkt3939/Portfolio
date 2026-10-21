from __future__ import annotations

import hashlib
import io
import re
import warnings
from pathlib import Path
from uuid import uuid4

from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from sqlalchemy.orm import Session

from .config import ROOT, Settings, get_settings
from .models import Media


MAX_IMAGE_BYTES = 8 * 1024 * 1024
Image.MAX_IMAGE_PIXELS = 25_000_000


class InvalidImage(ValueError):
    pass


def store_image(
    db: Session,
    data: bytes,
    original_name: str,
    alt_vi: str = "",
    settings: Settings | None = None,
) -> Media:
    if not data or len(data) > MAX_IMAGE_BYTES:
        raise InvalidImage("Ảnh phải có dung lượng từ 1 byte đến 8 MB")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(io.BytesIO(data)) as probe:
                probe.verify()
            with Image.open(io.BytesIO(data)) as source:
                if source.format not in {"JPEG", "PNG", "WEBP"}:
                    raise InvalidImage("Chỉ chấp nhận JPEG, PNG hoặc WebP")
                image = source.convert("RGBA" if "A" in source.getbands() else "RGB")
                image.thumbnail((2400, 2400), Image.Resampling.LANCZOS)
                output = io.BytesIO()
                image.save(output, format="WEBP", quality=88, method=6)
                clean = output.getvalue()
                width, height = image.size
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, Image.DecompressionBombWarning) as exc:
        raise InvalidImage("Tệp tải lên không phải ảnh hợp lệ") from exc
    cfg = settings or get_settings()
    identifier = uuid4().hex
    relative = Path(identifier[:2]) / f"{identifier}.webp"
    target = (cfg.upload_dir / relative).resolve()
    if not target.is_relative_to(cfg.upload_dir.resolve()):
        raise InvalidImage("Đường dẫn upload không hợp lệ")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(clean)
    item = Media(
        public_url=f"/assets/uploads/{relative.as_posix()}",
        disk_path=str(relative.as_posix()),
        original_name=re.split(r"[\\/]", original_name)[-1][:255],
        mime_type="image/webp",
        size_bytes=len(clean),
        sha256=hashlib.sha256(clean).hexdigest(),
        width=width,
        height=height,
        alt_vi=alt_vi.strip()[:500],
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _font(path: Path, size: int):
    return ImageFont.truetype(str(path), size=size)


def generate_og_image(slug: str, title: str, kind: str, settings: Settings | None = None) -> str:
    cfg = settings or get_settings()
    width, height = 1200, 630
    canvas = Image.new("RGB", (width, height), "#f8f7f3")
    draw = ImageDraw.Draw(canvas)
    serif = _font(ROOT / "assets/fonts/NotoSerif.ttf", 68)
    sans = _font(ROOT / "assets/fonts/NotoSans.ttf", 25)
    mono = _font(ROOT / "assets/fonts/NotoSans.ttf", 18)
    draw.line((85, 82, width - 85, 82), fill="#d9dcd2", width=2)
    draw.text((85, 112), f"NGUYEN TRUONG BAO  /  {kind.upper()}", font=mono, fill="#405d47")
    words = title.split()
    lines, current = [], ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if draw.textlength(candidate, font=serif) > 1000 and current:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    y = 190
    for line in lines[:4]:
        draw.text((85, y), line, font=serif, fill="#222722")
        y += 86
    draw.text((85, 555), "Cybersecurity research & write-ups", font=sans, fill="#60665e")
    target = cfg.upload_dir / "og" / f"{slug}.png"
    target.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(target, format="PNG", optimize=True)
    return f"/assets/uploads/og/{slug}.png"
