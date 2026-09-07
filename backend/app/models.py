import enum
import uuid
from datetime import datetime, timezone
from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base


def uid() -> str: return str(uuid.uuid4())

class JobStatus(str, enum.Enum):
    RECEIVED="RECEIVED"; ANALYZING="ANALYZING"; WAITING_APPROVAL="WAITING_APPROVAL"; READY="READY"; QUEUED="QUEUED"; PRINTING="PRINTING"; COMPLETED="COMPLETED"; FAILED="FAILED"; CANCELLED="CANCELLED"; IGNORED="IGNORED"
class CommandStatus(str, enum.Enum): PENDING="PENDING"; CLAIMED="CLAIMED"; SUCCESS="SUCCESS"; FAILED="FAILED"; CANCELLED="CANCELLED"

class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc), server_default=func.now(), onupdate=lambda:datetime.now(timezone.utc))

class User(Timestamped, Base):
    __tablename__="users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(320), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str] = mapped_column(String(120))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

class Organization(Timestamped, Base):
    __tablename__="organizations"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(160), unique=True)

class OrganizationMember(Timestamped, Base):
    __tablename__="organization_members"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(30), default="OWNER")
    __table_args__=(UniqueConstraint("organization_id", "user_id", name="uq_org_member"),)

class WorkshopMember(Timestamped, Base):
    __tablename__="workshop_members"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    role: Mapped[str] = mapped_column(String(30), default="OPERATOR")
    __table_args__=(UniqueConstraint("workshop_id","user_id",name="uq_workshop_member"),)

class PushSubscription(Timestamped, Base):
    __tablename__="push_subscriptions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    endpoint: Mapped[str] = mapped_column(String(2048), unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))

class Connector(Timestamped, Base):
    __tablename__="connectors"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    connector_type: Mapped[str] = mapped_column(String(30))
    name: Mapped[str] = mapped_column(String(120))
    secret_hash: Mapped[str] = mapped_column(String(64), unique=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config: Mapped[dict] = mapped_column(JSON, default=dict)

class ConnectorEvent(Timestamped, Base):
    __tablename__="connector_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    connector_id: Mapped[str] = mapped_column(ForeignKey("connectors.id"), index=True)
    external_id: Mapped[str] = mapped_column(String(255))
    document_id: Mapped[str | None] = mapped_column(ForeignKey("documents.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="RECEIVED")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    __table_args__=(UniqueConstraint("connector_id","external_id",name="uq_connector_external_event"),)

class Customer(Timestamped, Base):
    __tablename__="customers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

class Product(Timestamped, Base):
    __tablename__="products"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    sku: Mapped[str | None] = mapped_column(String(80), nullable=True)
    unit_price: Mapped[float] = mapped_column(Numeric(12,2), default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class Service(Timestamped, Base):
    __tablename__="services"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    unit_price: Mapped[float] = mapped_column(Numeric(12,2), default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

class PriceRule(Timestamped, Base):
    __tablename__="price_rules"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    priority: Mapped[int] = mapped_column(Integer, default=100)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    conditions: Mapped[dict] = mapped_column(JSON, default=dict)
    pricing: Mapped[dict] = mapped_column(JSON, default=dict)

class PrintCost(Timestamped, Base):
    __tablename__="print_costs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    print_job_id: Mapped[str] = mapped_column(ForeignKey("print_jobs.id"), unique=True, index=True)
    estimated_amount: Mapped[float] = mapped_column(Numeric(12,2), default=0)
    final_amount: Mapped[float | None] = mapped_column(Numeric(12,2), nullable=True)
    currency: Mapped[str] = mapped_column(String(3), default="XOF")
    breakdown: Mapped[dict] = mapped_column(JSON, default=dict)

class Invoice(Timestamped, Base):
    __tablename__="invoices"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    customer_id: Mapped[str | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    number: Mapped[str] = mapped_column(String(60), unique=True)
    status: Mapped[str] = mapped_column(String(30), default="DRAFT")
    currency: Mapped[str] = mapped_column(String(3), default="XOF")
    total_amount: Mapped[float] = mapped_column(Numeric(12,2), default=0)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class InvoiceLine(Base):
    __tablename__="invoice_lines"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    print_job_id: Mapped[str | None] = mapped_column(ForeignKey("print_jobs.id"), nullable=True)
    description: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit_amount: Mapped[float] = mapped_column(Numeric(12,2), default=0)
    total_amount: Mapped[float] = mapped_column(Numeric(12,2), default=0)

class Payment(Timestamped, Base):
    __tablename__="payments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    invoice_id: Mapped[str] = mapped_column(ForeignKey("invoices.id"), index=True)
    amount: Mapped[float] = mapped_column(Numeric(12,2))
    method: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(30), default="CONFIRMED")
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)

class Workshop(Timestamped, Base):
    __tablename__="workshops"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))

class ComputerAgent(Timestamped, Base):
    __tablename__="computer_agents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    enrollment_token: Mapped[str] = mapped_column(String(128), unique=True, index=True)
    agent_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    machine_fingerprint: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_online: Mapped[bool] = mapped_column(Boolean, default=False)

class Printer(Timestamped, Base):
    __tablename__="printers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    computer_agent_id: Mapped[str] = mapped_column(ForeignKey("computer_agents.id"), index=True)
    system_name: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(160))
    manufacturer: Mapped[str | None] = mapped_column(String(120), nullable=True)
    model: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="UNKNOWN")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    color_supported: Mapped[bool] = mapped_column(Boolean, default=True)
    duplex_supported: Mapped[bool] = mapped_column(Boolean, default=False)
    capabilities: Mapped[dict] = mapped_column(JSON, default=dict)
    __table_args__=(UniqueConstraint("computer_agent_id", "system_name", name="uq_printer_system"),)

