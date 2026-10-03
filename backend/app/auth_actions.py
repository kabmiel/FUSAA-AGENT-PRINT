"""Bearer links are random, hashed at rest, expiring and consumed atomically."""
from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from urllib.parse import urlencode

from fastapi import HTTPException
from .models import AuthActionToken, OrganizationMember, User


def require_link_scope(db, issuer, target, organization_id):
    """An organization invitation must not grant access to another organization."""
    member = db.query(OrganizationMember).filter_by(user_id=issuer.id, organization_id=organization_id).first()
    if not member or member.role not in {"OWNER", "ADMIN"}: raise HTTPException(403, "Accès administrateur requis")
    if target.id == issuer.id: return
    memberships = db.query(OrganizationMember).filter_by(user_id=target.id).all()
    if any(item.organization_id != organization_id for item in memberships) or (any(item.role in {"OWNER", "ADMIN"} for item in memberships) and member.role != "OWNER"):
        raise HTTPException(403, "Ce compte dépasse votre périmètre de récupération. Utilisez sa console autorisée.")


def issue_link(db, user, purpose):
    # Use the same user-first lock order as activation/reset, so renewal cannot
    # revive an old link while a password change is consuming/revoking it.
    user = db.query(User).filter_by(id=user.id).populate_existing().with_for_update().one()
    if (purpose == "ACTIVATE" and user.is_active) or (purpose == "RESET" and not user.is_active):
        raise HTTPException(409, "Le compte ne permet plus ce type de lien. Actualisez la liste.")
    now = datetime.now(timezone.utc)
    db.query(AuthActionToken).filter_by(user_id=user.id, purpose=purpose, consumed_at=None).update({"consumed_at": now}, synchronize_session=False)
    raw = secrets.token_urlsafe(32)
    expires = now + (timedelta(hours=72) if purpose == "ACTIVATE" else timedelta(minutes=15))
    db.add(AuthActionToken(user_id=user.id, purpose=purpose, token_hash=hashlib.sha256(raw.encode()).hexdigest(), expires_at=expires))
    path = "/inscription" if purpose == "ACTIVATE" else "/reinitialiser"
    # Fragments do not go into HTTP access logs or Referer headers.
    return path + "?" + urlencode({"email": user.email}) + "#" + urlencode({"token": raw})


def valid_action(db, raw, purpose):
    action = db.query(AuthActionToken).filter_by(token_hash=hashlib.sha256(raw.encode()).hexdigest(), purpose=purpose).first()
    now = datetime.now(timezone.utc)
    expires = action.expires_at if action else None
    if expires and expires.tzinfo is None: expires = expires.replace(tzinfo=timezone.utc)
    if not action or action.consumed_at is not None or expires <= now:
        raise HTTPException(400, "Ce lien est invalide, expiré ou déjà utilisé. Demandez un nouveau lien.")
    user = db.query(User).filter_by(id=action.user_id).populate_existing().with_for_update().first()
    if not user or (purpose == "ACTIVATE" and user.is_active) or (purpose == "RESET" and not user.is_active):
        raise HTTPException(400, "Ce lien ne correspond plus à l'état du compte. Demandez un nouveau lien.")
    return action, user


def consume_action(db, action):
    now = datetime.now(timezone.utc)
    changed = db.query(AuthActionToken).filter(AuthActionToken.id == action.id, AuthActionToken.consumed_at.is_(None), AuthActionToken.expires_at > now).update({"consumed_at": now}, synchronize_session=False)
    if not changed: raise HTTPException(409, "Ce lien vient d'être utilisé. Reconnectez-vous ou demandez un nouveau lien.")


def revoke_reset_links(db, user):
    db.query(AuthActionToken).filter_by(user_id=user.id, purpose="RESET", consumed_at=None).update({"consumed_at": datetime.now(timezone.utc)}, synchronize_session=False)
