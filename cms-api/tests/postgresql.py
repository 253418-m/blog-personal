"""Infraestructura compartida de integración opt-in, sin administrar el esquema."""

import os
from pathlib import Path
import unittest

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")


@unittest.skipUnless(TEST_DATABASE_URL, "TEST_DATABASE_URL absent; PostgreSQL integration is opt-in")
class PostgreSQLTestCase(unittest.TestCase):
    """Cada prueba usa su propia transacción exterior y siempre la revierte."""

    @classmethod
    def setUpClass(cls):
        try:
            url = make_url(TEST_DATABASE_URL)
        except Exception:
            raise ValueError("TEST_DATABASE_URL must be a valid local PostgreSQL SQLAlchemy URL") from None
        if (
            url.drivername != "postgresql+psycopg"
            or url.host not in {"localhost", "127.0.0.1"}
            or url.database != "cms_core"
            or url.query
        ):
            raise ValueError(
                "Integration tests require postgresql+psycopg, localhost/127.0.0.1, "
                "database cms_core and no URL query overrides"
            )
        cls.engine = create_engine(url, pool_pre_ping=True)
        cls.addClassCleanup(cls.engine.dispose)
        try:
            with cls.engine.connect() as connection:
                tables = set(inspect(connection).get_table_names())
                required = {
                    "templates", "documents", "canvas_blocks", "review_reports",
                    "admin_users", "alembic_version",
                }
                if not required.issubset(tables):
                    raise RuntimeError("Run alembic upgrade head on the local cms_core DB before integration tests")
                backend_root = Path(__file__).resolve().parents[1]
                config = Config(str(backend_root / "alembic.ini"))
                config.set_main_option("script_location", str(backend_root / "alembic"))
                expected_heads = set(ScriptDirectory.from_config(config).get_heads())
                actual_heads = set(connection.scalars(text("SELECT version_num FROM alembic_version")))
                if not expected_heads or actual_heads != expected_heads:
                    raise RuntimeError("The local database must be at Alembic head before integration tests")
        except RuntimeError:
            raise
        except Exception:
            raise RuntimeError("Cannot validate local PostgreSQL; check its availability and Alembic configuration") from None

    def setUp(self):
        self.connection = self.engine.connect()
        self.addCleanup(self.connection.close)
        self.transaction = self.connection.begin()
        self.addCleanup(self._rollback_outer_transaction)
        self.session = Session(bind=self.connection, join_transaction_mode="create_savepoint")
        self.addCleanup(self.session.close)

    def _rollback_outer_transaction(self):
        if self.transaction.is_active:
            self.transaction.rollback()


class IsolatedAdminPostgreSQLTestCase(PostgreSQLTestCase):
    """AdminUser ficticio en pg_temp; public.admin_users permanece inaccesible al ORM."""

    def setUp(self):
        super().setUp()
        # La tabla temporal conserva tipos, constraints y defaults reales, pero
        # solo existe en esta conexión y desaparece al revertir la transacción.
        self.connection.execute(text(
            "CREATE TEMP TABLE admin_users "
            "(LIKE public.admin_users INCLUDING ALL) ON COMMIT DROP"
        ))
        temporary_oid = self.connection.scalar(text("SELECT 'pg_temp.admin_users'::regclass::oid"))
        resolved_oid = self.connection.scalar(text("SELECT 'admin_users'::regclass::oid"))
        public_oid = self.connection.scalar(text("SELECT 'public.admin_users'::regclass::oid"))
        if resolved_oid != temporary_oid or resolved_oid == public_oid:
            raise RuntimeError("Administrative tests require an isolated temporary table")
