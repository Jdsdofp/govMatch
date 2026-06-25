"""Fonte TCE-PB — download.tce.pb.gov.br (CSV/ZIP anual).

Endpoint: GET /dados-abertos/dados-consolidados/licitacoes/licitacoes-{ano}.zip
Retorna ZIP com CSV separado por `;`, encoding UTF-8-BOM.
Anos disponíveis: 2015–ano atual.
"""
import csv
import io
import logging
import zipfile
from datetime import datetime

import httpx

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_BASE = "https://download.tce.pb.gov.br/dados-abertos/dados-consolidados/licitacoes"
_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}
_ANOS_RETROATIVOS = 2  # ano atual + anterior


class TCEPBSource(BaseSource):
    source_id = "tce_pb"
    interval_seconds = 86400  # 24h — download de ZIP anual

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "PB":
            return []

        ano_atual = datetime.now().year
        editais: list[EditalRaw] = []

        for ano in range(ano_atual, ano_atual - _ANOS_RETROATIVOS, -1):
            lote = await self._baixar_ano(ano, palavras_chave)
            editais.extend(lote)
            logger.info("[TCE-PB] Ano %d: %d editais", ano, len(lote))

        logger.info("[TCE-PB] Total: %d editais", len(editais))
        return editais

    async def _baixar_ano(self, ano: int, palavras_chave: list[str] | None) -> list[EditalRaw]:
        url = f"{_BASE}/licitacoes-{ano}.zip"
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=120, follow_redirects=True) as c:
                r = await c.get(url)
                if r.status_code != 200:
                    logger.debug("[TCE-PB] Ano %d: HTTP %d", ano, r.status_code)
                    return []
                return _parsear_zip(r.content, ano, palavras_chave)
        except Exception as exc:
            logger.error("[TCE-PB] Erro ao baixar ano %d: %s", ano, exc)
            return []

    async def testar_conexao(self) -> bool:
        ano = datetime.now().year
        url = f"{_BASE}/licitacoes-{ano}.zip"
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as c:
                r = await c.head(url)
                return r.status_code in (200, 302)
        except Exception:
            return False


def _parsear_zip(conteudo: bytes, ano: int, palavras_chave: list[str] | None) -> list[EditalRaw]:
    editais = []
    try:
        with zipfile.ZipFile(io.BytesIO(conteudo)) as zf:
            nomes_csv = [n for n in zf.namelist() if n.endswith(".csv")]
            if not nomes_csv:
                return []
            with zf.open(nomes_csv[0]) as f:
                reader = csv.DictReader(
                    io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"),
                    delimiter=";",
                )
                for row in reader:
                    edital = _mapear(row, ano)
                    if edital is None:
                        continue
                    if palavras_chave:
                        texto = f"{edital.objeto} {edital.orgao}".lower()
                        if not all(p.lower() in texto for p in palavras_chave):
                            continue
                    editais.append(edital)
    except Exception as exc:
        logger.error("[TCE-PB] Erro ao parsear ZIP ano %d: %s", ano, exc)
    return editais


def _mapear(row: dict, ano: int) -> EditalRaw | None:
    try:
        numero = (row.get("numero_licitacao") or row.get("numero_protocolo_tce") or "").strip()
        cod_ug = (row.get("codigo_unidade_gestora") or "").strip()
        if not numero and not cod_ug:
            return None
        numero_controle = f"tce_pb:{cod_ug}:{ano}:{numero}"
        orgao = (row.get("descricao_unidade_gestora") or row.get("nome_municipio") or "").strip()
        objeto = (row.get("objeto_licitacao") or "").strip()
        modalidade = (row.get("modalidade") or "").strip()
        valor = _parse_float(row.get("valor_ofertado"))
        data_hom = _parse_data(row.get("data_homologacao"))
        return EditalRaw(
            numero_controle=numero_controle,
            orgao=orgao,
            objeto=objeto,
            modalidade=modalidade,
            valor_estimado=valor,
            data_abertura=data_hom,
            data_encerramento=None,
            link_edital=None,
            exclusivo_me=False,
            estado="PB",
            municipio=(row.get("nome_municipio") or "").strip() or None,
            fonte="tce_pb",
        )
    except Exception as exc:
        logger.debug("[TCE-PB] Erro ao mapear: %s", exc)
        return None


def _parse_float(v) -> float | None:
    if not v:
        return None
    try:
        return float(str(v).strip().replace(".", "").replace(",", "."))
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
