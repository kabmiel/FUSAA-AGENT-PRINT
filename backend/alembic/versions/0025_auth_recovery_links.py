"""Single-use activation/recovery links and revocable password sessions."""
from alembic import context, op
import sqlalchemy as sa

revision = "0025_auth_recovery_links"
down_revision = "0024_customer_credit_accounts"
branch_labels = None
depends_on = None


def upgrade():
    inspector = None if context.is_offline_mode() else sa.inspect(op.get_bind())
    if inspector is None or "auth_version" not in {col["name"] for col in inspector.get_columns("users")}:
        op.add_column("users", sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"))
    if inspector is None or not inspector.has_table("auth_action_tokens"):
        op.create_table("auth_action_tokens",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.String(36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("purpose", sa.String(16), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("consumed_at", sa.DateTime(timezone=True)),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
            sa.CheckConstraint("purpose IN ('ACTIVATE', 'RESET')", name="ck_auth_action_purpose"))
        op.create_index("ix_auth_action_tokens_user_id", "auth_action_tokens", ["user_id"])


def downgrade():
    op.drop_table("auth_action_tokens")
    with op.batch_alter_table("users") as batch:
        batch.drop_column("auth_version")
