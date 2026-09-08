"""Store manual verification of public order payments."""
from alembic import op
import sqlalchemy as sa

revision="0012_guest_payment_verification"
down_revision="0011_guest_orders"
branch_labels=None
depends_on=None

def upgrade():
    columns={column["name"] for column in sa.inspect(op.get_bind()).get_columns("guest_orders")}
    if "payment_reference" not in columns:
        op.add_column("guest_orders",sa.Column("payment_reference",sa.String(120),nullable=True))
    if "payment_verified_at" not in columns:
        op.add_column("guest_orders",sa.Column("payment_verified_at",sa.DateTime(timezone=True),nullable=True))
    if "payment_verified_by" not in columns:
        # SQLite cannot add a foreign-key constraint with ALTER TABLE. Alembic's
        # batch operation rebuilds the table safely while PostgreSQL keeps a
        # normal ALTER operation.
        with op.batch_alter_table("guest_orders") as batch:
            batch.add_column(sa.Column("payment_verified_by",sa.String(36),sa.ForeignKey("users.id",name="fk_guest_orders_payment_verified_by_users"),nullable=True))

def downgrade():
    with op.batch_alter_table("guest_orders") as batch:
        batch.drop_column("payment_verified_by")
        batch.drop_column("payment_verified_at")
        batch.drop_column("payment_reference")
