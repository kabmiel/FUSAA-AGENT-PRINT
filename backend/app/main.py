import secrets
import jwt
import hashlib
import json
import io
import zipfile
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import FileResponse, HTMLResponse, PlainTextResponse, StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy import text, or_, JSON
from .config import settings
from .database import Base, SessionLocal, engine, get_db
from .events import agent_hub, hub
from .models import AgentCommand, AuditLog, CommandStatus, ComputerAgent, Connector, ConnectorEvent, Customer, Document, Invoice, InvoiceLine, JobStatus, Organization, OrganizationMember, Payment, PriceRule, PrintCost, PrintJob, Printer, Product, PushSubscription, Service, User, Workshop, WorkshopMember, WorkshopSettings as WorkshopSettingsModel
from .schemas import *
from .security import create_access_token, current_user, hash_password, verify_password
from .services import ALLOWED_MIMES, audit, build_command, create_preview, inspect_file, issue_agent_key, storage_path, transition
from .ai import DeterministicProvider, OllamaProvider, SafetyLevel, TOOL_SAFETY, execute_safe_tool, resolve_job
from .assistant_schemas import AssistantExecuteRequest, AssistantRequest, AssistantResponse, ToolCall
from .assistant_flow import workflow_response, safe_result_response
from .document_processing import DocumentProcessor, LayoutEngine
from .processing_schemas import LayoutRequest, ProcessRequest
from .connector_schemas import ConnectorCreate, ConnectorOut, ConnectorSecretOut
from .connectors import IncomingDocument, ingest_incoming_document, verify_meta_signature, whatsapp_media_message_ids
from .business_schemas import CatalogIn, CustomerIn, CustomerOut, FinalCostIn, InvoiceCreate, InvoiceOut, PaymentIn, PriceRuleIn, PriceRuleOut, PrintCostOut, ServiceIn
from .business import estimate_print_cost
from .multisite_schemas import RouteJobIn, WorkshopMemberIn
from .observability import RequestAuditMiddleware, configure_logging
from .local_monitor import router as local_monitor_router
from .access import accessible_workshop_ids, require_workshop_write, accessible_documents, require_document_access, require_document_write, utc_datetime

@asynccontextmanager
async def lifespan(_app):
    settings.validate_runtime();configure_logging(settings.log_level)
    settings.storage_dir.mkdir(parents=True,exist_ok=True)
    if settings.database_url.startswith("sqlite"): Base.metadata.create_all(engine)
    yield

