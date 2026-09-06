"""Scoped, local notifications. No message body, file content or print action."""
import hashlib
import ipaddress
import json
import secrets
from datetime import datetime,timedelta,timezone
from pathlib import Path
from typing import Literal
from fastapi import APIRouter,Depends,HTTPException,Request
from pydantic import BaseModel,Field
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .security import current_user
from .models import User,ComputerAgent,Workshop,LocalActivity,BrowserLink
from .access import accessible_workshop_ids,require_workshop_write,utc_datetime
from .events import hub

router=APIRouter(prefix="/api/v1")
def hash_value(value):return hashlib.sha256(value.encode()).hexdigest()
def loopback_only(request):
    host=request.client.host if request.client else ""
    try:allowed=ipaddress.ip_address(host).is_private or host in {"testclient"}
    except ValueError:allowed=False
    if not allowed:raise HTTPException(403,"Liaison disponible uniquement sur le réseau local")
def item_dict(item):
    return {"id":item.id,"source":item.source,"title":item.title,"detail":item.detail,"created_at":utc_datetime(item.created_at).isoformat()}

async def record_activity(db,workshop_id,user_id,event_key,source,title,detail):
    existing=db.query(LocalActivity).filter_by(event_key=event_key).first()
    if existing:return {"id":existing.id,"duplicate":True}
    item=LocalActivity(workshop_id=workshop_id,user_id=user_id,event_key=event_key,source=source,title=title,detail=detail)
    db.add(item)
    try:db.commit()
    except IntegrityError:
        db.rollback();existing=db.query(LocalActivity).filter_by(event_key=event_key).one()
        return {"id":existing.id,"duplicate":True}
    await hub.publish("LOCAL_ACTIVITY",{"activity_id":item.id},db.get(Workshop,workshop_id).organization_id)
    return {"id":item.id,"duplicate":False}

class DesktopEvent(BaseModel):
    event_id:str=Field(min_length=10,max_length=128)
    file_name:str=Field(min_length=1,max_length=255)
@router.post("/agent/{agent_id}/desktop-events")
async def desktop_event(agent_id:str,data:DesktopEvent,request:Request,db:Session=Depends(get_db)):
    agent=db.get(ComputerAgent,agent_id)
    key=request.headers.get("X-Agent-Key","")
    if not agent or not agent.agent_key or not secrets.compare_digest(agent.agent_key,key):raise HTTPException(401,"Agent non authentifié")
    name=Path(data.file_name).name
    return await record_activity(db,agent.workshop_id,None,hash_value(agent.id+":"+data.event_id),"DESKTOP","Nouveau fichier sur le Bureau",name+" — prêt à être sélectionné dans Nouveau document.")

