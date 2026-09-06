"""Privacy-preserving polling watcher for files arriving on the Windows Desktop.

Only a file name and a deterministic event id leave the computer.  File data,
paths and metadata are never uploaded.  A durable outbox makes an event safe
to retry when the local API is temporarily unavailable.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Callable


log = logging.getLogger("fusaa-agent.desktop")

SUPPORTED_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png"}
STATE_VERSION = 1
MAX_SENT_EVENTS = 1_000


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _atomic_json_write(path: Path, value: dict) -> None:
    """Write state without leaving a partial file after a power loss."""
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())
    for attempt in range(3):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            # Windows security software or an indexer can briefly hold either
            # filename. Retry before using the already-complete temp file.
            if attempt < 2:
                time.sleep(0.15 * (attempt + 1))
    try:
        path.write_bytes(temporary.read_bytes())
        temporary.unlink(missing_ok=True)
    except OSError:
        # Keep the in-memory state and let the next poll retry persistence.
        raise


class DesktopWatcher:
    """Poll one Desktop folder and post stable, new supported files once.

    A first scan establishes a baseline rather than notifying every document
    that already existed before FUSAA started.  Later files are sent after
    their size and modification time remain unchanged for ``stable_seconds``.
    """

    def __init__(
        self,
        directory: Path,
        state_file: Path,
        health_file: Path,
        *,
        stable_seconds: float = 4,
        poll_seconds: float = 2,
        max_backoff_seconds: float = 60,
        agent_id: str | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.state_file = Path(state_file)
        self.health_file = Path(health_file)
        self.stable_seconds = max(float(stable_seconds), 0)
        self.poll_seconds = max(float(poll_seconds), 0.25)
        self.max_backoff_seconds = max(float(max_backoff_seconds), 1)
        self.agent_id = agent_id
        self.state = self._load_state()
        self.last_error: str | None = None
        self.last_event_at: str | None = None
        self._normalize_state()

    def _empty_state(self) -> dict:
        return {
            "version": STATE_VERSION,
            "agent_id": self.agent_id,
            "initialized": False,
            "files": {},
            "pending": {},
            "sent": {},
        }

    def _load_state(self) -> dict:
        try:
            data = json.loads(self.state_file.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return data
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as error:
            log.warning("Desktop watcher state ignored: %s", error)
        return self._empty_state()

    def _normalize_state(self) -> None:
        self.state.setdefault("version", STATE_VERSION)
        self.state.setdefault("agent_id", self.agent_id)
        self.state.setdefault("initialized", False)
        for key in ("files", "pending", "sent"):
            if not isinstance(self.state.get(key), dict):
                self.state[key] = {}

    def set_agent_id(self, agent_id: str) -> None:
        """Bind durable state to the enrolled agent that owns it."""
        previous = self.state.get("agent_id")
        if previous and previous != agent_id:
            # A state file must not deduplicate files across two separate agents.
            self.agent_id = agent_id
            self.state = self._empty_state()
        else:
            self.agent_id = agent_id
            self.state["agent_id"] = agent_id
        self._save_state()

    def _save_state(self) -> None:
        self.state["version"] = STATE_VERSION
        self.state["agent_id"] = self.agent_id
        _atomic_json_write(self.state_file, self.state)

    @staticmethod
    def _path_key(path: Path) -> str:
        # casefold matches Windows' case-insensitive Desktop semantics.
        return str(path.resolve()).casefold()

    @staticmethod
    def _signature(path: Path) -> str:
        stat = path.stat()
        return f"{stat.st_size}:{stat.st_mtime_ns}"

    def _event_id(self, path_key: str, signature: str) -> str:
        digest = hashlib.sha256((path_key + "\0" + signature).encode("utf-8")).hexdigest()
        return "desktop-" + digest

    def _scan(self) -> dict[str, tuple[Path, str]]:
        if not self.directory.is_dir():
            raise RuntimeError(f"Desktop folder unavailable: {self.directory}")
        found: dict[str, tuple[Path, str]] = {}
        try:
            entries = list(self.directory.iterdir())
        except OSError as error:
            raise RuntimeError(f"Desktop folder cannot be read: {error}") from error
        for path in entries:
            if path.suffix.casefold() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                if not path.is_file():
                    continue
                found[self._path_key(path)] = (path, self._signature(path))
            except OSError:
                # A file can disappear while Windows Explorer is copying it.
                continue
        return found

    def _queue_stable_files(self, found: dict[str, tuple[Path, str]], now: float) -> None:
        files: dict = self.state["files"]
        pending: dict = self.state["pending"]

        if not self.state["initialized"]:
            # Establish a baseline for files that predate the watcher.
            for path_key, (_, signature) in found.items():
                files[path_key] = {
                    "signature": signature,
                    "changed_at": now,
                    "sent_signature": signature,
                }
            self.state["initialized"] = True
            return

        present = set(found)
        for path_key, (path, signature) in found.items():
            record = files.get(path_key)
            if not isinstance(record, dict) or record.get("signature") != signature:
                # A file that is still changing has not become a usable arrival yet.
                # Discard an older unsent version of the same file name.
                for event_id, item in list(pending.items()):
                    if isinstance(item, dict) and item.get("path_key") == path_key:
                        pending.pop(event_id, None)
                files[path_key] = {"signature": signature, "changed_at": now}
                continue

            changed_at = float(record.get("changed_at", now))
            if record.get("sent_signature") == signature or now - changed_at < self.stable_seconds:
                continue

            event_id = self._event_id(path_key, signature)
            if event_id in pending or event_id in self.state["sent"]:
                continue
            pending[event_id] = {
                "event_id": event_id,
                "path_key": path_key,
                "signature": signature,
                "file_name": path.name,
                "created_at": now,
                "attempts": 0,
                "next_attempt_at": now,
            }

        # A removed file can be forgotten once it has no notification to retry.
        pending_paths = {item.get("path_key") for item in pending.values() if isinstance(item, dict)}
        for path_key in list(files):
            if path_key not in present and path_key not in pending_paths:
                files.pop(path_key, None)

    def _remember_sent(self, event_id: str, now: float) -> None:
        sent: dict = self.state["sent"]
        sent[event_id] = now
        if len(sent) > MAX_SENT_EVENTS:
            for old_event, _ in sorted(sent.items(), key=lambda item: item[1])[: len(sent) - MAX_SENT_EVENTS]:
                sent.pop(old_event, None)

    def _flush_pending(self, notify: Callable[[dict], object], now: float) -> None:
        pending: dict = self.state["pending"]
        for event_id, item in list(pending.items()):
            if not isinstance(item, dict):
                pending.pop(event_id, None)
                continue
            if float(item.get("next_attempt_at", 0)) > now:
                continue
            payload = {"event_id": event_id, "file_name": item.get("file_name", "")}
            if not payload["file_name"]:
                pending.pop(event_id, None)
                continue
            try:
                notify(payload)
            except Exception as error:  # Network failures remain in the durable outbox.
                attempts = int(item.get("attempts", 0)) + 1
                item["attempts"] = attempts
                item["next_attempt_at"] = now + min(2**min(attempts, 6), self.max_backoff_seconds)
                self.last_error = f"Notification pending: {error}"
                log.warning("Desktop notification retained for retry: %s", error)
                continue

            pending.pop(event_id, None)
            file_record = self.state["files"].get(item.get("path_key"))
            if isinstance(file_record, dict) and file_record.get("signature") == item.get("signature"):
                file_record["sent_signature"] = item["signature"]
            self._remember_sent(event_id, now)
            self.last_event_at = _utc_now()
            self.last_error = None

    def _write_health(self, state: str, now_iso: str) -> None:
        health = {
            "agent_id": self.agent_id,
            "state": state,
            "last_check": now_iso,
            "pending": len(self.state["pending"]),
        }
        if self.last_event_at:
            health["last_event_at"] = self.last_event_at
        if self.last_error:
            health["last_error"] = self.last_error
        try:
            _atomic_json_write(self.health_file, health)
        except OSError as error:
            log.warning("Desktop watcher health not written: %s", error)

    def poll(self, notify: Callable[[dict], object], *, now: float | None = None) -> None:
        """Perform a single scan.  Kept public for deterministic unit tests."""
        instant = time.time() if now is None else float(now)
        now_iso = _utc_now()
        try:
            found = self._scan()
            self._queue_stable_files(found, instant)
            # Persist the outbox before attempting a network operation.
            self._save_state()
            self._flush_pending(notify, instant)
            self._save_state()
        except Exception as error:
            self.last_error = str(error)
            log.warning("Desktop watcher scan failed: %s", error)
            self._write_health("error", now_iso)
            return
        self._write_health("watching", now_iso)

    def run(self, notify: Callable[[dict], object], stop: Event) -> None:
        while not stop.is_set():
            self.poll(notify)
            stop.wait(self.poll_seconds)
