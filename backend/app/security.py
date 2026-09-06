from datetime import datetime, timedelta, timezone
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib import PasswordHash
from sqlalchemy.orm import Session
from .config import settings
from .database import get_db
from .models import User

password_hash=PasswordHash.recommended()
bearer=HTTPBearer()
def hash_password(password:str)->str: return password_hash.hash(password)
def verify_password(password:str, hashed:str)->bool: return password_hash.verify(password, hashed)
def create_access_token(user_id:str)->str:
    return jwt.encode({"sub":user_id,"exp":datetime.now(timezone.utc)+timedelta(minutes=settings.access_token_minutes)},settings.jwt_secret,algorithm="HS256")
def current_user(credentials:HTTPAuthorizationCredentials=Depends(bearer),db:Session=Depends(get_db))->User:
    try: subject=jwt.decode(credentials.credentials,settings.jwt_secret,algorithms=["HS256"])["sub"]
    except Exception: raise HTTPException(status.HTTP_401_UNAUTHORIZED,"Invalid or expired token")
    user=db.get(User,subject)
    if not user or not user.is_active: raise HTTPException(status.HTTP_401_UNAUTHORIZED,"Inactive user")
    return user
