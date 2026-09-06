"""Local activity inbox and locally paired Brave extension."""
from alembic import op
import sqlalchemy as sa
revision="0009_local_activity"
down_revision="0008_multisite"
branch_labels=None
depends_on=None

def upgrade():
    # Local development creates missing tables at startup; migration also supports it.
    if not sa.inspect(op.get_bind()).has_table("local_activities"):
        op.create_table("local_activities",sa.Column("id",sa.String(36),primary_key=True),sa.Column("workshop_id",sa.String(36),sa.ForeignKey("workshops.id"),nullable=False,index=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=True),sa.Column("event_key",sa.String(64),nullable=False,unique=True),sa.Column("source",sa.String(20),nullable=False),sa.Column("title",sa.String(300),nullable=False),sa.Column("detail",sa.String(600),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True),nullable=False))
    if not sa.inspect(op.get_bind()).has_table("browser_links"):
        op.create_table("browser_links",sa.Column("id",sa.String(36),primary_key=True),sa.Column("user_id",sa.String(36),sa.ForeignKey("users.id"),nullable=False,index=True),sa.Column("workshop_id",sa.String(36),sa.ForeignKey("workshops.id"),nullable=False),sa.Column("pairing_hash",sa.String(64),nullable=False,unique=True),sa.Column("expires_at",sa.DateTime(timezone=True),nullable=False),sa.Column("credential_hash",sa.String(64),nullable=True,unique=True),sa.Column("enabled",sa.Boolean(),nullable=False),sa.Column("last_seen_at",sa.DateTime(timezone=True),nullable=True),sa.Column("page_ready",sa.Boolean(),nullable=False))
def downgrade():
    op.drop_table("browser_links")
    op.drop_table("local_activities")
