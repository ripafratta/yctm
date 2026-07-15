"""Caso d'uso: reset dei video in uno stato di errore."""

import logging
from typing import Literal

from sqlalchemy.orm import Session

from yctm.domain.models import AcquisitionStatus
from yctm.infrastructure.database.repositories import VideoRepository

logger = logging.getLogger(__name__)

ResetTarget = Literal["retryable", "terminal", "all"]

_TARGET_MAP: dict[ResetTarget, tuple[str, ...]] = {
    "retryable": (AcquisitionStatus.RETRYABLE_ERROR,),
    "terminal": (AcquisitionStatus.TERMINAL_ERROR,),
    "all": (AcquisitionStatus.RETRYABLE_ERROR, AcquisitionStatus.TERMINAL_ERROR),
}


def reset_videos(session: Session, target: ResetTarget) -> str:
    """Reimposta a pending i video nello stato indicato."""
    repo = VideoRepository(session)
    statuses = _TARGET_MAP[target]

    total = 0
    for status in statuses:
        count = repo.reset_to_pending(status)
        total += count
        if count:
            logger.info("Reset %d video dallo stato '%s' a 'pending'.", count, status)

    session.commit()

    if total == 0:
        return f"Nessun video in stato '{target}' da resettare."

    return f"Resettati {total} video a 'pending'."
