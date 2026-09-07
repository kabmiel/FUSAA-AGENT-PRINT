"""Public guest print orders and secure tracking tokens."""
from alembic import op
import sqlalchemy as sa

revision="0011_guest_orders"
down_revision="0010_workshop_settings"
branch_labels=None
depends_on=None

def upgrade():
    if not sa.inspect(op.get_bind()).has_table("guest_orders"):
        op.create_table(
            "guest_orders",
            sa.Column("id",sa.String(36),primary_key=True),
            sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False,index=True),
            sa.Column("workshop_id",sa.String(36),sa.ForeignKey("workshops.id"),nullable=False,index=True),
            sa.Column("print_job_id",sa.String(36),sa.ForeignKey("print_jobs.id"),nullable=False,unique=True,index=True),
            sa.Column("order_number",sa.String(60),nullable=False,unique=True,index=True),
            sa.Column("phone",sa.String(50),nullable=False,index=True),
            sa.Column("display_name",sa.String(160),nullable=True),
            sa.Column("access_token_hash",sa.String(64),nullable=False,unique=True),
            sa.Column("payment_status",sa.String(30),nullable=False,server_default="PENDING"),
            sa.Column("created_at",sa.DateTime(timezone=True),nullable=True),
            sa.Column("updated_at",sa.DateTime(timezone=True),nullable=True),
        )

def downgrade():
    op.drop_table("guest_orders")
