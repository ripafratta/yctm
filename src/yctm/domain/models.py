"""Tipi di dominio per l'acquisizione delle trascrizioni."""

from enum import StrEnum


class AcquisitionStatus(StrEnum):
    """Stato di acquisizione di un video."""

    NOT_REQUESTED = "not_requested"
    STORED = "stored"
    RETRYABLE_ERROR = "retryable_error"
    TERMINAL_ERROR = "terminal_error"

    @property
    def is_terminal(self) -> bool:
        """Indica se il video non deve essere riesaminato."""
        return self in {self.STORED, self.TERMINAL_ERROR}


class YctmError(Exception):
    """Errore applicativo base."""


class RecoverableAcquisitionError(YctmError):
    """Errore che consente nuovi tentativi di estrazione."""
