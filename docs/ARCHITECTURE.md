# Architecture

FUSAA is a modular monorepo: `backend` is the API and print-control plane, `local-agent` is the Windows data-plane executor, and `backend/app/web` is the initial mobile-first PWA shell. Future frontends can replace that shell without changing the API contract.

The hierarchy is Organization → Workshop → ComputerAgent → Printer. Documents and jobs belong to an Organization; each job is routed to one agent and one printer.

The cloud API has no inbound connection to the workshop PC. The agent authenticates, heartbeats, synchronizes printer inventory and polls its own command queue through HTTPS. WebSocket is only for dashboard notifications.

PostgreSQL is the production database. SQLite is enabled only as a zero-configuration local/test fallback. Alembic revision `0001_print_core` creates the initial schema.
