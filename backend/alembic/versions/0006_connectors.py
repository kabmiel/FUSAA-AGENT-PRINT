"""Connector configuration and idempotent intake events.

Revision ID: 0006_connectors
Revises: 0005_push_subscriptions
"""
from alembic import op
import sqlalchemy as sa
revision="0006_connectors"
down_revision="0005_push_subscriptions"
branch_labels=None
depends_on=None
def upgrade():
    op.create_table("connectors",sa.Column("id",sa.String(36),primary_key=True),sa.Column("organization_id",sa.String(36),sa.ForeignKey("organizations.id"),nullable=False),sa.Column("workshop_id",sa.String(36),sa.ForeignKey("workshops.id"),nullable=False),sa.Column("connector_type",sa.String(30),nullable=False),sa.Column("name",sa.String(120),nullable=False),sa.Column("secret_hash",sa.String(64),nullable=False),sa.Column("enabled",sa.Boolean(),nullable=False),sa.Column("config",sa.JSON(),nullable=False),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("secret_hash"))
    op.create_table("connector_events",sa.Column("id",sa.String(36),primary_key=True),sa.Column("connector_id",sa.String(36),sa.ForeignKey("connectors.id"),nullable=False),sa.Column("external_id",sa.String(255),nullable=False),sa.Column("document_id",sa.String(36),sa.ForeignKey("documents.id")),sa.Column("status",sa.String(30),nullable=False),sa.Column("error_message",sa.Text()),sa.Column("created_at",sa.DateTime(timezone=True)),sa.Column("updated_at",sa.DateTime(timezone=True)),sa.UniqueConstraint("connector_id","external_id",name="uq_connector_external_event"))
def downgrade():op.drop_table("connector_events");op.drop_table("connectors")
