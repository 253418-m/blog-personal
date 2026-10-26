"""Documents y lifecycle reales sobre pg_temp; no se usan cuentas ni contenido reales."""

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import UUID

from sqlalchemy import select, text, update
from sqlalchemy.exc import SQLAlchemyError
from uuid6 import uuid7

from app.api.v1.endpoints.documents import get_document_service
from app.infrastructure.database.document_repository import SQLAlchemyDocumentRepository
from app.infrastructure.database.models import AdminUserModel, DocumentModel, TemplateModel
from app.main import app
from app.services.document_service import DocumentService
from app.services.quarto_export import FileSystemQuartoExporter
from app.services.quarto_render import QuartoRenderResult, QuartoRenderService
from tests.auth_support import AUTH_USER_ID
from tests.test_templates import TemplateHTTPTestCase


class _FixtureQuartoRenderer:
    def render_site(self, *, staging_dir: Path, expected_slug: str) -> QuartoRenderResult:
        destination = staging_dir / "posts" / expected_slug
        destination.mkdir(parents=True)
        (staging_dir / "index.html").write_text("Sitio temporal", encoding="utf-8")
        (destination / "index.html").write_text("Post temporal", encoding="utf-8")
        return QuartoRenderResult(True, 0, 1)


class DocumentHTTPTestCase(TemplateHTTPTestCase):
    def setUp(self):
        super().setUp()
        name = self.connection.scalar(text(
            "SELECT conname FROM pg_constraint WHERE conrelid='pg_temp.documents'::regclass AND contype='u'"
        ))
        quoted = self.connection.dialect.identifier_preparer.quote(name)
        self.connection.execute(text(f"ALTER TABLE pg_temp.documents RENAME CONSTRAINT {quoted} TO uq_documents_slug"))
        self.quarto_directory = TemporaryDirectory()
        self.addCleanup(self.quarto_directory.cleanup)
        self.quarto_root = Path(self.quarto_directory.name)
        (self.quarto_root / "posts").mkdir()
        (self.quarto_root / "_quarto.yml").write_text(
            "project:\n  type: website\n  output-dir: docs\n", encoding="utf-8"
        )
        self.quarto_exporter = FileSystemQuartoExporter(self.quarto_root)
        self.quarto_render_service = QuartoRenderService(self.quarto_root, _FixtureQuartoRenderer())
        app.dependency_overrides[get_document_service] = lambda: DocumentService(
            self.session_factory, self.quarto_exporter, self.quarto_render_service
        )
        self.post_template = self.seed(allow_published_edit=True, metadata_contract=[
            {"field_key": "category", "expected_type": "STRING", "is_required": True},
            {"field_key": "reading_time", "expected_type": "INTEGER", "is_required": False},
            {"field_key": "enabled", "expected_type": "BOOLEAN", "is_required": False},
            {"field_key": "date", "expected_type": "DATE", "is_required": False},
        ])
        landing_contract = [{"field_key": "title", "expected_type": "STRING", "is_required": True}]
        self.landing_template = self.seed(
            name="Landing editable ficticia", target_type="LANDING", is_default=False,
            allow_published_edit=True, metadata_contract=landing_contract,
        )
        self.fixed_landing_template = self.seed(
            name="Landing fija ficticia", target_type="LANDING", is_default=False,
            allow_published_edit=False, metadata_contract=landing_contract,
        )

    def payload(self, **changes):
        body = {
            "title": "Post ficticio", "slug": "post-ficticio", "content_type": "POST",
            "template_id": self.post_template["template_id"],
            "metadata_values": {"category": "Pruebas", "reading_time": 5},
            "content": "# Markdown ficticio\n\nContenido sin renderizar.",
        }
        body.update(changes)
        return body

    def create_document(self, **changes):
        return self.client.post("/api/v1/documents", json=self.payload(**changes), headers=self.headers)

    def seed_document(self, **changes):
        response = self.create_document(**changes)
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()

    def seed_landing(self, *, editable=True, **changes):
        values = dict(content_type="LANDING", slug="landing-ficticia",
                      template_id=(self.landing_template if editable else self.fixed_landing_template)["template_id"],
                      metadata_values={"title": "Landing ficticia"})
        values.update(changes)
        return self.seed_document(**values)

    def put_document(self, document, **changes):
        body = {key: document[key] for key in ("title", "slug", "template_id", "metadata_values", "content")}
        body.update(changes)
        return self.client.put("/api/v1/documents/" + document["document_id"], json=body, headers=self.headers)

    def fetch(self, document):
        return self.client.get("/api/v1/documents/" + document["document_id"], headers=self.headers)

    def list_documents(self, **filters):
        return self.client.get("/api/v1/documents", params=filters, headers=self.headers)

    def publish(self, document):
        return self.client.post("/api/v1/documents/" + document["document_id"] + "/publish", headers=self.headers)

    def archive(self, document):
        return self.client.post("/api/v1/documents/" + document["document_id"] + "/archive", headers=self.headers)

    def remove_document(self, document):
        return self.client.delete("/api/v1/documents/" + document["document_id"], headers=self.headers)

    def document_rows(self):
        return [dict(row) for row in self.connection.execute(
            select(DocumentModel.__table__).order_by(DocumentModel.document_id)
        ).mappings()]


