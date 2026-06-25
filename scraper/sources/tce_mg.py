"""Fonte TCE-MG — transparencia.tce.mg.gov.br (Angular SPA)."""
import logging
import httpx

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_API_URL = "https://transparencia.tce.mg.gov.br/apiserver/licitacao"
_HEADERS = {"Accept": "application/json", "User-Agent": "Mozilla/5.0"}


class TCEMGSource(BaseSource):
    source_id = "tce_mg"
    interval_seconds = 21600
    _base_url = "https://transparencia.tce.mg.gov.br/#/licitacao"

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "MG":
            return []

        editais: list[EditalRaw] = []
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=20, follow_redirects=True, verify=False) as c:
                params = {"page": 0, "size": 50, "sort": "dataPublicacao,desc"}
                r = await c.get(_API_URL, params=params)
                if r.status_code != 200:
                    logger.warning("[TCE-MG] API status %d", r.status_code)
                    return []

                dados = r.json()
                itens = dados.get("content", dados) if isinstance(dados, dict) else dados

                for item in itens:
                    edital = _mapear_tce_mg(item)
                    if edital is None:
                        continue
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)

            logger.info("[TCE-MG] %d editais encontrados", len(editais))
        except Exception as exc:
            logger.error("[TCE-MG] Erro: %s", exc)

        return editais

    async def testar_conexao(self) -> bool:
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=10, verify=False) as c:
                r = await c.get(_API_URL, params={"page": 0, "size": 1})
                return r.status_code < 500
        except Exception:
            return False


def _mapear_tce_mg(item: dict) -> EditalRaw | None:
    try:
        numero = str(item.get("numeroProcesso") or item.get("numero") or item.get("id") or "")
        if not numero:
            return None
        return EditalRaw(
            numero_controle=f"tce_mg:{numero}",
            orgao=item.get("nomeOrgao") or item.get("orgao") or "",
            objeto=item.get("objeto") or item.get("descricao") or "",
            modalidade=item.get("modalidade") or item.get("tipoLicitacao") or "",
            fonte="tce_mg",
            estado="MG",
            link_edital=item.get("link") or item.get("url"),
        )
    except Exception as exc:
        logger.warning("[TCE-MG] Erro ao mapear: %s", exc)
        return None
