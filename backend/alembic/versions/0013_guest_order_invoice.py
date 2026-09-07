"""Link public orders to their printable receipts."""
from alembic import op
import sqlalchemy as sa

revision="0013_guest_order_invoice"
down_revision="0012_guest_payment_verification"
branch_labels=None
depends_on=None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("guest_orders")}
    if "invoice_id" not in columns:
        op.add_column("guest_orders",sa.Column("invoice_id",sa.String(36),sa.ForeignKey("invoices.id"),nullable=True,unique=True))

def downgrade():
    with op.batch_alter_table("guest_orders") as batch:
        batch.drop_column("invoice_id")
