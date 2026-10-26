"""CRUD HTTP con PostgreSQL real y copias pg_temp; sin tocar datos del usuario."""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.exc import SQLAlchemyError
from uuid6 import uuid7

from app.api.v1.endpoints.templates import get_template_service
from app.domain.enums import DocumentStatus
from app.infrastructure.database.models import AdminUserModel, DocumentModel, TemplateModel
from app.infrastructure.database.session import get_session
from app.infrastructure.database.template_repository import SQLAlchemyTemplateRepository
from app.main import app
from app.services.template_service import TemplateService
from tests.auth_support import AUTH_USER_ID, signed_fixture_token
from tests.test_auth_http import AuthHTTPTestCase


def create_payload(**overrides):
    body = {
        "name": "Template ficticia POST", "target_type": "POST", "is_default": True,
        "allow_published_edit": False,
        "metadata_contract": [{"field_key": "category", "expected_type": "STRING", "is_required": True}],
        "layout_structure": {"sections": ["header", "content"]},
    }
    body.update(overrides)
    return body


def update_payload(template, **overrides):
    body = {key: template[key] for key in ("name", "is_default", "metadata_contract", "layout_structure")}
    body.update(overrides)
    return body


class TemplateHTTPTestCase(AuthHTTPTestCase):
    def setUp(self):
        super().setUp()
        for table in ("templates", "documents"):
            self.connection.execute(text(
                f"CREATE TEMP TABLE {table} (LIKE public.{table} INCLUDING ALL) ON COMMIT DROP"
            ))
            self.assertEqual(
                self.connection.scalar(text(f"SELECT '{table}'::regclass::oid")),
                self.connection.scalar(text(f"SELECT 'pg_temp.{table}'::regclass::oid")),
            )
        # LIKE no copia FK: restaurar la relación contra la Template temporal.
        # PostgreSQL también renombra UNIQUE al copiar: conservar su identidad
        # para probar la traducción concreta de la restricción de producción.
        unique_name = self.connection.scalar(text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid='pg_temp.templates'::regclass AND contype='u'"
        ))
        quoted_name = self.connection.dialect.identifier_preparer.quote(unique_name)
        self.connection.execute(text(
            f"ALTER TABLE pg_temp.templates RENAME CONSTRAINT {quoted_name} TO uq_templates_name"
        ))
        self.connection.execute(text(
            "ALTER TABLE pg_temp.documents ADD CONSTRAINT fk_documents_template_id_templates "
            "FOREIGN KEY (template_id) REFERENCES pg_temp.templates(template_id) ON DELETE RESTRICT"
        ))
        app.dependency_overrides[get_template_service] = lambda: TemplateService(self.session_factory)
        # Auth y CRUD comparten esta conexión de prueba, pero no una transacción
        # real de producción. Liberar el savepoint de lectura conserva las
        # escrituras del servicio hasta el rollback exterior del test.
        def authenticated_session():
            with self.session_factory() as session, session.begin():
                yield session

        app.dependency_overrides[get_session] = authenticated_session
        self.headers = {"Authorization": "Bearer " + signed_fixture_token()}

    def create(self, **overrides):
        return self.client.post("/api/v1/templates", json=create_payload(**overrides), headers=self.headers)

    def seed(self, **overrides):
        response = self.create(**overrides)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def listing(self, **params):
        return self.client.get("/api/v1/templates", params=params, headers=self.headers)

    def put(self, template, **overrides):
        return self.client.put(
            "/api/v1/templates/" + template["template_id"],
            json=update_payload(template, **overrides), headers=self.headers,
        )

    def delete(self, template):
        return self.client.delete("/api/v1/templates/" + template["template_id"], headers=self.headers)

    def rows(self):
        return self.connection.execute(
            select(TemplateModel.__table__).order_by(TemplateModel.created_at, TemplateModel.template_id)
        ).mappings().all()

    def assert_single_default(self, template):
        defaults = [str(row["template_id"]) for row in self.rows() if row["is_default"]]
        self.assertEqual(defaults, [template["template_id"]])

    def add_document(self, template, status=DocumentStatus.BORRADOR):
        document_id = uuid7()
        self.connection.execute(DocumentModel.__table__.insert().values(
            document_id=document_id, slug="template-fixture-" + str(document_id),
            title="Documento ficticio", content_type="POST", status=status,
            template_id=UUID(template["template_id"]), updated_at=datetime.now(timezone.utc),
            content="Contenido ficticio", created_at=datetime.now(timezone.utc),
            frozen_template={"fixture": True} if status in (DocumentStatus.PUBLICADO, DocumentStatus.ARCHIVADO) else None,
        ))


