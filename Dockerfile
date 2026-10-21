FROM python:3.12-slim AS builder
WORKDIR /app
COPY pyproject.toml ./
COPY portfolio_cms ./portfolio_cms
RUN pip install --no-cache-dir --prefix=/install .

FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/usr/local/bin:$PATH"
RUN useradd --create-home --uid 10001 portfolio
WORKDIR /app
COPY --from=builder /install /usr/local
COPY alembic.ini ./
COPY migrations ./migrations
COPY portfolio_cms ./portfolio_cms
COPY content ./content
COPY seeds ./seeds
COPY assets ./assets
COPY dist ./dist
RUN mkdir -p /uploads && chown -R portfolio:portfolio /app /uploads
USER portfolio
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn portfolio_cms.main:app --host 0.0.0.0 --port 8000 --proxy-headers --forwarded-allow-ips=10.0.0.0/8"]
