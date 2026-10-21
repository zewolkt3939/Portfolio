from __future__ import annotations

import json
from html import escape
from math import ceil
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import ROOT, Settings, get_settings
from ..database import get_db
from ..publications import display_date, filter_posts, public_post, published_posts


router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=ROOT / "portfolio_cms/templates")


def _context(request: Request, locale: str, settings: Settings, **extra):
    return {
        "request": request,
        "locale": locale,
        "base_url": settings.public_base_url,
        "display_date": lambda value: display_date(value, locale),
        "analytics_script_url": settings.analytics_script_url,
        "analytics_website_id": settings.analytics_website_id,
        "csp_nonce": getattr(request.state, "csp_nonce", ""),
        **extra,
    }


@router.get("/health/live")
def live():
    return {"status": "ok"}


@router.get("/health/ready")
def ready(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ready"}


def _research_index(
    request: Request,
    locale: str,
    q: str,
    tag: str,
    kind: str,
    platform: str,
    difficulty: str,
    page: int,
    db: Session,
    settings: Settings,
):
    page_size = 12
    all_posts = published_posts(db)
    filtered = filter_posts(all_posts, q=q, tag=tag, kind=kind, platform=platform, difficulty=difficulty)
    pages = max(1, ceil(len(filtered) / page_size))
    page = min(page, pages)
    start = (page - 1) * page_size
    selected = filtered[start : start + page_size]
    all_tags = sorted(
        {tag_item["name"] for item in all_posts for tag_item in item.get("tags", [])},
        key=str.casefold,
    )
    platforms = sorted({item["platform"] for item in all_posts if item.get("platform")}, key=str.casefold)
    difficulties = sorted({item["difficulty"] for item in all_posts if item.get("difficulty")}, key=str.casefold)
    query = {"q": q, "tag": tag, "kind": kind, "platform": platform, "difficulty": difficulty}
    return templates.TemplateResponse(
        request,
        "public/research_index.html",
        _context(
            request,
            locale,
            settings,
            posts=selected,
            tags=all_tags,
            platforms=platforms,
            difficulties=difficulties,
            query=query,
            page=page,
            pages=pages,
            total=len(filtered),
            page_query=lambda number: urlencode({**query, "page": number}),
            noindex=False,
        ),
    )


@router.get("/research.html", response_class=HTMLResponse)
def research_en(
    request: Request,
    q: str = "",
    tag: str = "",
    kind: str = Query(default="", pattern=r"^(|research|writeup)$"),
    platform: str = Query(default="", max_length=80),
    difficulty: str = Query(default="", max_length=40),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return _research_index(request, "en", q, tag, kind, platform, difficulty, page, db, settings)


@router.get("/vi/research.html", response_class=HTMLResponse)
def research_vi(
    request: Request,
    q: str = "",
    tag: str = "",
    kind: str = Query(default="", pattern=r"^(|research|writeup)$"),
    platform: str = Query(default="", max_length=80),
    difficulty: str = Query(default="", max_length=40),
    page: int = Query(default=1, ge=1),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    return _research_index(request, "vi", q, tag, kind, platform, difficulty, page, db, settings)


def _post_page(request: Request, slug: str, locale: str, db: Session, settings: Settings):
    post = public_post(db, slug)
    if not post:
        raise HTTPException(status_code=404, detail="Không tìm thấy bài viết")
    related = []
    tag_slugs = {item["slug"] for item in post.get("tags", [])}
    for candidate in published_posts(db):
        if candidate["slug"] == slug:
            continue
        if tag_slugs & {item["slug"] for item in candidate.get("tags", [])}:
            related.append(candidate)
        if len(related) == 3:
            break
    return templates.TemplateResponse(
        request,
        "public/post.html",
        _context(
            request,
            locale,
            settings,
            post=post,
            related=related,
            noindex=False,
            json_ld=json.dumps(
                {
                    "@context": "https://schema.org",
                    "@type": "BlogPosting",
                    "headline": post.get("title_vi"),
                    "alternativeHeadline": post.get("title_en"),
                    "description": post.get("abstract_en"),
                    "datePublished": post.get("published_at"),
                    "dateModified": post.get("updated_at"),
                    "author": {"@type": "Person", "name": "Nguyen Truong Bao"},
                    "mainEntityOfPage": f"{settings.public_base_url}/research/{slug}.html",
                    "image": f"{settings.public_base_url}{post.get('cover_url')}" if post.get("cover_url") else None,
                },
                ensure_ascii=False,
            ).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"),
        ),
    )


@router.get("/research/{slug}.html", response_class=HTMLResponse)
def post_en(request: Request, slug: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _post_page(request, slug, "en", db, settings)


@router.get("/vi/research/{slug}.html", response_class=HTMLResponse)
def post_vi(request: Request, slug: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _post_page(request, slug, "vi", db, settings)


@router.get("/sitemap.xml")
def sitemap(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    static_routes = ["", "about.html", "projects.html", "certifications.html", "experience.html", "skills.html", "contact.html"]
    urls = []
    for route in static_routes + ["research.html"]:
        for prefix in ("", "vi/"):
            urls.append(f"<url><loc>{settings.public_base_url}/{prefix}{route}</loc></url>")
    for item in published_posts(db):
        for prefix in ("", "vi/"):
            urls.append(
                f"<url><loc>{settings.public_base_url}/{prefix}research/{item['slug']}.html</loc>"
                f"<lastmod>{(item.get('updated_at') or '')[:10]}</lastmod></url>"
            )
    body = '<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' + "".join(urls) + "</urlset>"
    return Response(body, media_type="application/xml")


@router.get("/robots.txt")
def robots(settings: Settings = Depends(get_settings)):
    body = f"User-agent: *\nAllow: /\nDisallow: /admin\nDisallow: /api/admin\nSitemap: {settings.public_base_url}/sitemap.xml\n"
    return Response(body, media_type="text/plain")


def _feed(locale: str, db: Session, settings: Settings):
    title = "Ghi chép an ninh mạng của Nguyễn Trường Bảo" if locale == "vi" else "Nguyen Truong Bao — Security research"
    prefix = "/vi" if locale == "vi" else ""
    entries = []
    for item in published_posts(db)[:20]:
        link = f"{settings.public_base_url}{prefix}/research/{item['slug']}.html"
        entries.append(
            f"<entry><title>{escape(item['title_vi'], quote=False)}</title><id>{escape(link, quote=False)}</id><link href=\"{escape(link, quote=True)}\"/>"
            f"<updated>{escape(item.get('updated_at') or '')}</updated><summary>{escape(item['abstract_en'] if locale == 'en' else item['summary_vi'])}</summary></entry>"
        )
    body = f'<?xml version="1.0" encoding="UTF-8"?><feed xmlns="http://www.w3.org/2005/Atom"><title>{escape(title, quote=False)}</title><id>{escape(settings.public_base_url + prefix + "/research.html", quote=False)}</id>' + "".join(entries) + "</feed>"
    return Response(body, media_type="application/atom+xml")


@router.get("/feed.xml")
def feed_en(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _feed("en", db, settings)


@router.get("/vi/feed.xml")
def feed_vi(db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    return _feed("vi", db, settings)