class DocumentCreateTests(DocumentHTTPTestCase):
    def test_requires_jwt(self):
        self.assertEqual(self.client.post("/api/v1/documents", json=self.payload()).status_code, 401)

    def test_post_is_created_as_draft_with_exact_public_fields(self):
        document = self.seed_document()
        self.assertEqual(document["status"], "BORRADOR")
        self.assertEqual(document["content_type"], "POST")
        self.assertEqual(set(document), set(self.payload()) | {"document_id", "status", "created_at", "updated_at", "published_at"})

    def test_landing_is_created_as_draft(self):
        document = self.seed_landing()
        self.assertEqual((document["content_type"], document["status"]), ("LANDING", "BORRADOR"))

    def test_uuid7_and_utc_timestamps_and_null_publication(self):
        before = datetime.now(timezone.utc)
        document = self.seed_document()
        self.assertEqual(UUID(document["document_id"]).version, 7)
        for field in ("created_at", "updated_at"):
            timestamp = datetime.fromisoformat(document[field])
            self.assertEqual(timestamp.utcoffset(), timedelta(0))
            self.assertTrue(before <= timestamp <= datetime.now(timezone.utc))
        self.assertIsNone(document["published_at"])

    def test_duplicate_slug_returns_409(self):
        self.seed_document()
        self.assertEqual(self.create_document().status_code, 409)
        self.assertEqual(len(self.document_rows()), 1)

    def test_invalid_slug_returns_422(self):
        for slug in ("", "Uppercase", "has space", "-start", "end-", "two--hyphens", "slash/path", "áccent"):
            self.assertEqual(self.create_document(slug=slug).status_code, 422)

    def test_missing_template_returns_404(self):
        self.assertEqual(self.create_document(template_id=str(uuid7())).status_code, 404)

    def test_post_with_landing_template_returns_422(self):
        self.assertEqual(self.create_document(template_id=self.landing_template["template_id"]).status_code, 422)

    def test_landing_with_post_template_returns_422(self):
        self.assertEqual(self.create_document(content_type="LANDING").status_code, 422)

    def test_optional_metadata_correct_types_are_preserved(self):
        values = {"category": "Pruebas", "reading_time": 8, "enabled": False, "date": "2024-02-29"}
        self.assertEqual(self.seed_document(metadata_values=values)["metadata_values"], values)

    def test_wrong_metadata_types_return_422(self):
        for values in ({"category": 7}, {"reading_time": True}, {"reading_time": 3.0}, {"enabled": 1}, {"date": "2025-02-29"}):
            self.assertEqual(self.create_document(metadata_values=values).status_code, 422)

    def test_unknown_metadata_returns_422(self):
        self.assertEqual(self.create_document(metadata_values={"unknown": "value"}).status_code, 422)

    def test_draft_allows_missing_required_metadata_and_empty_content(self):
        document = self.seed_document(metadata_values={}, content="")
        self.assertEqual(document["metadata_values"], {})
        self.assertEqual(document["content"], "")

    def test_system_fields_unknown_fields_and_invalid_schema_are_rejected(self):
        for values in (
            {"status": "PUBLICADO"}, {"document_id": str(uuid7())}, {"created_at": "2026-01-01T00:00:00Z"},
            {"updated_at": "2026-01-01T00:00:00Z"}, {"published_at": None}, {"extra": 1},
            {"title": "   "}, {"content": None}, {"metadata_values": []}, {"content_type": "DEV_BLOG"},
        ):
            self.assertEqual(self.create_document(**values).status_code, 422)

    def test_markdown_and_quarto_text_round_trips_without_interpretation(self):
        content = '---\ntitle: "Ficticio"\n---\n\n```python\nprint("no ejecutar")\n```\n<script>fixture</script>'
        document = self.seed_document(content=content)
        self.assertEqual(self.fetch(document).json()["content"], content)