class TemplateCreateTests(TemplateHTTPTestCase):
    def test_requires_bearer(self):
        response = self.client.post("/api/v1/templates", json=create_payload())
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
        self.assertEqual(len(self.rows()), 0)

    def test_creates_first_default_with_complete_response(self):
        template = self.seed()
        self.assertEqual(set(template), set(create_payload()) | {"template_id", "created_at"})
        self.assertEqual(template["metadata_contract"], create_payload()["metadata_contract"])
        self.assertEqual(template["layout_structure"], create_payload()["layout_structure"])
        self.assert_single_default(template)

    def test_first_nondefault_is_rejected_without_writes(self):
        self.assertEqual(self.create(is_default=False).status_code, 422)
        self.assertEqual(len(self.rows()), 0)

    def test_generated_id_is_uuid7(self):
        self.assertEqual(UUID(self.seed()["template_id"]).version, 7)

    def test_created_at_is_current_utc(self):
        before = datetime.now(timezone.utc)
        timestamp = datetime.fromisoformat(self.seed()["created_at"])
        self.assertEqual(timestamp.utcoffset(), timedelta(0))
        self.assertTrue(before <= timestamp <= datetime.now(timezone.utc))

    def test_duplicate_name_returns_409(self):
        original = self.seed()
        self.assertEqual(self.create().status_code, 409)
        self.assertEqual(len(self.rows()), 1)
        self.assert_single_default(original)

    def test_empty_metadata_returns_422(self):
        self.assertEqual(self.create(metadata_contract=[]).status_code, 422)

    def test_duplicate_field_key_returns_422(self):
        item = create_payload()["metadata_contract"][0]
        self.assertEqual(self.create(metadata_contract=[item, {**item, "field_key": " category "}]).status_code, 422)

    def test_unknown_target_returns_422(self):
        for target in ("DEV_BLOG", "LANDING_CV", "OTHER"):
            self.assertEqual(self.create(target_type=target).status_code, 422)

    def test_unknown_expected_type_returns_422(self):
        item = {**create_payload()["metadata_contract"][0], "expected_type": "OBJECT"}
        self.assertEqual(self.create(metadata_contract=[item]).status_code, 422)

    def test_new_default_transfers_previous_default(self):
        self.seed()
        second = self.seed(name="Segunda ficticia", target_type="LANDING")
        self.assertEqual(len(self.rows()), 2)
        self.assert_single_default(second)

    def test_published_edit_boolean_is_not_forced_by_target(self):
        first = self.seed(allow_published_edit=True)
        second = self.seed(name="Landing ficticia", target_type="LANDING", allow_published_edit=False, is_default=False)
        self.assertTrue(first["allow_published_edit"])
        self.assertFalse(second["allow_published_edit"])

    def test_invalid_names_metadata_keys_booleans_and_layout_are_rejected(self):
        item = create_payload()["metadata_contract"][0]
        for changes in (
            {"name": "   "}, {"metadata_contract": [{**item, "field_key": " "}]},
            {"metadata_contract": [{**item, "is_required": "true"}]},
            {"is_default": 1}, {"allow_published_edit": "false"},
            {"layout_structure": []}, {"layout_structure": None}, {"unexpected": "value"},
        ):
            with self.subTest(fields=list(changes)):
                self.assertEqual(self.create(**changes).status_code, 422)
        self.assertEqual(len(self.rows()), 0)