app=FastAPI(title="FUSAA PRINT AGENT",version="0.1.0",docs_url=None if settings.environment.lower()=="production" else "/docs",redoc_url=None if settings.environment.lower()=="production" else "/redoc",lifespan=lifespan)
app.include_router(local_monitor_router)
assistant_provider=OllamaProvider(settings.ollama_base_url,settings.ollama_model) if settings.ai_provider.lower()=="ollama" else DeterministicProvider()
document_processor=DocumentProcessor()
layout_engine=LayoutEngine()
app.add_middleware(CORSMiddleware,allow_origins=settings.cors_origins.split(","),allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.add_middleware(TrustedHostMiddleware,allowed_hosts=settings.trusted_hosts.split(",") if settings.environment.lower()=="production" else ["*"])
app.add_middleware(RequestAuditMiddleware)

@app.middleware("http")
async def security_headers(request:Request,call_next):
    response=await call_next(request)
    response.headers["X-Content-Type-Options"]="nosniff";response.headers["X-Frame-Options"]="DENY";response.headers["Referrer-Policy"]="strict-origin-when-cross-origin";response.headers["Permissions-Policy"]="geolocation=(), microphone=(), camera=()"
    return response

@app.get("/healthz",include_in_schema=False)
def healthz():return {"status":"ok"}

@app.get("/api/v1/system/health")
def local_system_health(user:User=Depends(current_user)):
    path=Path(__file__).resolve().parents[2]/"runtime"/"health.json"
    if not path.exists():return {"supervisor":"not_started","api":True,"ollama":False,"agent":False,"backup_today":False}
    try:
        report=json.loads(path.read_text(encoding="utf-8"))
        recent=(datetime.now(timezone.utc)-datetime.fromisoformat(report["last_check"])).total_seconds()<90
        return {**{key:report.get(key) for key in ("api","ollama","agent","backup_today","last_check")},"supervisor":"running" if recent else "stale"}
    except (OSError,ValueError,KeyError):return {"supervisor":"unavailable"}
@app.get("/readyz",include_in_schema=False)
def readyz():
    try:
        with engine.connect() as connection:connection.execute(text("SELECT 1"))
        settings.storage_dir.mkdir(parents=True,exist_ok=True)
    except Exception as error:raise HTTPException(503,"Service not ready") from error
    return {"status":"ready"}

def one(db,model,id):
    obj=db.get(model,id)
    if not obj: raise HTTPException(404,f"{model.__name__} not found")
    return obj
def require_member(db,user,organization_id):
    if not db.query(OrganizationMember).filter_by(organization_id=organization_id,user_id=user.id).first(): raise HTTPException(403,"No access to this organization")
def require_org_admin(db,user,organization_id):
    member=db.query(OrganizationMember).filter_by(organization_id=organization_id,user_id=user.id).one_or_none()
    if not member or member.role not in {"OWNER","ADMIN"}:raise HTTPException(403,"Organization administrator role required")
def can_access_workshop(db,user,workshop):
    org_member=db.query(OrganizationMember).filter_by(organization_id=workshop.organization_id,user_id=user.id).one_or_none()
    return bool(org_member and (org_member.role in {"OWNER","ADMIN"} or db.query(WorkshopMember).filter_by(workshop_id=workshop.id,user_id=user.id).first()))
def require_workshop_access(db,user,workshop):
    if not can_access_workshop(db,user,workshop):raise HTTPException(403,"No access to this workshop")
@app.post("/api/v1/customers",response_model=CustomerOut,status_code=201)
def create_customer(data:CustomerIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_member(db,user,data.organization_id);customer=Customer(**data.model_dump());db.add(customer);db.flush();audit(db,user.id,"CUSTOMER_CREATED","Customer",customer.id,result="SUCCESS");db.commit();db.refresh(customer);return customer
@app.get("/api/v1/customers",response_model=list[CustomerOut])
def list_customers(organization_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_member(db,user,organization_id);return db.query(Customer).filter_by(organization_id=organization_id).order_by(Customer.name).all()
@app.post("/api/v1/products",status_code=201)
def create_product(data:CatalogIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_member(db,user,data.organization_id);product=Product(**data.model_dump());db.add(product);db.flush();audit(db,user.id,"PRODUCT_CREATED","Product",product.id,result="SUCCESS");db.commit();return {"id":product.id,"name":product.name}
@app.post("/api/v1/services",status_code=201)
def create_service(data:ServiceIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_member(db,user,data.organization_id);service=Service(**data.model_dump());db.add(service);db.flush();audit(db,user.id,"SERVICE_CREATED","Service",service.id,result="SUCCESS");db.commit();return {"id":service.id,"name":service.name}
@app.post("/api/v1/price-rules",response_model=PriceRuleOut,status_code=201)
def create_price_rule(data:PriceRuleIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_member(db,user,data.organization_id);rule=PriceRule(**data.model_dump());db.add(rule);db.flush();audit(db,user.id,"PRICE_RULE_CREATED","PriceRule",rule.id,result="SUCCESS");db.commit();db.refresh(rule);return rule
@app.get("/api/v1/price-rules",response_model=list[PriceRuleOut])
def list_price_rules(organization_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_member(db,user,organization_id);return db.query(PriceRule).filter_by(organization_id=organization_id).order_by(PriceRule.priority).all()
@app.post("/api/v1/jobs/{job_id}/cost/estimate",response_model=PrintCostOut)
def estimate_job_cost(job_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    job=one(db,PrintJob,job_id);require_member(db,user,job.organization_id);amount,breakdown=estimate_print_cost(db,job);cost=db.query(PrintCost).filter_by(print_job_id=job.id).one_or_none()
    if not cost:cost=PrintCost(print_job_id=job.id,estimated_amount=float(amount),currency="XOF",breakdown=breakdown);db.add(cost)
    else:cost.estimated_amount=float(amount);cost.breakdown=breakdown
    job.estimated_cost=float(amount);audit(db,user.id,"PRINT_COST_ESTIMATED","PrintJob",job.id,parameters=breakdown,result="SUCCESS");db.commit();db.refresh(cost);return cost
@app.post("/api/v1/jobs/{job_id}/cost/final",response_model=PrintCostOut)
def final_job_cost(job_id:str,data:FinalCostIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    job=one(db,PrintJob,job_id);require_member(db,user,job.organization_id);cost=db.query(PrintCost).filter_by(print_job_id=job.id).one_or_none()
    if not cost:cost=PrintCost(print_job_id=job.id,estimated_amount=float(job.estimated_cost or 0),currency="XOF",breakdown={});db.add(cost)
    cost.final_amount=data.amount;job.final_cost=data.amount;audit(db,user.id,"PRINT_COST_FINALIZED","PrintJob",job.id,parameters={"amount":data.amount},result="SUCCESS");db.commit();db.refresh(cost);return cost
@app.post("/api/v1/invoices",response_model=InvoiceOut,status_code=201)
def create_invoice(data:InvoiceCreate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_member(db,user,data.organization_id)
    if data.customer_id:
        customer=one(db,Customer,data.customer_id)
        if customer.organization_id!=data.organization_id:raise HTTPException(422,"Customer belongs to another organization")
    jobs=[one(db,PrintJob,item) for item in data.job_ids]
    if any(job.organization_id!=data.organization_id for job in jobs):raise HTTPException(422,"Job belongs to another organization")
    invoice=Invoice(organization_id=data.organization_id,customer_id=data.customer_id,number=f"FUS-{datetime.now(timezone.utc):%Y%m%d}-{secrets.token_hex(3).upper()}",currency=data.currency);db.add(invoice);db.flush();total=0.0
    for job in jobs:
        amount=float(job.final_cost or job.estimated_cost or estimate_print_cost(db,job)[0]);db.add(InvoiceLine(invoice_id=invoice.id,print_job_id=job.id,description=f"Impression {job.id[:8]}",quantity=1,unit_amount=amount,total_amount=amount));total+=amount
    invoice.total_amount=total;audit(db,user.id,"INVOICE_CREATED","Invoice",invoice.id,parameters={"jobs":data.job_ids,"total":total},result="SUCCESS");db.commit();db.refresh(invoice);return invoice
@app.post("/api/v1/invoices/{invoice_id}/payments",status_code=201)
def record_payment(invoice_id:str,data:PaymentIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    invoice=one(db,Invoice,invoice_id);require_member(db,user,invoice.organization_id);payment=Payment(invoice_id=invoice.id,**data.model_dump());db.add(payment);db.flush();paid=sum(float(p.amount) for p in db.query(Payment).filter_by(invoice_id=invoice.id,status="CONFIRMED").all());invoice.status="PAID" if paid>=float(invoice.total_amount) else "PARTIALLY_PAID";audit(db,user.id,"PAYMENT_RECORDED","Payment",payment.id,parameters={"invoice_id":invoice.id,"amount":data.amount},result="SUCCESS");db.commit();return {"payment_id":payment.id,"invoice_status":invoice.status,"paid_amount":paid}
@app.get("/api/v1/business/stats")
def business_stats(organization_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_member(db,user,organization_id);invoices=db.query(Invoice).filter_by(organization_id=organization_id).all();jobs=db.query(PrintJob).filter_by(organization_id=organization_id).all();return {"customers":db.query(Customer).filter_by(organization_id=organization_id).count(),"invoices":len(invoices),"paid_revenue":sum(float(i.total_amount) for i in invoices if i.status=="PAID"),"estimated_print_revenue":sum(float(j.estimated_cost or 0) for j in jobs),"completed_jobs":sum(j.status==JobStatus.COMPLETED for j in jobs)}

@app.post("/api/v1/connectors",response_model=ConnectorSecretOut,status_code=201)
def create_connector(data:ConnectorCreate,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_org_admin(db,user,data.organization_id);workshop=one(db,Workshop,data.workshop_id)
    if workshop.organization_id!=data.organization_id:raise HTTPException(422,"Workshop does not belong to organization")
    secret=secrets.token_urlsafe(36);connector=Connector(**data.model_dump(),secret_hash=hashlib.sha256(secret.encode()).hexdigest());db.add(connector);db.flush();audit(db,user.id,"CONNECTOR_CREATED","Connector",connector.id,parameters={"type":connector.connector_type},result="SUCCESS");db.commit();db.refresh(connector);return {**ConnectorOut.model_validate(connector).model_dump(),"secret":secret}

@app.get("/api/v1/connectors",response_model=list[ConnectorOut])
def list_connectors(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return db.query(Connector).filter(Connector.workshop_id.in_(accessible_workshop_ids(db,user))).all()

async def receive_connector_document(connector_id:str,external_id:str|None,file:UploadFile,request:Request,db:Session):
    connector=one(db,Connector,connector_id);provided=request.headers.get("X-Connector-Key","")
    if not connector.enabled or not secrets.compare_digest(connector.secret_hash,hashlib.sha256(provided.encode()).hexdigest()):raise HTTPException(401,"Invalid connector key")
    content=await file.read();external_id=external_id or hashlib.sha256(content).hexdigest()
    existing=db.query(ConnectorEvent).filter_by(connector_id=connector.id,external_id=external_id).one_or_none()
    if existing:
        job=db.query(PrintJob).filter_by(document_id=existing.document_id).first() if existing.document_id else None
        return {"event_id":existing.id,"status":existing.status,"job_id":job.id if job else None,"duplicate":True}
    event=ConnectorEvent(connector_id=connector.id,external_id=external_id);db.add(event);db.flush()
    incoming=IncomingDocument(filename=file.filename or "incoming_document",mime_type=file.content_type or "application/octet-stream",content=content,source=connector.connector_type,external_id=external_id,metadata={"connector_id":connector.id,"connector_name":connector.name})
    try:document,job=ingest_incoming_document(db,incoming,connector.organization_id,connector.workshop_id);event.document_id=document.id;event.status="PROCESSED";audit(db,f"connector:{connector.id}","CONNECTOR_DOCUMENT_INGESTED","Document",document.id,parameters={"event_id":event.id,"source":connector.connector_type},result="SUCCESS");db.commit();await hub.publish("NEW_DOCUMENT",{"document_id":document.id,"job_id":job.id,"source":connector.connector_type},connector.organization_id);return {"event_id":event.id,"status":event.status,"job_id":job.id,"duplicate":False}
    except Exception as error:
        event.status="FAILED";event.error_message=str(error);db.commit();raise HTTPException(422,f"Connector intake failed: {error}")

@app.post("/api/v1/connectors/{connector_id}/incoming",status_code=201)
async def connector_incoming(connector_id:str,file:UploadFile=File(...),external_id:str|None=None,request:Request=None,db:Session=Depends(get_db)):
    return await receive_connector_document(connector_id,external_id,file,request,db)

@app.post("/api/v1/connectors/{connector_id}/email/incoming",status_code=201)
async def email_connector_incoming(connector_id:str,file:UploadFile=File(...),external_id:str|None=None,request:Request=None,db:Session=Depends(get_db)):
    connector=one(db,Connector,connector_id)
    if connector.connector_type!="EMAIL":raise HTTPException(409,"This connector is not an EMAIL connector")
    return await receive_connector_document(connector_id,external_id,file,request,db)

@app.get("/api/v1/connectors/{connector_id}/whatsapp/webhook",include_in_schema=False)
def verify_whatsapp_webhook(connector_id:str,request:Request,db:Session=Depends(get_db)):
    """Meta verification handshake. The generated connector secret is the verify token."""
    connector=one(db,Connector,connector_id)
    params=request.query_params
    supplied=params.get("hub.verify_token","")
    if connector.connector_type!="WHATSAPP" or not connector.enabled:raise HTTPException(404,"WhatsApp connector not found")
    if params.get("hub.mode")!="subscribe" or not secrets.compare_digest(connector.secret_hash,hashlib.sha256(supplied.encode()).hexdigest()):raise HTTPException(403,"Webhook verification failed")
    challenge=params.get("hub.challenge")
    if challenge is None:raise HTTPException(422,"Missing webhook challenge")
    return PlainTextResponse(challenge)

@app.post("/api/v1/connectors/{connector_id}/whatsapp/webhook",include_in_schema=False)
async def receive_whatsapp_webhook(connector_id:str,request:Request,db:Session=Depends(get_db)):
    """Accept signed official webhook notices only; no Brave session or chat body is read."""
    connector=one(db,Connector,connector_id)
    if connector.connector_type!="WHATSAPP" or not connector.enabled:raise HTTPException(404,"WhatsApp connector not found")
    if not settings.meta_whatsapp_app_secret:raise HTTPException(503,"WhatsApp webhook is not activated: META_WHATSAPP_APP_SECRET is missing")
    raw_body=await request.body()
    if not verify_meta_signature(raw_body,request.headers.get("X-Hub-Signature-256"),settings.meta_whatsapp_app_secret):raise HTTPException(401,"Invalid Meta webhook signature")
    try:payload=json.loads(raw_body)
    except json.JSONDecodeError as error:raise HTTPException(422,"Invalid WhatsApp webhook payload") from error
    accepted=0
    for external_id in whatsapp_media_message_ids(payload):
        if db.query(ConnectorEvent).filter_by(connector_id=connector.id,external_id=external_id).first():continue
        db.add(ConnectorEvent(connector_id=connector.id,external_id=external_id,status="MEDIA_PENDING"));accepted+=1
    audit(db,f"whatsapp:{connector.id}","WHATSAPP_MEDIA_NOTICED","Connector",connector.id,parameters={"attachment_messages":accepted},result="SUCCESS")
    db.commit()
    return {"status":"accepted","attachment_messages":accepted,"note":"Media download stays disabled until an explicit Meta media-access integration is configured."}

def derived_document(db:Session,source:Document,content:bytes,mime_type:str,extension:str,metadata:dict)->Document:
    key=f"processed/{secrets.token_urlsafe(18)}.{extension}";storage_path(key).write_bytes(content)
    preview_key=create_preview(storage_path(key),mime_type)
    document=Document(organization_id=source.organization_id,original_name=f"print_ready_{source.id[:8]}.{extension}",storage_key=key,mime_type=mime_type,size_bytes=len(content),metadata_json={**metadata,"source_document_id":source.id,"derived":True},preview_key=preview_key)
    db.add(document);db.flush();return document

@app.post("/api/v1/assistant/understand",response_model=AssistantResponse)
def understand_assistant(data:AssistantRequest,user:User=Depends(current_user),db:Session=Depends(get_db)):
    response=workflow_response(data,db,user)
    if response:return response
    calls=[]
    for raw in assistant_provider.understand_command(data.message):
        name,args=raw["name"],raw.get("arguments",{})
        safety=TOOL_SAFETY.get(name)
        if safety is None: continue
        # Free-form model output never creates a physical-action button.
        if safety!=SafetyLevel.SAFE:continue
        result=execute_safe_tool(db,user,name,args)
        calls.append(ToolCall(name=name,arguments=args,safety=safety,result=result))
    audit(db,user.id,"AI_COMMAND_UNDERSTOOD","Assistant","command",parameters={"message":data.message,"tools":[call.name for call in calls]},result="SUCCESS");db.commit()
    return safe_result_response(calls)

@app.post("/api/v1/assistant/execute",response_model=dict)
async def execute_assistant(data:AssistantExecuteRequest,user:User=Depends(current_user),db:Session=Depends(get_db)):
    safety=TOOL_SAFETY.get(data.name)
    if safety is None: raise HTTPException(400,"Tool is not allowed")
    if safety!=SafetyLevel.SAFE and not data.confirmed: raise HTTPException(409,"Explicit confirmation is required")
    if safety==SafetyLevel.SAFE:return {"result":execute_safe_tool(db,user,data.name,data.arguments),"safety":safety}
    job=resolve_job(db,user,data.arguments.get("job_reference"))
    if not job: raise HTTPException(404,"Print job reference not found")
    require_workshop_write(db,user,job.workshop_id)
    if data.name=="prepare_print_job":
        prepared=prepare_job(job.id,JobOptions(**data.arguments),user,db)
        return {"job_id":prepared.id,"status":prepared.status}
    if data.name=="request_print":
        require_workshop_write(db,user,one(db,ComputerAgent,job.computer_agent_id).workshop_id)
        if job.status!=JobStatus.READY:raise HTTPException(409,"Job must be prepared before printing")
        printer=one(db,Printer,job.printer_id);job.approved_at=datetime.now(timezone.utc)
        try:command=build_command(db,job,printer)
        except ValueError as error:raise HTTPException(409,str(error))
        audit(db,user.id,"AI_PRINT_CONFIRMED","PrintJob",job.id,parameters={"command_id":command.id},result="SUCCESS");db.commit();await agent_hub.notify(job.computer_agent_id,"COMMAND_AVAILABLE");await hub.publish("PRINT_JOB_UPDATED",{"job_id":job.id,"status":job.status},job.organization_id);return {"job_id":job.id,"command_id":command.id,"status":job.status}
    if data.name=="cancel_print_job":
        return await cancel_job(job.id,user,db)
    if data.name=="ignore_print_job":
        if job.status!=JobStatus.WAITING_APPROVAL:raise HTTPException(409,"Only pending jobs can be ignored")
        transition(job,JobStatus.IGNORED);audit(db,user.id,"AI_PRINT_IGNORED","PrintJob",job.id,result="SUCCESS");db.commit();await hub.publish("PRINT_JOB_UPDATED",{"job_id":job.id,"status":job.status},job.organization_id);return {"job_id":job.id,"status":job.status}
    raise HTTPException(400,"Tool requires structured print settings and is not available in this release")

@app.post("/api/v1/auth/register",response_model=TokenOut,status_code=201)
def register(data:RegisterIn,db:Session=Depends(get_db)):
    if db.query(User).filter_by(email=data.email.lower()).first(): raise HTTPException(409,"Email already registered")
    user=User(email=data.email.lower(),password_hash=hash_password(data.password),display_name=data.display_name); db.add(user); db.commit(); db.refresh(user)
    audit(db,user.id,"USER_REGISTERED","User",user.id); db.commit(); return TokenOut(access_token=create_access_token(user.id))

@app.post("/api/v1/auth/login",response_model=TokenOut)
def login(data:LoginIn,db:Session=Depends(get_db)):
    user=db.query(User).filter_by(email=data.email.lower()).first()
    if not user or not verify_password(data.password,user.password_hash): raise HTTPException(401,"Incorrect email or password")
    return TokenOut(access_token=create_access_token(user.id))

@app.get("/api/v1/push/public-key")
def push_public_key(user:User=Depends(current_user)):
    if not settings.vapid_public_key: raise HTTPException(503,"Web Push is not configured on this server")
    return {"public_key":settings.vapid_public_key}

@app.post("/api/v1/push/subscriptions",status_code=201)
def subscribe_push(data:PushSubscriptionIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    existing=db.query(PushSubscription).filter_by(endpoint=data.endpoint).one_or_none()
    if existing:
        existing.user_id=user.id;existing.p256dh=data.p256dh;existing.auth=data.auth
    else: db.add(PushSubscription(user_id=user.id,**data.model_dump()))
    audit(db,user.id,"PUSH_SUBSCRIBED","PushSubscription",existing.id if existing else "new");db.commit();return {"ok":True}

@app.delete("/api/v1/push/subscriptions")
def unsubscribe_push(endpoint:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    item=db.query(PushSubscription).filter_by(endpoint=endpoint,user_id=user.id).one_or_none()
    if item: db.delete(item);audit(db,user.id,"PUSH_UNSUBSCRIBED","PushSubscription",item.id);db.commit()
    return {"ok":True}

@app.post("/api/v1/organizations",status_code=201)
def create_org(data:OrganizationIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if settings.single_workshop_id:raise HTTPException(409,"FUSAA est configuré pour un seul atelier")
    org=Organization(name=data.name);db.add(org);db.flush();db.add(OrganizationMember(organization_id=org.id,user_id=user.id,role="OWNER"));audit(db,user.id,"ORGANIZATION_CREATED","Organization",org.id);db.commit();return {"id":org.id,"name":org.name}

@app.get("/api/v1/workspaces")
def available_workspaces(user:User=Depends(current_user),db:Session=Depends(get_db)):
    allowed=accessible_workshop_ids(db,user)
    return [{"organization_id":org.id,"organization_name":org.name,"workshop_id":workshop.id,"workshop_name":workshop.name} for workshop,org in db.query(Workshop,Organization).join(Organization,Workshop.organization_id==Organization.id).filter(Workshop.id.in_(allowed)).all()]

def configured_workshop(user:User,db:Session,write=False):
    allowed=accessible_workshop_ids(db,user,write=write)
    if not allowed:raise HTTPException(404,"Aucun atelier FUSAA configuré pour ce compte")
    workshop_id=settings.single_workshop_id or allowed[0]
    workshop=one(db,Workshop,workshop_id)
    if workshop.id not in allowed:raise HTTPException(403,"Cet atelier n’est pas accessible")
    return workshop

def ensure_workshop_settings(db:Session,workshop:Workshop):
    preferences=db.get(WorkshopSettingsModel,workshop.id)
    if not preferences:
        if settings.single_workshop_name:workshop.name=settings.single_workshop_name
        preferences=WorkshopSettingsModel(workshop_id=workshop.id)
        db.add(preferences);db.flush()
    return preferences

@app.get("/api/v1/settings",response_model=WorkshopSettingsOut)
def get_workshop_settings(user:User=Depends(current_user),db:Session=Depends(get_db)):
    workshop=configured_workshop(user,db);preferences=ensure_workshop_settings(db,workshop);db.commit();db.refresh(preferences)
    return {**{field:getattr(preferences,field) for field in ("workshop_id","default_copies","default_paper_size","default_orientation","default_color_mode","default_duplex","popup_enabled","smart_suggestions")},"workshop_name":workshop.name}

@app.put("/api/v1/settings",response_model=WorkshopSettingsOut)
def update_workshop_settings(data:WorkshopSettingsIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    workshop=configured_workshop(user,db,write=True);preferences=ensure_workshop_settings(db,workshop)
    values=data.model_dump(exclude={"workshop_name"})
    for field,value in values.items():setattr(preferences,field,value)
    if data.workshop_name:workshop.name=data.workshop_name
    audit(db,user.id,"WORKSHOP_SETTINGS_UPDATED","Workshop",workshop.id,parameters=values,result="SUCCESS");db.commit();db.refresh(preferences)
    return {**{field:getattr(preferences,field) for field in ("workshop_id","default_copies","default_paper_size","default_orientation","default_color_mode","default_duplex","popup_enabled","smart_suggestions")},"workshop_name":workshop.name}

@app.post("/api/v1/workshops",status_code=201)
def create_workshop(data:WorkshopIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if settings.single_workshop_id:raise HTTPException(409,"FUSAA est configuré pour un seul atelier")
    one(db,Organization,data.organization_id);require_org_admin(db,user,data.organization_id);workshop=Workshop(**data.model_dump());db.add(workshop);db.flush();db.add(WorkshopMember(workshop_id=workshop.id,user_id=user.id,role="MANAGER"));audit(db,user.id,"WORKSHOP_CREATED","Workshop",workshop.id);db.commit();return {"id":workshop.id,"name":workshop.name}

@app.get("/api/v1/workshops")
def list_workshops(organization_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_member(db,user,organization_id);allowed=set(accessible_workshop_ids(db,user));return [{"id":w.id,"name":w.name} for w in db.query(Workshop).filter_by(organization_id=organization_id).all() if w.id in allowed and can_access_workshop(db,user,w)]

@app.post("/api/v1/workshops/{workshop_id}/members",status_code=201)
def assign_workshop_member(workshop_id:str,data:WorkshopMemberIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    workshop=one(db,Workshop,workshop_id);require_org_admin(db,user,workshop.organization_id);target=db.query(User).filter_by(email=data.user_email.lower()).one_or_none()
    if settings.single_workshop_id and workshop.id!=settings.single_workshop_id:raise HTTPException(403,"Only the configured FUSAA workshop may be assigned")
    if not target:raise HTTPException(404,"User must register before being assigned")
    if not db.query(OrganizationMember).filter_by(organization_id=workshop.organization_id,user_id=target.id).first():db.add(OrganizationMember(organization_id=workshop.organization_id,user_id=target.id,role="OPERATOR"))
    member=db.query(WorkshopMember).filter_by(workshop_id=workshop.id,user_id=target.id).one_or_none()
    if member:member.role=data.role
    else:member=WorkshopMember(workshop_id=workshop.id,user_id=target.id,role=data.role);db.add(member)
    audit(db,user.id,"WORKSHOP_MEMBER_ASSIGNED","Workshop",workshop.id,parameters={"user_id":target.id,"role":data.role},result="SUCCESS");db.commit();return {"workshop_id":workshop.id,"user_id":target.id,"role":data.role}

@app.post("/api/v1/agents",response_model=AgentEnrollmentOut,status_code=201)
def create_agent(data:AgentIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    if settings.single_workshop_id and data.workshop_id!=settings.single_workshop_id:raise HTTPException(403,"Only the configured FUSAA workshop may receive an agent")
    workshop=one(db,Workshop,data.workshop_id);require_org_admin(db,user,workshop.organization_id);agent=ComputerAgent(**data.model_dump(),enrollment_token=secrets.token_urlsafe(32));db.add(agent);db.flush();audit(db,user.id,"AGENT_ENROLLMENT_CREATED","ComputerAgent",agent.id);db.commit();db.refresh(agent);return agent

@app.get("/api/v1/agents",response_model=list[AgentOut])
def list_agents(user:User=Depends(current_user),db:Session=Depends(get_db)): return db.query(ComputerAgent).filter(ComputerAgent.workshop_id.in_(accessible_workshop_ids(db,user))).all()

@app.post("/api/v1/agent/register",response_model=AgentTokenOut)
def agent_register(data:AgentRegisterIn,request:Request,db:Session=Depends(get_db)):
    agent=db.query(ComputerAgent).filter_by(enrollment_token=data.enrollment_token).one_or_none()
    if not agent: raise HTTPException(401,"Invalid enrollment token")
    if settings.single_workshop_id and agent.workshop_id!=settings.single_workshop_id:raise HTTPException(403,"Agent outside the configured FUSAA workshop")
    if agent.agent_key and agent.machine_fingerprint!=data.machine_fingerprint: raise HTTPException(409,"Agent already enrolled by another machine")
    agent.agent_key=agent.agent_key or issue_agent_key();agent.machine_fingerprint=data.machine_fingerprint;agent.is_online=True;agent.last_heartbeat_at=datetime.now(timezone.utc)
    audit(db,"agent-registration","AGENT_REGISTERED","ComputerAgent",agent.id,agent_id=agent.id);db.commit();return AgentTokenOut(agent_id=agent.id,agent_key=agent.agent_key)

def authenticated_agent(agent_id:str,key:str,db:Session)->ComputerAgent:
    agent=one(db,ComputerAgent,agent_id)
    if not agent.agent_key or not secrets.compare_digest(agent.agent_key,key):raise HTTPException(401,"Invalid agent key")
    return agent

@app.post("/api/v1/agent/{agent_id}/heartbeat")
async def heartbeat(agent_id:str,data:HeartbeatIn,request:Request,db:Session=Depends(get_db)):
    agent=authenticated_agent(agent_id,request.headers.get("X-Agent-Key",""),db);agent.is_online=True;agent.last_heartbeat_at=datetime.now(timezone.utc);audit(db,agent_id,"AGENT_HEARTBEAT","ComputerAgent",agent.id,agent_id=agent.id);db.commit();await hub.publish("AGENT_ONLINE",{"agent_id":agent.id},one(db,Workshop,agent.workshop_id).organization_id);return {"ok":True}

@app.put("/api/v1/agent/{agent_id}/printers",response_model=list[PrinterOut])
async def sync_printers(agent_id:str,items:list[PrinterIn],request:Request,db:Session=Depends(get_db)):
    agent=authenticated_agent(agent_id,request.headers.get("X-Agent-Key",""),db); seen=set();out=[]
    for item in items:
        seen.add(item.system_name);printer=db.query(Printer).filter_by(computer_agent_id=agent.id,system_name=item.system_name).one_or_none()
        if not printer: printer=Printer(computer_agent_id=agent.id,**item.model_dump());db.add(printer)
        else:
            for k,v in item.model_dump().items():setattr(printer,k,v)
        out.append(printer)
    db.flush()
    for printer in db.query(Printer).filter_by(computer_agent_id=agent.id).all():
        if printer.system_name not in seen:printer.status="OFFLINE"
    audit(db,agent_id,"PRINTERS_SYNCED","ComputerAgent",agent.id,agent_id=agent.id,parameters={"count":len(items)});db.commit();await hub.publish("PRINTERS_UPDATED",{"agent_id":agent.id},one(db,Workshop,agent.workshop_id).organization_id);return out

@app.get("/api/v1/printers",response_model=list[PrinterOut])
def list_printers(user:User=Depends(current_user),db:Session=Depends(get_db)):return db.query(Printer).join(ComputerAgent,Printer.computer_agent_id==ComputerAgent.id).filter(ComputerAgent.workshop_id.in_(accessible_workshop_ids(db,user))).all()

@app.post("/api/v1/documents/upload",response_model=PrintJobOut,status_code=201)
async def upload_document(organization_id:str,workshop_id:str,request:Request,file:UploadFile=File(...),user:User=Depends(current_user),db:Session=Depends(get_db)):
    one(db,Organization,organization_id);require_member(db,user,organization_id);workshop=one(db,Workshop,workshop_id)
    require_workshop_write(db,user,workshop_id)
    if workshop.organization_id!=organization_id: raise HTTPException(422,"Workshop does not belong to organization")
    upload_id=request.headers.get("X-Upload-ID")
    upload_key="upload:"+hashlib.sha256((user.id+":"+upload_id).encode()).hexdigest() if upload_id else None
    if upload_key:
        existing=db.query(PrintJob).filter_by(idempotency_key=upload_key).first()
        if existing:return existing
    content=await file.read();mime=file.content_type or "application/octet-stream"
    try:document,job=ingest_incoming_document(db,IncomingDocument(filename=file.filename or "document",mime_type=mime,content=content,source="UPLOAD",external_id=secrets.token_urlsafe(12),metadata={"uploaded_by":user.id}),organization_id,workshop_id)
    except ValueError as error:
        code=415 if mime not in ALLOWED_MIMES else 413;raise HTTPException(code,str(error))
    except Exception as error:raise HTTPException(422,f"Cannot inspect file: {error}")
    job.idempotency_key=upload_key
    audit(db,user.id,"DOCUMENT_UPLOADED","Document",document.id,parameters={"job_id":job.id});audit(db,user.id,"PRINT_JOB_CREATED","PrintJob",job.id);db.commit();db.refresh(job);await hub.publish("NEW_PRINT_JOB",{"job_id":job.id,"status":job.status},job.organization_id);return job

@app.get("/api/v1/documents/{document_id}/content")
def document_content(document_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    doc=one(db,Document,document_id);require_document_access(db,user,doc);path=storage_path(doc.storage_key)
    if not path.exists():raise HTTPException(410,"Document file unavailable")
    return FileResponse(path,media_type=doc.mime_type,filename=doc.original_name)

@app.get("/api/v1/documents/{document_id}/preview")
def document_preview(document_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    doc=one(db,Document,document_id);require_document_access(db,user,doc)
    if not doc.preview_key: raise HTTPException(404,"Preview unavailable")
    path=storage_path(doc.preview_key)
    if not path.exists(): raise HTTPException(410,"Preview file unavailable")
    return FileResponse(path,media_type="image/jpeg")

@app.get("/api/v1/documents",response_model=list[DocumentOut])
def list_documents(user:User=Depends(current_user),db:Session=Depends(get_db)):
    return accessible_documents(db,user).order_by(Document.created_at.desc()).all()

@app.post("/api/v1/documents/{document_id}/process",response_model=DocumentOut,status_code=201)
def process_document(document_id:str,data:ProcessRequest,user:User=Depends(current_user),db:Session=Depends(get_db)):
    source=one(db,Document,document_id);require_document_write(db,user,source)
    options=data.model_dump(exclude_none=True)
    if data.operation=="resize" and (data.width_px is None or data.height_px is None):raise HTTPException(422,"width_px and height_px are required")
    if data.operation=="crop" and None in {data.left,data.top,data.right,data.bottom}:raise HTTPException(422,"left, top, right and bottom are required")
    try:content,mime,extension,metadata=document_processor.process(storage_path(source.storage_key),source.mime_type,data.operation,options)
    except Exception as error:raise HTTPException(422,f"Processing failed: {error}")
    document=derived_document(db,source,content,mime,extension,metadata);audit(db,user.id,"DOCUMENT_PROCESSED","Document",document.id,parameters={"source_document_id":source.id,**options},result="SUCCESS");db.commit();db.refresh(document);return document

@app.post("/api/v1/layouts/sheet",response_model=DocumentOut,status_code=201)
def create_layout(data:LayoutRequest,user:User=Depends(current_user),db:Session=Depends(get_db)):
    source=one(db,Document,data.source_document_id);require_document_write(db,user,source)
    try:content,metadata=layout_engine.create_sheet(storage_path(source.storage_key),source.mime_type,**data.model_dump(exclude={"source_document_id"}))
    except Exception as error:raise HTTPException(422,f"Layout failed: {error}")
    document=derived_document(db,source,content,"application/pdf","pdf",{"operation":"layout_sheet",**metadata});audit(db,user.id,"LAYOUT_CREATED","Document",document.id,parameters={"source_document_id":source.id,**data.model_dump(exclude={"source_document_id"})},result="SUCCESS");db.commit();db.refresh(document);return document

@app.post("/api/v1/documents/{document_id}/print-jobs",response_model=PrintJobOut,status_code=201)
async def create_job_from_document(document_id:str,workshop_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    document=one(db,Document,document_id);require_member(db,user,document.organization_id);workshop=one(db,Workshop,workshop_id)
    require_document_write(db,user,document);require_workshop_write(db,user,workshop_id)
    if workshop.organization_id!=document.organization_id:raise HTTPException(422,"Workshop does not belong to document organization")
    job=PrintJob(organization_id=document.organization_id,workshop_id=workshop.id,document_id=document.id,status=JobStatus.RECEIVED);db.add(job);db.flush();transition(job,JobStatus.ANALYZING);transition(job,JobStatus.WAITING_APPROVAL);audit(db,user.id,"PRINT_JOB_CREATED_FROM_DERIVED_DOCUMENT","PrintJob",job.id,parameters={"document_id":document.id},result="SUCCESS");db.commit();db.refresh(job);await hub.publish("NEW_PRINT_JOB",{"job_id":job.id,"status":job.status},job.organization_id);return job

@app.get("/api/v1/audit",response_model=list[AuditOut])
def audit_history(limit:int=50,user:User=Depends(current_user),db:Session=Depends(get_db)):
    # Only return records for resources visible to the caller.
    visible_jobs={item[0] for item in db.query(PrintJob.id).filter(PrintJob.workshop_id.in_(accessible_workshop_ids(db,user))).all()}
    return db.query(AuditLog).filter(((AuditLog.resource_type=="PrintJob") & (AuditLog.resource_id.in_(visible_jobs))) | (AuditLog.actor==user.id)).order_by(AuditLog.timestamp.desc()).limit(min(limit,200)).all()

@app.get("/api/v1/jobs",response_model=list[PrintJobOut])
def list_jobs(user:User=Depends(current_user),db:Session=Depends(get_db)):return db.query(PrintJob).filter(PrintJob.workshop_id.in_(accessible_workshop_ids(db,user))).order_by(PrintJob.created_at.desc()).all()

@app.get("/api/v1/jobs/{job_id}",response_model=PrintJobOut)
def get_job(job_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    job=one(db,PrintJob,job_id);require_member(db,user,job.organization_id);require_workshop_access(db,user,one(db,Workshop,job.workshop_id));return job

@app.post("/api/v1/jobs/{job_id}/prepare",response_model=PrintJobOut)
def prepare_job(job_id:str,data:JobOptions,user:User=Depends(current_user),db:Session=Depends(get_db)):
    job=one(db,PrintJob,job_id);require_member(db,user,job.organization_id);printer=one(db,Printer,data.printer_id)
    require_workshop_write(db,user,job.workshop_id)
    if one(db,ComputerAgent,printer.computer_agent_id).workshop_id!=job.workshop_id:raise HTTPException(422,"Route the job before selecting a printer in another workshop")
    if one(db,Workshop,one(db,ComputerAgent,printer.computer_agent_id).workshop_id).organization_id!=job.organization_id: raise HTTPException(422,"Printer belongs to another organization")
    if job.status!=JobStatus.WAITING_APPROVAL:raise HTTPException(409,"Job is not waiting for approval")
    agent=one(db,ComputerAgent,printer.computer_agent_id)
    for k,v in data.model_dump().items():setattr(job,k,v)
    job.computer_agent_id=agent.id;transition(job,JobStatus.READY);audit(db,user.id,"PRINT_JOB_PREPARED","PrintJob",job.id,parameters=data.model_dump());db.commit();return job

@app.post("/api/v1/jobs/{job_id}/route",response_model=PrintJobOut)
def route_job(job_id:str,data:RouteJobIn,user:User=Depends(current_user),db:Session=Depends(get_db)):
    job=one(db,PrintJob,job_id);require_member(db,user,job.organization_id);workshop=one(db,Workshop,data.workshop_id)
    require_workshop_write(db,user,job.workshop_id)
    if workshop.organization_id!=job.organization_id or not can_access_workshop(db,user,workshop):raise HTTPException(403,"Cannot route to this workshop")
    if job.status not in {JobStatus.WAITING_APPROVAL,JobStatus.READY}:raise HTTPException(409,"Only unprinted jobs can be routed")
    require_workshop_write(db,user,workshop.id)
    job.workshop_id=workshop.id
    job.printer_id=None;job.computer_agent_id=None;job.status=JobStatus.WAITING_APPROVAL
    if data.printer_id:
        printer=one(db,Printer,data.printer_id);agent=one(db,ComputerAgent,printer.computer_agent_id)
        if agent.workshop_id!=workshop.id:raise HTTPException(422,"Printer does not belong to target workshop")
        job.printer_id=printer.id;job.computer_agent_id=agent.id
    audit(db,user.id,"PRINT_JOB_ROUTED","PrintJob",job.id,parameters={"workshop_id":workshop.id,"printer_id":data.printer_id},result="SUCCESS");db.commit();db.refresh(job);return job

@app.post("/api/v1/jobs/{job_id}/confirm",response_model=dict)
async def confirm_job(job_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    job=one(db,PrintJob,job_id);require_member(db,user,job.organization_id)
    require_workshop_write(db,user,job.workshop_id)
    if job.status!=JobStatus.READY:raise HTTPException(409,"Job must be prepared before confirmation")
    require_workshop_write(db,user,one(db,ComputerAgent,job.computer_agent_id).workshop_id)
    printer=one(db,Printer,job.printer_id);job.approved_at=datetime.now(timezone.utc)
    try:command=build_command(db,job,printer)
    except ValueError as e:raise HTTPException(409,str(e))
    audit(db,user.id,"PRINT_CONFIRMED","PrintJob",job.id,parameters={"command_id":command.id});db.commit();await agent_hub.notify(job.computer_agent_id,"COMMAND_AVAILABLE");await hub.publish("PRINT_JOB_UPDATED",{"job_id":job.id,"status":job.status},job.organization_id);return {"job_id":job.id,"command_id":command.id,"status":job.status}

@app.post("/api/v1/jobs/{job_id}/cancel",response_model=dict)
async def cancel_job(job_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    job=one(db,PrintJob,job_id);require_member(db,user,job.organization_id)
    require_workshop_write(db,user,job.workshop_id)
    if job.status in {JobStatus.COMPLETED,JobStatus.FAILED,JobStatus.CANCELLED,JobStatus.IGNORED}: raise HTTPException(409,"This job cannot be cancelled")
    print_command=db.query(AgentCommand).filter_by(print_job_id=job.id,command_type="PRINT").one_or_none()
    if not print_command or print_command.status==CommandStatus.PENDING:
        if print_command: print_command.status=CommandStatus.CANCELLED
        transition(job,JobStatus.CANCELLED);audit(db,user.id,"PRINT_CANCELLED_BEFORE_DISPATCH","PrintJob",job.id);db.commit();await hub.publish("PRINT_JOB_UPDATED",{"job_id":job.id,"status":job.status},job.organization_id);return {"job_id":job.id,"status":job.status,"cancelled_before_dispatch":True}
    if not job.computer_agent_id: raise HTTPException(409,"No agent assigned")
    key=f"cancel:{job.id}";command=db.query(AgentCommand).filter_by(idempotency_key=key).one_or_none()
    if not command:
        details=print_command.result or {}
        command=AgentCommand(computer_agent_id=job.computer_agent_id,print_job_id=job.id,command_type="CANCEL",idempotency_key=key,payload={"printer_system_name":details.get("printer"),"spooler_job_id":details.get("spooler_job_id"),"target_command_id":print_command.id})
        db.add(command);audit(db,user.id,"PRINT_CANCEL_REQUESTED","PrintJob",job.id,parameters={"command_id":command.id})
    db.commit();await agent_hub.notify(job.computer_agent_id,"COMMAND_AVAILABLE");return {"job_id":job.id,"status":job.status,"cancel_command_id":command.id}

@app.get("/api/v1/agent/{agent_id}/commands")
def poll_commands(agent_id:str,request:Request,db:Session=Depends(get_db)):
    authenticated_agent(agent_id,request.headers.get("X-Agent-Key",""),db)
    # A crashed agent must not strand a command forever. The idempotency key prevents a second command.
    lease_cutoff=datetime.now(timezone.utc)-timedelta(minutes=5)
    db.query(AgentCommand).filter(AgentCommand.computer_agent_id==agent_id,AgentCommand.status==CommandStatus.CLAIMED,AgentCommand.claimed_at < lease_cutoff,or_(AgentCommand.result.is_(None),AgentCommand.result==JSON.NULL)).update({AgentCommand.status:CommandStatus.PENDING,AgentCommand.claimed_at:None},synchronize_session=False)
    candidates=db.query(AgentCommand).filter_by(computer_agent_id=agent_id,status=CommandStatus.PENDING).with_for_update(skip_locked=True).all()
    commands=[]
    for c in candidates:
        claimed=db.query(AgentCommand).filter(AgentCommand.id==c.id,AgentCommand.status==CommandStatus.PENDING).update({AgentCommand.status:CommandStatus.CLAIMED,AgentCommand.claimed_at:datetime.now(timezone.utc),AgentCommand.attempt_count:AgentCommand.attempt_count+1},synchronize_session=False)
        if claimed:commands.append(c)
    db.commit();return [{"id":c.id,"type":c.command_type,"payload":c.payload,"idempotency_key":c.idempotency_key} for c in commands]

@app.get("/api/v1/agent/{agent_id}/documents/{document_id}")
def agent_document(agent_id:str,document_id:str,request:Request,db:Session=Depends(get_db)):
    authenticated_agent(agent_id,request.headers.get("X-Agent-Key",""),db);doc=one(db,Document,document_id)
    permitted=db.query(AgentCommand).join(PrintJob,AgentCommand.print_job_id==PrintJob.id).filter(AgentCommand.computer_agent_id==agent_id,PrintJob.document_id==document_id).first()
    if not permitted: raise HTTPException(403,"Document is not assigned to this agent")
    path=storage_path(doc.storage_key)
    if not path.exists(): raise HTTPException(410,"Document file unavailable")
    return FileResponse(path,media_type=doc.mime_type,filename=doc.original_name)

@app.post("/api/v1/agent/{agent_id}/commands/{command_id}/result")
async def command_result(agent_id:str,command_id:str,data:CommandResultIn,request:Request,db:Session=Depends(get_db)):
    authenticated_agent(agent_id,request.headers.get("X-Agent-Key",""),db);command=one(db,AgentCommand,command_id)
    if command.computer_agent_id!=agent_id:raise HTTPException(403,"Command belongs to another agent")
    if command.status in {CommandStatus.SUCCESS,CommandStatus.FAILED,CommandStatus.CANCELLED}:return {"ok":True,"already_reported":True}
    job=one(db,PrintJob,command.print_job_id)
    if command.command_type=="CANCEL":
        command.status=CommandStatus.SUCCESS if data.status.upper()=="SUCCESS" else CommandStatus.FAILED;command.result=data.result
        if command.status==CommandStatus.SUCCESS and job.status not in {JobStatus.CANCELLED,JobStatus.COMPLETED,JobStatus.FAILED}:
            transition(job,JobStatus.CANCELLED)
        audit(db,agent_id,"PRINT_CANCEL_RESULT","PrintJob",job.id,result=command.status.value,agent_id=agent_id,parameters=data.result);db.commit();await hub.publish("PRINT_JOB_UPDATED",{"job_id":job.id,"status":job.status},job.organization_id);return {"ok":True}
    if job.status in {JobStatus.CANCELLED,JobStatus.COMPLETED,JobStatus.FAILED,JobStatus.IGNORED}:
        command.status=CommandStatus.CANCELLED;db.commit();return {"ok":True,"terminal_job":True}
    if data.status.upper()=="DISPATCHED":
        command.result=data.result;command.claimed_at=datetime.now(timezone.utc)
        if job.status==JobStatus.QUEUED: transition(job,JobStatus.PRINTING)
        audit(db,agent_id,"PRINT_DISPATCHED","PrintJob",job.id,result="DISPATCHED",agent_id=agent_id,parameters=data.result);db.commit();await hub.publish("PRINT_STARTED",{"job_id":job.id,"status":job.status},job.organization_id);return {"ok":True,"tracking":True}
    command.status=CommandStatus.SUCCESS if data.status.upper()=="SUCCESS" else CommandStatus.FAILED;command.result=data.result
    try: transition(job,JobStatus.PRINTING);transition(job,JobStatus.COMPLETED if command.status==CommandStatus.SUCCESS else JobStatus.FAILED)
    except ValueError:
        job.status=JobStatus.COMPLETED if command.status==CommandStatus.SUCCESS else JobStatus.FAILED
    job.error_message=data.error_message;job.completed_at=datetime.now(timezone.utc) if command.status==CommandStatus.SUCCESS else None;audit(db,agent_id,"PRINT_COMMAND_RESULT","PrintJob",job.id,result=command.status.value,agent_id=agent_id,parameters=data.result);db.commit();await hub.publish("PRINT_COMPLETED" if command.status==CommandStatus.SUCCESS else "PRINT_FAILED",{"job_id":job.id,"status":job.status},job.organization_id);return {"ok":True}

@app.get("/api/v1/dashboard")
def dashboard(user:User=Depends(current_user),db:Session=Depends(get_db)):
    jobs=db.query(PrintJob).filter(PrintJob.workshop_id.in_(accessible_workshop_ids(db,user))).all();agents=db.query(ComputerAgent).filter(ComputerAgent.workshop_id.in_(accessible_workshop_ids(db,user))).all();printers=db.query(Printer).join(ComputerAgent,Printer.computer_agent_id==ComputerAgent.id).filter(ComputerAgent.workshop_id.in_(accessible_workshop_ids(db,user))).all();return {"agents_online":sum(bool(a.is_online and a.last_heartbeat_at and utc_datetime(a.last_heartbeat_at)>datetime.now(timezone.utc)-timedelta(seconds=90)) for a in agents),"printers":len(printers),"printers_available":sum(p.status in {"ONLINE","READY","IDLE"} and p.enabled for p in printers),"jobs_waiting":sum(j.status==JobStatus.WAITING_APPROVAL for j in jobs),"jobs_printing":sum(j.status==JobStatus.PRINTING for j in jobs),"jobs_completed":sum(j.status==JobStatus.COMPLETED for j in jobs),"jobs_failed":sum(j.status==JobStatus.FAILED for j in jobs)}

@app.get("/api/v1/supervision")
def central_supervision(organization_id:str,user:User=Depends(current_user),db:Session=Depends(get_db)):
    require_org_admin(db,user,organization_id);now=datetime.now(timezone.utc);changed=False;items=[]
    query=db.query(Workshop).filter_by(organization_id=organization_id)
    if settings.single_workshop_id:query=query.filter(Workshop.id==settings.single_workshop_id)
    for workshop in query.all():
        agents=db.query(ComputerAgent).filter_by(workshop_id=workshop.id).all()
        for agent in agents:
            if agent.is_online and (not agent.last_heartbeat_at or utc_datetime(agent.last_heartbeat_at)<now-timedelta(seconds=90)):agent.is_online=False;changed=True
        printers=db.query(Printer).join(ComputerAgent).filter(ComputerAgent.workshop_id==workshop.id).all();jobs=db.query(PrintJob).filter_by(workshop_id=workshop.id).all()
        items.append({"workshop_id":workshop.id,"name":workshop.name,"agents":[{"id":a.id,"name":a.name,"online":a.is_online,"last_heartbeat_at":a.last_heartbeat_at} for a in agents],"printers":[{"id":p.id,"name":p.name,"status":p.status,"enabled":p.enabled} for p in printers],"jobs":{"waiting":sum(j.status==JobStatus.WAITING_APPROVAL for j in jobs),"printing":sum(j.status==JobStatus.PRINTING for j in jobs),"completed":sum(j.status==JobStatus.COMPLETED for j in jobs),"failed":sum(j.status==JobStatus.FAILED for j in jobs)}})
    if changed:db.commit()
    return {"organization_id":organization_id,"workshops":items}

@app.websocket("/ws/events")
async def events(ws:WebSocket):
    try:user_id=jwt.decode(ws.query_params.get("token",""),settings.jwt_secret,algorithms=["HS256"])["sub"]
    except Exception:
        # Accepting first makes the policy close code observable by browsers.
        # The client can then stop its reconnect loop and ask for login again.
        await ws.accept();await ws.close(code=1008);return
    db=SessionLocal()
    try: organizations={member.organization_id for member in db.query(OrganizationMember).filter_by(user_id=user_id).all()}
    finally:db.close()
    await hub.connect(ws,organizations,user_id)
    try:
        while True:await ws.receive_text()
    except Exception:hub.disconnect(ws)

@app.websocket("/ws/agent/{agent_id}")
async def agent_socket(ws:WebSocket,agent_id:str):
    db=next(get_db())
    try:
        authenticated_agent(agent_id,ws.query_params.get("key",""),db)
    except HTTPException:
        db.close();await ws.close(code=1008);return
    db.close();await agent_hub.connect(agent_id,ws)
    try:
        while True: await ws.receive_text()
    except Exception: agent_hub.disconnect(agent_id,ws)

@app.get("/",response_class=HTMLResponse)
def index():return HTMLResponse((Path(__file__).parent/"web"/"index.html").read_text(encoding="utf-8"))

@app.get("/browser-extension.zip",include_in_schema=False)
def browser_extension_download():
    """Download the Chromium extension as a ready-to-load ZIP."""
    folder=Path(__file__).resolve().parents[2]/"browser-extension"
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,"w",zipfile.ZIP_DEFLATED) as archive:
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in {".js",".json",".html",".css",".md"}:
                archive.write(path,path.name)
    buffer.seek(0)
    return StreamingResponse(iter([buffer.getvalue()]),media_type="application/zip",headers={"Content-Disposition":"attachment; filename=FUSAA-WhatsApp-Extension.zip"})

@app.get("/manifest.webmanifest")
def manifest(): return {"name":"FUSAA Service","short_name":"FUSAA","start_url":"/","display":"standalone","background_color":"#07111f","theme_color":"#07111f"}

@app.get("/app.js",response_class=HTMLResponse)
def app_js():return HTMLResponse((Path(__file__).parent/"web"/"app.js").read_text(encoding="utf-8"),media_type="application/javascript")

@app.get("/sw.js",response_class=HTMLResponse)
def service_worker(): return HTMLResponse("""const CACHE='fusaa-pwa-v3';const SHELL=['/','/app.js','/manifest.webmanifest'];self.addEventListener('install',e=>e.waitUntil(caches.open(CACHE).then(c=>c.addAll(SHELL)).then(()=>self.skipWaiting())));self.addEventListener('activate',e=>e.waitUntil(self.clients.claim()));self.addEventListener('fetch',e=>{if(e.request.method!=='GET')return;let u=new URL(e.request.url);if(u.origin!==location.origin||u.pathname.startsWith('/api/'))return;e.respondWith(fetch(e.request).then(r=>{caches.open(CACHE).then(c=>c.put(e.request,r.clone()));return r}).catch(()=>caches.match(e.request).then(r=>r||(e.request.mode==='navigate'?caches.match('/'):undefined))))});self.addEventListener('push',e=>{let d={};try{d=e.data.json()}catch{};e.waitUntil(self.registration.showNotification('FUSAA Service',{body:d.event||'Nouvel événement d’impression',data:d.payload||{}}))});self.addEventListener('notificationclick',e=>{e.notification.close();e.waitUntil(clients.openWindow('/'))});""",media_type="application/javascript")