class DocumentListGetTests(DocumentHTTPTestCase):
    def test_list_and_get_require_jwt(self):
        for path in ("/api/v1/documents", "/api/v1/documents/" + str(uuid7())):
            self.assertEqual(self.client.get(path).status_code, 401)

    def test_empty_list(self):
        self.assertEqual(self.list_documents().json(), {"items": []})

    def test_lists_all_and_gets_complete_document(self):
        post = self.seed_document()
        landing = self.seed_landing()
        self.assertEqual(self.list_documents().json(), {"items": [post, landing]})
        self.assertEqual(self.fetch(post).json(), post)

    def test_filters_post_and_landing(self):
        post = self.seed_document()
        landing = self.seed_landing()
        self.assertEqual(self.list_documents(content_type="POST").json(), {"items": [post]})
        self.assertEqual(self.list_documents(content_type="LANDING").json(), {"items": [landing]})

    def test_filters_draft_published_archived_and_combined(self):
        draft = self.seed_document(slug="draft-fixture")
        published = self.publish(self.seed_document(slug="published-fixture")).json()
        archived = self.archive(self.publish(self.seed_landing()).json()).json()
        for state, document in (("BORRADOR", draft), ("PUBLICADO", published), ("ARCHIVADO", archived)):
            self.assertEqual(self.list_documents(status=state).json(), {"items": [document]})
        self.assertEqual(self.list_documents(content_type="POST", status="PUBLICADO").json(), {"items": [published]})

    def test_stable_created_at_and_id_order(self):
        first = self.seed_document()
        second = self.seed_document(slug="second-fixture")
        early = datetime(2020, 1, 1, tzinfo=timezone.utc)
        self.connection.execute(update(DocumentModel).where(DocumentModel.document_id == UUID(second["document_id"])).values(created_at=early))
        self.assertEqual(self.list_documents().json()["items"][0]["document_id"], second["document_id"])
        self.connection.execute(update(DocumentModel).values(created_at=early))
        self.assertEqual([d["document_id"] for d in self.list_documents().json()["items"]], sorted([first["document_id"], second["document_id"]]))

    def test_missing_document_returns_404(self):
        self.assertEqual(self.fetch({"document_id": str(uuid7())}).status_code, 404)

    def test_invalid_filters_and_legacy_review_status_are_rejected(self):
        for filters in ({"status": "EN_REVISION"}, {"status": "OTHER"}, {"content_type": "DEV_BLOG"}):
            self.assertEqual(self.list_documents(**filters).status_code, 422)


