import hashlib
import mimetypes
import secrets
from datetime import datetime, timezone
from pathlib import Path
from PIL import Image
from pypdf import PdfReader
from sqlalchemy.orm import Session
from .config import settings
from .models import AgentCommand, AuditLog, ComputerAgent, Document, JobStatus, PrintJob, Printer

ALLOWED_MIMES={"application/pdf","image/jpeg","image/png"}
TERMINAL={JobStatus.COMPLETED,JobStatus.FAILED,JobStatus.CANCELLED,JobStatus.IGNORED}
TRANSITIONS={JobStatus.RECEIVED:{JobStatus.ANALYZING},JobStatus.ANALYZING:{JobStatus.WAITING_APPROVAL,JobStatus.FAILED},JobStatus.WAITING_APPROVAL:{JobStatus.READY,JobStatus.IGNORED,JobStatus.CANCELLED},JobStatus.READY:{JobStatus.QUEUED,JobStatus.CANCELLED},JobStatus.QUEUED:{JobStatus.PRINTING,JobStatus.FAILED,JobStatus.CANCELLED},JobStatus.PRINTING:{JobStatus.COMPLETED,JobStatus.FAILED,JobStatus.CANCELLED}}

def audit(db:Session,actor:str,action:str,resource_type:str,resource_id:str,result:str="SUCCESS",parameters:dict|None=None,agent_id:str|None=None):
    db.add(AuditLog(actor=actor,action=action,resource_type=resource_type,resource_id=resource_id,result=result,parameters=parameters or {},agent_id=agent_id))

def transition(job:PrintJob,target:JobStatus):
    if target not in TRANSITIONS.get(job.status,set()): raise ValueError(f"Invalid transition {job.status} → {target}")
    job.status=target

def inspect_file(path:Path,mime:str)->dict:
    data={"mime_type":mime,"warnings":[]}
    if mime=="application/pdf":
        reader=PdfReader(path); data["pages"]=len(reader.pages)
        if reader.pages:
            box=reader.pages[0].mediabox; data.update(width_points=float(box.width),height_points=float(box.height),orientation="LANDSCAPE" if box.width>box.height else "PORTRAIT")
    else:
        with Image.open(path) as image:
            dpi=image.info.get("dpi",(None,None)); data.update(width_px=image.width,height_px=image.height,dpi_x=dpi[0],dpi_y=dpi[1],orientation="LANDSCAPE" if image.width>image.height else "PORTRAIT")
            if not dpi[0] or dpi[0]<150: data["warnings"].append("DPI faible ou absent : contrôler la qualité avant impression.")
    return data

def create_preview(source:Path,mime:str)->str:
    """Create a derived JPEG; the original source is never altered."""
    key=f"previews/{secrets.token_urlsafe(18)}.jpg"; destination=storage_path(key)
    if mime=="application/pdf":
        import fitz
        pdf=fitz.open(source)
        if not pdf.page_count: raise ValueError("PDF has no pages")
        pix=pdf[0].get_pixmap(matrix=fitz.Matrix(1.5,1.5),alpha=False);pix.save(destination)
        pdf.close()
    else:
        with Image.open(source) as image:
            preview=image.convert("RGB")
            preview.thumbnail((1200,1200))
            # thumbnail mutates the image object only, never the uploaded source file.
            preview.save(destination,"JPEG",quality=85,optimize=True)
    return key

def storage_path(key:str)->Path:
    target=settings.storage_dir/key; target.parent.mkdir(parents=True,exist_ok=True); return target

def issue_agent_key()->str: return secrets.token_urlsafe(48)
def fingerprint_file(content:bytes)->str: return hashlib.sha256(content).hexdigest()

def build_command(db:Session,job:PrintJob,printer:Printer)->AgentCommand:
    if not printer.enabled or printer.status.upper() not in {"ONLINE","READY","IDLE"}: raise ValueError("Selected printer is unavailable")
    if not job.computer_agent_id: raise ValueError("No agent assigned")
    if printer.computer_agent_id!=job.computer_agent_id:raise ValueError("Printer does not match assigned agent")
    agent=db.get(ComputerAgent,job.computer_agent_id)
    if not agent or agent.workshop_id!=job.workshop_id:raise ValueError("Printer does not belong to job workshop")
    token=f"print:{job.id}" # exactly one command per job
    existing=db.query(AgentCommand).filter_by(idempotency_key=token).one_or_none()
    if existing:return existing
    doc=db.get(Document,job.document_id)
    cmd=AgentCommand(computer_agent_id=job.computer_agent_id,print_job_id=job.id,idempotency_key=token,payload={"document_id":doc.id,"printer_system_name":printer.system_name,"copies":job.copies,"paper_size":job.paper_size,"orientation":job.orientation,"color_mode":job.color_mode,"duplex":job.duplex,"pages":job.pages})
    db.add(cmd); transition(job,JobStatus.QUEUED); return cmd
