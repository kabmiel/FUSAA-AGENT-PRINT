"""Archive public orders without deleting their records."""
from alembic import op
import sqlalchemy as sa

revision="0014_guest_order_archive"
down_revision="0013_guest_order_invoice"
branch_labels=None
depends_on=None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("guest_orders")}
    if "archived_at" not in columns:
        op.add_column("guest_orders",sa.Column("archived_at",sa.DateTime(timezone=True),nullable=True))
    if "archived_by" not in columns:
        with op.batch_alter_table("guest_orders") as batch:
            batch.add_column(sa.Column("archived_by",sa.String(36),sa.ForeignKey("users.id",name="fk_guest_orders_archived_by_users"),nullable=True))

def downgrade():
    with op.batch_alter_table("guest_orders") as batch:
        batch.drop_column("archived_by")
        batch.drop_column("archived_at")