class DocumentUpdateTests(DocumentHTTPTestCase):
    def test_updates_all_editable_fields_and_preserves_identity_and_creation(self):
        document = self.seed_document()
        response = self.put_document(document, title="Título nuevo", slug="new-slug", metadata_values={}, content="")
        self.assertEqual(response.status_code, 200)
        updated = response.json()
        self.assertEqual((updated["title"], updated["slug"], updated["metadata_values"], updated["content"]), ("Título nuevo", "new-slug", {}, ""))
        for field in ("document_id", "content_type", "status", "created_at", "published_at"):
            self.assertEqual(updated[field], document[field])
        self.assertGreater(datetime.fromisoformat(updated["updated_at"]), datetime.fromisoformat(document["updated_at"]))

    def test_switches_template_of_same_type(self):
        document = self.seed_document()
        second = self.seed(name="Otra POST ficticia", is_default=False)
        response = self.put_document(document, template_id=second["template_id"], metadata_values={"category": "Pruebas"})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["template_id"], second["template_id"])

    def test_switch_to_incompatible_template_returns_422(self):
        self.assertEqual(self.put_document(self.seed_document(), template_id=self.landing_template["template_id"]).status_code, 422)

    def test_missing_template_returns_404(self):
        self.assertEqual(self.put_document(self.seed_document(), template_id=str(uuid7())).status_code, 404)

    def test_duplicate_slug_returns_409(self):
        first = self.seed_document()
        second = self.seed_document(slug="second-fixture")
        self.assertEqual(self.put_document(second, slug=first["slug"]).status_code, 409)

    def test_content_type_status_and_system_fields_are_forbidden(self):
        document = self.seed_document()
        for fields in ({"content_type": "LANDING"}, {"status": "PUBLICADO"}, {"created_at": document["created_at"]},
                       {"published_at": None}, {"updated_at": document["updated_at"]}, {"document_id": document["document_id"]}):
            self.assertEqual(self.put_document(document, **fields).status_code, 422)

    def test_invalid_metadata_is_rejected_without_changes(self):
        document = self.seed_document()
        before = self.document_rows()
        for metadata in ({"reading_time": True}, {"unknown": "value"}):
            self.assertEqual(self.put_document(document, metadata_values=metadata).status_code, 422)
        self.assertEqual(self.document_rows(), before)

    def test_missing_document_returns_404(self):
        missing = {**self.payload(), "document_id": str(uuid7())}
        self.assertEqual(self.put_document(missing).status_code, 404)


class DocumentPublishTests(DocumentHTTPTestCase):
    def test_publishes_draft_and_sets_both_timestamps(self):
        document = self.seed_document()
        before = datetime.now(timezone.utc)
        response = self.publish(document)
        self.assertEqual(response.status_code, 200)
        published = response.json()
        self.assertEqual(published["status"], "PUBLICADO")
        self.assertEqual(published["updated_at"], published["published_at"])
        self.assertTrue(before <= datetime.fromisoformat(published["published_at"]) <= datetime.now(timezone.utc))
        self.assertEqual(published["created_at"], document["created_at"])

    def test_missing_required_metadata_returns_422_without_changes(self):
        document = self.seed_document(metadata_values={})
        self.assertEqual(self.publish(document).status_code, 422)
        self.assertEqual(self.fetch(document).json(), document)

    def test_empty_or_whitespace_content_returns_422(self):
        for i, content in enumerate(("", " \n\t")):
            document = self.seed_document(slug=f"empty-{i}", content=content)
            self.assertEqual(self.publish(document).status_code, 422)

    def test_republishing_returns_409(self):
        document = self.seed_document()
        published = self.publish(document).json()
        self.assertEqual(self.publish(document).status_code, 409)
        self.assertEqual(self.fetch(document).json(), published)

    def test_publish_archived_returns_409(self):
        document = self.seed_document()
        self.publish(document)
        self.archive(document)
        self.assertEqual(self.publish(document).status_code, 409)

    def test_revalidates_changed_template_contract(self):
        document = self.seed_document()
        self.connection.execute(update(TemplateModel).where(TemplateModel.template_id == UUID(document["template_id"])).values(
            metadata_contract=[{"field_key": "category", "expected_type": "INTEGER", "is_required": True},
                               {"field_key": "reading_time", "expected_type": "INTEGER", "is_required": False}]))
        self.assertEqual(self.publish(document).status_code, 422)
        self.assertEqual(self.fetch(document).json(), document)

    def test_missing_document_returns_404(self):
        self.assertEqual(self.publish({"document_id": str(uuid7())}).status_code, 404)


