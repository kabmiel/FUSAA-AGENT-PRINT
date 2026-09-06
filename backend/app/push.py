import asyncio
import json
from pywebpush import WebPushException, webpush
from .config import settings
from .database import SessionLocal
from .models import OrganizationMember, PushSubscription

async def notify_organization(organization_id:str,event:str,payload:dict):
    if not settings.vapid_private_key or not settings.vapid_public_key:return
    await asyncio.to_thread(_send,organization_id,event,payload)

def _send(organization_id:str,event:str,payload:dict):
    db=SessionLocal()
    try:
        subscriptions=db.query(PushSubscription).join(OrganizationMember,PushSubscription.user_id==OrganizationMember.user_id).filter(OrganizationMember.organization_id==organization_id,OrganizationMember.role.in_(["OWNER","ADMIN"])).all()
        for subscription in subscriptions:
            try:webpush(subscription_info={"endpoint":subscription.endpoint,"keys":{"p256dh":subscription.p256dh,"auth":subscription.auth}},data=json.dumps({"event":event,"payload":payload}),vapid_private_key=settings.vapid_private_key,vapid_claims={"sub":settings.vapid_claim_email})
            except WebPushException as error:
                if getattr(error.response,"status_code",None) in {404,410}:db.delete(subscription)
        db.commit()
    finally:db.close()
