# Deployment checklist

1. Install Docker Engine on the server and terminate TLS at a reverse proxy (Caddy, Nginx or Traefik).
2. Copy `.env.example` to `.env`; set a random `JWT_SECRET` (32+ characters), a strong `POSTGRES_PASSWORD`, explicit `CORS_ORIGINS`, `TRUSTED_HOSTS`, and `ENVIRONMENT=production`.
3. Use PostgreSQL; SQLite is rejected in production mode.
4. Start with `docker compose up --build -d`. The API waits for PostgreSQL and runs Alembic migrations before serving traffic.
5. Check `GET /healthz` and `GET /readyz` through the reverse proxy.
6. Back up the PostgreSQL volume and document storage daily. Test restoration before relying on backups.
7. Configure VAPID keys and HTTPS before enabling Web Push.
8. Enroll each Windows agent only after confirming the API certificate and its workshop.

The production backend disables interactive API documentation by default. Keep `.env`, agent state files, VAPID/private keys and database backups outside Git.
