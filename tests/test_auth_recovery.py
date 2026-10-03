"""Focused account checks: in-memory database, no email/AI/server calls."""
import importlib.util
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app import database, main, recover_admin
from app.auth_actions import issue_link
from app.database import Base, get_db
from app.models import AuthActionToken, Organization, OrganizationMember, User, Workshop, WorkshopMember
from app.security import create_access_token, hash_password, verify_password


def proof(link): return parse_qs(urlsplit(link).fragment)["token"][0]


@pytest.fixture
def accounts(monkeypatch):
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    monkeypatch.setattr(main.settings, "single_workshop_id", "")
    with Session(engine, autoflush=False) as db:
        owner = User(id="owner", email="owner@example.com", display_name="Admin", password_hash=hash_password("1234"))
        viewer = User(id="viewer", email="viewer@example.com", display_name="Lecteur", password_hash=hash_password("4321"))
        db.add_all([owner, viewer, Organization(id="org", name="FUSAA")]); db.flush()
        db.add(Workshop(id="shop", organization_id="org", name="Atelier")); db.flush()
        for user, role in [(owner, "OWNER"), (viewer, "OPERATOR")]:
            db.add(OrganizationMember(organization_id="org", user_id=user.id, role=role))
            db.add(WorkshopMember(workshop_id="shop", user_id=user.id, role="OPERATOR"))
        db.commit()
        def override(): yield db
        previous = main.app.dependency_overrides.get(get_db)
        main.app.dependency_overrides[get_db] = override
        client = TestClient(main.app)  # No lifespan: never opens the real application DB.
        try: yield client, db, owner, viewer, engine
        finally:
            client.close()
            if previous is None: main.app.dependency_overrides.pop(get_db, None)
            else: main.app.dependency_overrides[get_db] = previous
    engine.dispose()


def auth(user): return {"Authorization": "Bearer " + create_access_token(user.id, user.auth_version)}


def test_activation_link_preserves_roles_and_requires_single_use_proof(accounts):
    client, db, owner, _, _ = accounts
    invited = client.post("/api/v1/workshops/shop/members", headers=auth(owner), json={"user_email": "invite@example.com", "role": "OPERATOR"})
    assert invited.status_code == 201
    raw = proof(invited.json()["registration_url"])
    payload = {"email": "invite@example.com", "display_name": "Invité", "password": "1234"}
    assert client.post("/api/v1/auth/login", json={"email": payload["email"], "password": "1234"}).status_code == 401
    assert client.post("/api/v1/auth/register", json=payload).status_code == 400
    assert client.post("/api/v1/auth/action/inspect", json={"token": raw, "purpose": "ACTIVATE"}).json()["email"] == payload["email"]
    assert client.post("/api/v1/auth/action/inspect", json={"token": raw, "purpose": "RESET"}).status_code == 400
    assert client.post("/api/v1/auth/register", json={**payload, "invitation_token": raw, "email": "another@example.com"}).status_code == 400
    result = client.post("/api/v1/auth/register", json={**payload, "invitation_token": raw})
    assert result.status_code == 201
    target = db.query(User).filter_by(email=payload["email"]).one()
    assert target.is_active and verify_password("1234", target.password_hash)
    assert db.query(OrganizationMember).filter_by(user_id=target.id).one().role == "OPERATOR"
    assert db.query(WorkshopMember).filter_by(user_id=target.id).one().role == "OPERATOR"
    assert client.post("/api/v1/auth/action/inspect", json={"token": raw, "purpose": "ACTIVATE"}).status_code == 400
    assert client.post("/api/v1/auth/register", json={**payload, "invitation_token": raw}).status_code == 409


