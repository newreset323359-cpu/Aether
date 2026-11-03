# AETHER v1.0 deployment and Android setup

## Fastest evaluation deployment (Docker Compose + PostgreSQL)

1. Install Docker Engine and Docker Compose on a VPS or computer.
2. In the project root, copy `.env.example` to `.env`.
3. Replace all secret placeholders with random values. Generate values with:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```
   Use a different random value for `POSTGRES_PASSWORD`, `AETHER_JWT_SECRET`, and `AETHER_BOOTSTRAP_KEY`.
4. Set `AETHER_CORS_ORIGINS` to the exact URL origin used by your PWA, for example `http://192.168.1.20:8080` on a trusted LAN or your production `https://` domain.
5. Run:
   ```bash
   docker compose up --build -d
   docker compose ps
   docker compose logs -f aether-api
   ```
6. Open `http://SERVER_IP:8080` on Android while on the same trusted network. For internet access, put the web service behind HTTPS/TLS and firewall the database/API containers.
7. In the PWA, select **Institutional**, enter the same-origin backend URL, then choose **First-time admin setup**. Enter a username, a 12+ character password, and the one-time bootstrap key from `.env`.
8. After bootstrap succeeds, remove or rotate `AETHER_BOOTSTRAP_KEY` and restart the API service. Sign in normally on subsequent visits.
9. Admin can create users and grant roles using the documented `/api/v1/admin/*` endpoints.

## Direct backend development mode

```bash
cd backend
pip install -r requirements.txt
# Configure AETHER_DATABASE_URL, AETHER_JWT_SECRET, AETHER_BOOTSTRAP_KEY,
# and AETHER_CORS_ORIGINS in the environment first.
uvicorn app.main:app --host 0.0.0.0 --port 8000
```
Open the PWA separately and set API base to `http://SERVER_IP:8000`. CORS must include the PWA's exact origin. For Android, `127.0.0.1` means the phone itself, not your computer.

## Security essentials
- Use HTTPS/TLS outside localhost; HTTP on a LAN is not suitable for public exposure.
- Use unique secrets; do not commit `.env` or send secrets in chat.
- Restrict firewall access; never expose PostgreSQL publicly.
- Use PostgreSQL for multi-user deployment; SQLite is for local development/evaluation.
- JWTs expire after 60 minutes; the PWA holds the access token in sessionStorage.
- The v1.0 role policy enforces portfolio-scoped access: viewer/analyst are read-only, trader may write transaction-ledger entries, owner/manager may write portfolio data.
- Admin access is required for user administration, reference-data imports and audit logs.
- This is a hardened foundation, not a fully certified trading system. See `SECURITY_AND_INTEGRATIONS_v1.0.md` for remaining controls and vendor integration requirements.
