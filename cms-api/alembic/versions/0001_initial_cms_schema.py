"""initial_cms_schema

Revision ID: 0001_initial_cms_schema
Revises: None

Migración inicial explícita, sin datos semilla ni generación de UUID.
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "0001_initial_cms_schema"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "templates",
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("target_type", sa.String(), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        sa.Column("allow_published_edit", sa.Boolean(), nullable=False),
        sa.Column("metadata_contract", postgresql.JSONB(), nullable=False),
        sa.Column("layout_structure", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("template_id", name="pk_templates"),
        sa.UniqueConstraint("name", name="uq_templates_name"),
    )
    op.create_table(
        "documents",
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slug", sa.String(), nullable=False),
        sa.Column("title", sa.String(), nullable=False),
        sa.Column("content_type", sa.String(), nullable=False),
        sa.Column("status", sa.String(length=11), nullable=False),
        sa.Column("template_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("frozen_template", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("metadata_values", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('BORRADOR', 'EN_REVISION', 'PUBLICADO', 'ARCHIVADO')",
            name=op.f("ck_documents_document_status"),
        ),
        sa.ForeignKeyConstraint(
            ["template_id"], ["templates.template_id"],
            name="fk_documents_template_id_templates", ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("document_id", name="pk_documents"),
        sa.UniqueConstraint("slug", name="uq_documents_slug"),
    )
    op.create_index("ix_documents_template_id", "documents", ["template_id"])
    op.create_index("ix_documents_status", "documents", ["status"])
    op.create_table(
        "canvas_blocks",
        sa.Column("block_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("block_type", sa.String(), nullable=False),
        sa.Column("order_index", sa.Integer(), nullable=False),
        sa.Column("content_payload", postgresql.JSONB(), nullable=False),
        sa.Column("style_config", postgresql.JSONB(none_as_null=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.document_id"],
            name="fk_canvas_blocks_document_id_documents", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("block_id", name="pk_canvas_blocks"),
        sa.UniqueConstraint(
            "document_id", "order_index",
            name="uq_canvas_blocks_document_id_order_index",
        ),
    )
    op.create_table(
        "review_reports",
        sa.Column("report_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("document_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("findings", postgresql.JSONB(), nullable=False),
        sa.Column("audited_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["document_id"], ["documents.document_id"],
            name="fk_review_reports_document_id_documents", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("report_id", name="pk_review_reports"),
    )
    op.create_index(
        "ix_review_reports_document_id_audited_at",
        "review_reports", ["document_id", sa.text("audited_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_review_reports_document_id_audited_at", table_name="review_reports")
    op.drop_table("review_reports")
    op.drop_table("canvas_blocks")
    op.drop_index("ix_documents_status", table_name="documents")
    op.drop_index("ix_documents_template_id", table_name="documents")
    op.drop_table("documents")
    op.drop_table("templates")
