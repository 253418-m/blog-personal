"""Entrada explícita al bootstrap; importar el módulo nunca crea cuentas."""

from app.services.admin_bootstrap import AdminBootstrapService, CreatedAdmin


ADMIN_BOOTSTRAP_STATUS = "READY_FOR_MANUAL_EXECUTION"


def create_first_admin(username: str, password: str) -> CreatedAdmin:
    # La Session existente se importa solo al ejecutar explícitamente la operación.
    from app.infrastructure.database.session import SessionLocal

    return AdminBootstrapService(SessionLocal).create_first_admin(username, password)
