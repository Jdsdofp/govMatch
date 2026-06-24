"""Rota de status do agendador."""
from fastapi import APIRouter

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get("/status")
async def status_scheduler():
    from services.scheduler_registry import get_scheduler
    scheduler = get_scheduler()
    return {"sources": scheduler.get_status()}
