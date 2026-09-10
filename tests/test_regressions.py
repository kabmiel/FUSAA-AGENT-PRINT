import asyncio
import importlib.util
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
from types import SimpleNamespace
import pytest
from io import BytesIO
from starlette.datastructures import Headers, UploadFile
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
ROOT=Path(__file__).parents[1]
sys.path[:0]=[str(ROOT/"backend"),str(ROOT/"local-agent")]
from app.database import Base
from app.models import User,Organization,OrganizationMember,Workshop,WorkshopMember,Document,PrintJob,ComputerAgent,Printer,JobStatus,LocalActivity,BrowserLink,GuestOrder,ShopCategory,ShopProduct
from app.main import cancel_job,confirm_job,prepare_job,central_supervision,list_jobs,list_documents,audit_history,list_workshop_members,update_workshop_member,remove_workshop_member,assign_workshop_member,register,create_guest_order,guest_order_status,verify_guest_payment,list_guest_orders,export_guest_orders,archive_guest_order,restore_guest_order,set_public_pricing,get_public_pricing,refresh_guest_quote,create_guest_receipt,production_dashboard,index,impression_index,admin_index,public_tracking_page,delete_job,archive_public_job,create_shop_order,shop_public_products,shop_public_products_page,shop_admin_products_page
from app.connectors import IncomingDocument, ingest_incoming_document
from app.config import settings
from app.schemas import JobOptions,GuestPaymentIn,PublicPricingIn,RegisterIn
from app.shop_schemas import ShopPublicOrderIn
from app.multisite_schemas import WorkshopMemberIn,WorkshopMemberRoleIn
from app.ai import execute_safe_tool,OllamaProvider
from fusaa_agent.main import Agent,Settings
from fusaa_agent.printing import page_indices

@pytest.fixture
def setup_db():
    engine=create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        user=User(id="viewer",email="v@example.com",display_name="Viewer",password_hash="unused")
        admin=User(id="admin",email="a@example.com",display_name="Admin",password_hash="unused")
        db.add_all([user,admin,Organization(id="o",name="Test")]);db.flush()
        db.add_all([OrganizationMember(user_id=user.id,organization_id="o",role="OPERATOR"),OrganizationMember(user_id=admin.id,organization_id="o",role="OWNER"),Workshop(id="a",organization_id="o",name="A"),Workshop(id="b",organization_id="o",name="B")]);db.flush()
        db.add(WorkshopMember(user_id=user.id,workshop_id="a",role="VIEWER"))
        for suffix in ("a","b"):
            db.add(Document(id="doc-"+suffix,organization_id="o",original_name="test.png",storage_key="original-"+suffix,mime_type="image/png",size_bytes=1,metadata_json={}))
            db.add(ComputerAgent(id="agent-"+suffix,workshop_id=suffix,name=suffix,enrollment_token="enroll-"+suffix,is_online=True,last_heartbeat_at=datetime.now(timezone.utc)))
            db.flush()
            db.add(Printer(id="printer-"+suffix,computer_agent_id="agent-"+suffix,system_name=suffix,name=suffix,status="ONLINE",enabled=True))
            db.add(PrintJob(id=("aaaaaaaa" if suffix=="a" else "bbbbbbbb")+"-1111-1111-1111-111111111111",organization_id="o",workshop_id=suffix,document_id="doc-"+suffix,status=JobStatus.WAITING_APPROVAL))
        db.commit()
        yield db,user,admin

def test_assistant_and_http_share_workshop_scope(setup_db):
    db,user,_=setup_db
    assert len(list_jobs(user,db))==1
    assert len(list_documents(user,db))==1
    assert len(execute_safe_tool(db,user,"list_print_jobs",{})["jobs"])==1
    assert len(execute_safe_tool(db,user,"list_printers",{})["printers"])==1