class DocumentPublishedEditingTests(DocumentHTTPTestCase):
    def test_post_is_immutable_even_when_template_allows_published_edit(self):
        document = self.seed_document()
        published = self.publish(document).json()
        before = self.document_rows()
        response = self.put_document(document, title="No cambiar", slug="no-cambiar", metadata_values={}, content="No cambiar")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.document_rows(), before)
        self.assertEqual(self.fetch(document).json(), published)

    def test_post_cannot_switch_templates_after_publication(self):
        document = self.seed_document()
        self.publish(document)
        other = self.seed(name="Otra POST ficticia", is_default=False)
        self.assertEqual(self.put_document(document, template_id=other["template_id"]).status_code, 409)

    def test_landing_can_be_published_and_edited_when_allowed(self):
        document = self.seed_landing()
        published = self.publish(document).json()
        response = self.put_document(document, title="Landing editada", content="# Nuevo texto")
        self.assertEqual(response.status_code, 200)
        edited = response.json()
        self.assertEqual(edited["status"], "PUBLICADO")
        self.assertEqual(edited["published_at"], published["published_at"])
        self.assertEqual(edited["content"], "# Nuevo texto")
        self.assertGreater(datetime.fromisoformat(edited["updated_at"]), datetime.fromisoformat(published["updated_at"]))

    def test_landing_with_readonly_template_cannot_be_edited_or_bypass_with_other_template(self):
        document = self.seed_landing(editable=False)
        self.publish(document)
        before = self.document_rows()
        self.assertEqual(self.put_document(document, title="No cambiar").status_code, 409)
        self.assertEqual(self.put_document(document, template_id=self.landing_template["template_id"]).status_code, 409)
        self.assertEqual(self.document_rows(), before)

    def test_published_landing_keeps_publication_validation(self):
        document = self.seed_landing()
        self.publish(document)
        for changes in ({"content": " "}, {"metadata_values": {}}):
            self.assertEqual(self.put_document(document, **changes).status_code, 422)

    def test_archived_post_and_landing_are_not_editable(self):
        for document in (self.seed_document(), self.seed_landing()):
            self.publish(document)
            archived = self.archive(document).json()
            self.assertEqual(self.put_document(document, title="No cambiar").status_code, 409)
            self.assertEqual(self.fetch(document).json(), archived)


class DocumentArchiveTests(DocumentHTTPTestCase):
    def test_archives_post_and_preserves_publication_date(self):
        document = self.seed_document()
        published = self.publish(document).json()
        response = self.archive(document)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], "ARCHIVADO")
        self.assertEqual(response.json()["published_at"], published["published_at"])
        self.assertGreater(datetime.fromisoformat(response.json()["updated_at"]), datetime.fromisoformat(published["updated_at"]))

    def test_archives_published_landing(self):
        document = self.seed_landing()
        self.publish(document)
        self.assertEqual(self.archive(document).json()["status"], "ARCHIVADO")

    def test_draft_cannot_be_archived(self):
        document = self.seed_document()
        self.assertEqual(self.archive(document).status_code, 409)
        self.assertEqual(self.fetch(document).json(), document)

    def test_archived_is_terminal(self):
        document = self.seed_document()
        self.publish(document)
        archived = self.archive(document).json()
        self.assertEqual(self.archive(document).status_code, 409)
        self.assertEqual(self.publish(document).status_code, 409)
        self.assertEqual(self.fetch(document).json(), archived)

    def test_missing_document_returns_404(self):
        self.assertEqual(self.archive({"document_id": str(uuid7())}).status_code, 404)


