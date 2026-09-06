from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).parents[1]/"backend"))
import pytest
from app.models import JobStatus
from app.services import TRANSITIONS, create_preview, transition
from app.ai import DeterministicProvider, SafetyLevel, TOOL_SAFETY
from app.connectors import verify_meta_signature, whatsapp_media_message_ids
from app.document_processing import DocumentProcessor, LayoutEngine
from app.config import settings
from PIL import Image
import hashlib
import hmac

class Job:
    def __init__(self,status):self.status=status

def test_happy_path_transition_contract():
    job=Job(JobStatus.RECEIVED)
    for state in [JobStatus.ANALYZING,JobStatus.WAITING_APPROVAL,JobStatus.READY,JobStatus.QUEUED,JobStatus.PRINTING,JobStatus.COMPLETED]:transition(job,state)
    assert job.status is JobStatus.COMPLETED

def test_cannot_bypass_confirmation():
    with pytest.raises(ValueError):transition(Job(JobStatus.WAITING_APPROVAL),JobStatus.QUEUED)

def test_no_command_transition_after_completion():
    assert not TRANSITIONS.get(JobStatus.COMPLETED)

def test_printing_job_can_be_cancelled():
    job=Job(JobStatus.PRINTING)
    transition(job,JobStatus.CANCELLED)
    assert job.status is JobStatus.CANCELLED

def test_image_preview_is_derived(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"storage_dir",tmp_path)
    source=tmp_path/"source.png";Image.new("RGB",(1400,700),(20,40,60)).save(source)
    key=create_preview(source,"image/png")
    assert (tmp_path/key).exists()
    assert Image.open(tmp_path/key).size[0] <= 1200

def test_ai_never_auto_executes_print_intent():
    tool=DeterministicProvider().understand_command("Imprime le travail 12345678")[0]
    assert tool["name"] == "request_print"
    assert TOOL_SAFETY[tool["name"]] is SafetyLevel.CRITICAL

def test_processor_preserves_source_and_creates_derived_image(tmp_path):
    source=tmp_path/"original.png";Image.new("RGB",(30,10),(1,2,3)).save(source);original=source.read_bytes()
    result,mime,extension,metadata=DocumentProcessor().process(source,"image/png","rotate",{"degrees":90,"dpi":300})
    assert source.read_bytes()==original and mime=="image/png" and extension=="png" and metadata["width_px"]==10
    assert result

def test_layout_engine_has_deterministic_capacity(tmp_path):
    source=tmp_path/"card.png";Image.new("RGB",(100,60),(1,2,3)).save(source)
    pdf,metadata=LayoutEngine().create_sheet(source,"image/png",86,54,10,2)
    assert pdf.startswith(b"%PDF") and metadata["columns"]==2 and metadata["rows"]==5

def test_health_endpoints_are_public_and_lightweight():
    from fastapi.testclient import TestClient
    from app.main import app
    client=TestClient(app)
    assert client.get("/healthz").status_code==200
    assert client.get("/readyz").status_code==200

def test_whatsapp_webhook_only_extracts_attachment_ids_and_requires_signature():
    payload={"entry":[{"changes":[{"value":{"messages":[{"id":"image-1","type":"image","text":{"body":"private"}},{"id":"document-2","type":"document"},{"id":"text-3","type":"text"}]}}]}]}
    assert whatsapp_media_message_ids(payload)==["image-1","document-2"]
    raw=b'{"object":"whatsapp_business_account"}';secret="local-meta-secret"
    signature="sha256="+hmac.new(secret.encode(),raw,hashlib.sha256).hexdigest()
    assert verify_meta_signature(raw,signature,secret)
    assert not verify_meta_signature(raw,signature,"wrong-secret")
