"""Fallos seguros de la CLI; no se conecta a PostgreSQL ni usa credenciales reales."""

from contextlib import redirect_stderr, redirect_stdout
import getpass
from io import StringIO
import unittest
from unittest.mock import Mock, patch
import warnings

from app.cli.create_admin import main


class CreateAdminCLITests(unittest.TestCase):
    def test_password_argument_is_rejected_without_echoing_its_value(self):
        bootstrap = Mock()
        output = StringIO()
        with redirect_stderr(output), self.assertRaises(SystemExit) as raised:
            main(["--password", "argument-fixture-never-echo"], bootstrap=bootstrap)
        self.assertEqual(raised.exception.code, 2)
        self.assertNotIn("argument-fixture-never-echo", output.getvalue())
        bootstrap.assert_not_called()

    def test_password_mismatch_never_calls_bootstrap(self):
        bootstrap = Mock()
        with patch("builtins.input", return_value="cli-fixture"), patch(
            "app.cli.create_admin.getpass.getpass", side_effect=["test-password", "other-fixture"]
        ), redirect_stdout(StringIO()):
            self.assertEqual(main([], bootstrap=bootstrap), 1)
        bootstrap.assert_not_called()

    def test_terminal_without_hidden_input_aborts_before_reading_password(self):
        bootstrap = Mock()

        def fallback(prompt):
            warnings.warn("hidden input unavailable in fixture", getpass.GetPassWarning)
            self.fail("The CLI must abort before the fallback can read visible input")

        with patch("builtins.input", return_value="cli-fixture"), patch(
            "app.cli.create_admin.getpass.getpass", side_effect=fallback
        ), redirect_stdout(StringIO()):
            self.assertEqual(main([], bootstrap=bootstrap), 1)
        bootstrap.assert_not_called()

    def test_eof_and_interrupt_abort_safely(self):
        for error in (EOFError(), KeyboardInterrupt()):
            bootstrap = Mock()
            with patch("builtins.input", side_effect=error), redirect_stdout(StringIO()):
                self.assertEqual(main([], bootstrap=bootstrap), 1)
            bootstrap.assert_not_called()

    def test_unexpected_error_does_not_expose_internal_details(self):
        bootstrap = Mock(side_effect=RuntimeError("internal-fixture-never-echo"))
        output = StringIO()
        with patch("builtins.input", return_value="cli-fixture"), patch(
            "app.cli.create_admin.getpass.getpass", side_effect=["test-password", "test-password"]
        ), redirect_stdout(output):
            self.assertEqual(main([], bootstrap=bootstrap), 1)
        self.assertNotIn("internal-fixture-never-echo", output.getvalue())
        self.assertNotIn("test-password", output.getvalue())

    def test_fastapi_exposes_only_auth_routes_without_business_endpoints(self):
        from app.main import app

        self.assertEqual(set(app.openapi()["paths"]), {"/api/v1/auth/login", "/api/v1/auth/me"})
