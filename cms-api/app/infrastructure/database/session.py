"""Engine síncrono y sesiones; las transacciones pertenecen al caso de uso.

Importar este módulo exige DATABASE_URL pero no abre conexiones ni crea tablas.
Para una futura operación atómica puede usarse `with SessionLocal.begin() as
session:`. La dependency solo cierra la sesión: nunca confirma implícitamente.
"""

from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_database_url


database_url = make_url(get_database_url())
if database_url.drivername != "postgresql+psycopg":
    raise ValueError("DATABASE_URL debe usar el driver postgresql+psycopg.")

engine = create_engine(database_url, pool_pre_ping=True, hide_parameters=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_session() -> Iterator[Session]:
    """Cede una Session y la cierra al terminar, incluso ante excepciones."""
    with SessionLocal() as session:
        yield session
