"""
Camada de serviço — orquestra scraper, OCR e persistência no banco.
"""

import logging
from datetime import datetime

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import AlertaMonitoramento, Edital, EditalStatus, SyncLog
from scraper.browser import EditalRaw, GovMatchScraper
from scraper.sources.base import EditalRaw as SourceEditalRaw
from scraper.ocr_processor import processar_pdf

logger = logging.getLogger(__name__)


# ── sync de editais ──────────────────────────────────────────────────────────

async def sincronizar_editais(
    db: AsyncSession,
    palavras_chave: list[str] | None = None,
    estado: str | None = None,
    max_paginas: int = 5,
) -> dict:
    """
    Dispara o scraper, processa PDFs e persiste editais novos no banco.
    Retorna um resumo da operação para o SyncLog.
    """
    log = SyncLog(iniciado_em=datetime.utcnow())
    db.add(log)
    await db.flush()

    try:
        async with GovMatchScraper(headless=True) as scraper:
            editais_raw = await scraper.buscar_editais(
                palavras_chave=palavras_chave,
                estado=estado,
                max_paginas=max_paginas,
            )

        log.total_encontrados = len(editais_raw)
        novos = 0

        for raw in editais_raw:
            novo = await _persistir_edital(db, raw)
            if novo:
                novos += 1

        log.total_novos = novos
        log.status = "concluido"

    except Exception as exc:
        log.erro = str(exc)
        log.status = "erro"
        logger.error("Erro no sync: %s", exc)

    finally:
        log.finalizado_em = datetime.utcnow()
        await db.flush()

    return {
        "total_encontrados": log.total_encontrados,
        "total_novos": log.total_novos,
        "status": log.status,
        "erro": log.erro,
    }


async def _persistir_edital(db: AsyncSession, raw: EditalRaw) -> bool:
    """Insere o edital se ainda não existir. Retorna True se foi inserido."""
    existente = await db.scalar(
        select(Edital).where(Edital.numero_controle == raw.numero_controle)
    )
    if existente:
        return False

    texto_pdf: str | None = None
    if raw.link_pdf:
        try:
            async with GovMatchScraper(headless=True) as scraper:
                caminho = await scraper.baixar_pdf(
                    raw.link_pdf,
                    f"{raw.numero_controle.replace('/', '_')}.pdf",
                )
            if caminho:
                extraido = await processar_pdf(caminho)
                texto_pdf = extraido.texto_completo
                # Enriquece com dados do OCR quando o scraper não encontrou
                if raw.valor_estimado is None and extraido.valor_estimado:
                    raw.valor_estimado = extraido.valor_estimado
                if not raw.exclusivo_me and extraido.exclusivo_me:
                    raw.exclusivo_me = True
        except Exception as exc:
            logger.warning("Falha ao processar PDF para %s: %s", raw.numero_controle, exc)

    edital = Edital(
        numero_controle=raw.numero_controle,
        orgao=raw.orgao,
        uasg=raw.uasg,
        objeto=raw.objeto,
        modalidade=raw.modalidade,
        valor_estimado=raw.valor_estimado,
        data_abertura=raw.data_abertura,
        data_encerramento=raw.data_encerramento,
        link_edital=raw.link_edital,
        link_pdf=raw.link_pdf,
        exclusivo_me=raw.exclusivo_me,
        estado=raw.estado,
        municipio=raw.municipio,
        texto_extraido=texto_pdf,
        status=EditalStatus.PUBLICADO,
    )
    db.add(edital)
    return True


async def processar_lote(
    db: AsyncSession,
    editais_raw: list[SourceEditalRaw],
    fonte: str,
) -> dict:
    """
    Persiste lote de editais de qualquer fonte. Deduplicação por numero_controle.
    Retorna resumo: { total_recebidos, novos, duplicados, erros }.
    """
    log = SyncLog(iniciado_em=datetime.utcnow(), fonte=fonte)
    db.add(log)
    await db.flush()

    log.total_encontrados = len(editais_raw)
    novos = 0
    erros = 0

    for raw in editais_raw:
        try:
            inserido = await _persistir_edital_fonte(db, raw)
            if inserido:
                novos += 1
        except Exception as exc:
            erros += 1
            logger.warning("[%s] Falha ao persistir %s: %s", fonte, raw.numero_controle, exc)

    log.total_novos = novos
    log.status = "concluido"
    log.finalizado_em = datetime.utcnow()
    await db.flush()

    return {
        "fonte": fonte,
        "total_recebidos": len(editais_raw),
        "novos": novos,
        "duplicados": len(editais_raw) - novos - erros,
        "erros": erros,
    }


