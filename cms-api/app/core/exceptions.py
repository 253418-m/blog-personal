"""Excepciones de dominio; mapeo a respuestas HTTP pendiente."""


class DomainError(Exception):
    """Base de los errores propios del dominio editorial."""


class ResourceNotFound(DomainError):
    """El recurso solicitado no existe."""


class DomainConflict(DomainError):
    """La operación entra en conflicto con el estado del dominio."""


class InvalidTransition(DomainError):
    """La transición de estado no está permitida."""


class BusinessRuleViolation(DomainError):
    """La operación incumple una regla de negocio."""
