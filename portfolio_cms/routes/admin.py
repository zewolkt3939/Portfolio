from __future__ import annotations

import json
import re
import secrets
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import ROOT, Settings, get_settings
from ..content import apply_input, publish_post, restore_revision, snapshot
from ..database import get_db
from ..markdown import render_markdown
from ..media import InvalidImage, generate_og_image, store_image
from ..models import AdminUser, Post, PostRevision
from ..notion import NotionImporter, NotionImportError
from ..publications import display_date
from ..schemas import NotionImportInput, PostInput, PreviewInput, PublishChecklist
from ..security import (
    LOGIN_CSRF_COOKIE,
    SESSION_COOKIE,
    create_session,
    csrf_token,
    load_session,
    login_is_limited,
    login_subjects,
    record_login,
    require_admin,
    require_csrf,
    verify_password,
    verify_totp_or_recovery,
)


router = APIRouter(include_in_schema=False)
templates = Jinja2Templates(directory=ROOT / "portfolio_cms/templates")


def _cookie_args(settings: Settings) -> dict:
    return {"secure": settings.secure_cookies, "httponly": True, "samesite": "strict", "path": "/"}


def _admin(request: Request, db: Session):
    try:
        return require_admin(request, db)
    except HTTPException:
        return None


def _context(request: Request, db: Session, settings: Settings, **extra):
    auth = _admin(request, db)
    raw = auth[2] if auth else ""
    return {
        "request": request,
        "admin": auth[0] if auth else None,
        "csrf": csrf_token(raw, settings) if raw else "",
        **extra,
    }


def _must_admin(request: Request, db: Session):
    try:
        return require_admin(request, db)
    except HTTPException:
        raise HTTPException(status_code=401, detail="Cần đăng nhập admin") from None


def _validation_error(exc: Exception, status_code: int = 422):
    detail = exc.errors(include_context=False) if isinstance(exc, ValidationError) else str(exc)
    return JSONResponse({"detail": detail}, status_code=status_code)


@router.get("/admin/login", response_class=HTMLResponse)
def login_page(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if _admin(request, db):
        return RedirectResponse("/admin/posts", 303)
    token = secrets.token_urlsafe(32)
    response = templates.TemplateResponse(request, "admin/login.html", {"request": request, "login_csrf": token, "error": ""})
    response.set_cookie(LOGIN_CSRF_COOKIE, token, max_age=900, **_cookie_args(settings))
    return response


@router.post("/admin/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    login_csrf: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    cookie_token = request.cookies.get(LOGIN_CSRF_COOKIE, "")
    if not cookie_token or not secrets.compare_digest(cookie_token, login_csrf):
        raise HTTPException(status_code=403, detail="Phiên đăng nhập không hợp lệ")
    subjects = login_subjects(username, request, settings)
    if login_is_limited(db, subjects, settings):
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"request": request, "login_csrf": login_csrf, "error": "Quá nhiều lần thử. Hãy đợi 15 phút."},
            status_code=429,
        )
    user = db.scalar(select(AdminUser).where(AdminUser.username == username.strip().casefold(), AdminUser.is_active.is_(True)))
    if not user or not verify_password(password, user.password_hash):
        record_login(db, subjects, False)
        return templates.TemplateResponse(
            request,
            "admin/login.html",
            {"request": request, "login_csrf": login_csrf, "error": "Tên đăng nhập hoặc mật khẩu chưa đúng."},
            status_code=401,
        )
    record_login(db, subjects, True)
    raw, _ = create_session(db, user, authenticated=False, settings=settings)
    response = RedirectResponse("/admin/totp", 303)
    response.set_cookie(SESSION_COOKIE, raw, max_age=settings.session_absolute_days * 86400, **_cookie_args(settings))
    response.delete_cookie(LOGIN_CSRF_COOKIE, path="/")
    return response