class DocumentDeleteTests(DocumentHTTPTestCase):
    def test_deletes_draft_with_204_and_no_body(self):
        document = self.seed_document()
        response = self.remove_document(document)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(response.content, b"")
        self.assertEqual(self.fetch(document).status_code, 404)

    def test_published_post_and_landing_cannot_be_deleted(self):
        for document in (self.seed_document(), self.seed_landing()):
            self.publish(document)
            self.assertEqual(self.remove_document(document).status_code, 409)

    def test_archived_post_and_landing_cannot_be_deleted(self):
        for document in (self.seed_document(), self.seed_landing()):
            self.publish(document)
            self.archive(document)
            self.assertEqual(self.remove_document(document).status_code, 409)

    def test_missing_document_returns_404(self):
        self.assertEqual(self.remove_document({"document_id": str(uuid7())}).status_code, 404)

    def test_template_deletion_remains_blocked_until_draft_is_deleted(self):
        document = self.seed_document()
        self.assertEqual(self.delete(self.post_template).status_code, 409)
        self.assertEqual(self.remove_document(document).status_code, 204)
        self.assertEqual(self.delete(self.post_template).status_code, 200)


class DocumentAuthorizationTests(DocumentHTTPTestCase):
    def requests_for_all_routes(self):
        fake = {**self.payload(), "document_id": str(uuid7())}
        return (self.create_document(), self.list_documents(), self.fetch(fake), self.put_document(fake),
                self.publish(fake), self.archive(fake), self.remove_document(fake))

    def test_missing_and_invalid_tokens_are_rejected_on_all_seven_routes(self):
        for headers in ({}, {"Authorization": "Bearer invalid-fixture"}):
            self.headers = headers
            for response in self.requests_for_all_routes():
                self.assertEqual(response.status_code, 401)
                self.assertEqual(response.headers["WWW-Authenticate"], "Bearer")
        self.assertEqual(self.document_rows(), [])

    def test_inactive_admin_is_rejected_on_all_seven_routes(self):
        self.connection.execute(update(AdminUserModel).where(AdminUserModel.user_id == AUTH_USER_ID).values(is_active=False))
        for response in self.requests_for_all_routes():
            self.assertEqual(response.status_code, 403)
        self.assertEqual(self.document_rows(), [])


class DocumentTransactionTests(DocumentHTTPTestCase):
    def test_unique_constraint_is_final_slug_guard(self):
        document = self.seed_document()
        with patch.object(SQLAlchemyDocumentRepository, "get_by_slug", return_value=None):
            response = self.create_document()
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.fetch(document).json(), document)
        self.assertEqual(len(self.document_rows()), 1)

    def test_create_failure_rolls_back_insert(self):
        original = SQLAlchemyDocumentRepository.create

        def fail(repository, document):
            original(repository, document)
            raise SQLAlchemyError("private-fixture-detail")

        with patch.object(SQLAlchemyDocumentRepository, "create", fail):
            response = self.create_document()
        self.assertEqual(response.status_code, 503)
        self.assertNotIn("private-fixture-detail", response.text)
        self.assertEqual(self.document_rows(), [])

    def test_update_publish_archive_failures_roll_back_all_changes(self):
        document = self.seed_document()
        original = SQLAlchemyDocumentRepository.update

        def fail(repository, row):
            original(repository, row)
            raise SQLAlchemyError("private-fixture-detail")

        for operation in (lambda: self.put_document(document, title="No persistir"), lambda: self.publish(document)):
            before = self.document_rows()
            with patch.object(SQLAlchemyDocumentRepository, "update", fail):
                self.assertEqual(operation().status_code, 503)
            self.assertEqual(self.document_rows(), before)
        self.publish(document)
        before = self.document_rows()
        with patch.object(SQLAlchemyDocumentRepository, "update", fail):
            self.assertEqual(self.archive(document).status_code, 503)
        self.assertEqual(self.document_rows(), before)

    def test_delete_failure_rolls_back(self):
        document = self.seed_document()
        before = self.document_rows()
        original = SQLAlchemyDocumentRepository.delete

        def fail(repository, row):
            original(repository, row)
            raise SQLAlchemyError("private-fixture-detail")

        with patch.object(SQLAlchemyDocumentRepository, "delete", fail):
            self.assertEqual(self.remove_document(document).status_code, 503)
        self.assertEqual(self.document_rows(), before)
