# FUSAA PRINT AGENT

Installation locale Windows : voir [fonctionnement autonome](docs/WINDOWS_AUTONOMY.md).
État des correctifs et vérifications : [audit et phase 14](docs/AUDIT_FIXES_PHASE14.md).

Monorepo for a secure, multi-workshop print orchestration platform. The browser manages jobs; only the outbound-connected Windows Local Agent can execute a physical print.

## MVP workflow

Upload a PDF/image → inspect and create a `WAITING_APPROVAL` job → select a synchronized printer → confirm → backend creates an idempotent command → Local Agent claims and executes it → agent reports `SUCCESS`/`FAILED` → dashboard updates through WebSocket.

## Quick start (development)

```powershell
# Renseignez le fichier .env unique à la racine du projet.
docker compose up --build
```

Backend docs: `http://localhost:8000/docs`; dashboard: `http://localhost:8000/`.

Create an initial user with the API (`POST /api/v1/auth/register`), create an organization/workshop, then run the local agent from `local-agent` using its generated enrollment token.

See `docs/ARCHITECTURE.md`, `docs/SECURITY.md`, `docs/PRINT_WORKFLOW.md`, and `docs/LOCAL_AGENT.md` before deploying.