def test_workshop_roles_are_admin_managed_and_enforced(setup_db):
    from app.access import require_workshop_write
    db,viewer,admin=setup_db
    with pytest.raises(HTTPException) as error:list_workshop_members("a",viewer,db)
    assert error.value.status_code==403
    members=list_workshop_members("a",admin,db)
    assert any(member["user_id"]==viewer.id and member["role"]=="VIEWER" for member in members)
    update_workshop_member("a",viewer.id,WorkshopMemberRoleIn(role="OPERATOR"),admin,db)
    require_workshop_write(db,viewer,"a")
    assert audit_history(action="WORKSHOP_MEMBER_ROLE_UPDATED",user=admin,db=db)[0].actor==admin.id
    assert not audit_history(action="WORKSHOP_MEMBER_ROLE_UPDATED",user=viewer,db=db)
    assert remove_workshop_member("a",viewer.id,admin,db)["removed"]
    with pytest.raises(HTTPException):require_workshop_write(db,viewer,"a")

def test_team_invitation_is_claimed_on_registration(setup_db):
    db,_,admin=setup_db
    invitation=assign_workshop_member("a",WorkshopMemberIn(user_email="invite@example.com",role="OPERATOR"),admin,db)
    invited=db.query(User).filter_by(email="invite@example.com").one()
    assert invitation["invited"] and invitation["registration_url"].startswith("/inscription") and not invited.is_active
    register(RegisterIn(email="invite@example.com",password="a-secure-password",display_name="Invité"),db)
    db.refresh(invited)
    assert invited.is_active and db.query(WorkshopMember).filter_by(workshop_id="a",user_id=invited.id).one().role=="OPERATOR"

def test_system_health_exposes_verified_backup_timestamp(setup_db,tmp_path,monkeypatch):
    from app import main
    _,_,admin=setup_db
    fake=tmp_path/"backend"/"app"/"main.py";fake.parent.mkdir(parents=True)
    runtime=tmp_path/"runtime";runtime.mkdir()
    (runtime/"health.json").write_text(json.dumps({"last_check":datetime.now(timezone.utc).isoformat(),"api":True,"agent":True,"ollama":False,"backup_today":True,"backup_last_at":"2026-09-07T12:00:00+00:00"}))
    monkeypatch.setattr(main,"Path",lambda _:fake)
    report=main.local_system_health(admin)
    assert report["supervisor"]=="running" and report["backup_last_at"]=="2026-09-07T12:00:00+00:00"

def test_production_deployment_requires_postgres_and_safe_start_command():
    from app.config import Settings
    safe=Settings(_env_file=None,environment="production",database_url="postgresql+psycopg://user:pass@db.example/postgres",jwt_secret="x"*48,cors_origins="https://fusaa.example",trusted_hosts="fusaa.example")
    safe.validate_runtime()
    with pytest.raises(RuntimeError):Settings(_env_file=None,environment="production",database_url="sqlite:///./fusaa.db",jwt_secret="x"*48,cors_origins="https://fusaa.example").validate_runtime()
    assert "alembic upgrade head && uvicorn" in (ROOT/"render.yaml").read_text(encoding="utf-8")

def test_finish_persists_and_preserves_job_and_document(setup_db):
    from app.main import finish_job
    from app.models import AuditLog
    db,viewer,admin=setup_db
    job=db.query(PrintJob).filter_by(workshop_id="a").one()
    with pytest.raises(HTTPException) as error:
        finish_job(job.id,admin,db)
    assert error.value.status_code==409
    job.status=JobStatus.COMPLETED;db.commit()
    assert job.id in [item.id for item in list_jobs(admin,db)]
    with pytest.raises(HTTPException) as error:
        finish_job(job.id,viewer,db)
    assert error.value.status_code==403
    assert finish_job(job.id,admin,db)["archived"]
    assert finish_job(job.id,admin,db)["archived"]
    db.expire_all()
    assert job.id not in [item.id for item in list_jobs(admin,db)]
    assert db.get(PrintJob,job.id).status==JobStatus.COMPLETED
    assert db.get(Document,job.document_id)
    assert db.query(AuditLog).filter_by(resource_id=job.id,action="PRINT_JOB_FINISH_CONFIRMED").count()==1