class Document(Timestamped, Base):
    __tablename__="documents"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(512), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(Integer)
    metadata_json: Mapped[dict] = mapped_column(JSON, default=dict)
    preview_key: Mapped[str | None] = mapped_column(String(512), nullable=True)

class PrintJob(Timestamped, Base):
    __tablename__="print_jobs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    computer_agent_id: Mapped[str | None] = mapped_column(ForeignKey("computer_agents.id"), nullable=True)
    printer_id: Mapped[str | None] = mapped_column(ForeignKey("printers.id"), nullable=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("documents.id"), index=True)
    source: Mapped[str] = mapped_column(String(40), default="UPLOAD")
    status: Mapped[JobStatus] = mapped_column(Enum(JobStatus), default=JobStatus.RECEIVED, index=True)
    copies: Mapped[int] = mapped_column(Integer, default=1)
    paper_size: Mapped[str | None] = mapped_column(String(30), nullable=True)
    orientation: Mapped[str | None] = mapped_column(String(20), nullable=True)
    color_mode: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duplex: Mapped[bool] = mapped_column(Boolean, default=False)
    pages: Mapped[str | None] = mapped_column(String(120), nullable=True)
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), unique=True, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    estimated_cost: Mapped[float | None] = mapped_column(Numeric(12,2), nullable=True)
    final_cost: Mapped[float | None] = mapped_column(Numeric(12,2), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

class GuestOrder(Timestamped, Base):
    __tablename__="guest_orders"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    organization_id: Mapped[str] = mapped_column(ForeignKey("organizations.id"), index=True)
    workshop_id: Mapped[str] = mapped_column(ForeignKey("workshops.id"), index=True)
    print_job_id: Mapped[str] = mapped_column(ForeignKey("print_jobs.id"), unique=True, index=True)
    order_number: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    phone: Mapped[str] = mapped_column(String(50), index=True)
    display_name: Mapped[str | None] = mapped_column(String(160), nullable=True)
    access_token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    payment_status: Mapped[str] = mapped_column(String(30), default="PENDING")
    payment_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    payment_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    payment_verified_by: Mapped[str | None] = mapped_column(ForeignKey("users.id"), nullable=True)

class AgentCommand(Timestamped, Base):
    __tablename__="agent_commands"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    computer_agent_id: Mapped[str] = mapped_column(ForeignKey("computer_agents.id"), index=True)
    print_job_id: Mapped[str] = mapped_column(ForeignKey("print_jobs.id"), index=True)
    command_type: Mapped[str] = mapped_column(String(40), default="PRINT")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    idempotency_key: Mapped[str] = mapped_column(String(128), unique=True)
    status: Mapped[CommandStatus] = mapped_column(Enum(CommandStatus), default=CommandStatus.PENDING, index=True)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    result: Mapped[dict | None] = mapped_column(JSON, nullable=True)

class AuditLog(Base):
    __tablename__="audit_logs"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    actor: Mapped[str] = mapped_column(String(255))
    action: Mapped[str] = mapped_column(String(80), index=True)
    resource_type: Mapped[str] = mapped_column(String(80))
    resource_id: Mapped[str] = mapped_column(String(36))
    parameters: Mapped[dict] = mapped_column(JSON, default=dict)
    result: Mapped[str] = mapped_column(String(40))
    ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    agent_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda:datetime.now(timezone.utc), server_default=func.now())

class LocalActivity(Base):
    __tablename__="local_activities"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    workshop_id: Mapped[str]=mapped_column(ForeignKey("workshops.id"),index=True)
    user_id: Mapped[str|None]=mapped_column(ForeignKey("users.id"),nullable=True)
    event_key: Mapped[str]=mapped_column(String(64),unique=True)
    source: Mapped[str]=mapped_column(String(20))
    title: Mapped[str]=mapped_column(String(300))
    detail: Mapped[str]=mapped_column(String(600))
    created_at: Mapped[datetime]=mapped_column(DateTime(timezone=True),default=lambda:datetime.now(timezone.utc))

class BrowserLink(Base):
    __tablename__="browser_links"
    id: Mapped[str]=mapped_column(String(36),primary_key=True,default=uid)
    user_id: Mapped[str]=mapped_column(ForeignKey("users.id"),index=True)
    workshop_id: Mapped[str]=mapped_column(ForeignKey("workshops.id"))
    pairing_hash: Mapped[str]=mapped_column(String(64),unique=True)
    expires_at: Mapped[datetime]=mapped_column(DateTime(timezone=True))
    credential_hash: Mapped[str|None]=mapped_column(String(64),nullable=True,unique=True)
    enabled: Mapped[bool]=mapped_column(Boolean,default=False)
    last_seen_at: Mapped[datetime|None]=mapped_column(DateTime(timezone=True),nullable=True)
    page_ready: Mapped[bool]=mapped_column(Boolean,default=False)

class WorkshopSettings(Timestamped, Base):
    __tablename__="workshop_settings"
    workshop_id: Mapped[str]=mapped_column(ForeignKey("workshops.id"),primary_key=True)
    default_copies: Mapped[int]=mapped_column(Integer,default=1)
    default_paper_size: Mapped[str]=mapped_column(String(8),default="A4")
    default_orientation: Mapped[str]=mapped_column(String(12),default="PORTRAIT")
    default_color_mode: Mapped[str]=mapped_column(String(15),default="COLOR")
    default_duplex: Mapped[bool]=mapped_column(Boolean,default=False)
    popup_enabled: Mapped[bool]=mapped_column(Boolean,default=True)
    smart_suggestions: Mapped[bool]=mapped_column(Boolean,default=True)