class TemplateListTests(TemplateHTTPTestCase):
    def test_requires_bearer(self):
        self.assertEqual(self.client.get("/api/v1/templates").status_code, 401)

    def test_empty_catalog(self):
        response = self.listing()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"items": []})

    def test_returns_all_templates_and_complete_fields(self):
        first = self.seed()
        second = self.seed(name="Landing ficticia", target_type="LANDING", is_default=False)
        self.assertEqual(self.listing().json(), {"items": [first, second]})

    def test_filters_post(self):
        first = self.seed()
        self.seed(name="Landing ficticia", target_type="LANDING", is_default=False)
        self.assertEqual(self.listing(target_type="POST").json(), {"items": [first]})

    def test_filters_landing(self):
        self.seed()
        second = self.seed(name="Landing ficticia", target_type="LANDING", is_default=False)
        self.assertEqual(self.listing(target_type="LANDING").json(), {"items": [second]})

    def test_order_is_created_at_ascending_with_id_tiebreaker(self):
        first = self.seed()
        second = self.seed(name="Segunda ficticia", is_default=False)
        earlier = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.connection.execute(update(TemplateModel).where(TemplateModel.template_id == UUID(second["template_id"])).values(created_at=earlier))
        self.assertEqual(self.listing().json()["items"][0]["template_id"], second["template_id"])
        self.connection.execute(update(TemplateModel).values(created_at=earlier))
        ids = [item["template_id"] for item in self.listing().json()["items"]]
        self.assertEqual(ids, sorted([first["template_id"], second["template_id"]]))

    def test_invalid_target_filter_returns_422(self):
        self.assertEqual(self.listing(target_type="DEV_BLOG").status_code, 422)


class TemplateUpdateTests(TemplateHTTPTestCase):
    def test_requires_bearer(self):
        self.assertEqual(self.client.put("/api/v1/templates/" + str(uuid7()), json=update_payload(create_payload())).status_code, 401)

    def test_missing_template_returns_404(self):
        template = {**create_payload(), "template_id": str(uuid7())}
        response = self.put(template)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.json(), {"detail": "Template no encontrada."})

    def test_replaces_all_editable_fields_and_preserves_immutable_fields(self):
        template = self.seed()
        changes = {"name": "Nombre ficticio nuevo", "metadata_contract": [
            {"field_key": "date", "expected_type": "DATE", "is_required": False}],
            "layout_structure": {"sections": ["content"], "custom": {"nested": [1, True, None]}}}
        response = self.put(template, **changes)
        self.assertEqual(response.status_code, 200)
        for field, value in changes.items():
            self.assertEqual(response.json()[field], value)
        for field in ("template_id", "created_at", "target_type", "allow_published_edit"):
            self.assertEqual(response.json()[field], template[field])

    def test_duplicate_name_returns_409(self):
        first = self.seed()
        second = self.seed(name="Segunda ficticia", is_default=False)
        self.assertEqual(self.put(second, name=first["name"]).status_code, 409)

    def test_empty_metadata_returns_422(self):
        self.assertEqual(self.put(self.seed(), metadata_contract=[]).status_code, 422)

    def test_duplicate_field_key_returns_422(self):
        template = self.seed()
        self.assertEqual(self.put(template, metadata_contract=template["metadata_contract"] * 2).status_code, 422)

    def test_target_type_is_forbidden_even_when_unchanged(self):
        self.assertEqual(self.put(self.seed(), target_type="POST").status_code, 422)

    def test_allow_published_edit_is_forbidden(self):
        self.assertEqual(self.put(self.seed(), allow_published_edit=True).status_code, 422)

    def test_transfer_default_leaves_exactly_one(self):
        self.seed()
        second = self.seed(name="Segunda ficticia", is_default=False)
        self.assertEqual(self.put(second, is_default=True).status_code, 200)
        self.assert_single_default(second)

    def test_cannot_leave_zero_defaults(self):
        first = self.seed()
        self.seed(name="Segunda ficticia", is_default=False)
        self.assertEqual(self.put(first, is_default=False).status_code, 422)
        self.assert_single_default(first)

    def test_generated_fields_and_partial_put_are_rejected(self):
        template = self.seed()
        for changes in ({"template_id": str(uuid7())}, {"created_at": template["created_at"]}):
            self.assertEqual(self.put(template, **changes).status_code, 422)
        response = self.client.put("/api/v1/templates/" + template["template_id"], json={"name": "Partial"}, headers=self.headers)
        self.assertEqual(response.status_code, 422)


