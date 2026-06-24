"""Interface base para todas as fontes de scraping."""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class EditalRaw:
    numero_controle: str      # deve ser único globalmente — prefixar com fonte: se necessário
    orgao: str
    objeto: str
    modalidade: str
    fonte: str                # ex: "pncp", "bll", "tce_sp"
    uasg: str | None = field(default=None)
    valor_estimado: float | None = field(default=None)
    data_abertura: datetime | None = field(default=None)
    data_encerramento: datetime | None = field(default=None)
    link_edital: str | None = field(default=None)
    link_pdf: str | None = field(default=None)
    exclusivo_me: bool = field(default=False)
    estado: str | None = field(default=None)
    municipio: str | None = field(default=None)
    texto_pdf: str | None = field(default=None)


class BaseSource(ABC):
    """Contrato que todo scraper de portal deve implementar."""

    source_id: str           # identificador único, ex: "pncp"
    interval_seconds: int    # intervalo de agendamento

    @abstractmethod
    async def buscar(
        self,
        palavras_chave: list[str] | None = None,
        estado: str | None = None,
    ) -> list[EditalRaw]:
        """Busca editais na fonte. Nunca lança exceção — retorna lista vazia se falhar."""
        ...

    async def testar_conexao(self) -> bool:
        """Verifica se o portal está acessível. Padrão: sempre True."""
        return True
