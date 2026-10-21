import re

from pydantic import BaseModel, Field, field_validator


SLUG_PATTERN = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class PostInput(BaseModel):
    slug: str = Field(min_length=3, max_length=120)
    kind: str = Field(pattern=r"^(research|writeup)$")
    title_vi: str = Field(min_length=3, max_length=240)
    title_en: str | None = Field(default=None, max_length=240)
    summary_vi: str = Field(min_length=10, max_length=800)
    abstract_en: str = Field(min_length=30, max_length=5000)
    body_markdown_vi: str = Field(min_length=20, max_length=300_000)
    platform: str | None = Field(default=None, max_length=80)
    machine: str | None = Field(default=None, max_length=120)
    difficulty: str | None = Field(default=None, max_length=40)
    evidence_type: str = Field(pattern=r"^(personal|reference)$")
    cover_url: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("slug")
    @classmethod
    def valid_slug(cls, value: str) -> str:
        value = value.strip().lower()
        if not SLUG_PATTERN.fullmatch(value):
            raise ValueError("slug chỉ gồm chữ thường ASCII, số và dấu gạch ngang")
        return value

    @field_validator("title_vi", "title_en", "summary_vi", "abstract_en", "platform", "machine", "difficulty")
    @classmethod
    def trim_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, values: list[str]) -> list[str]:
        result = []
        for value in values:
            value = re.sub(r"\s+", " ", value.strip())[:80]
            if value and value.casefold() not in {item.casefold() for item in result}:
                result.append(value)
        return result


class PreviewInput(BaseModel):
    body_markdown_vi: str = Field(max_length=300_000)


class PublishChecklist(BaseModel):
    retired_or_permitted: bool = False
    redacted: bool = False
    sources_checked: bool = False


class NotionImportInput(BaseModel):
    url: str = Field(min_length=20, max_length=1000)

