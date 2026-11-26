# Deploy NextGen for Earth to Render

This repository includes `render.yaml` for a two-service deployment (Next.js web and FastAPI API) with a managed private Render PostgreSQL database. The web app calls the API through its same-origin Next.js proxy. The API is a separate Render web service with its own public hostname for health checks and controlled bootstrap; its protected routes still require authentication. Never expose database credentials or JWT secrets to the browser.

## Before deploying

1. Push the reviewed branch to GitHub. Confirm the repository includes `render.yaml`, both Dockerfiles, migrations, and the captured media assets.
2. Open the Render Dashboard and create a new Blueprint from the GitHub repository. Select `render.yaml` and review the resources before approving.
3. Keep all three services in the same region. The blueprint uses Frankfurt; change the region consistently if your workspace offers a closer supported region.
4. The API service uses a paid Starter plan because Render's pre-deploy migration command is not available on Free web services. The web service and database also use paid entry-level plans in this Blueprint. Review the current monthly estimate in Render before approving.
5. Set `PUBLIC_BASE_URL` on `nextgen-api` to the final HTTPS web URL (or the custom domain once attached). The initial Blueprint value assumes `https://nextgen-web.onrender.com`; correct it if Render assigns a different hostname. The Blueprint wires the frontend's `BACKEND_API_HOSTPORT` from the API service's internal hostname and port. Keep both services in the same region; Render resolves this reference automatically.

## First deployment

1. Wait for Postgres to become available.
2. The API pre-deploy command runs `uv run alembic upgrade head` before the API starts.
3. Confirm `https://<api-host>/api/health` reports healthy and the web service root returns HTTP 200.
4. Add the custom domain under the web service's Settings → Custom Domains and follow Render's DNS instructions. Do not point the public domain at the API service.
5. In the API service's Environment page, confirm `ENVIRONMENT=production`, a generated `JWT_SECRET_KEY`, the internal Postgres URL, and the correct `PUBLIC_BASE_URL`. Render's Postgres connection string uses the standard `postgresql://` form; the application normalizes it to `postgresql+asyncpg://`.

## Bootstrap the founder and organisation

Do not create a shared public demo password or disable authentication. After the API is live, run the bootstrap script from a trusted local checkout using a private terminal session and the API's HTTPS URL:

```bash
cd /path/to/odk-m106
source .venv/bin/activate
read -r -p 'Founder email: ' BOOTSTRAP_ADMIN_IDENTIFIER
printf 'Founder password: '
stty -echo
IFS= read -r BOOTSTRAP_ADMIN_PASSWORD
stty echo
printf '\n'
export BOOTSTRAP_ADMIN_IDENTIFIER BOOTSTRAP_ADMIN_PASSWORD
export BOOTSTRAP_API_URL='https://<api-host>/api'
export BOOTSTRAP_ORGANIZATION_NAME='Next Gen For Earth'
export BOOTSTRAP_ORGANIZATION_SLUG='next-gen-for-earth-demo'
export BOOTSTRAP_ORGANIZATION_COUNTRY_CODE='KE'
uv run python scripts/bootstrap_nextgen.py
unset BOOTSTRAP_ADMIN_IDENTIFIER BOOTSTRAP_ADMIN_PASSWORD
```

The script uses API workflows and is designed to be rerun safely. Keep the password out of shell history, source control, screenshots, and chat. Confirm the bootstrap output before running the website import.

## Import the public website catalogue and images

The importer accepts either the organisation slug or UUID:

```bash
uv run python -m scripts.import_nextgen_website \
  --organization-slug next-gen-for-earth-demo \
  --publish-website-content
```

For a staging-only tenant, the same option accepts the UUID shown in the admin UI. The importer stores source attribution and image manifest details. It does not create staff accounts or mark institutional partners as verified. Run the seed and import scripts against the Render database—not the local staging database—using the database's external connection URL from a trusted local terminal (include Render's required TLS setting). The API itself continues to use the internal database URL configured by the Blueprint. The organisation has confirmed permission and individual consent for the source website images and content used in this deployment. Preserve source attribution. Treat impact figures as organisation-reported, not independently audited.

## Production checks

- Verify login, session refresh/logout, role-based access, invitation acceptance, and organisation scoping.
- Verify public CMS, programme, people, partner, course, research, and gallery endpoints.
- Confirm CORS remains restrictive; the Next.js BFF is the public API access path.
- Configure backups and test a restore before importing operational data.
- Configure object storage before accepting user uploads; container filesystems are ephemeral.
- Add monitoring, error reporting, uptime checks, and a documented incident contact.
- Review the imported public catalogue and people listings after provisioning. Partner entries are source-listed organisations, not automatically verified active relationships.

## Notes

- `preDeployCommand` requires a paid Render web-service plan. Do not silently remove migrations to fit a free tier; use a paid plan or run the migration as a controlled one-off job before deploying.
- The included managed Postgres database starts on Render’s smallest paid database plan. Upgrade capacity and configure retention/backups to meet the organisation's recovery requirements.
- A staging environment should use a separate database, domain, JWT secret, and bootstrap owner identity from production.
