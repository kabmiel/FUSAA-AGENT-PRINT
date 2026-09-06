"""External inputs are normalized before entering Print Core."""
from dataclasses import dataclass
import hmac
import hashlib
from pathlib import Path
import secrets
from sqlalchemy.orm import Session
from .models import Document, JobStatus, PrintJob
from .config import settings
from .services import ALLOWED_MIMES, create_preview, inspect_file, storage_path, transition

@dataclass(frozen=True)
class IncomingDocument:
    filename:str
    mime_type:str
    content:bytes
    source:str
    external_id:str
    metadata:dict

class Connector:
    name="abstract"
    def normalize(self,*args,**kwargs)->IncomingDocument:raise NotImplementedError

class UploadConnector(Connector):name="UPLOAD"
class APIConnector(Connector):name="API"
class EmailConnector(Connector):name="EMAIL"
class WhatsAppConnector(Connector):
    name="WHATSAPP"
    def normalize(self,*args,**kwargs):raise NotImplementedError("WhatsApp requires an approved official integration; browser automation is intentionally not implemented.")

def verify_meta_signature(raw_body:bytes,signature:str|None,app_secret:str)->bool:
    """Validate Meta's X-Hub-Signature-256 without retaining message content."""
    if not app_secret or not signature or not signature.startswith("sha256="):return False
    expected="sha256="+hmac.new(app_secret.encode("utf-8"),raw_body,hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected,signature)

def whatsapp_media_message_ids(payload:dict)->list[str]:
    """Return only attachment message ids; text, contacts and phone data are ignored."""
    identifiers=[]
    for entry in payload.get("entry",[]):
        for change in entry.get("changes",[]):
            for message in change.get("value",{}).get("messages",[]):
                if message.get("type") in {"document","image"} and isinstance(message.get("id"),str):identifiers.append(message["id"])
    return identifiers

def ingest_incoming_document(db:Session,incoming:IncomingDocument,organization_id:str,workshop_id:str)->tuple[Document,PrintJob]:
    if incoming.mime_type not in ALLOWED_MIMES:raise ValueError("Only PDF, JPEG and PNG are accepted")
    if not incoming.content or len(incoming.content)>settings.max_upload_bytes:raise ValueError("File must be between 1 byte and configured limit")
    safe_name=Path(incoming.filename or "document").name;key=f"originals/{secrets.token_urlsafe(18)}-{safe_name}";path=storage_path(key);path.write_bytes(incoming.content)
    try:metadata={**inspect_file(path,incoming.mime_type),"incoming":incoming.metadata,"external_id":incoming.external_id};preview_key=create_preview(path,incoming.mime_type)
    except Exception:
        path.unlink(missing_ok=True);raise
    document=Document(organization_id=organization_id,original_name=safe_name,storage_key=key,mime_type=incoming.mime_type,size_bytes=len(incoming.content),metadata_json=metadata,preview_key=preview_key);db.add(document);db.flush()
    job=PrintJob(organization_id=organization_id,workshop_id=workshop_id,document_id=document.id,source=incoming.source,status=JobStatus.RECEIVED);db.add(job);db.flush();transition(job,JobStatus.ANALYZING);transition(job,JobStatus.WAITING_APPROVAL)
    return document,job
