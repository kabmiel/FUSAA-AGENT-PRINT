"""Shared workshop authorization for HTTP and assistant tools."""
from fastapi import HTTPException
from sqlalchemy import or_, select
from .models import OrganizationMember, WorkshopMember, Workshop, PrintJob, Document
from .config import settings

def accessible_workshop_ids(db, user, write=False):
    admin_orgs=select(OrganizationMember.organization_id).where(OrganizationMember.user_id==user.id, OrganizationMember.role.in_(["OWNER","ADMIN"]))
    member_orgs=select(OrganizationMember.organization_id).where(OrganizationMember.user_id==user.id)
    assigned=select(WorkshopMember.workshop_id).where(WorkshopMember.user_id==user.id)
    if write: assigned=assigned.where(WorkshopMember.role.in_(["OPERATOR","MANAGER"]))
    query=db.query(Workshop).filter(Workshop.organization_id.in_(member_orgs),or_(Workshop.organization_id.in_(admin_orgs),Workshop.id.in_(assigned)))
    if settings.single_workshop_id:query=query.filter(Workshop.id==settings.single_workshop_id)
    return [w.id for w in query.all()]

def require_workshop_write(db,user,workshop_id):
    if workshop_id not in accessible_workshop_ids(db,user,write=True):raise HTTPException(403,"Operator access to this workshop is required")

def accessible_documents(db,user):
    admin_orgs=select(OrganizationMember.organization_id).where(OrganizationMember.user_id==user.id,OrganizationMember.role.in_(["OWNER","ADMIN"]))
    if settings.single_workshop_id:
        configured_org=select(Workshop.organization_id).where(Workshop.id==settings.single_workshop_id)
        admin_orgs=admin_orgs.where(OrganizationMember.organization_id.in_(configured_org))
    visible=select(PrintJob.document_id).where(PrintJob.workshop_id.in_(accessible_workshop_ids(db,user)))
    return db.query(Document).filter(or_(Document.organization_id.in_(admin_orgs),Document.id.in_(visible),Document.metadata_json["source_document_id"].as_string().in_(visible)))

def require_document_access(db,user,document):
    if not accessible_documents(db,user).filter(Document.id==document.id).first():raise HTTPException(403,"No access to this document")

def require_document_write(db,user,document):
    if settings.single_workshop_id:
        configured_org=db.query(Workshop.organization_id).filter(Workshop.id==settings.single_workshop_id).scalar()
        if configured_org and document.organization_id!=configured_org:raise HTTPException(403,"Document outside the configured FUSAA workshop")
    if db.query(OrganizationMember).filter(OrganizationMember.user_id==user.id,OrganizationMember.organization_id==document.organization_id,OrganizationMember.role.in_(["OWNER","ADMIN"])).first():return
    source=(document.metadata_json or {}).get("source_document_id",document.id)
    if not db.query(PrintJob).filter(PrintJob.document_id==source,PrintJob.workshop_id.in_(accessible_workshop_ids(db,user,write=True))).first():
        raise HTTPException(403,"Operator access to this document is required")

def utc_datetime(value):
    from datetime import timezone
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value
