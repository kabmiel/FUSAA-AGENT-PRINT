"""Store the administrator's liquid-glass intensity."""
from alembic import op
import sqlalchemy as sa


revision = "0023_workshop_app_transparency"
down_revision = "0022_invoice_line_display_order"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("workshop_settings") as batch:
        batch.add_column(sa.Column("app_transparency", sa.Integer(), nullable=False, server_default="46"))


def downgrade():
    with op.batch_alter_table("workshop_settings") as batch:
        batch.drop_column("app_transparency")
