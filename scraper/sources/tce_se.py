"""Fonte TCE-SE — tce.se.gov.br/visualizadorRelatorios (Swagger REST).

Endpoint: GET /api/Contratos/ContratosVigentes
Retorna contratos vigentes do próprio TCE-SE (179 registros), sem paginação.
Sem autenticação. Documentação: /swagger/ui/index
"""
import logging
from datetime import datetime

import httpx

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_BASE = "https://www.tce.se.gov.br/visualizadorRelatorios"
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


class TCESESource(BaseSource):
    source_id = "tce_se"
    interval_seconds = 21600  # 6 horas

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "SE":
            return []

        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=20, follow_redirects=True) as c:
                r = await c.get(f"{_BASE}/api/Contratos/ContratosVigentes")
                if r.status_code != 200:
                    logger.warning("[TCE-SE] HTTP %d", r.status_code)
                    return []
                itens = r.json()
        except Exception as exc:
            logger.error("[TCE-SE] Erro ao buscar: %s", exc)
            return []

        editais: list[EditalRaw] = []
        for item in (itens if isinstance(itens, list) else []):
            edital = _mapear(item)
            if edital is None:
                continue
            if palavras_chave:
                texto = f"{edital.objeto} {edital.orgao}".lower()
                if not all(p.lower() in texto for p in palavras_chave):
                    continue
            editais.append(edital)

        logger.info("[TCE-SE] %d contratos encontrados", len(editais))
        return editais

    async def testar_conexao(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as c:
                r = await c.get(f"{_BASE}/api/Contratos/ContratosVigentes")
                return r.status_code == 200
        except Exception:
            return False


def _mapear(item: dict) -> EditalRaw | None:
    try:
        id_c = str(item.get("IdContrato") or "").strip()
        if not id_c:
            return None
        nr = str(item.get("NrProcesso") or "").strip()
        ano = str(item.get("AnoProcesso") or "").strip()
        numero_controle = f"tce_se:{id_c}:{ano}:{nr}"
        orgao = "TCE-SE"
        objeto = (item.get("Objeto") or "").strip()
        modalidade = (item.get("TipoProcesso") or "").strip()
        valor = _parse_float(item.get("ValorGlobal"))
        data_ini = _parse_data(item.get("DataInicio"))
        data_fim = _parse_data(item.get("DataFim"))
        fornecedor = (item.get("Fornecedor") or "").strip()
        return EditalRaw(
            numero_controle=numero_controle,
            orgao=orgao,
            objeto=f"{objeto} — {fornecedor}" if fornecedor else objeto,
            modalidade=modalidade,
            valor_estimado=valor,
            data_abertura=data_ini,
            data_encerramento=data_fim,
            link_edital=None,
            exclusivo_me=False,
            estado="SE",
            fonte="tce_se",
        )
    except Exception as exc:
        logger.debug("[TCE-SE] Erro ao mapear: %s", exc)
        return None


def _parse_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_data(raw) -> datetime | None:
    if not raw:
        return None
    raw = str(raw).strip()[:10]
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None
