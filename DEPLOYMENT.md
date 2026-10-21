# VPS deployment runbook

For the selected Amazon Lightsail 4 GB production target, follow the detailed
[LIGHTSAIL_DEPLOYMENT.md](LIGHTSAIL_DEPLOYMENT.md) runbook. This file remains the
provider-neutral reference for the container stack.

The public site is hybrid: Caddy serves static portfolio pages and uploads, while
FastAPI renders Research/Write-up pages and the CMS. PostgreSQL is the only source
of published article content.

## 1. Prepare the server

Use Ubuntu 24.04 LTS with Docker Engine and the Compose plugin. Point the public
domain to the VPS before starting Caddy. Copy this repository to the server and
prepare the environment first:

```bash
cp .env.example .env
python3 -m pip install .
python3 -m portfolio_cms.cli fernet-key
```

Fill every `replace-with-...` value in `.env`. Use URL-safe random values for the
two database role passwords. Generate application secrets with
`openssl rand -base64 48`; generate `FIELD_ENCRYPTION_KEY` with
`python -m portfolio_cms.cli fernet-key`. Generate
`UMAMI_TWO_FACTOR_ENCRYPTION_KEY` with `openssl rand -base64 32`. The example pins
Umami to an immutable multi-architecture digest; test upgrades before changing it.
For releases from GHCR, set `APP_IMAGE` to the commit-SHA image.

After filling `.env`, export its values while building so the optional Umami
script is added to static pages:

```bash
set -a
. ./.env
set +a
python3 tools/build_site.py
python3 tools/check_site.py
python3 tools/package_site.py
```

## 2. Start and initialize

```bash
docker compose up -d postgres app caddy umami
docker compose exec app portfolio-cms create-admin --username bao
docker compose exec app portfolio-cms seed-legacy
docker compose ps
curl --fail https://YOUR_DOMAIN/health/ready
```

The admin command prints one TOTP provisioning URI and eight one-use recovery
codes. Store the codes offline. No registration route exists. Change Umami's
initial administrator password on first login and add the website ID to `.env`.
Rebuild the static Caddy image after setting analytics variables.

## 3. Backup schedule

The maintenance image creates a PostgreSQL custom dump and backs it up together
with the upload volume. Restic encrypts the repository and applies the policy of
7 daily, 4 weekly, and 6 monthly snapshots.

```bash
docker compose --profile maintenance run --rm backup
```

Add that command to root's systemd timer or cron once per day. Keep `.env` readable
only by the deployment account. Review backup output and alert on a nonzero exit.

Before considering the deployment complete, perform the restore drill once:

```bash
docker compose --profile maintenance run --rm --entrypoint portfolio-restore-check backup
```

The drill restores files into an isolated work directory, validates both database
dumps and the upload snapshot, restores them into temporary Portfolio and Umami
databases, checks the restored content, and removes the temporary databases.

## 4. Release and rollback

CI publishes `ghcr.io/OWNER/portfolio-cms:GIT_SHA` only after tests, dependency
audit, Bandit, migrations, static checks, and the container scan pass. To release:

```bash
APP_IMAGE=ghcr.io/OWNER/portfolio-cms:NEW_SHA docker compose pull app
APP_IMAGE=ghcr.io/OWNER/portfolio-cms:NEW_SHA docker compose up -d app
curl --fail https://YOUR_DOMAIN/health/ready
```

For rollback, repeat these commands with the previous SHA. Take a backup before a
schema migration. Alembic runs automatically when the app container starts.

## 5. Operational checks

- PostgreSQL and FastAPI have no host port; only Caddy publishes 80/443.
- `/admin`, preview API, and Umami's dashboard must stay out of public analytics.
- Test one draft, preview, publish, archive, revision restore, image upload, and
  Notion import after the first deploy.
- Verify EN/VI links, mobile width, sitemap, RSS, canonical and Open Graph output.
- Update the Notion integration token without committing it to the repository.
