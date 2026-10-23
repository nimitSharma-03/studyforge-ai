# Deployment Guide (Render)

StudyForge AI deploys as three Render resources:

| Resource | Render type | Purpose |
| --- | --- | --- |
| `studyforge-db` | PostgreSQL | All persistent data |
| `studyforge-api` | Web Service (Python) | FastAPI backend |
| `studyforge-web` | Static Site | React frontend served from Render's CDN |

Nothing is stored on the web service's disk, so Render's ephemeral filesystem is not a problem: uploaded files are processed in memory and discarded, and exports are generated per request.

## Option A — Blueprint (recommended)

1. Push the repository to GitHub.
2. In the Render dashboard choose **New → Blueprint**, connect the repository and confirm. Render reads [`render.yaml`](../render.yaml) and creates all three resources, wiring `DATABASE_URL` from the database into the API.
3. Wait for both services to finish their first deploy.
4. If Render assigned different hostnames than `studyforge-api.onrender.com` / `studyforge-web.onrender.com` (names are taken globally), update:
   - on **studyforge-api**: `ALLOWED_ORIGINS` = the static site URL;
   - on **studyforge-web**: `VITE_API_BASE_URL` = the API URL, then **Manual Deploy → Clear build cache & deploy** (Vite embeds the value at build time).

## Option B — Manual setup

### 1. PostgreSQL
New → PostgreSQL. Name `studyforge-db`, plan Free (or paid for durability), same region as the API. Copy the **Internal Database URL**.

### 2. API web service
New → Web Service → connect the repository.

| Setting | Value |
| --- | --- |
| Root directory | `backend` |
| Runtime | Python 3 |
| Build command | `pip install --upgrade pip && pip install -r requirements.txt` |
| Start command | `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers --forwarded-allow-ips "*" --timeout-keep-alive 30` |
| Health check path | `/api/health` |

Environment variables:

| Key | Value |
| --- | --- |
| `PYTHON_VERSION` | `3.11.9` |
| `APP_ENV` | `production` |
| `DATABASE_URL` | Internal Database URL from step 1 |
| `ALLOWED_ORIGINS` | Static site URL, e.g. `https://studyforge-web.onrender.com` |
| `MAX_UPLOAD_MB` | `25` |
| `ENABLE_DOCS` | `true` to keep `/docs` available for reviewers (optional) |

`postgres://` and `postgresql://` URLs are converted to the `postgresql+psycopg://` driver automatically. Tables are created on start-up.

### 3. Static site
New → Static Site → same repository.

| Setting | Value |
| --- | --- |
| Root directory | `frontend` |
| Build command | `npm ci && npm run build` |
| Publish directory | `dist` |
| Environment | `VITE_API_BASE_URL` = API URL (no trailing slash) |
| Redirects/Rewrites | Rewrite `/*` → `/index.html` (client-side routing) |

## Verification checklist

```bash
curl https://<api>/api/health          # {"status":"ok","database":"ok","database_backend":"postgresql",...}
curl -I https://<web>/app/learn        # 200 (SPA rewrite works for deep links)
```

Then open the site, click **Try the demo notes**, open a topic, ask a question, take a mid-semester test and check the results page. The repository's Playwright script automates this:

```bash
python scripts/e2e_smoke.py https://<web> e2e-screenshots
```

## Free-tier behaviour

- **Cold starts:** a free web service sleeps after about 15 minutes without requests; the next request can take up to a minute. The static site still loads instantly and shows a "connecting to the server" banner while it retries.
- **Database lifetime:** Render's free PostgreSQL instances are time-limited and are deleted unless upgraded. Upgrade the database plan for long-term persistence; the application needs no changes.
- **Single instance:** rate limits and the TF-IDF index cache are in memory, which is correct for one instance. Scaling to several instances would require a shared store (e.g. Redis) for rate limiting.
- **Memory:** the dependency set (scikit-learn, NumPy, PyMuPDF) fits comfortably in the free instance's 512 MB for typical lecture documents; very large uploads are bounded by `MAX_UPLOAD_MB` and `MAX_PAGES`.

## Troubleshooting

| Problem | Cause / fix |
| --- | --- |
| Browser shows CORS errors | `ALLOWED_ORIGINS` on the API does not exactly match the site origin (scheme + host, no trailing slash). |
| Frontend requests go to `localhost` | `VITE_API_BASE_URL` was missing at build time; set it and redeploy with cleared cache. |
| Deep links return 404 | Add the `/*` → `/index.html` rewrite on the static site. |
| Health check fails with `database: error` | Wrong `DATABASE_URL`, or the free database expired. |
| Build fails on Python version | Ensure `PYTHON_VERSION=3.11.9` (or `backend/.python-version`). |
