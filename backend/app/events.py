import asyncio
from fastapi import WebSocket
from .push import notify_organization
from .database import SessionLocal
from .models import User, OrganizationMember, PrintJob, ComputerAgent, Workshop, Document, LocalActivity
from .access import accessible_workshop_ids, accessible_documents

class EventHub:
    def __init__(self): self.connections={}
    async def connect(self,ws:WebSocket,organizations:set[str],user_id=None): await ws.accept(); self.connections[ws]=(organizations,user_id)
    def disconnect(self,ws:WebSocket): self.connections.pop(ws,None)
    async def publish(self,event:str,payload:dict,organization_id:str):
        for ws,(organizations,user_id) in list(self.connections.items()):
            if organization_id not in organizations: continue
            if not self.can_receive(user_id,organization_id,payload):continue
            try: await ws.send_json({"event":event,"payload":payload})
            except Exception: self.disconnect(ws)
        if event!="LOCAL_ACTIVITY":await notify_organization(organization_id,event,payload)
    @staticmethod
    def can_receive(user_id,organization_id,payload):
        with SessionLocal() as db:
            user=db.get(User,user_id)
            if not user or not user.is_active:return False
            member=db.query(OrganizationMember).filter_by(user_id=user_id,organization_id=organization_id).first()
            if not member:return False
            if payload.get("activity_id"):
                activity=db.get(LocalActivity,payload["activity_id"])
                workshop=db.get(Workshop,activity.workshop_id) if activity else None
                return bool(activity and workshop and workshop.organization_id==organization_id and activity.workshop_id in accessible_workshop_ids(db,user) and (activity.user_id is None or activity.user_id==user_id))
            workshops=accessible_workshop_ids(db,user)
            if payload.get("job_id"):
                job=db.get(PrintJob,payload["job_id"])
                return bool(job and job.organization_id==organization_id and (member.role in {"OWNER","ADMIN"} or job.workshop_id in workshops))
            if payload.get("agent_id"):
                agent=db.get(ComputerAgent,payload["agent_id"])
                workshop=db.get(Workshop,agent.workshop_id) if agent else None
                return bool(agent and workshop and workshop.organization_id==organization_id and (member.role in {"OWNER","ADMIN"} or agent.workshop_id in workshops))
            if payload.get("document_id"):
                document=db.get(Document,payload["document_id"])
                return bool(document and document.organization_id==organization_id and (member.role in {"OWNER","ADMIN"} or accessible_documents(db,user).filter(Document.id==document.id).first() is not None))
            return member.role in {"OWNER","ADMIN"}
hub=EventHub()

class AgentHub:
    """Ephemeral outbound WSS notification channel; command retrieval remains idempotent HTTP."""
    def __init__(self): self.connections:dict[str,WebSocket]={}
    async def connect(self,agent_id:str,ws:WebSocket): await ws.accept();self.connections[agent_id]=ws
    def disconnect(self,agent_id:str,ws:WebSocket):
        if self.connections.get(agent_id) is ws:self.connections.pop(agent_id,None)
    async def notify(self,agent_id:str,event:str):
        ws=self.connections.get(agent_id)
        if not ws:return
        try:await ws.send_json({"event":event})
        except Exception:self.connections.pop(agent_id,None)
agent_hub=AgentHub()
