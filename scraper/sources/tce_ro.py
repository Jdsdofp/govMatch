"""Fonte TCE-RO — transparencia.tcero.tc.br (API REST pública).

Endpoint: GET /api/licitacoes
A API ignora parâmetros de paginação e retorna todos os registros de uma vez.
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
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=60, follow_redirects=True) as c:
                r = await c.get(_BASE)
                if r.status_code != 200:
                    logger.warning("[TCE-RO] HTTP %d", r.status_code)
                    return []
                itens = r.json()
                for item in itens:
                    edital = _mapear(item)
                    if edital is None:
                        continue
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)
        except Exception as exc:
            logger.error("[TCE-RO] Erro ao buscar: %s", exc)
            return []

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
