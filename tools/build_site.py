"""Build English and Vietnamese static HTML from the shared content sources."""
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
import html
import json
import os
import re
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
NAV = {
    "en": [("about", "About"), ("projects", "Projects"), ("research", "Research"), ("certifications", "Certifications"), ("contact", "Contact")],
    "vi": [("about", "Giới thiệu"), ("projects", "Dự án"), ("research", "Nghiên cứu"), ("certifications", "Chứng chỉ"), ("contact", "Liên hệ")],
}
UI = {
    "en": {"skip": "Skip to content", "menu": "Menu", "primary": "Primary navigation", "student": "Cybersecurity student · Da Nang, Vietnam", "more": "More pages", "experience": "Experience", "skills": "Skills &amp; labs", "resume": "Résumé ↗", "motto": "Observe carefully. Test deliberately. Document clearly.", "switch": "Đọc bằng tiếng Việt", "code": "VI"},
    "vi": {"skip": "Đi đến nội dung", "menu": "Menu", "primary": "Điều hướng chính", "student": "Sinh viên An ninh mạng · Đà Nẵng, Việt Nam", "more": "Các trang khác", "experience": "Kinh nghiệm", "skills": "Kỹ năng &amp; thực hành", "resume": "Hồ sơ ↗", "motto": "Quan sát kỹ. Kiểm thử có chủ đích. Ghi chép rõ ràng.", "switch": "Read in English", "code": "EN"},
}


def translate_html(source, translations):
    """Translate exact text nodes and selected accessible attributes."""
    def text_node(match):
        value = match.group(1)
        stripped = value.strip()
        key = html.unescape(stripped)
        if not stripped or key not in translations:
            return match.group(0)
        leading = value[:len(value) - len(value.lstrip())]
        trailing = value[len(value.rstrip()):]
        return ">" + leading + html.escape(translations[key], quote=False) + trailing + "<"
    source = re.sub(r">([^<>]+)<", text_node, source)
    for attribute in ("aria-label", "alt"):
        source = re.sub(
            rf'{attribute}="([^"]+)"',
            lambda m: f'{attribute}="{html.escape(translations.get(html.unescape(m.group(1)), html.unescape(m.group(1))), quote=True)}"',
            source,
        )
    return source


def localize_paths(body, source_route, target_route, route_set, locale):
    """Keep HTML links inside the locale and shared assets at repository root."""
    attrs = re.compile(r'(?P<attr>href|src|poster)="(?P<url>[^"]+)"')
    source_parent = (ROOT / source_route).parent
    target_parent = (ROOT / target_route).parent
    def replace(match):
        raw = match.group("url")
        parsed = urlsplit(raw)
        if parsed.scheme or parsed.netloc or raw.startswith(("#", "mailto:", "tel:")):
            return match.group(0)
        source_target = (source_parent / parsed.path).resolve() if parsed.path else (ROOT / source_route).resolve()
        try:
            root_relative = source_target.relative_to(ROOT).as_posix()
        except ValueError:
            return match.group(0)
        final_target = ROOT / "vi" / root_relative if locale == "vi" and root_relative in route_set else ROOT / root_relative
        relative = os.path.relpath(final_target, target_parent).replace("\\", "/")
        if relative == ".":
            relative = ""
        localized = urlunsplit(("", "", relative, parsed.query, parsed.fragment))
        return f'{match.group("attr")}="{localized}"'
    return attrs.sub(replace, body)