@router.get("/activities")
def activities(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return [item_dict(item) for item in db.query(LocalActivity).filter(LocalActivity.workshop_id.in_(accessible_workshop_ids(db,user)),or_(LocalActivity.user_id.is_(None),LocalActivity.user_id==user.id)).order_by(LocalActivity.created_at.desc()).limit(100)]

class PairStart(BaseModel):
    workshop_id:str
@router.post("/browser-link/start")
def start_pair(data:PairStart,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_workshop_write(db,user,data.workshop_id)
    code=secrets.token_urlsafe(24)
    link=BrowserLink(user_id=user.id,workshop_id=data.workshop_id,pairing_hash=hash_value(code),expires_at=datetime.now(timezone.utc)+timedelta(minutes=10))
    db.add(link);db.commit()
    return {"code":code,"expires_in_minutes":10}

class PairFinish(BaseModel):
    code:str=Field(min_length=20,max_length=100)
@router.post("/browser-link/pair")
def pair(data:PairFinish,request:Request,db:Session=Depends(get_db)):
    loopback_only(request)
    link=db.query(BrowserLink).filter_by(pairing_hash=hash_value(data.code)).first()
    if not link or link.credential_hash or utc_datetime(link.expires_at)<datetime.now(timezone.utc):raise HTTPException(403,"Code expiré ou déjà utilisé")
    user=db.get(User,link.user_id)
    if not user or not user.is_active:raise HTTPException(403,"Compte inactif")
    require_workshop_write(db,user,link.workshop_id)
    credential=secrets.token_urlsafe(40)
    # Atomic consume: only one extension can exchange a pairing code.
    changed=db.query(BrowserLink).filter(BrowserLink.id==link.id,BrowserLink.credential_hash.is_(None)).update({"credential_hash":hash_value(credential),"enabled":True})
    if not changed:raise HTTPException(403,"Code déjà utilisé")
    db.commit()
    return {"credential":credential}

def authorized_browser(request,db):
    loopback_only(request)
    credential=request.headers.get("X-Fusaa-Link","")
    link=db.query(BrowserLink).filter_by(credential_hash=hash_value(credential),enabled=True).first()
    if not link:raise HTTPException(401,"Extension non associée")
    user=db.get(User,link.user_id)
    if not user or not user.is_active:raise HTTPException(403,"Compte inactif")
    require_workshop_write(db,user,link.workshop_id)
    return link

class BrowserEvent(BaseModel):
    event_id:str=Field(min_length=10,max_length=128)
    kind:Literal["MESSAGE","UNREAD"]
    count:int=Field(default=1,ge=1,le=999)
@router.post("/browser-link/events")
async def browser_event(data:BrowserEvent,request:Request,db:Session=Depends(get_db)):
    link=authorized_browser(request,db)
    link.last_seen_at=datetime.now(timezone.utc);link.page_ready=True
    # A duplicate event is intentionally a no-op for the inbox, but it is
    # still evidence that the paired page is alive. Persist the heartbeat
    # before idempotency can return early from record_activity().
    db.commit()
    title="Nouveau message WhatsApp" if data.kind=="MESSAGE" else "Nouveaux messages non lus sur WhatsApp"
    detail="Arrivée détectée dans Brave. Ouvrez WhatsApp pour consulter le message ou télécharger le fichier."
    return await record_activity(db,link.workshop_id,link.user_id,hash_value(link.id+":"+data.event_id),"WHATSAPP",title,detail)

class BrowserHeartbeat(BaseModel):
    page_ready:bool
@router.post("/browser-link/heartbeat")
def browser_heartbeat(data:BrowserHeartbeat,request:Request,db:Session=Depends(get_db)):
    link=authorized_browser(request,db);link.last_seen_at=datetime.now(timezone.utc);link.page_ready=data.page_ready;db.commit()
    return {"ok":True}

@router.post("/browser-link/unpair")
def unpair_browser(request:Request,db:Session=Depends(get_db)):
    """Let a locally paired extension revoke its own browser capability."""
    link=authorized_browser(request,db)
    link.enabled=False;link.credential_hash=None;link.page_ready=False;link.last_seen_at=datetime.now(timezone.utc)
    db.commit()
    return {"ok":True}

@router.post("/browser-link/revoke")
def revoke(user:User=Depends(current_user),db:Session=Depends(get_db)):
    db.query(BrowserLink).filter_by(user_id=user.id).update({"enabled":False,"expires_at":datetime.now(timezone.utc)})
    db.commit();return {"ok":True}

@router.get("/local-monitor/status")
def monitor_status(user:User=Depends(current_user),db:Session=Depends(get_db)):
    now=datetime.now(timezone.utc)
    links=db.query(BrowserLink).filter_by(user_id=user.id,enabled=True).all()
    live=[link for link in links if link.last_seen_at and now-utc_datetime(link.last_seen_at)<timedelta(seconds=100)]
    desktop={"state":"not_started"}
    path=Path(__file__).resolve().parents[2]/"local-agent"/"desktop-watch-health.json"
    try:
        data=json.loads(path.read_text(encoding="utf-8"))
        agent=db.get(ComputerAgent,data.get("agent_id"))
        if agent and agent.workshop_id in accessible_workshop_ids(db,user):
            last_check=utc_datetime(datetime.fromisoformat(data["last_check"]))
            desktop={"state":data["state"] if now-last_check<timedelta(seconds=45) else "stale","last_check":data["last_check"],"pending":data.get("pending",0)}
    except (OSError,TypeError,ValueError,KeyError):pass
    return {"desktop":desktop,"whatsapp":"watching" if any(link.page_ready for link in live) else "page_not_ready" if live else "disconnected" if links else "not_paired"}
