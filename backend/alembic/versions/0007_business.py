"""Business foundation: customers, pricing, invoices and payments.

Revision ID: 0007_business
Revises: 0006_connectors
"""
from alembic import op
import sqlalchemy as sa
revision="0007_business"
down_revision="0006_connectors"
branch_labels=None
depends_on=None
def upgrade():
    op.add_column("print_jobs",sa.Column("estimated_cost",sa.Numeric(12,2)))
    op.add_column("print_jobs",sa.Column("final_cost",sa.Numeric(12,2)))
    op.create_table("customers",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("name",sa.String(160),nullable=False),sa.Column("phone",sa.String(50)),sa.Column("email",sa.String(320)),sa.Column("notes",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
    op.create_table("products",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("name",sa.String(160),nullable=False),sa.Column("sku",sa.String(80)),sa.Column("unit_price",sa.Numeric(12,2),nullable=False),sa.Column("enabled",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
    op.create_table("services",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("name",sa.String(160),nullable=False),sa.Column("unit_price",sa.Numeric(12,2),nullable=False),sa.Column("enabled",sa.Boolean(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
    op.create_table("price_rules",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("name",sa.String(160),nullable=False),sa.Column("priority",sa.Integer(),nullable=False),sa.Column("enabled",sa.Boolean(),nullable=False),sa.Column("conditions",sa.JSON(),nullable=False),sa.Column("pricing",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
    op.create_table("print_costs",sa.Column("id",sa.String(36),primary_key=True),sa.Column("print_job_id",sa.String(36),sa.ForeignKey("print_jobs.id"),nullable=False),sa.Column("estimated_amount",sa.Numeric(12,2),nullable=False),sa.Column("final_amount",sa.Numeric(12,2)),sa.Column("currency",sa.String(3),nullable=False),sa.Column("breakdown",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("print_job_id"))
    op.create_table("invoices",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("customer_id",sa.String(36),sa.ForeignKey("customers.id")),sa.Column("number",sa.String(60),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("currency",sa.String(3),nullable=False),sa.Column("total_amount",sa.Numeric(12,2),nullable=False),sa.Column("due_at",sa.DateTime(timezone=True)),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("number"))
    op.create_table("invoice_lines",sa.Column("id",sa.String(36),primary_key=True),sa.Column("invoice_id",sa.String(36),sa.ForeignKey("invoices.id"),nullable=False),sa.Column("print_job_id",sa.String(36),sa.ForeignKey("print_jobs.id")),sa.Column("description",sa.String(255),nullable=False),sa.Column("quantity",sa.Integer(),nullable=False),sa.Column("unit_amount",sa.Numeric(12,2),nullable=False),sa.Column("total_amount",sa.Numeric(12,2),nullable=False))
    op.create_table("payments",sa.Column("id",sa.String(36),primary_key=True),sa.Column("invoice_id",sa.String(36),sa.ForeignKey("invoices.id"),nullable=False),sa.Column("amount",sa.Numeric(12,2),nullable=False),sa.Column("method",sa.String(40),nullable=False),sa.Column("status",sa.String(30),nullable=False),sa.Column("reference",sa.String(120)),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)))
def downgrade():
    for table in ["payments","invoice_lines","invoices","print_costs","price_rules","services","products","customers"]:op.drop_table(table)
    op.drop_column("print_jobs","final_cost");op.drop_column("print_jobs","estimated_cost")
