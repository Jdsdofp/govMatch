"""Fonte TCE-RS — dados.tce.rs.gov.br (portal CKAN com CSV diário).

Estratégia: download do ZIP consolidado de licitações do ano atual
(~174 MB, atualizado diariamente) com cache local de 24h.
Formato: CSVs separados por ";", encoding UTF-8 BOM.
Arquivo principal: LICITACAO.csv (leiaute LicitaCon v1.4).
Portal: https://dados.tce.rs.gov.br/group/licitacoes
"""
import asyncio
import csv
import io
import logging
import os
import time
import zipfile
from datetime import datetime

import httpx

from scraper.sources.base import BaseSource, EditalRaw

logger = logging.getLogger(__name__)

_BASE_URL = "https://dados.tce.rs.gov.br/dados/licitacon/licitacao/ano"
_CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "cache")
_CACHE_TTL = 86_400  # 24 horas
_HEADERS = {
    "Accept": "*/*",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
}


class TCERSSource(BaseSource):
    source_id = "tce_rs"
    interval_seconds = 86_400  # 1 vez por dia

    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        if estado and estado.upper() != "RS":
            return []

        ano = datetime.now().year
        zip_data = await self._obter_zip(ano)
        if not zip_data:
            logger.warning("[TCE-RS] Falha ao obter ZIP %d", ano)
            return []

        editais = await asyncio.get_event_loop().run_in_executor(
            None, self._parsear_zip, zip_data, palavras_chave
        )
        logger.info("[TCE-RS] %d editais lidos do CSV %d", len(editais), ano)
        return editais

    async def testar_conexao(self) -> bool:
        ano = datetime.now().year
        url = f"{_BASE_URL}/{ano}.csv.zip"
        try:
            async with httpx.AsyncClient(headers=_HEADERS, timeout=15) as c:
                r = await c.head(url)
                return r.status_code == 200
        except Exception:
            return False

    # ------------------------------------------------------------------
    async def _obter_zip(self, ano: int) -> bytes | None:
        os.makedirs(_CACHE_DIR, exist_ok=True)
        cache_path = os.path.join(_CACHE_DIR, f"tce_rs_{ano}.zip")

        # Usa cache se ainda fresco
        if os.path.exists(cache_path):
            idade = time.time() - os.path.getmtime(cache_path)
            if idade < _CACHE_TTL:
                logger.debug("[TCE-RS] Usando cache local (%.1fh)", idade / 3600)
                with open(cache_path, "rb") as f:
                    return f.read()

        url = f"{_BASE_URL}/{ano}.csv.zip"
        logger.info("[TCE-RS] Baixando %s ...", url)
        try:
            async with httpx.AsyncClient(
                headers=_HEADERS, timeout=300, follow_redirects=True
            ) as c:
                r = await c.get(url)
                if r.status_code != 200:
                    logger.error("[TCE-RS] HTTP %d ao baixar ZIP", r.status_code)
                    return None
                data = r.content
                with open(cache_path, "wb") as f:
                    f.write(data)
                logger.info("[TCE-RS] ZIP salvo (%d MB)", len(data) // 1_000_000)
                return data
        except Exception as exc:
            logger.error("[TCE-RS] Erro ao baixar ZIP: %s", exc)
            return None

    def _parsear_zip(
        self, zip_data: bytes, palavras_chave: list[str] | None
    ) -> list[EditalRaw]:
        editais: list[EditalRaw] = []
        try:
            with zipfile.ZipFile(io.BytesIO(zip_data)) as z:
                # Localiza LICITACAO.csv (exclui LICITANTE e variações com LOTE)
                licit_file = next(
                    (
                        n for n in z.namelist()
                        if "LICITACAO" in n.upper()
                        and "LICITANTE" not in n.upper()
                        and "LOTE" not in n.upper()
                    ),
                    None,
                )
                if not licit_file:
                    logger.error("[TCE-RS] LICITACAO.csv não encontrado no ZIP")
                    return []

                logger.debug("[TCE-RS] Lendo %s", licit_file)
                with z.open(licit_file) as f:
                    reader = csv.DictReader(
                        io.TextIOWrapper(f, encoding="utf-8-sig", errors="replace"),
                        delimiter=",",
                    )
                    for row in reader:
                        edital = _mapear_licitacon(row)
                        if edital is None:
                            continue
                        if palavras_chave:
                            texto = f"{edital.objeto} {edital.orgao}".lower()
                            if not all(p.lower() in texto for p in palavras_chave):
                                continue
                        editais.append(edital)
        except Exception as exc:
            logger.error("[TCE-RS] Erro ao parsear ZIP: %s", exc)
        return editais


# ---------------------------------------------------------------------------

def _mapear_licitacon(row: dict) -> EditalRaw | None:
    try:
        nr = row.get("NR_LICITACAO") or row.get("CD_LICITACAO") or ""
        ano = row.get("ANO_LICITACAO") or ""
        cd_orgao = row.get("CD_ORGAO") or ""
        if not nr:
            return None

        numero_controle = f"tce_rs:{cd_orgao}:{ano}:{nr}"
        objeto = (
            row.get("DS_OBJETO")
            or row.get("DS_LICITACAO")
            or row.get("OB_LICITACAO")
            or ""
        )
        orgao = row.get("NM_ORGAO") or row.get("DS_ORGAO") or cd_orgao or ""
        modalidade = row.get("DS_MODALIDADE") or row.get("CD_TIPO_MODALIDADE") or ""
        valor = _parse_valor_br(
            row.get("VL_LICITACAO") or row.get("VL_ESTIMADO") or ""
        )
        data_abertura = _parse_data_br(
            row.get("DT_ABERTURA") or row.get("DT_INICIO_PROPOSTA") or ""
        )
        data_enc = _parse_data_br(
            row.get("DT_HOMOLOGACAO") or row.get("DT_FIM_PROPOSTA") or ""
        )

        return EditalRaw(
            numero_controle=numero_controle,
            orgao=orgao,
            objeto=objeto,
            modalidade=modalidade,
            valor_estimado=valor,
            data_abertura=data_abertura,
            data_encerramento=data_enc,
            fonte="tce_rs",
            estado="RS",
        )
    except Exception as exc:
        logger.debug("[TCE-RS] Erro ao mapear linha: %s", exc)
        return None


def _parse_valor_br(raw: str) -> float | None:
    if not raw:
        return None
    try:
        return float(raw.strip().replace(".", "").replace(",", "."))
    except (ValueError, AttributeError):
        return None


def _parse_data_br(raw: str) -> datetime | None:
    if not raw:
        return None
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d/%m/%Y %H:%M:%S"):
        try:
            return datetime.strptime(raw.strip()[:19], fmt)
        except ValueError:
            continue
    return None
