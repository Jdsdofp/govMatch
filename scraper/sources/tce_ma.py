"""Fonte TCE-MA — app.tcema.tc.br (API REST pública, OpenAPI 3.0).

Endpoint: GET /tce/api/sinccontrata/procedimentolicitatorio?page=N&size=N
Paginação Spring: content[], totalPages, totalElements
46.134+ licitações, sem autenticação.
"""
import logging
from datetime import datetime

import httpx

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_BASE = "https://app.tcema.tc.br/tce/api"
_ENDPOINT = f"{_BASE}/sinccontrata/procedimentolicitatorio"
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
_PAGE_SIZE = 100
_MAX_PAGES = 50  # 5.000 licitações por ciclo — evita sobrecarga


class TCEMASource(BaseSource):
    source_id = "tce_ma"
    interval_seconds = 21600  # 6 horas

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "MA":
            return []

        editais: list[EditalRaw] = []
        async with httpx.AsyncClient(headers=_HEADERS, timeout=30, follow_redirects=True) as c:
            for page in range(_MAX_PAGES):
                try:
                    r = await c.get(_ENDPOINT, params={"page": page, "size": _PAGE_SIZE})
                    if r.status_code != 200:
                        logger.warning("[TCE-MA] HTTP %d na página %d", r.status_code, page)
                        break
                    d = r.json()
                    itens = d.get("content", [])
                    if not itens:
                        break
                    for item in itens:
                        edital = _mapear(item)
                        if edital is None:
                            continue
                        if palavras_chave:
                            texto = f"{edital.objeto} {edital.orgao}".lower()
                            if not all(p.lower() in texto for p in palavras_chave):
                                continue
                        editais.append(edital)
                    if d.get("last", True):
                        break
                except Exception as exc:
                    logger.error("[TCE-MA] Erro na página %d: %s", page, exc)
                    break

        logger.info("[TCE-MA] %d editais encontrados", len(editais))
        return editais

    async def testar_conexao(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as c:
                r = await c.get(_ENDPOINT, params={"page": 0, "size": 1})
                return r.status_code == 200
        except Exception:
            return False


def _mapear(item: dict) -> EditalRaw | None:
    try:
        id_proc = str(item.get("idProcedimento") or item.get("id") or "").strip()
        if not id_proc:
            return None
        cnpj = str(item.get("cnpjProcedimento") or "").strip()
        numero_controle = f"tce_ma:{cnpj}:{id_proc}"
        orgao = (
            item.get("nomeEntidadeProcedimento")
            or item.get("nomeEntidadeEnvio")
            or item.get("nomeEnteProcedimento")
            or ""
        ).strip()
        objeto = (item.get("objeto") or "").strip()
        modalidade = (item.get("nomeTipoProcedimento") or item.get("tipoProcedimento") or "").strip()
        valor = _parse_float(item.get("valor"))
        data_abertura = _parse_data(item.get("dataSessao") or item.get("dataPublicacao"))
        data_enc = _parse_data(item.get("dataEnvio"))
        link = item.get("link_documento") or None
        return EditalRaw(
            numero_controle=numero_controle,
            orgao=orgao,
            objeto=objeto,
            modalidade=modalidade,
            valor_estimado=valor,
            data_abertura=data_abertura,
            data_encerramento=data_enc,
            link_edital=link,
            exclusivo_me=False,
            estado="MA",
            fonte="tce_ma",
        )
    except Exception as exc:
        logger.debug("[TCE-MA] Erro ao mapear: %s", exc)
        return None


def _parse_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(".", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_data(raw) -> datetime | None:
    if not raw:
        return None
    raw = str(raw).strip()[:19]
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S", "%d/%m/%Y"):
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None
