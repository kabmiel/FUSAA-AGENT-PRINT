# Security decisions

- Passwords are Argon2 hashes; API sessions are short-lived signed JWTs.
- Password changes/recovery increment a session version, revoking old API tokens and private event access. At the administrator's request, new passwords accept 4–128 characters without complexity rules; long unique passwords remain recommended.
- Activation (72 hours) and recovery (15 minutes) require random single-use proofs, hashed at rest. Old email-only invitations must be renewed. Forgotten administrator passwords are recovered from an authorized local/server console, not through public email lookup; see [account recovery](RECUPERATION_COMPTE.md).
- Agent enrollment uses a single generated token, then binds the agent to a machine fingerprint and rotates to a long random agent key. Do not put that key in source control.
- The agent can only retrieve documents referenced by commands assigned to it.
- The backend never sends shell, PowerShell, or dynamic Python instructions. The local agent has a fixed `PRINT` handler.
- Uploads accept only PDF/JPEG/PNG, have a 100 MB limit, are inspected before a job is created and retain the original file unchanged.
- Job transitions are validated. A print command has `print:<job_id>` as a unique idempotency key, protecting against repeated confirmation and reconnects.
- Important actions are persisted in `AuditLog`. Production mode rejects the bundled development JWT secret, SQLite and wildcard CORS. It enables trusted-host checks, security headers, JSON request logs and `/healthz`/`/readyz` probes.
- TLS, secret management, antivirus scanning, encrypted object storage, token rotation, application-level rate limiting, backup restoration drills and external security review remain deployment requirements.
