"""Add Markdown content and creation timestamp without removing historical data.

Revision ID: 0003_simplify_documents
Revises: 0002_add_admin_users
"""

from alembic import op
import sqlalchemy as sa


revision = "0003_simplify_documents"
down_revision = "0002_add_admin_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("documents", sa.Column("content", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("created_at", sa.DateTime(timezone=True), nullable=True))
    # La base auditada está vacía. Si hubiera filas históricas, no inventar
    # contenido: usar texto vacío y la fecha de actualización ya disponible.
    op.execute("UPDATE documents SET content = '', created_at = updated_at")
    op.alter_column("documents", "content", existing_type=sa.Text(), nullable=False)
    op.alter_column("documents", "created_at", existing_type=sa.DateTime(timezone=True), nullable=False)


def downgrade() -> None:
    # No perder texto ni fechas de Documents creados después de la migración.
    # También se aplica al SQL offline, cuando posteriormente se ejecute.
    op.execute("""
        DO $$ BEGIN
            LOCK TABLE documents IN ACCESS EXCLUSIVE MODE;
            IF EXISTS (SELECT 1 FROM documents) THEN
                RAISE EXCEPTION 'No se puede revertir 0003 con Documents existentes.';
            END IF;
        END $$
    """)
    op.drop_column("documents", "created_at")
    op.drop_column("documents", "content")
