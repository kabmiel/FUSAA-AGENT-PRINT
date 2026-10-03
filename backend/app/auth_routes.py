from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from .database import get_db
from .models import User
from .schemas import AuthActionInspectIn, PasswordChangeIn, PasswordResetIn, TokenOut
from .security import current_user, create_access_token, hash_password, verify_password
from .auth_actions import valid_action, consume_action, revoke_reset_links
from .services import audit

router = APIRouter(prefix="/api/v1/auth", tags=["Accès et récupération"])


@router.post("/action/inspect")
def inspect_action(data: AuthActionInspectIn, db: Session = Depends(get_db)):
    action, user = valid_action(db, data.token, data.purpose)
    return {"email": user.email, "display_name": user.display_name, "expires_at": action.expires_at}


@router.post("/password/change", response_model=TokenOut)
def change_password(data: PasswordChangeIn, user: User = Depends(current_user), db: Session = Depends(get_db)):
    # Lock the live row, not just the object resolved by the dependency.
    version = user.auth_version or 0
    user = db.query(User).filter_by(id=user.id).populate_existing().with_for_update().one()
    if not user.is_active or (user.auth_version or 0) != version: raise HTTPException(401, "Session expirée. Reconnectez-vous.")
    if not verify_password(data.current_password, user.password_hash): raise HTTPException(403, "Mot de passe actuel incorrect")
    user.password_hash = hash_password(data.password)
    user.auth_version = (user.auth_version or 0) + 1
    revoke_reset_links(db, user)
    audit(db, user.id, "PASSWORD_CHANGED", "User", user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.auth_version))


@router.post("/password/reset", response_model=TokenOut)
def reset_password(data: PasswordResetIn, db: Session = Depends(get_db)):
    action, user = valid_action(db, data.token, "RESET")
    consume_action(db, action)
    user.password_hash = hash_password(data.password)
    user.auth_version = (user.auth_version or 0) + 1
    revoke_reset_links(db, user)
    audit(db, user.id, "PASSWORD_RESET", "User", user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.auth_version))