async def _persistir_edital_fonte(db: AsyncSession, raw: SourceEditalRaw) -> bool:
    """Insere edital de qualquer fonte. Retorna True se inserido."""
    existente = await db.scalar(
        select(Edital).where(Edital.numero_controle == raw.numero_controle)
    )
    if existente:
        return False

    texto_pdf: str | None = None
    if raw.link_pdf:
        try:
            async with GovMatchScraper(headless=True) as scraper:
                caminho = await scraper.baixar_pdf(
                    raw.link_pdf,
                    f"{raw.numero_controle.replace('/', '_').replace(':', '_')}.pdf",
                )
            if caminho:
                extraido = await processar_pdf(caminho)
                texto_pdf = extraido.texto_completo
                if raw.valor_estimado is None and extraido.valor_estimado:
                    raw.valor_estimado = extraido.valor_estimado
                if not raw.exclusivo_me and extraido.exclusivo_me:
                    raw.exclusivo_me = True
        except Exception as exc:
            logger.warning("Falha ao processar PDF %s: %s", raw.numero_controle, exc)

    edital = Edital(
        numero_controle=raw.numero_controle,
        orgao=raw.orgao,
        uasg=raw.uasg,
        objeto=raw.objeto,
        modalidade=raw.modalidade,
        valor_estimado=raw.valor_estimado,
        data_abertura=raw.data_abertura,
        data_encerramento=raw.data_encerramento,
        link_edital=raw.link_edital,
        link_pdf=raw.link_pdf,
        exclusivo_me=raw.exclusivo_me,
        estado=raw.estado,
        municipio=raw.municipio,
        texto_extraido=texto_pdf,
        status=EditalStatus.PUBLICADO,
        fonte=raw.fonte,
    )
    db.add(edital)
    return True


# ── consultas ────────────────────────────────────────────────────────────────

async def listar_editais(
    db: AsyncSession,
    palavras_chave: str | None = None,
    estado: str | None = None,
    exclusivo_me: bool | None = None,
    modalidade: str | None = None,
    status: EditalStatus | None = None,
    pagina: int = 1,
    por_pagina: int = 20,
) -> tuple[list[Edital], int]:
    """Retorna (lista_de_editais, total) respeitando os filtros informados."""
    stmt = select(Edital)

    if palavras_chave:
        termos = palavras_chave.split()
        condicoes = [
            or_(
                Edital.objeto.ilike(f"%{t}%"),
                Edital.orgao.ilike(f"%{t}%"),
                Edital.texto_extraido.ilike(f"%{t}%"),
            )
            for t in termos
        ]
        for c in condicoes:
            stmt = stmt.where(c)

    if estado:
        stmt = stmt.where(Edital.estado == estado.upper())

    if exclusivo_me is not None:
        stmt = stmt.where(Edital.exclusivo_me == exclusivo_me)

    if modalidade:
        stmt = stmt.where(Edital.modalidade.ilike(f"%{modalidade}%"))

    if status:
        stmt = stmt.where(Edital.status == status)

    # Total para paginação
    from sqlalchemy import func
    total_stmt = select(func.count()).select_from(stmt.subquery())
    total: int = await db.scalar(total_stmt) or 0

    stmt = (
        stmt.order_by(Edital.data_abertura.desc().nullslast(), Edital.criado_em.desc())
        .offset((pagina - 1) * por_pagina)
        .limit(por_pagina)
    )

    resultado = await db.scalars(stmt)
    return list(resultado.all()), total


async def buscar_edital_por_id(db: AsyncSession, edital_id: int) -> Edital | None:
    return await db.get(Edital, edital_id)


# ── alertas ──────────────────────────────────────────────────────────────────

async def registrar_alerta(
    db: AsyncSession,
    edital_id: int,
    dispositivo_token: str | None = None,
) -> AlertaMonitoramento:
    alerta = AlertaMonitoramento(
        edital_id=edital_id,
        dispositivo_token=dispositivo_token,
        ativo=True,
    )
    db.add(alerta)
    await db.flush()
    return alerta


async def listar_alertas_ativos(db: AsyncSession) -> list[AlertaMonitoramento]:
    resultado = await db.scalars(
        select(AlertaMonitoramento).where(AlertaMonitoramento.ativo == True)
    )
    return list(resultado.all())


async def desativar_alerta(db: AsyncSession, edital_id: int) -> bool:
    resultado = await db.scalars(
        select(AlertaMonitoramento).where(
            AlertaMonitoramento.edital_id == edital_id,
            AlertaMonitoramento.ativo == True,
        )
    )
    alertas = list(resultado.all())
    if not alertas:
        return False
    for a in alertas:
        a.ativo = False
    return True
