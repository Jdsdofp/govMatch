"""Registro singleton do scheduler — evita import circular de main.py."""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from services.scheduler_service import SchedulerService

_scheduler: "SchedulerService | None" = None


def set_scheduler(s: "SchedulerService") -> None:
    global _scheduler
    _scheduler = s


def get_scheduler() -> "SchedulerService":
    if _scheduler is None:
        raise RuntimeError("Scheduler não inicializado.")
    return _scheduler