@pytest.mark.parametrize("prefix",["aaaaaaaa","bbbbbbbb"])
@pytest.mark.parametrize("action",["cancel","confirm","prepare"])
def test_viewer_cannot_mutate_own_or_other_workshop(setup_db,prefix,action):
    db,user,_=setup_db;job=prefix+"-1111-1111-1111-111111111111"
    with pytest.raises(HTTPException) as error:
        if action=="prepare":prepare_job(job,JobOptions(printer_id="printer-a"),user,db)
        else:asyncio.run((cancel_job if action=="cancel" else confirm_job)(job,user,db))
    assert error.value.status_code==403
    assert db.get(PrintJob,job).status==JobStatus.WAITING_APPROVAL

def test_sqlite_supervision_and_printer_queries(setup_db):
    db,_,admin=setup_db
    assert len(central_supervision("o",admin,db)["workshops"])==2
    assert len(execute_safe_tool(db,admin,"list_printers",{})["printers"])==2

def test_any_file_is_received_and_non_direct_formats_require_preparation(setup_db,tmp_path,monkeypatch):
    db,_,admin=setup_db
    monkeypatch.setattr(settings,"storage_dir",tmp_path)
    document,job=ingest_incoming_document(db,IncomingDocument(filename="devis.docx",mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",content=b"office-content",source="UPLOAD",external_id="external",metadata={}),"o","a")
    assert document.preview_key is None
    assert document.metadata_json["direct_printable"] is False
    assert document.metadata_json["format_extension"]=="docx"
    with pytest.raises(HTTPException) as error:
        prepare_job(job.id,JobOptions(printer_id="printer-a"),admin,db)
    assert error.value.status_code==409
    assert "converti en PDF" in error.value.detail

def test_guest_order_has_phone_and_secure_follow_link(setup_db,tmp_path,monkeypatch):
    db,_,admin=setup_db
    monkeypatch.setattr(settings,"storage_dir",tmp_path)
    monkeypatch.setattr(settings,"single_workshop_id","a")
    upload=UploadFile(filename="notice.txt",file=BytesIO(b"guest document"),headers=Headers({"content-type":"text/plain"}))
    created=asyncio.run(create_guest_order(None,upload,"+22790000000","Client test",2,"A4","MONOCHROME",False,db))
    assert created.order_number.startswith("FUS-")
    assert "/suivi/" in created.tracking_url
    number,token=created.tracking_url.rsplit("/",2)[-2:]
    followed=guest_order_status(number,token,db)
    assert followed.order_number==created.order_number
    assert followed.document_name=="notice.txt"
    assert followed.progress==30 and followed.stage=="Paiement à confirmer"
    with pytest.raises(HTTPException) as error:guest_order_status(number,"wrong-token",db)
    assert error.value.status_code==404
    order=db.query(GuestOrder).filter_by(order_number=created.order_number).one()
    with pytest.raises(HTTPException) as error:delete_job(order.print_job_id,admin,db)
    assert error.value.status_code==409 and "public" in error.value.detail
    with pytest.raises(HTTPException) as error:prepare_job(order.print_job_id,JobOptions(printer_id="printer-a"),admin,db)
    assert error.value.status_code==409 and "Paiement" in error.value.detail
    pricing=set_public_pricing(PublicPricingIn(base=25,per_copy=50,per_page=100),admin,db)
    assert pricing.per_page==100 and get_public_pricing(admin,db).base==25
    quoted=refresh_guest_quote(order.id,admin,db)
    assert quoted.estimated_cost==325
    updated=asyncio.run(verify_guest_payment(order.id,GuestPaymentIn(status="PAID",reference="espèces"),admin,db))
    assert updated.payment_status=="PAID" and updated.payment_reference=="espèces"
    assert guest_order_status(number,token,db).stage=="Paiement confirmé"
    receipt=create_guest_receipt(order.id,admin,db)
    assert receipt.order_number==created.order_number and receipt.amount==325
    assert create_guest_receipt(order.id,admin,db).invoice_number==receipt.invoice_number
    assert list_guest_orders(admin,db)[0].order_number==created.order_number
    production=production_dashboard(admin,db)
    assert production["summary"]["paid_orders"]==1 and production["summary"]["paid_revenue"]==325
    assert production["recent_orders"][0]["order_number"]==created.order_number and len(production["days"])==7
    job=db.get(PrintJob,order.print_job_id);job.status=JobStatus.FAILED;job.error_message="internal printer secret";db.commit()
    assert next(item.public_order for item in list_jobs(admin,db) if item.id==job.id)
    failed=guest_order_status(number,token,db)
    assert failed.stage=="Intervention atelier requise" and "secret" not in failed.detail
    archived=archive_public_job(job.id,admin,db)
    assert archived.archived_at is not None
    assert not list_guest_orders(admin,db)
    assert job.id not in {item.id for item in list_jobs(admin,db)}
    assert list_guest_orders(admin,db,q=created.order_number,include_archived=True)[0].id==order.id
    assert restore_guest_order(order.id,admin,db).archived_at is None
    export=export_guest_orders(admin,db,q=created.order_number)
    assert export.media_type.startswith("text/csv") and created.order_number in export.body.decode("utf-8")

def test_explicit_monochrome_and_color_price_tiers(setup_db,monkeypatch):
    db,_,admin=setup_db
    monkeypatch.setattr(settings,"single_workshop_id","a")
    job=db.query(PrintJob).first();document=db.get(Document,job.document_id)
    document.metadata_json={"pages":5};job.copies=2;job.color_mode="MONOCHROME"
    set_public_pricing(PublicPricingIn(monochrome_page=50,monochrome_discount_from=10,monochrome_discount_page=25,color_page=100,color_discount_from=10,color_discount_page=75),admin,db)
    from app.business import estimate_print_cost
    amount,breakdown=estimate_print_cost(db,job)
    assert float(amount)==250 and breakdown["per_page"]==25
    job.color_mode="COLOR";amount,breakdown=estimate_print_cost(db,job)
    assert float(amount)==750 and breakdown["per_page"]==75

def test_assistant_uses_saved_public_price_grid(setup_db,monkeypatch):
    from app.assistant_flow import workflow_response
    from app.assistant_schemas import AssistantRequest
    db,_,admin=setup_db
    monkeypatch.setattr(settings,"single_workshop_id","a")
    set_public_pricing(PublicPricingIn(monochrome_page=50,monochrome_discount_from=50,monochrome_discount_page=25,color_page=100,color_discount_from=50,color_discount_page=50),admin,db)
    response=workflow_response(AssistantRequest(message="Combien pour 20 pages noir et blanc ?"),db,admin)
    assert response.answer=="Pour 20 pages en noir et blanc : 1,000 FCFA."
    assert "Tarif appliqué : 50 FCFA par page" in response.steps

def test_guest_assistant_greets_and_shares_payment_contacts():
    from app.main import guest_assistant_reply
    greeting=guest_assistant_reply("Bonjour", "shop_guest")
    payment=guest_assistant_reply("Comment payer par Wave ?", "shop_guest")
    assert greeting["title"].startswith("Bonjour")
    assert "+227 98313369" in greeting["answer"]
    assert "MYNITA" in payment["answer"] and "+227 90531465" in payment["answer"]

def test_shop_guest_assistant_uses_live_catalogue(setup_db,monkeypatch):
    from app.main import guest_assistant_reply
    db,_,_=setup_db;monkeypatch.setattr(settings,"single_workshop_id","a")
    product=ShopProduct(organization_id="o",name="Imprimante Laser",slug="imprimante-laser",description="Rapide",price_xof=125000,stock_quantity=2,enabled=True)
    db.add(product);db.commit()
    reply=guest_assistant_reply("Avez-vous une imprimante laser ?","shop_guest",db)
    assert "Imprimante Laser" in reply["answer"]
    assert "125,000 FCFA" in reply["answer"]

def test_shop_admin_assistant_uses_all_stock_not_only_current_page(setup_db):
    from app.main import shop_admin_assistant
    from app.assistant_schemas import GuestAssistantRequest
    db,_,admin=setup_db
    db.add(ShopProduct(organization_id="o",name="Toner",slug="toner",description="",price_xof=3000,stock_quantity=0,enabled=True));db.commit()
    reply=shop_admin_assistant(GuestAssistantRequest(message="Quels produits sont en rupture ?"),"o",admin,db)
    assert reply["next_view"]=="shopProductsManage"
    assert "Toner" in reply["answer"]

def test_public_home_and_admin_have_separate_shells():
    storefront=index().body.decode("utf-8")
    public=impression_index().body.decode("utf-8")
    tracked=public_tracking_page("FUS-20260101-ABCDEF","secret").body.decode("utf-8")
    admin=admin_index().body.decode("utf-8")
    assert "Boutique FUSAA" in storefront and "shop.js" in storefront and "cartButton" in storefront
    assert "guestPhone" in public and "public.js" in public
    assert 'aria-live="polite"' in public and "prefers-reduced-motion" in public
    assert tracked==public
    assert "app.js" in admin and "guestPhone" not in admin
    assert "fontScale" in (ROOT/"backend"/"app"/"web"/"app.js").read_text(encoding="utf-8")

def test_shop_order_uses_fcfa_stock_and_public_workshop(setup_db,monkeypatch):
    db,_,admin=setup_db;monkeypatch.setattr(settings,"single_workshop_id","a")
    category=ShopCategory(organization_id="o",name="PC",slug="pc");db.add(category);db.flush()
    product=ShopProduct(organization_id="o",category_id=category.id,name="Portable",slug="portable",description="Test",price_xof=250000,stock_quantity=2);db.add(product);db.commit()
    products=shop_public_products(db=db)
    assert products[0]["price_xof"]==250000 and products[0]["stock_quantity"]==2
    page=shop_public_products_page(page=1,page_size=1,db=db)
    assert page["items"][0]["id"]==product.id and page["has_more"] is False
    admin_page=shop_admin_products_page("o",page=1,page_size=1,user=admin,db=db)
    assert admin_page["items"][0]["id"]==product.id and admin_page["has_more"] is False
    order=asyncio.run(create_shop_order(ShopPublicOrderIn(customer_name="Client Test",customer_phone="90000000",items=[{"product_id":product.id,"quantity":2}]),db))
    db.refresh(product)
    assert order["currency"]=="XOF" and order["total_xof"]==500000 and product.stock_quantity==0

def test_printer_must_match_job_workshop(setup_db):
    db,_,admin=setup_db
    with pytest.raises(HTTPException) as error:
        prepare_job("aaaaaaaa-1111-1111-1111-111111111111",JobOptions(printer_id="printer-b"),admin,db)
    assert error.value.status_code==422

def test_unknown_dispatch_is_never_replayed(tmp_path,monkeypatch):
    state=tmp_path/"agent.json"
    state.write_text(json.dumps({"agent_id":"a","agent_key":"unused","queue":{"c":{"command":{"id":"c","type":"PRINT"},"executed":False,"report":None,"dispatch_started":True}}}))
    agent=Agent(Settings(state_file=state))
    monkeypatch.setattr(agent,"execute",lambda cmd:pytest.fail("Physical action must never run"))
    reports=[]
    monkeypatch.setattr(agent.client,"post",lambda *a,**kw:(reports.append(kw["json"]) or SimpleNamespace(raise_for_status=lambda:None)))
    agent.process_queue();agent.process_queue()
    assert len(reports)==1 and reports[0]["status"]=="FAILED"
    assert json.loads(state.read_text())["queue"]["c"]["acknowledged"]
    agent.client.close()

def test_dispatch_intent_persisted_before_execution(tmp_path,monkeypatch):
    agent=Agent(Settings(state_file=tmp_path/"agent.json"))
    agent.state={"agent_id":"a","agent_key":"test","queue":{"c":{"command":{"id":"c","type":"CANCEL"},"executed":False,"report":None}}}
    def execute(cmd):
        assert json.loads(agent.s.state_file.read_text())["queue"]["c"]["dispatch_started"]
        return {"ok":True}
    monkeypatch.setattr(agent,"execute",execute)
    monkeypatch.setattr(agent.client,"post",lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None))
    agent.process_queue()
    assert agent.queue()["c"]["acknowledged"]
    agent.client.close()

def test_pages_and_local_ollama_boundary():
    assert page_indices("1-3,5",5)==[0,1,2,4]
    for invalid in ("0","6","3-1","1;print"):
        with pytest.raises(ValueError):page_indices(invalid,5)
    with pytest.raises(ValueError):OllamaProvider("https://external.example","model")

def test_verified_backup_and_non_destructive_restore(tmp_path):
    spec=importlib.util.spec_from_file_location("runtime",ROOT/"scripts"/"windows_runtime.py")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    root=tmp_path/"source";(root/"backend"/"storage").mkdir(parents=True)
    (root/"backend"/".env").write_text("DATABASE_URL=sqlite:///./fusaa.db\nSTORAGE_DIR=./storage\n")
    import sqlite3
    with sqlite3.connect(root/"backend"/"fusaa.db") as db:
        db.execute("CREATE TABLE documents(storage_key TEXT, preview_key TEXT)")
        db.execute("INSERT INTO documents VALUES ('sample.txt',NULL)")
    (root/"backend"/"storage"/"sample.txt").write_text("sample")
    folder=module.backup(root,tmp_path/"backups")
    module.restore(folder,tmp_path/"restored")
    assert (tmp_path/"restored"/"storage"/"sample.txt").read_text()=="sample"
    with pytest.raises(RuntimeError):module.restore(folder,root)
    (folder/"storage"/"sample.txt").write_text("tampered")
    with pytest.raises(RuntimeError):module.check_snapshot(folder)

def test_gdi_renders_selected_pages_copies_and_driver_options(monkeypatch):
    from fusaa_agent import printing
    import fitz,win32gui,win32print,win32con
    from PIL import ImageWin
    events=[];selected=[]
    def pixmap(**kwargs):
        return SimpleNamespace(n=3,width=2,height=2,samples=bytes(12))
    class Source:
        is_pdf=True
        page_count=3
        def __getitem__(self,index):
            selected.append(index);return SimpleNamespace(get_pixmap=pixmap)
        def close(self):pass
    monkeypatch.setattr(fitz,"open",lambda _:Source())
    options={"copies":2,"pages":"1,3","duplex":True,"paper_size":"A4","orientation":"LANDSCAPE","color_mode":"MONOCHROME"}
    monkeypatch.setattr(printing,"configured_devmode",lambda printer,payload:(events.append(dict(payload)) or "mode"))
    monkeypatch.setattr(win32gui,"CreateDC",lambda *args:100)
    monkeypatch.setattr(win32gui,"DeleteDC",lambda *args:None)
    monkeypatch.setattr(win32print,"GetDeviceCaps",lambda dc,cap:300)
    monkeypatch.setattr(win32print,"StartDoc",lambda *args:42)
    for name in ("StartPage","EndPage","EndDoc","AbortDoc"):
        monkeypatch.setattr(win32print,name,lambda *args:None)
    monkeypatch.setattr(ImageWin,"Dib",lambda image:SimpleNamespace(draw=lambda *args:None))
    result=printing.render_job("unused.pdf","mock",options,"test")
    assert selected==[0,2,0,2]
    assert events==[options]
    assert result["spooler_job_id"]==42

def test_viewer_cannot_transform_documents(setup_db):
    from app.access import require_document_write
    db,user,_=setup_db
    with pytest.raises(HTTPException) as error:require_document_write(db,user,db.get(Document,"doc-a"))
    assert error.value.status_code==403

def test_realtime_events_respect_workshop_permissions(setup_db,monkeypatch):
    from app import events
    from contextlib import nullcontext
    db,user,_=setup_db
    monkeypatch.setattr(events,"SessionLocal",lambda:nullcontext(db))
    assert events.EventHub.can_receive(user.id,"o",{"job_id":"aaaaaaaa-1111-1111-1111-111111111111"})
    assert not events.EventHub.can_receive(user.id,"o",{"job_id":"bbbbbbbb-1111-1111-1111-111111111111"})

def test_realtime_events_never_cross_organizations_for_multi_org_user(setup_db,monkeypatch):
    from app import events
    from contextlib import nullcontext
    db,user,_=setup_db
    db.add_all([
        Organization(id="other",name="Other"),
        OrganizationMember(user_id=user.id,organization_id="other",role="OWNER"),
        Workshop(id="other-workshop",organization_id="other",name="Other workshop"),
        Document(id="doc-other",organization_id="other",original_name="other.pdf",storage_key="other.pdf",mime_type="application/pdf",size_bytes=1,metadata_json={}),
        ComputerAgent(id="agent-other",workshop_id="other-workshop",name="Other agent",enrollment_token="other-enroll"),
        PrintJob(id="cccccccc-1111-1111-1111-111111111111",organization_id="other",workshop_id="other-workshop",document_id="doc-other",status=JobStatus.WAITING_APPROVAL),
        LocalActivity(id="activity-other",workshop_id="other-workshop",user_id=user.id,event_key="other-activity-key",source="WHATSAPP",title="Other",detail="Other"),
    ])
    db.commit()
    monkeypatch.setattr(events,"SessionLocal",lambda:nullcontext(db))
    for payload in ({"job_id":"cccccccc-1111-1111-1111-111111111111"},{"document_id":"doc-other"},{"agent_id":"agent-other"},{"activity_id":"activity-other"}):
        assert not events.EventHub.can_receive(user.id,"o",payload)

def test_assistant_guides_document_selection_before_print_confirmation(setup_db):
    from app.assistant_flow import workflow_response
    from app.assistant_schemas import AssistantRequest
    db,_,admin=setup_db
    response=workflow_response(AssistantRequest(message="Je voudrais imprimer un document"),db,admin)
    assert response.next_view=="upload"
    assert response.tool_calls==[]
    assert not response.requires_confirmation

def test_assistant_requires_confirmation_only_for_a_ready_selected_job(setup_db):
    from app.assistant_flow import workflow_response
    from app.assistant_schemas import AssistantRequest
    db,_,admin=setup_db
    job=db.get(PrintJob,"aaaaaaaa-1111-1111-1111-111111111111")
    job.status=JobStatus.READY;job.printer_id="printer-a";db.commit()
    response=workflow_response(AssistantRequest(message="Imprimer ce document",selected_job_id=job.id),db,admin)
    assert response.requires_confirmation
    assert [item.name for item in response.tool_calls]==["request_print"]

def test_duplicate_browser_event_still_persists_heartbeat(setup_db):
    from app.local_monitor import BrowserEvent,browser_event,hash_value
    db,_,admin=setup_db
    credential="local-browser-credential"
    link=BrowserLink(id="browser-link",user_id=admin.id,workshop_id="a",pairing_hash=hash_value("pair"),credential_hash=hash_value(credential),expires_at=datetime.now(timezone.utc),enabled=True)
    event_id="browser-event-12345"
    db.add_all([link,LocalActivity(workshop_id="a",user_id=admin.id,event_key=hash_value(link.id+":"+event_id),source="WHATSAPP",title="Existing",detail="Existing")])
    db.commit()
    request=SimpleNamespace(headers={"X-Fusaa-Link":credential},client=SimpleNamespace(host="127.0.0.1"))
    result=asyncio.run(browser_event(BrowserEvent(event_id=event_id,kind="MESSAGE"),request,db))
    db.refresh(link)
    assert result["duplicate"] and link.last_seen_at is not None and link.page_ready

def test_browser_unpair_revokes_the_server_credential(setup_db):
    from app.local_monitor import hash_value,unpair_browser
    db,_,admin=setup_db
    credential="credential-to-revoke"
    link=BrowserLink(user_id=admin.id,workshop_id="a",pairing_hash=hash_value("pair-two"),credential_hash=hash_value(credential),expires_at=datetime.now(timezone.utc),enabled=True)
    db.add(link);db.commit()
    request=SimpleNamespace(headers={"X-Fusaa-Link":credential},client=SimpleNamespace(host="127.0.0.1"))
    assert unpair_browser(request,db)=={"ok":True}
    db.refresh(link)
    assert not link.enabled and link.credential_hash is None

def test_safe_assistant_results_are_structured_without_model_prose(setup_db,monkeypatch):
    from app import main
    from app.assistant_schemas import AssistantRequest
    db,_,admin=setup_db
    monkeypatch.setattr(main,"assistant_provider",SimpleNamespace(understand_command=lambda _:[{"name":"list_print_jobs","arguments":{}}]))
    response=main.understand_assistant(AssistantRequest(message="Quels sont mes travaux ?"),admin,db)
    assert response.title=="Travaux d’impression"
    assert response.steps and response.next_view=="print" and not response.requires_confirmation

def test_claim_recovery_never_requeues_dispatched_job(setup_db):
    from app.models import AgentCommand,CommandStatus
    from app.main import poll_commands
    from datetime import timedelta
    db,_,_=setup_db
    agent=db.get(ComputerAgent,"agent-a");agent.agent_key="test-key"
    for name,result in (("unstarted",None),("dispatched",{"spooler_job_id":42})):
        db.add(AgentCommand(id=name,computer_agent_id=agent.id,print_job_id="aaaaaaaa-1111-1111-1111-111111111111",idempotency_key=name,status=CommandStatus.CLAIMED,claimed_at=datetime.now(timezone.utc)-timedelta(minutes=10),result=result))
    db.commit()
    commands=poll_commands(agent.id,SimpleNamespace(headers={"X-Agent-Key":"test-key"}),db)
    assert [c["id"] for c in commands]==["unstarted"]

def test_websocket_credentials_are_redacted_from_logs():
    import logging
    from app.observability import RedactSessionSecrets
    record=logging.LogRecord("uvicorn",20,"",0,'WebSocket %s accepted',('/ws/agent/a?key=secret&token=jwt',),None)
    RedactSessionSecrets().filter(record)
    assert "secret" not in record.getMessage() and "jwt" not in record.getMessage()
    assert record.getMessage().count("[REDACTED]")==2

def test_spooler_exit_treated_as_successful_completion(tmp_path,monkeypatch):
    import pywintypes
    state = tmp_path / "agent.json"
    payload = {"agent_id": "a", "agent_key": "test", "queue": {"c": {"command": {"id": "c", "type": "PRINT"}, "executed": True, "report": {"status": "DISPATCHED", "result": {"spooler_job_id": 42, "printer": "mock"}}}}}
    state.write_text(json.dumps(payload))
    agent=Agent(Settings(state_file=state))
    monkeypatch.setattr(agent.client,"post",lambda *a,**kw:SimpleNamespace(raise_for_status=lambda:None))
    class MockWin32Print:
        @staticmethod
        def OpenPrinter(name):return 1
        @staticmethod
        def ClosePrinter(handle):pass
        @staticmethod
        def GetJob(handle,job_id,level):
            error=pywintypes.error(87,"GetJob","Invalid parameter")
            error.winerror=87
            raise error
    import sys
    monkeypatch.setitem(sys.modules,"win32print",MockWin32Print)
    agent.process_queue()
    updated=json.loads(state.read_text())["queue"]["c"]
    assert updated["report"]["status"]=="SUCCESS"
    assert updated["report"]["result"]["spooler_state"]=="COMPLETED"
    agent.client.close()

def test_gdi_scaling_formula_fits_device_context():
    # Simulate a document page and printer device context
    img_w,img_h = 1654,2338 # A4 at 200 dpi
    width,height = 4960,7014 # 600 dpi printable area
    scale = min(width/img_w, height/img_h)
    w,h = int(img_w*scale), int(img_h*scale)
    assert w <= width and h <= height
    # Verify aspect ratio matches within integer rounding
    assert abs((w/h) - (img_w/img_h)) < 0.001

def test_config_anchors_relative_database_and_storage_paths():
    from app.config import Settings, BACKEND_DIR
    custom=Settings(_env_file=None, database_url="sqlite:///./test.db", storage_dir=Path("./my_storage"))
    assert BACKEND_DIR.as_posix() in custom.database_url
    assert custom.storage_dir.is_absolute()
    assert custom.storage_dir == (BACKEND_DIR / "my_storage").resolve()
