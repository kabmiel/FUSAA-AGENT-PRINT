# Local Agent

Install Python 3.11+ on the Windows PC, then:

```powershell
cd local-agent
pip install -e ".[windows]"
$env:BACKEND_URL="https://your-api.example"
$env:ENROLLMENT_TOKEN="token-returned-when-the-agent-was-created"
python -m fusaa_agent.main
```

The state file contains the agent credential and its durable local command queue; protect it with the service account ACL. The agent never listens on a network port. It maintains an outbound WSS channel for immediate command notifications and uses HTTPS heartbeat/polling with exponential backoff as a reliable fallback. A command result is retained locally until the API acknowledges it, so a network loss after dispatch does not cause a repeat print. The server reclaims an unacknowledged command only after a five-minute lease.

For actual Windows printing, install `pywin32` and a trusted associated application capable of printing PDF/image files. Unsupported setups are reported as failed commands, not simulated as successful prints.

Cancellation is supported only while the selected Windows driver exposes a spooler job identifier. A driver without that identifier leaves the job in progress and reports a cancellation failure rather than claiming it was cancelled.

## Desktop notifications

The agent watches the current user's Desktop by polling it locally. New PDF, JPG/JPEG and PNG files are announced in FUSAA only after their size and modification time have remained unchanged for four seconds. Existing files establish the initial baseline and are not announced. FUSAA sends the file name and a deduplication identifier; it never uploads the file, its contents or its Desktop path.

The durable outbox in `desktop-watch-state.json` retries a notification after a local API interruption. `desktop-watch-health.json` feeds the System status screen. Both files stay on the PC.

Optional settings in `local-agent/.env`:

```text
DESKTOP_WATCH_ENABLED=true
DESKTOP_WATCH_DIRECTORY=C:\Users\YourName\Desktop
DESKTOP_WATCH_POLL_SECONDS=2
DESKTOP_WATCH_STABLE_SECONDS=4
```
