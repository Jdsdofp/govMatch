"""Rota de status do agendador."""
from fastapi import APIRouter

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])


@router.get("/status")
async def status_scheduler():
    from main import scheduler
    return {"sources": scheduler.get_status()}
