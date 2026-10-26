"""Inicialización editorial pendiente de los valores oficiales de la plantilla.

No se insertan seeds desde migraciones ni desde el arranque de FastAPI.
La futura capa service coordinará dentro de una transacción la existencia de
al menos una Template y exactamente una default, incluyendo concurrencia.
"""

from sqlalchemy.orm import Session


BOOTSTRAP_STATUS = "BOOTSTRAP_PENDING"


def bootstrap_default_template(session: Session) -> None:
    """Punto reservado; CONTRACT_PENDING, no ejecuta consultas ni inserciones."""
    raise NotImplementedError(
        "BOOTSTRAP_PENDING: definir los valores oficiales de la Template default."
    )
