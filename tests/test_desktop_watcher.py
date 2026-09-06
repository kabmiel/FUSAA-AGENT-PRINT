import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "local-agent"))

from fusaa_agent.desktop_watcher import DesktopWatcher
from fusaa_agent.main import Agent, Settings


def watcher_for(tmp_path, *, stable_seconds=2):
    desktop = tmp_path / "Desktop"
    desktop.mkdir()
    return desktop, DesktopWatcher(
        desktop,
        tmp_path / "desktop-watch-state.json",
        tmp_path / "desktop-watch-health.json",
        stable_seconds=stable_seconds,
        agent_id="agent-test",
    )


def test_desktop_watcher_notifies_only_new_stable_supported_files(tmp_path):
    desktop, watcher = watcher_for(tmp_path)
    (desktop / "already-there.pdf").write_bytes(b"old")
    sent = []

    watcher.poll(sent.append, now=0)
    (desktop / "ignore.txt").write_text("not printable")
    document = desktop / "devis client.PNG"
    document.write_bytes(b"copying")
    watcher.poll(sent.append, now=1)
    document.write_bytes(b"copying is still in progress")
    watcher.poll(sent.append, now=2)
    watcher.poll(sent.append, now=3.9)
    assert sent == []

    watcher.poll(sent.append, now=4.1)
    assert len(sent) == 1
    assert sent[0]["file_name"] == "devis client.PNG"
    assert set(sent[0]) == {"event_id", "file_name"}
    assert sent[0]["event_id"].startswith("desktop-")

    watcher.poll(sent.append, now=10)
    assert len(sent) == 1
    health = json.loads((tmp_path / "desktop-watch-health.json").read_text())
    assert health["state"] == "watching"
    assert health["agent_id"] == "agent-test"
    assert health["pending"] == 0


def test_desktop_watcher_persists_outbox_and_retries_without_duplicates(tmp_path):
    desktop, watcher = watcher_for(tmp_path, stable_seconds=1)
    watcher.poll(lambda _: None, now=0)
    (desktop / "arrivee.pdf").write_bytes(b"pdf")
    watcher.poll(lambda _: None, now=1)

    calls = []

    def unavailable(payload):
        calls.append(payload)
        raise OSError("API temporarily unavailable")

    watcher.poll(unavailable, now=2)
    durable = json.loads((tmp_path / "desktop-watch-state.json").read_text())
    assert len(durable["pending"]) == 1

    restarted = DesktopWatcher(
        desktop,
        tmp_path / "desktop-watch-state.json",
        tmp_path / "desktop-watch-health.json",
        stable_seconds=1,
        agent_id="agent-test",
    )
    restarted.poll(calls.append, now=3)
    assert len(calls) == 1  # backoff prevents an immediate duplicate retry
    restarted.poll(calls.append, now=4)
    assert len(calls) == 2
    assert calls[0] == calls[1]
    durable = json.loads((tmp_path / "desktop-watch-state.json").read_text())
    assert durable["pending"] == {}
    assert len(durable["sent"]) == 1


def test_desktop_watcher_reports_an_unavailable_desktop(tmp_path):
    watcher = DesktopWatcher(
        tmp_path / "missing-desktop",
        tmp_path / "state.json",
        tmp_path / "desktop-watch-health.json",
        agent_id="agent-test",
    )
    watcher.poll(lambda _: None, now=0)
    health = json.loads((tmp_path / "desktop-watch-health.json").read_text())
    assert health["state"] == "error"
    assert health["agent_id"] == "agent-test"
    assert health["pending"] == 0


def test_agent_posts_desktop_event_to_its_scoped_endpoint(tmp_path):
    agent = Agent(Settings(state_file=tmp_path / "agent.json", _env_file=None))
    agent.client.close()
    calls = []
    agent.client = SimpleNamespace(
        post=lambda url, **kwargs: (
            calls.append((url, kwargs)) or SimpleNamespace(raise_for_status=lambda: None)
        )
    )
    agent.state = {"agent_id": "agent-42", "agent_key": "local-key"}

    agent.report_desktop_event({"event_id": "desktop-123456", "file_name": "bon.pdf"})
    assert calls == [
        (
            "/api/v1/agent/agent-42/desktop-events",
            {
                "headers": {"X-Agent-Key": "local-key"},
                "json": {"event_id": "desktop-123456", "file_name": "bon.pdf"},
            },
        )
    ]
