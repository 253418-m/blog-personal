"""Bootstrap interactivo; nunca acepta credenciales como argumentos."""

import argparse
from collections.abc import Callable, Sequence
import getpass
import warnings

from app.infrastructure.database.bootstrap_admin import create_first_admin
from app.services.admin_bootstrap import AdminBootstrapError, CreatedAdmin


class _ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        # argparse normalmente repetiría los argumentos desconocidos, que
        # podrían contener una contraseña proporcionada por equivocación.
        self.exit(2, "Este comando no acepta argumentos; usa la entrada interactiva.\n")


def main(
    argv: Sequence[str] | None = None,
    *,
    bootstrap: Callable[[str, str], CreatedAdmin] | None = None,
) -> int:
    parser = _ArgumentParser(description="Crear exclusivamente el primer administrador.")
    parser.parse_args(argv)
    try:
        username = input("Username: ")
        with warnings.catch_warnings():
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Password: ")
            confirmation = getpass.getpass("Confirm password: ")
        if password != confirmation:
            print("Las contraseñas no coinciden; no se creó ningún usuario.")
            return 1
        (bootstrap or create_first_admin)(username, password)
    except (EOFError, KeyboardInterrupt):
        print("Bootstrap cancelado.")
        return 1
    except getpass.GetPassWarning:
        print("No hay una terminal con entrada oculta; bootstrap cancelado.")
        return 1
    except AdminBootstrapError as error:
        print(str(error))
        return 1
    except Exception:
        # No propagar tracebacks, SQL, URLs ni detalles criptográficos a la CLI.
        print("No se pudo completar el bootstrap; revisa la configuración local.")
        return 1
    print("Administrador creado correctamente.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
