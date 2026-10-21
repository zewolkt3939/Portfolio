"""Create an allowlisted Lightsail deployment archive without private source files."""

from __future__ import annotations

import io
import tarfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "build" / "portfolio-lightsail.tar.gz"
ROOT_FILES = {
    ".dockerignore",
    ".env.example",
    ".gitattributes",
    "alembic.ini",
    "Caddyfile",
    "CMS_USER_GUIDE.md",
    "compose.yaml",
    "Coursera YZZXJ9446ZZN.pdf",
    "DEPLOYMENT.md",
    "DESIGN.md",
    "Dockerfile",
    "Dockerfile.backup",
    "Dockerfile.caddy",
    "LIGHTSAIL_DEPLOYMENT.md",
    "README.md",
    "RESEARCH_EDITORIAL.md",
    "pyproject.toml",
    "robots.txt",
    "script.js",
    "site.webmanifest",
    "styles.css",
    "WEBSITE_ARCHITECTURE.md",
}
DIRECTORIES = (
    "assets",
    "content",
    "deploy",
    "dist",
    "migrations",
    "portfolio_cms",
    "projects",
    "research",
    "seeds",
    "tools",
    "vi",
)
IGNORED_PARTS = {"__pycache__", ".pytest_cache", ".ruff_cache"}
IGNORED_SUFFIXES = {".db", ".pyc", ".pyo"}


def deployment_files() -> list[Path]:
    files = {ROOT / name for name in ROOT_FILES}
    files.update(ROOT.glob("*.html"))
    for directory in DIRECTORIES:
        files.update(path for path in (ROOT / directory).rglob("*") if path.is_file())
    return sorted(
        path
        for path in files
        if path.is_file()
        and not path.is_symlink()
        and not IGNORED_PARTS.intersection(path.relative_to(ROOT).parts)
        and path.suffix.casefold() not in IGNORED_SUFFIXES
    )


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    files = deployment_files()
    with tarfile.open(OUTPUT, "w:gz", format=tarfile.PAX_FORMAT) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            data = path.read_bytes()
            info = tarfile.TarInfo(relative)
            info.size = len(data)
            info.mtime = 0
            info.uid = info.gid = 0
            info.uname = info.gname = "root"
            info.mode = 0o755 if relative.startswith("deploy/") and relative.endswith(".sh") else 0o644
            archive.addfile(info, io.BytesIO(data))
    print(f"Created {OUTPUT} with {len(files)} allowlisted files.")


if __name__ == "__main__":
    main()
