"""Fonte TCE-RO — transparencia.tcero.tc.br (API REST pública).

Endpoint: GET /api/licitacoes?page=N&size=N
Retorna JSON com campos completos de licitações do próprio TCE-RO.
Sem autenticação, sem CAPTCHA.
"""
import logging
from datetime import datetime

import httpx

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_BASE = "https://transparencia.tcero.tc.br/api/licitacoes"
_HEADERS = {
    "Accept": "application/json",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
_PAGE_SIZE = 100


class TCEROSource(BaseSource):
    source_id = "tce_ro"
    interval_seconds = 21600  # 6 horas

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "RO":
            return []

        editais: list[EditalRaw] = []
        page = 0
        async with httpx.AsyncClient(headers=_HEADERS, timeout=30, follow_redirects=True) as c:
            while True:
                try:
                    r = await c.get(_BASE, params={"page": page, "size": _PAGE_SIZE})
                    if r.status_code != 200:
                        logger.warning("[TCE-RO] HTTP %d na página %d", r.status_code, page)
                        break
                    itens = r.json()
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
                    if len(itens) < _PAGE_SIZE:
                        break
                    page += 1
                except Exception as exc:
                    logger.error("[TCE-RO] Erro na página %d: %s", page, exc)
                    break

        logger.info("[TCE-RO] %d editais encontrados", len(editais))
        return editais

    async def testar_conexao(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=10) as c:
                r = await c.get(_BASE, params={"page": 0, "size": 1})
                return r.status_code == 200
        except Exception:
            return False


def _mapear(item: dict) -> EditalRaw | None:
    try:
        cod = str(item.get("codLicitacao") or "")
        if not cod:
            return None
        numero = item.get("licitacaoNumero", "")
        ano = item.get("licitacaoAno", "")
        return EditalRaw(
            numero_controle=f"tce_ro:{cod}",
            orgao="TCE-RO",
            objeto=item.get("licitacaoObjeto") or item.get("licitacaoResumoObjeto") or "",
            modalidade=item.get("tipoLicitacaoDescricao") or "",
            valor_estimado=_parse_float(item.get("valorEstimado")),
            data_abertura=_parse_data(item.get("licitacaoDataAbertura")),
            data_encerramento=None,
            link_edital=item.get("editalArquivo") or None,
            exclusivo_me=False,
            estado="RO",
            fonte="tce_ro",
        )
    except Exception as exc:
        logger.debug("[TCE-RO] Erro ao mapear: %s", exc)
        return None


def _parse_float(v) -> float | None:
    if v is None:
        return None
    try:
        return float(str(v).replace(".", "").replace(",", "."))
    except (ValueError, TypeError):
        return None


def _parse_data(raw: str | None) -> datetime | None:
    if not raw:
        return None
    for fmt in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw.strip()[:19], fmt)
        except ValueError:
            continue
    return None
