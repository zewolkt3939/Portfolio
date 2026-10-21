import json

import pyotp
from bs4 import BeautifulSoup

from portfolio_cms import legacy
from portfolio_cms.legacy import seed_legacy_posts
from portfolio_cms.content import apply_input
from portfolio_cms.models import AdminUser
from portfolio_cms.security import encrypt_totp, password_hasher
from tests.helpers import new_post, post_input


def test_public_api_old_urls_filters_and_feeds(client, session_factory):
    total_expected = len(legacy.LEGACY_POSTS)
    writeups_expected = sum(1 for item in legacy.LEGACY_POSTS if item["kind"] == "writeup")
    htb_expected = sum(1 for item in legacy.LEGACY_POSTS if "HTB" in item["tags"])
    with session_factory() as db:
        created, updated, skipped = seed_legacy_posts(db)
        assert (created, updated, skipped) == (total_expected, 0, 0)
        assert seed_legacy_posts(db) == (0, 0, total_expected)
    response = client.get("/api/v1/posts")
    assert response.status_code == 200
    assert response.json()["total"] == total_expected
    assert "body_markdown_vi" not in response.json()["items"][0]
    assert client.get("/api/v1/posts?kind=writeup").json()["total"] == writeups_expected
    assert client.get("/api/v1/posts?tag=HTB").json()["total"] == htb_expected
    filtered_page = client.get("/research.html?platform=Hack%20The%20Box&difficulty=Very%20Easy")
    assert filtered_page.status_code == 200
    assert filtered_page.text.count('class="research-card"') == 3
    detail = client.get("/api/v1/posts/sql-parameterization")
    assert detail.status_code == 200
    assert "<script" not in detail.json()["html_vi"]
    english_page = client.get("/research/sql-parameterization.html")
    assert "SQL injection: testing the boundary between data and code" in english_page.text
    assert "Personal lab evidence" in english_page.text
    for path in ("/research/sql-parameterization.html", "/vi/research/sql-parameterization.html", "/research.html"):
        page = client.get(path)
        assert page.status_code == 200
        assert "hreflang=\"vi\"" in page.text
    assert client.get("/sitemap.xml").status_code == 200
    assert client.get("/feed.xml").status_code == 200
    assert "/admin" in client.get("/robots.txt").text


def test_legacy_seed_files_fall_back_to_working_directory(tmp_path, monkeypatch):
    source = tmp_path / "seeds" / "posts" / "sql-parameterization.md"
    source.parent.mkdir(parents=True)
    source.write_text("## Seed content\n\nThis body is long enough for validation.", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(legacy, "ROOT", tmp_path / "installed-package")

    post = legacy.read_legacy_post(legacy.LEGACY_POSTS[0])

    assert post.slug == "sql-parameterization"
    assert post.body_markdown_vi.startswith("## Seed content")


def test_password_totp_login_and_csrf(client, session_factory):
    secret = pyotp.random_base32()
    with session_factory() as db:
        db.add(AdminUser(
            username="bao",
            password_hash=password_hasher.hash("long-enough-test-password"),
            totp_secret_encrypted=encrypt_totp(secret),
            recovery_codes_json=json.dumps([]),
        ))
        db.commit()
    login = client.get("/admin/login")
    token = BeautifulSoup(login.text, "html.parser").select_one('[name="login_csrf"]')["value"]
    password_step = client.post(
        "/admin/login",
        data={"username": "bao", "password": "long-enough-test-password", "login_csrf": token},
        follow_redirects=False,
    )
    assert password_step.status_code == 303
    totp_page = client.get("/admin/totp")
    csrf = BeautifulSoup(totp_page.text, "html.parser").select_one('[name="csrf"]')["value"]
    second_step = client.post(
        "/admin/totp", data={"code": pyotp.TOTP(secret).now(), "csrf": csrf}, follow_redirects=False
    )
    assert second_step.status_code == 303
    posts = client.get("/admin/posts")
    assert posts.status_code == 200
    admin_csrf = BeautifulSoup(posts.text, "html.parser").body["data-csrf"]
    assert client.post("/api/admin/preview", json={"body_markdown_vi": "## Test"}).status_code == 403
    preview = client.post(
        "/api/admin/preview",
        json={"body_markdown_vi": "## Kiểm thử\n\nNội dung"},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert preview.status_code == 200
    assert "kiem-thu" in preview.json()["html"]
    payload = post_input("admin-flow").model_dump()
    created = client.post("/api/admin/posts", json=payload, headers={"X-CSRF-Token": admin_csrf})
    assert created.status_code == 200
    post_id = created.json()["id"]
    assert client.get("/research/admin-flow.html").status_code == 404
    full_preview = client.get(f"/admin/posts/{post_id}/preview")
    assert full_preview.status_code == 200
    assert full_preview.headers["x-robots-tag"].startswith("noindex")
    published = client.post(
        f"/api/admin/posts/{post_id}/publish",
        json={"retired_or_permitted": True, "redacted": True, "sources_checked": True},
        headers={"X-CSRF-Token": admin_csrf},
    )
    assert published.status_code == 200
    assert client.get("/research/admin-flow.html").status_code == 200
    assert "admin-flow.html" in client.get("/sitemap.xml").text
    archived = client.post(
        f"/api/admin/posts/{post_id}/archive", headers={"X-CSRF-Token": admin_csrf}
    )
    assert archived.status_code == 200
    assert client.get("/research/admin-flow.html").status_code == 404


def test_health_and_security_headers(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    assert response.headers["x-content-type-options"] == "nosniff"
    assert "frame-ancestors 'none'" in response.headers["content-security-policy"]
    admin = client.get("/admin/login")
    assert admin.headers["x-robots-tag"].startswith("noindex")
    paths = client.get("/api/openapi.json").json()["paths"]
    assert paths and all(not path.startswith(("/admin", "/api/admin")) for path in paths)


def test_draft_is_neither_public_nor_anonymous_preview(client, session_factory):
    data = post_input("private-draft")
    with session_factory() as db:
        post = new_post(data)
        db.add(post)
        apply_input(db, post, data, None)
        post_id = post.id
    assert client.get("/research/private-draft.html").status_code == 404
    preview = client.get(f"/admin/posts/{post_id}/preview", follow_redirects=False)
    assert preview.status_code == 303
    assert preview.headers["location"] == "/admin/login"