def test_local_admin_recovery_revokes_old_sessions_and_link(accounts, monkeypatch, capsys):
    from starlette.websockets import WebSocketDisconnect
    from app import events
    client, db, owner, _, engine = accounts
    old_session = auth(owner)
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(database, "SessionLocal", lambda: Session(engine, autoflush=False))
    monkeypatch.setattr(main, "SessionLocal", lambda: Session(engine, autoflush=False))
    monkeypatch.setattr(events, "SessionLocal", lambda: Session(engine, autoflush=False))
    monkeypatch.setattr(sys, "argv", ["recover_admin", "--server", "--email", "owner@example.com", "--base-url", "https://fusaa.example"])
    recover_admin.main()  # Configured DB is replaced by our in-memory fixture.
    link = capsys.readouterr().out.strip().splitlines()[-1]
    assert link.startswith("https://fusaa.example/reinitialiser?")
    raw = proof(link)
    assert db.query(AuthActionToken).one().token_hash != raw
    reset = client.post("/api/v1/auth/password/reset", json={"token": raw, "password": "aaaa"})
    assert reset.status_code == 200
    assert client.post("/api/v1/auth/password/reset", json={"token": raw, "password": "bbbb"}).status_code == 400
    assert client.post("/api/v1/auth/login", json={"email": owner.email, "password": "1234"}).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": owner.email, "password": "aaaa"}).status_code == 200
    assert client.get("/api/v1/workshops/shop/members", headers=old_session).status_code == 401
    assert not events.EventHub.can_receive(owner.id, "org", {}, auth_version=0)
    with pytest.raises(WebSocketDisconnect) as denied:
        with client.websocket_connect("/ws/events?token=" + old_session["Authorization"].removeprefix("Bearer ")) as connection:
            connection.receive_json()
    assert denied.value.code == 1008
    assert client.get("/api/v1/workshops/shop/members", headers={"Authorization": "Bearer " + reset.json()["access_token"]}).status_code == 200
    assert client.get("/reinitialiser").headers["referrer-policy"] == "no-referrer"


def test_password_change_and_expired_links(accounts):
    client, db, owner, _, _ = accounts
    headers = auth(owner)
    link = issue_link(db, owner, "RESET"); db.commit()
    row = db.query(AuthActionToken).one(); row.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1); db.commit()
    assert client.post("/api/v1/auth/password/reset", json={"token": proof(link), "password": "aaaa"}).status_code == 400
    assert client.post("/api/v1/auth/password/change", headers=headers, json={"current_password": "wrong", "password": "abcd"}).status_code == 403
    assert client.post("/api/v1/auth/password/change", headers=headers, json={"current_password": "1234", "password": "    "}).status_code == 422
    result = client.post("/api/v1/auth/password/change", headers=headers, json={"current_password": "1234", "password": "abcd"})
    assert result.status_code == 200
    assert client.get("/api/v1/workshops/shop/members", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/login", json={"email": owner.email, "password": "abcd"}).status_code == 200


def test_reset_link_is_scoped_to_confirmed_administrator(accounts):
    client, db, owner, viewer, _ = accounts
    route = "/api/v1/workshops/shop/members/viewer/reset-link"
    assert client.post(route, headers=auth(viewer), json={"current_password": "4321"}).status_code == 403
    assert client.post(route, headers=auth(owner), json={"current_password": "wrong"}).status_code == 403
    good = client.post(route, headers=auth(owner), json={"current_password": "1234"})
    assert good.status_code == 200
    renewed = client.post(route, headers=auth(owner), json={"current_password": "1234"})
    assert client.post("/api/v1/auth/action/inspect", json={"token": proof(good.json()["reset_url"]), "purpose": "RESET"}).status_code == 400
    assert client.post("/api/v1/auth/action/inspect", json={"token": proof(renewed.json()["reset_url"]), "purpose": "RESET"}).status_code == 200
    db.add(Organization(id="outside", name="Autre organisation")); db.flush()
    db.add(OrganizationMember(organization_id="outside", user_id=viewer.id, role="OPERATOR")); db.commit()
    assert client.post(route, headers=auth(owner), json={"current_password": "1234"}).status_code == 403


def test_migration_adopts_existing_and_upgrades_legacy_sqlite(monkeypatch):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    source = ROOT / "backend/alembic/versions/0025_auth_recovery_links.py"
    spec = importlib.util.spec_from_file_location("auth_migration", source)
    migration = importlib.util.module_from_spec(spec); spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.context, "is_offline_mode", lambda: False)
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE users (id VARCHAR(36) PRIMARY KEY)"))
        connection.execute(text("INSERT INTO users VALUES ('legacy')"))
        with Operations.context(MigrationContext.configure(connection)):
            migration.upgrade(); migration.upgrade()
        assert connection.execute(text("SELECT auth_version FROM users WHERE id='legacy'")).scalar() == 0
        assert inspect(connection).has_table("auth_action_tokens")
    engine.dispose()