@router.get("/admin/totp", response_class=HTMLResponse)
def totp_page(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    raw = request.cookies.get(SESSION_COOKIE)
    session = load_session(db, raw, require_authenticated=False, settings=settings)
    if not session:
        return RedirectResponse("/admin/login", 303)
    if session.authenticated:
        return RedirectResponse("/admin/posts", 303)
    return templates.TemplateResponse(
        request, "admin/totp.html", {"request": request, "csrf": csrf_token(raw or "", settings), "error": ""}
    )


@router.post("/admin/totp", response_class=HTMLResponse)
def totp_submit(
    request: Request,
    code: str = Form(...),
    csrf: str = Form(...),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    raw = request.cookies.get(SESSION_COOKIE)
    session = load_session(db, raw, require_authenticated=False, settings=settings)
    if not session or not secrets.compare_digest(csrf, csrf_token(raw or "", settings)):
        raise HTTPException(status_code=403, detail="Phiên xác minh không hợp lệ")
    subjects = login_subjects(session.user.username, request, settings)
    if login_is_limited(db, subjects, settings):
        return templates.TemplateResponse(
            request,
            "admin/totp.html",
            {"request": request, "csrf": csrf, "error": "Quá nhiều lần thử. Hãy đợi 15 phút."},
            status_code=429,
        )
    if not verify_totp_or_recovery(db, session.user, code, settings):
        record_login(db, subjects, False)
        return templates.TemplateResponse(
            request,
            "admin/totp.html",
            {"request": request, "csrf": csrf, "error": "Mã xác minh chưa đúng."},
            status_code=401,
        )
    session.authenticated = True
    session.user.last_login_at = datetime.now(timezone.utc)
    record_login(db, subjects, True)
    db.commit()
    return RedirectResponse("/admin/posts", 303)


@router.post("/admin/logout")
def logout(request: Request, csrf: str = Form(...), db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user, session, raw = _must_admin(request, db)
    if not secrets.compare_digest(csrf, csrf_token(raw, settings)):
        raise HTTPException(status_code=403, detail="CSRF token không hợp lệ")
    db.delete(session)
    db.commit()
    response = RedirectResponse("/admin/login", 303)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response


@router.get("/admin")
def admin_root():
    return RedirectResponse("/admin/posts", 303)


@router.get("/admin/posts", response_class=HTMLResponse)
def posts_page(
    request: Request,
    q: str = "",
    status: str = "",
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not _admin(request, db):
        return RedirectResponse("/admin/login", 303)
    query = select(Post).order_by(Post.updated_at.desc())
    if status in {"draft", "published", "archived"}:
        query = query.where(Post.status == status)
    rows = list(db.scalars(query).all())
    if q.strip():
        needle = q.strip().casefold()
        rows = [item for item in rows if needle in f"{item.title_vi} {item.title_en or ''} {item.slug}".casefold()]
    return templates.TemplateResponse(
        request, "admin/posts.html", _context(request, db, settings, posts=rows, q=q, status=status)
    )


def _empty_post() -> dict:
    return {
        "id": "", "slug": "", "kind": "research", "title_vi": "", "title_en": "",
        "summary_vi": "", "abstract_en": "", "body_markdown_vi": "", "platform": "",
        "machine": "", "difficulty": "", "evidence_type": "personal", "cover_url": "", "tags": [],
        "status": "draft", "has_unpublished_changes": False,
    }


@router.get("/admin/posts/new", response_class=HTMLResponse)
def new_post_page(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not _admin(request, db):
        return RedirectResponse("/admin/login", 303)
    return templates.TemplateResponse(
        request, "admin/editor.html", _context(request, db, settings, post=_empty_post(), revisions=[])
    )


@router.get("/admin/posts/{post_id}/edit", response_class=HTMLResponse)
def edit_post_page(request: Request, post_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not _admin(request, db):
        return RedirectResponse("/admin/login", 303)
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Không tìm thấy bài viết")
    data = snapshot(post)
    data.update({"id": post.id, "status": post.status, "has_unpublished_changes": post.has_unpublished_changes})
    return templates.TemplateResponse(
        request, "admin/editor.html", _context(request, db, settings, post=data, revisions=post.revisions[:20])
    )


@router.get("/admin/posts/{post_id}/preview", response_class=HTMLResponse)
def full_preview(request: Request, post_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not _admin(request, db):
        return RedirectResponse("/admin/login", 303)
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Không tìm thấy bài viết")
    return templates.TemplateResponse(
        request,
        "public/post.html",
        {
            "request": request,
            "locale": "vi",
            "base_url": settings.public_base_url,
            "display_date": lambda value: display_date(value, "vi"),
            "analytics_script_url": "",
            "analytics_website_id": "",
            "csp_nonce": getattr(request.state, "csp_nonce", ""),
            "post": snapshot(post),
            "related": [],
            "noindex": True,
            "json_ld": "{}",
        },
    )


@router.get("/admin/posts/{post_id}/revisions/{revision_id}", response_class=HTMLResponse)
def revision_page(
    request: Request,
    post_id: str,
    revision_id: str,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    if not _admin(request, db):
        return RedirectResponse("/admin/login", 303)
    post = db.get(Post, post_id)
    revision = db.get(PostRevision, revision_id)
    if not post or not revision or revision.post_id != post.id:
        raise HTTPException(404, "Không tìm thấy phiên bản")
    return templates.TemplateResponse(
        request,
        "admin/revision.html",
        _context(request, db, settings, post=post, revision=revision, data=json.loads(revision.snapshot)),
    )


@router.get("/admin/import/notion", response_class=HTMLResponse)
def notion_page(request: Request, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    if not _admin(request, db):
        return RedirectResponse("/admin/login", 303)
    return templates.TemplateResponse(request, "admin/notion.html", _context(request, db, settings))


def _json_payload(post: Post) -> dict:
    return {
        "id": post.id,
        "slug": post.slug,
        "status": post.status,
        "has_unpublished_changes": post.has_unpublished_changes,
        "updated_at": post.updated_at.isoformat(),
    }


@router.post("/api/admin/preview")
def preview(request: Request, payload: PreviewInput, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    _, _, raw = _must_admin(request, db)
    require_csrf(request, raw, settings)
    rendered = render_markdown(payload.body_markdown_vi)
    return {"html": rendered.html, "toc": rendered.toc, "reading_minutes": rendered.reading_minutes}


@router.post("/api/admin/posts")
def create_post(request: Request, payload: PostInput, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user, _, raw = _must_admin(request, db)
    require_csrf(request, raw, settings)
    post = Post(
        slug=payload.slug,
        title_vi=payload.title_vi,
        summary_vi=payload.summary_vi,
        abstract_en=payload.abstract_en,
        body_markdown_vi=payload.body_markdown_vi,
        body_html_cached="",
    )
    db.add(post)
    try:
        apply_input(db, post, payload, user.id)
    except (ValueError, ValidationError) as exc:
        db.rollback()
        return _validation_error(exc)
    return _json_payload(post)


@router.put("/api/admin/posts/{post_id}")
def save_post(request: Request, post_id: str, payload: PostInput, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user, _, raw = _must_admin(request, db)
    require_csrf(request, raw, settings)
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Không tìm thấy bài viết")
    try:
        apply_input(db, post, payload, user.id)
    except (ValueError, ValidationError) as exc:
        db.rollback()
        return _validation_error(exc)
    return _json_payload(post)


@router.post("/api/admin/posts/{post_id}/publish")
def publish(request: Request, post_id: str, checklist: PublishChecklist, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user, _, raw = _must_admin(request, db)
    require_csrf(request, raw, settings)
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Không tìm thấy bài viết")
    try:
        generate_og_image(post.slug, post.title_vi, post.kind, settings)
        post.cover_url = f"/assets/uploads/og/{post.slug}.png"
        publish_post(db, post, user.id, checklist)
    except ValueError as exc:
        db.rollback()
        return _validation_error(exc)
    return _json_payload(post)


@router.post("/api/admin/posts/{post_id}/archive")
def archive(request: Request, post_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user, _, raw = _must_admin(request, db)
    require_csrf(request, raw, settings)
    post = db.get(Post, post_id)
    if not post:
        raise HTTPException(404, "Không tìm thấy bài viết")
    post.status = "archived"
    post.updated_at = datetime.now(timezone.utc)
    db.add(PostRevision(post_id=post.id, editor_id=user.id, reason="archive", snapshot=json.dumps(snapshot(post), ensure_ascii=False)))
    db.commit()
    return _json_payload(post)


@router.post("/api/admin/posts/{post_id}/revisions/{revision_id}/restore")
def restore(request: Request, post_id: str, revision_id: str, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user, _, raw = _must_admin(request, db)
    require_csrf(request, raw, settings)
    post = db.get(Post, post_id)
    revision = db.get(PostRevision, revision_id)
    if not post or not revision or revision.post_id != post.id:
        raise HTTPException(404, "Không tìm thấy phiên bản")
    restore_revision(db, post, revision, user.id)
    return _json_payload(post)


@router.post("/api/admin/media")
async def upload_media(
    request: Request,
    image: UploadFile = File(...),
    alt_vi: str = Form(default=""),
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
):
    _, _, raw = _must_admin(request, db)
    require_csrf(request, raw, settings)
    data = await image.read(8 * 1024 * 1024 + 1)
    try:
        item = store_image(db, data, image.filename or "image", alt_vi, settings)
    except InvalidImage as exc:
        return _validation_error(exc)
    return {"url": item.public_url, "alt_vi": item.alt_vi, "width": item.width, "height": item.height}


def _slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value.replace("đ", "d").replace("Đ", "D")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:120] or "notion-draft"


@router.post("/api/admin/import/notion")
def import_notion(request: Request, payload: NotionImportInput, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)):
    user, _, raw = _must_admin(request, db)
    require_csrf(request, raw, settings)

    def save_image(data: bytes, name: str, alt: str):
        return store_image(db, data, name, alt, settings)

    importer = None
    try:
        importer = NotionImporter(settings.notion_api_token, settings.notion_api_version, save_image)
        imported = importer.import_page(payload.url)
        post = db.scalar(select(Post).where(Post.notion_page_id == imported.page_id))
        if not post:
            slug = _slugify(imported.title)
            base, number = slug, 2
            while db.scalar(select(Post).where(Post.slug == slug)):
                slug = f"{base}-{number}"
                number += 1
            post = Post(
                slug=slug,
                status="draft",
                title_vi=imported.title,
                summary_vi="Bản nháp nhập từ Notion, cần biên tập trước khi xuất bản.",
                abstract_en="Draft imported from Notion. Add an English abstract before publishing.",
                body_markdown_vi=imported.markdown,
                body_html_cached="",
                notion_page_id=imported.page_id,
                source_kind="notion",
            )
            db.add(post)
        data = PostInput(
            slug=post.slug,
            kind=post.kind,
            title_vi=imported.title,
            title_en=post.title_en,
            summary_vi=post.summary_vi or "Bản nháp nhập từ Notion, cần biên tập trước khi xuất bản.",
            abstract_en=post.abstract_en or "Draft imported from Notion. Add an English abstract before publishing.",
            body_markdown_vi=imported.markdown,
            platform=post.platform,
            machine=post.machine,
            difficulty=post.difficulty,
            evidence_type=post.evidence_type,
            cover_url=post.cover_url,
            tags=[tag.name for tag in post.tags] or ["Notion import"],
        )
        apply_input(db, post, data, user.id, reason="notion-import")
        post.notion_page_id = imported.page_id
        post.source_kind = "notion"
        db.commit()
        return {**_json_payload(post), "warnings": imported.warnings, "edit_url": f"/admin/posts/{post.id}/edit"}
    except (NotionImportError, InvalidImage, ValueError, ValidationError) as exc:
        db.rollback()
        return _validation_error(exc, 400)
    finally:
        if importer:
            importer.close()
