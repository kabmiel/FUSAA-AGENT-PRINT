"""Persist the single-workshop print preferences."""
from alembic import op
import sqlalchemy as sa

revision="0010_workshop_settings"
down_revision="0009_local_activity"
branch_labels=None
depends_on=None

def upgrade():
    if not sa.inspect(op.get_bind()).has_table("workshop_settings"):
        op.create_table(
            "workshop_settings",
            sa.Column("workshop_id",sa.String(36),sa.ForeignKey("workshops.id"),primary_key=True),
            sa.Column("default_copies",sa.Integer(),nullable=False,server_default="1"),
            sa.Column("default_paper_size",sa.String(8),nullable=False,server_default="A4"),
            sa.Column("default_orientation",sa.String(12),nullable=False,server_default="PORTRAIT"),
            sa.Column("default_color_mode",sa.String(15),nullable=False,server_default="COLOR"),
            sa.Column("default_duplex",sa.Boolean(),nullable=False,server_default=sa.false()),
            sa.Column("popup_enabled",sa.Boolean(),nullable=False,server_default=sa.true()),
            sa.Column("smart_suggestions",sa.Boolean(),nullable=False,server_default=sa.true()),
            sa.Column("created_at",sa.DateTime(timezone=True),nullable=True),
            sa.Column("updated_at",sa.DateTime(timezone=True),nullable=True),
        )

def downgrade():
    op.drop_table("workshop_settings")