class TemplateDeleteTests(TemplateHTTPTestCase):
    def test_requires_bearer(self):
        self.assertEqual(self.client.delete("/api/v1/templates/" + str(uuid7())).status_code, 401)

    def test_missing_template_returns_404(self):
        self.assertEqual(self.delete({"template_id": str(uuid7())}).status_code, 404)

    def test_last_template_returns_409(self):
        template = self.seed()
        self.assertEqual(self.delete(template).status_code, 409)
        self.assert_single_default(template)

    def test_referenced_template_is_rejected_for_every_document_status(self):
        template = self.seed()
        self.seed(name="Otra ficticia", is_default=False)
        for status in DocumentStatus:
            with self.subTest(status=status):
                self.add_document(template, status)
                before = [dict(row) for row in self.rows()]
                response = self.delete(template)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.json(), {"detail": "La Template está siendo utilizada por documentos."})
                self.assertEqual([dict(row) for row in self.rows()], before)

    def test_deletes_unused_nondefault(self):
        first = self.seed()
        second = self.seed(name="Segunda ficticia", is_default=False)
        response = self.delete(second)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"deleted_template_id": second["template_id"]})
        self.assertEqual(len(self.rows()), 1)
        self.assert_single_default(first)

    def test_deleting_default_chooses_oldest_remaining(self):
        first = self.seed()
        oldest = self.seed(name="Segunda ficticia", is_default=False)
        self.seed(name="Tercera ficticia", is_default=False)
        self.assertEqual(self.delete(first).status_code, 200)
        self.assertEqual(len(self.rows()), 2)
        self.assert_single_default(oldest)

    def test_document_fk_remains_a_final_guard_if_precheck_misses_reference(self):
        first = self.seed()
        self.seed(name="Segunda ficticia", is_default=False)
        self.add_document(first)
        before = [dict(row) for row in self.rows()]
        with patch.object(SQLAlchemyTemplateRepository, "count_documents_using_template", return_value=0):
            response = self.delete(first)
        self.assertEqual(response.status_code, 409)
        self.assertEqual([dict(row) for row in self.rows()], before)


class TemplateTransactionTests(TemplateHTTPTestCase):
    def test_failure_after_create_rolls_back_default_transfer_and_insert(self):
        first = self.seed()
        original = SQLAlchemyTemplateRepository.create

        def fail(repository, template):
            original(repository, template)
            raise SQLAlchemyError("private-database-fixture")

        with patch.object(SQLAlchemyTemplateRepository, "create", fail):
            response = self.create(name="Fallida ficticia")
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-database-fixture", response.text)
        self.assertEqual(len(self.rows()), 1)
        self.assert_single_default(first)

    def test_failure_after_update_rolls_back_all_changes(self):
        self.seed()
        second = self.seed(name="Segunda ficticia", is_default=False)
        before = [dict(row) for row in self.rows()]
        original = SQLAlchemyTemplateRepository.update

        def fail(repository, template):
            original(repository, template)
            if str(template.template_id) == second["template_id"]:
                raise SQLAlchemyError("private-database-fixture")

        with patch.object(SQLAlchemyTemplateRepository, "update", fail):
            self.assertEqual(self.put(second, is_default=True, name="Fallida ficticia").status_code, 503)
        self.assertEqual([dict(row) for row in self.rows()], before)

    def test_failure_after_delete_rolls_back_transfer_and_delete(self):
        first = self.seed()
        self.seed(name="Segunda ficticia", is_default=False)
        before = [dict(row) for row in self.rows()]
        original = SQLAlchemyTemplateRepository.delete

        def fail(repository, template):
            original(repository, template)
            raise SQLAlchemyError("private-database-fixture")

        with patch.object(SQLAlchemyTemplateRepository, "delete", fail):
            self.assertEqual(self.delete(first).status_code, 503)
        self.assertEqual([dict(row) for row in self.rows()], before)

    def test_database_unique_violation_returns_409_and_restores_default(self):
        first = self.seed()
        with patch.object(SQLAlchemyTemplateRepository, "get_by_name", return_value=None):
            response = self.create()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(len(self.rows()), 1)
        self.assert_single_default(first)


class TemplateAuthTests(TemplateHTTPTestCase):
    def test_inactive_admin_is_rejected_on_all_four_operations(self):
        self.connection.execute(update(AdminUserModel).where(AdminUserModel.user_id == AUTH_USER_ID).values(is_active=False))
        missing = {**create_payload(), "template_id": str(uuid7())}
        for response in (self.create(), self.listing(), self.put(missing), self.delete(missing)):
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.json(), {"detail": "Cuenta inactiva."})
        self.assertEqual(len(self.rows()), 0)

    def test_invalid_bearer_is_rejected_on_all_four_operations(self):
        self.headers = {"Authorization": "Bearer invalid-fixture"}
        missing = {**create_payload(), "template_id": str(uuid7())}
        for response in (self.create(), self.listing(), self.put(missing), self.delete(missing)):
            self.assertEqual(response.status_code, 401)
            self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
