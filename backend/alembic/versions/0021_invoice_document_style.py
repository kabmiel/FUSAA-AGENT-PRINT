"""Allow each issued billing document to keep its selected PDF style."""
from alembic import op
import sqlalchemy as sa


revision = "0021_invoice_document_style"
down_revision = "0020_billing_competition_trace"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("invoices") as batch:
        batch.add_column(sa.Column("document_style", sa.String(40), nullable=True))


def downgrade():
    with op.batch_alter_table("invoices") as batch:
        batch.drop_column("document_style")
