from __future__ import annotations

from contextlib import asynccontextmanager
import secrets
from urllib.parse import urlparse

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .config import ROOT, get_settings
from .database import Base, engine
from .routes import admin, api, public


@asynccontextmanager
async def lifespan(_app: FastAPI):
    settings = get_settings()
    settings.validate_production_secrets()
    if settings.database_url.startswith("sqlite"):
        Base.metadata.create_all(engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Nguyen Truong Bao Portfolio API",
        version="1.0.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    @app.middleware("http")
    async def security_headers(request, call_next):
        request.state.csp_nonce = secrets.token_urlsafe(18)
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        analytics_origin = ""
        if settings.analytics_script_url:
            parsed = urlparse(settings.analytics_script_url)
            if parsed.scheme == "https" and parsed.hostname:
                analytics_origin = f" https://{parsed.netloc}"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; img-src 'self' data: https:; style-src 'self'; "
            f"script-src 'self' 'nonce-{request.state.csp_nonce}'{analytics_origin}; font-src 'self'; connect-src 'self'{analytics_origin}; object-src 'none'; "
            "base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
        )
        if settings.production:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains; preload"
        if request.url.path.startswith(("/admin", "/api/admin")):
            response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
        return response

    app.include_router(public.router)
    app.include_router(api.router)
    app.include_router(admin.router)
    app.mount("/admin-static", StaticFiles(directory=ROOT / "portfolio_cms/static"), name="admin-static")
    app.mount("/assets/uploads", StaticFiles(directory=settings.upload_dir), name="uploads")
    if (ROOT / "dist").exists():
        app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="site")
    return app


app = create_app()