def build():
    pages = json.loads((ROOT / "content/pages.json").read_text(encoding="utf-8"))
    translations = json.loads((ROOT / "content/vi.json").read_text(encoding="utf-8"))
    route_set = {page["route"] for page in pages}
    count = 0
    analytics_url = os.getenv("ANALYTICS_SCRIPT_URL", "").strip()
    analytics_id = os.getenv("ANALYTICS_WEBSITE_ID", "").strip()
    analytics = ""
    if analytics_url.startswith("https://") and analytics_id:
        analytics = f'<script defer src="{html.escape(analytics_url, quote=True)}" data-website-id="{html.escape(analytics_id, quote=True)}"></script>'
    for locale in ("en", "vi"):
        ui = UI[locale]
        for page in pages:
            if page.get("dynamic"):
                continue
            source_route = page["route"]
            route = source_route if locale == "en" else "vi/" + source_route
            prefix = "../" * route.count("/")
            home = prefix + ("index.html" if locale == "en" else "vi/index.html")
            nav_prefix = prefix + ("" if locale == "en" else "vi/")
            links = "".join(f'<a href="{nav_prefix}{key}.html"'+(' aria-current="page"' if page["nav"] == key else '')+f'>{label}</a>' for key, label in NAV[locale])
            body = (ROOT / "content" / (page.get("source_vi", page["source"]) if locale == "vi" else page["source"])).read_text(encoding="utf-8").replace("{{root}}", prefix)
            if locale == "vi":
                body = translate_html(body, translations)
            body = localize_paths(body, source_route, route, route_set, locale)
            raw_title = translations.get(page["title"], page["title"]) if locale == "vi" else page["title"]
            raw_description = translations.get(page["description"], page["description"]) if locale == "vi" else page["description"]
            title = html.escape(raw_title)
            description = html.escape(raw_description, quote=True)
            counterpart = prefix + (source_route if locale == "vi" else "vi/" + source_route)
            canonical = prefix + route
            en_link = prefix + source_route
            vi_link = prefix + "vi/" + source_route
            article_type = source_route.startswith("research/")
            output = f'''<!doctype html>
<html lang="{locale}">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title} | Nguyen Truong Bao</title>
  <meta name="description" content="{description}"><meta name="theme-color" content="#f6f8f9">
  <meta property="og:title" content="{title} | Nguyen Truong Bao"><meta property="og:description" content="{description}"><meta property="og:type" content="{'article' if article_type else 'website'}">
  <link rel="canonical" href="{canonical}"><link rel="alternate" hreflang="en" href="{en_link}"><link rel="alternate" hreflang="vi" href="{vi_link}"><link rel="alternate" hreflang="x-default" href="{en_link}">
  <link rel="icon" href="{prefix}assets/favicon.svg" type="image/svg+xml"><link rel="manifest" href="{prefix}site.webmanifest">
  <link rel="preload" href="{prefix}assets/fonts/NotoSans.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="preload" href="{prefix}assets/fonts/NotoSerif.woff2" as="font" type="font/woff2" crossorigin>
  <link rel="stylesheet" href="{prefix}styles.css?v=20261021-2"><script src="{prefix}script.js?v=20261021-2" defer></script>{analytics}
</head>
<body>
  <a class="skip-link" href="#main">{ui['skip']}</a>
  <header class="site-header"><div class="shell nav-wrap">
    <a class="brand" href="{home}" aria-label="Nguyen Truong Bao — {'Trang chủ' if locale == 'vi' else 'Home'}"><span class="brand-mark" aria-hidden="true">nb.</span><span>Nguyen Truong Bao<small>Cybersecurity / Portfolio</small></span></a>
    <button class="menu-toggle" type="button" aria-expanded="false" aria-controls="primary-nav" hidden>{ui['menu']} <span aria-hidden="true">+</span></button>
    <nav id="primary-nav" class="primary-nav" aria-label="{ui['primary']}">{links}<a class="language-switch" href="{counterpart}" lang="{'en' if locale == 'vi' else 'vi'}" hreflang="{'en' if locale == 'vi' else 'vi'}" aria-label="{ui['switch']}">{ui['code']}</a></nav>
  </div></header>
  <main id="main">{body}</main>
  <footer class="site-footer shell"><div><a class="footer-name" href="{home}">Nguyen Truong Bao</a><p>{ui['student']}</p></div><nav aria-label="{ui['more']}"><a href="{nav_prefix}experience.html">{ui['experience']}</a><a href="{nav_prefix}skills.html">{ui['skills']}</a><a href="{prefix}assets/resume/NguyenTruongBao_CV_VinSOC.pdf" target="_blank" rel="noreferrer">{ui['resume']}</a><a href="https://github.com/zewolkt3939" target="_blank" rel="noreferrer">GitHub ↗</a></nav><p class="colophon">{ui['motto']}<br>© 2026 Nguyen Truong Bao</p></footer>
  <div class="toast" role="status" aria-live="polite"></div>
</body></html>
'''
            target = ROOT / route
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(unicodedata.normalize("NFC", output), encoding="utf-8")
            count += 1
    print(f"Built {count} static pages in English and Vietnamese.")


if __name__ == "__main__":
    build()
