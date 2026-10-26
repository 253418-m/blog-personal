"""Bases Pydantic; no se define aún un formato común de error o paginación."""

from pydantic import BaseModel, ConfigDict


class ContractPendingSchema(BaseModel):
    """Placeholder vacío; aún no valida un contrato de negocio utilizable.

    TODO(CONTRACT_PENDING): definir campos, obligatoriedad y nulabilidad antes
    de usar cualquier subclase en requests o responses. Se prohíben campos
    extra para evitar descartar información silenciosamente.
    """

    model_config = ConfigDict(extra="forbid")


class PreviewSessionSchema(ContractPendingSchema):
    """TODO(CONTRACT_PENDING): contrato de la sesión de previsualización."""
