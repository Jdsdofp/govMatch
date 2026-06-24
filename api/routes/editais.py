import logging
import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.schemas import (
    AlertaRequestSchema,
    AlertaResponseSchema,
    EditalListaSchema,
    EditalSchema,
    SyncResponseSchema,
    SyncResultadoSchema,
)
from database.engine import AsyncSessionLocal, get_session
from database.models import EditalStatus
from services import edital_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/editais", tags=["Editais"])

DbDep = Annotated[AsyncSession, Depends(get_session)]


# ── GET /editais/sync ────────────────────────────────────────────────────────

@router.get(
    "/sync",
    response_model=SyncResponseSchema,
    summary="Disparar crawler de editais em background",
    description=(
        "Inicia o scraper Playwright em segundo plano para buscar novas licitações "
        "no PNCP. Retorna imediatamente com um job_id para acompanhamento."
    ),
)
async def sincronizar(
    background_tasks: BackgroundTasks,
    palavras_chave: Annotated[
        str | None,
        Query(description="Termos separados por espaço. Ex: 'TI suporte rede'"),
    ] = None,
    estado: Annotated[
        str | None,
        Query(description="Sigla do estado. Ex: SP, RJ, MG"),
        Query(min_length=2, max_length=2),
    ] = None,
    max_paginas: Annotated[int, Query(ge=1, le=20)] = 5,
    fonte: Annotated[
        str | None,
        Query(description="ID da fonte: pncp, bll, bnc, licitacoes_e, tce_sp, tce_mg, tce_rs"),
    ] = None,
) -> SyncResponseSchema:
    job_id = str(uuid.uuid4())
    termos = palavras_chave.split() if palavras_chave else None

    # BackgroundTask cria sua própria sessão para não compartilhar a sessão do request
    background_tasks.add_task(
        _executar_sync,
        termos,
        estado,
        max_paginas,
        job_id,
        fonte,
    )

    return SyncResponseSchema(
        mensagem=f"Sincronização iniciada{'para ' + fonte if fonte else ' em background.'}",
        job_id=job_id,
    )


async def _executar_sync(
    palavras_chave: list[str] | None,
    estado: str | None,
    max_paginas: int,
    job_id: str,
    fonte: str | None = None,
) -> None:
    logger.info("Sync %s iniciado | palavras=%s | estado=%s | fonte=%s", job_id, palavras_chave, estado, fonte)
    if fonte:
        from services.scheduler_registry import get_scheduler
        from services.edital_service import processar_lote
        scheduler = get_scheduler()
        source = next((s for s in scheduler._sources if s.source_id == fonte), None)
        if source:
            async with AsyncSessionLocal() as db:
                try:
                    editais = await source.buscar(
                        palavras_chave=palavras_chave or None, estado=estado
                    )
                    resultado = await processar_lote(db, editais, fonte)
                    await db.commit()
                except Exception:
                    await db.rollback()
                    raise
            logger.info(
                "[sync manual] job=%s fonte=%s resultado=%s", job_id, fonte, resultado
            )
        else:
            logger.warning("[sync manual] Fonte '%s' não encontrada", fonte)
    else:
        async with AsyncSessionLocal() as db:
            try:
                resultado = await edital_service.sincronizar_editais(
                    db=db,
                    palavras_chave=palavras_chave,
                    estado=estado,
                    max_paginas=max_paginas,
                )
                await db.commit()
            except Exception:
                await db.rollback()
                raise
        logger.info(
            "Sync %s concluído | encontrados=%d | novos=%d | status=%s",
            job_id,
            resultado["total_encontrados"],
            resultado["total_novos"],
            resultado["status"],
        )


# ── GET /editais ─────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=EditalListaSchema,
    summary="Listar editais com filtros",
    description="Retorna lista paginada de editais filtrada por palavras-chave, estado, ME/EPP e modalidade.",
)
async def listar_editais(
    db: DbDep,
    q: Annotated[
        str | None,
        Query(description="Palavras-chave para busca no objeto e órgão"),
    ] = None,
    estado: Annotated[
        str | None,
        Query(description="UF. Ex: SP"),
        Query(min_length=2, max_length=2),
    ] = None,
    exclusivo_me: Annotated[
        bool | None,
        Query(description="Filtrar apenas editais exclusivos ME/EPP"),
    ] = None,
    modalidade: Annotated[
        str | None,
        Query(description="Modalidade. Ex: Pregão Eletrônico"),
    ] = None,
    status: Annotated[
        EditalStatus | None,
        Query(description="Status do edital"),
    ] = None,
    pagina: Annotated[int, Query(ge=1)] = 1,
    por_pagina: Annotated[int, Query(ge=1, le=100)] = 20,
) -> EditalListaSchema:
    editais, total = await edital_service.listar_editais(
        db=db,
        palavras_chave=q,
        estado=estado,
        exclusivo_me=exclusivo_me,
        modalidade=modalidade,
        status=status,
        pagina=pagina,
        por_pagina=por_pagina,
    )

    return EditalListaSchema(
        total=total,
        pagina=pagina,
        por_pagina=por_pagina,
        dados=[EditalSchema.model_validate(e) for e in editais],
    )


# ── GET /editais/{id} ────────────────────────────────────────────────────────

@router.get(
    "/{edital_id}",
    response_model=EditalSchema,
    summary="Detalhe de um edital",
)
async def detalhe_edital(edital_id: int, db: DbDep) -> EditalSchema:
    edital = await edital_service.buscar_edital_por_id(db, edital_id)
    if not edital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Edital {edital_id} não encontrado.",
        )
    return EditalSchema.model_validate(edital)


# ── POST /editais/{id}/alerta ─────────────────────────────────────────────────

@router.post(
    "/{edital_id}/alerta",
    response_model=AlertaResponseSchema,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar monitoramento de alerta",
    description=(
        "Ativa o monitoramento em tempo real para o edital indicado. "
        "O campo 'dispositivo_token' é opcional — quando fornecido, "
        "push notifications serão enviadas ao dispositivo."
    ),
)
async def registrar_alerta(
    edital_id: int,
    payload: AlertaRequestSchema,
    db: DbDep,
) -> AlertaResponseSchema:
    edital = await edital_service.buscar_edital_por_id(db, edital_id)
    if not edital:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Edital {edital_id} não encontrado.",
        )

    alerta = await edital_service.registrar_alerta(
        db=db,
        edital_id=edital_id,
        dispositivo_token=payload.dispositivo_token,
    )
    return AlertaResponseSchema.model_validate(alerta)


# ── DELETE /editais/{id}/alerta ───────────────────────────────────────────────

@router.delete(
    "/{edital_id}/alerta",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Desativar monitoramento de alerta",
)
async def desativar_alerta(edital_id: int, db: DbDep) -> None:
    removido = await edital_service.desativar_alerta(db, edital_id)
    if not removido:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Nenhum alerta ativo para o edital {edital_id}.",
        )
