"""
Script de seed — popula o banco com editais realistas para testes.
Execução: python seed.py

Cobre todos os 26 estados + DF com ao menos 1 edital cada.
"""

import asyncio
from datetime import datetime, timedelta

from database.engine import AsyncSessionLocal, create_tables
from database.models import Edital, EditalStatus

N = datetime.now


EDITAIS_SEED = [
    # ── SP ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0001/2026-PMSP-001",
        "orgao": "Prefeitura Municipal de São Paulo",
        "uasg": "15.451.487/0001-64",
        "objeto": "Contratação de empresa especializada em serviços de TI, suporte técnico e manutenção de infraestrutura de rede para a Secretaria de Gestão",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 850_000.00,
        "data_abertura": N() + timedelta(days=5),
        "data_encerramento": N() + timedelta(days=35),
        "exclusivo_me": False, "estado": "SP", "municipio": "São Paulo",
        "status": EditalStatus.PUBLICADO,
    },
    {
        "numero_controle": "0002/2026-INSS-SP",
        "orgao": "Instituto Nacional do Seguro Social — Gerência SP",
        "uasg": "29.979.036/0001-40",
        "objeto": "Prestação de serviços continuados de vigilância patrimonial desarmada nas agências do INSS na região metropolitana de São Paulo",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 4_800_000.00,
        "data_abertura": N() + timedelta(days=15),
        "data_encerramento": N() + timedelta(days=120),
        "exclusivo_me": False, "estado": "SP", "municipio": "São Paulo",
        "status": EditalStatus.PUBLICADO,
    },
    # ── MG ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0003/2026-PMBH-002",
        "orgao": "Prefeitura Municipal de Belo Horizonte",
        "uasg": "18.715.451/0001-59",
        "objeto": "Aquisição de equipamentos de informática — notebooks, impressoras e monitores para escritórios regionais — exclusivo ME/EPP",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 240_000.00,
        "data_abertura": N() + timedelta(days=3),
        "data_encerramento": N() + timedelta(days=20),
        "exclusivo_me": True, "estado": "MG", "municipio": "Belo Horizonte",
        "status": EditalStatus.PUBLICADO,
    },
    {
        "numero_controle": "0004/2026-CEFETMG-012",
        "orgao": "Centro Federal de Educação Tecnológica de Minas Gerais",
        "uasg": "25.224.880/0001-83",
        "objeto": "Reforma e adequação de laboratórios de informática — instalação elétrica, cabeamento estruturado e ar-condicionado — exclusivo ME/EPP",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 185_000.00,
        "data_abertura": N() + timedelta(days=6),
        "data_encerramento": N() + timedelta(days=40),
        "exclusivo_me": True, "estado": "MG", "municipio": "Belo Horizonte",
        "status": EditalStatus.PUBLICADO,
    },
    # ── RJ ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0005/2026-CMRJ-004",
        "orgao": "Câmara Municipal do Rio de Janeiro",
        "uasg": "42.498.733/0001-48",
        "objeto": "Contratação de serviços de desenvolvimento de software sob demanda, manutenção de sistemas legados e consultoria em transformação digital",
        "modalidade": "Concorrência Eletrônica",
        "valor_estimado": 1_500_000.00,
        "data_abertura": N() + timedelta(days=12),
        "data_encerramento": N() + timedelta(days=90),
        "exclusivo_me": False, "estado": "RJ", "municipio": "Rio de Janeiro",
        "status": EditalStatus.ABERTO,
    },
    # ── DF ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0006/2026-GDF-003",
        "orgao": "Governo do Distrito Federal — Secretaria de Saúde",
        "uasg": "00.394.700/0001-41",
        "objeto": "Prestação de serviços de limpeza e conservação predial nas unidades de saúde do DF com fornecimento de materiais e equipamentos",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 3_200_000.00,
        "data_abertura": N() + timedelta(days=8),
        "data_encerramento": N() + timedelta(days=60),
        "exclusivo_me": False, "estado": "DF", "municipio": "Brasília",
        "status": EditalStatus.PUBLICADO,
    },
    # ── BA ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0007/2026-UFBA-005",
        "orgao": "Universidade Federal da Bahia",
        "uasg": "15.180.714/0001-04",
        "objeto": "Fornecimento de material de escritório, papéis, canetas, cartuchos de impressora e suprimentos diversos — cota reservada ME/EPP",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 95_000.00,
        "data_abertura": N() + timedelta(days=2),
        "data_encerramento": N() + timedelta(days=15),
        "exclusivo_me": True, "estado": "BA", "municipio": "Salvador",
        "status": EditalStatus.DISPUTA_ABERTA,
    },
    # ── RS ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0008/2026-TCERS-006",
        "orgao": "Tribunal de Contas do Estado do Rio Grande do Sul",
        "uasg": "87.591.983/0001-57",
        "objeto": "Contratação de solução de segurança da informação — firewall next generation, antivírus corporativo e SIEM para monitoramento de incidentes",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 620_000.00,
        "data_abertura": N() + timedelta(days=7),
        "data_encerramento": N() + timedelta(days=45),
        "exclusivo_me": False, "estado": "RS", "municipio": "Porto Alegre",
        "status": EditalStatus.PUBLICADO,
    },
    # ── CE ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0009/2026-PMFOR-007",
        "orgao": "Prefeitura Municipal de Fortaleza",
        "uasg": "07.954.259/0001-60",
        "objeto": "Serviços de manutenção preventiva e corretiva de ar-condicionado em prédios públicos municipais — exclusivo microempresas e EPP",
        "modalidade": "Dispensa de Licitação",
        "valor_estimado": 48_000.00,
        "data_abertura": N() - timedelta(days=2),
        "data_encerramento": N() + timedelta(days=10),
        "exclusivo_me": True, "estado": "CE", "municipio": "Fortaleza",
        "status": EditalStatus.EM_ANDAMENTO,
    },
    # ── PR ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0010/2026-UFPR-009",
        "orgao": "Universidade Federal do Paraná",
        "uasg": "75.095.679/0001-49",
        "objeto": "Aquisição de reagentes químicos, vidrarias e equipamentos de laboratório para os cursos de Química, Biologia e Farmácia",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 380_000.00,
        "data_abertura": N() + timedelta(days=4),
        "data_encerramento": N() + timedelta(days=30),
        "exclusivo_me": False, "estado": "PR", "municipio": "Curitiba",
        "status": EditalStatus.PUBLICADO,
    },
    # ── PE ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0011/2026-GOVPE-010",
        "orgao": "Secretaria de Administração do Estado de Pernambuco",
        "uasg": "10.572.460/0001-00",
        "objeto": "Fornecimento de gêneros alimentícios, café, açúcar e insumos para copa dos órgãos estaduais — cota reservada microempresa",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 72_000.00,
        "data_abertura": N() + timedelta(days=1),
        "data_encerramento": N() + timedelta(days=12),
        "exclusivo_me": True, "estado": "PE", "municipio": "Recife",
        "status": EditalStatus.PUBLICADO,
    },
    # ── MA ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0012/2026-PMSLZ-013",
        "orgao": "Prefeitura Municipal de São Luís",
        "uasg": "06.223.132/0001-60",
        "objeto": "Contratação de serviços de TI, suporte técnico e manutenção de infraestrutura de rede para a Secretaria de Administração do Maranhão",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 320_000.00,
        "data_abertura": N() + timedelta(days=4),
        "data_encerramento": N() + timedelta(days=30),
        "exclusivo_me": False, "estado": "MA", "municipio": "São Luís",
        "status": EditalStatus.PUBLICADO,
    },
    # ── GO ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0013/2026-GOVGO-014",
        "orgao": "Secretaria de Estado da Economia de Goiás",
        "uasg": "01.409.580/0001-38",
        "objeto": "Aquisição de mobiliário ergonômico — cadeiras, mesas e divisórias para modernização dos escritórios da Secretaria — exclusivo ME/EPP",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 160_000.00,
        "data_abertura": N() + timedelta(days=9),
        "data_encerramento": N() + timedelta(days=35),
        "exclusivo_me": True, "estado": "GO", "municipio": "Goiânia",
        "status": EditalStatus.PUBLICADO,
    },
    # ── SC ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0014/2026-UFSC-015",
        "orgao": "Universidade Federal de Santa Catarina",
        "uasg": "83.899.526/0001-82",
        "objeto": "Contratação de serviços de desenvolvimento web e manutenção de sistemas de gestão acadêmica e administrativos",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 540_000.00,
        "data_abertura": N() + timedelta(days=11),
        "data_encerramento": N() + timedelta(days=55),
        "exclusivo_me": False, "estado": "SC", "municipio": "Florianópolis",
        "status": EditalStatus.PUBLICADO,
    },
    # ── AM ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0015/2026-PMMAN-016",
        "orgao": "Prefeitura Municipal de Manaus",
        "uasg": "04.417.039/0001-05",
        "objeto": "Fornecimento de combustível — gasolina e diesel — para a frota de veículos oficiais da Prefeitura de Manaus",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 2_100_000.00,
        "data_abertura": N() + timedelta(days=6),
        "data_encerramento": N() + timedelta(days=50),
        "exclusivo_me": False, "estado": "AM", "municipio": "Manaus",
        "status": EditalStatus.PUBLICADO,
    },
    # ── PA ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0016/2026-UFPA-017",
        "orgao": "Universidade Federal do Pará",
        "uasg": "05.058.070/0001-80",
        "objeto": "Contratação de empresa de segurança e vigilância para os campi da UFPA em Belém e interior do estado — exclusivo ME/EPP",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 890_000.00,
        "data_abertura": N() + timedelta(days=10),
        "data_encerramento": N() + timedelta(days=70),
        "exclusivo_me": False, "estado": "PA", "municipio": "Belém",
        "status": EditalStatus.PUBLICADO,
    },
    # ── MT ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0017/2026-GOVMT-018",
        "orgao": "Secretaria de Estado de Saúde de Mato Grosso",
        "uasg": "03.507.415/0001-10",
        "objeto": "Aquisição de medicamentos e insumos hospitalares para abastecimento das unidades de saúde estaduais — cota reservada ME/EPP",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 5_600_000.00,
        "data_abertura": N() + timedelta(days=14),
        "data_encerramento": N() + timedelta(days=80),
        "exclusivo_me": True, "estado": "MT", "municipio": "Cuiabá",
        "status": EditalStatus.PUBLICADO,
    },
    # ── MS ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0018/2026-PMCG-019",
        "orgao": "Prefeitura Municipal de Campo Grande",
        "uasg": "03.155.926/0001-44",
        "objeto": "Contratação de serviços de engenharia para manutenção de vias públicas, tapa-buracos e sinalização viária",
        "modalidade": "Concorrência Eletrônica",
        "valor_estimado": 8_500_000.00,
        "data_abertura": N() + timedelta(days=20),
        "data_encerramento": N() + timedelta(days=100),
        "exclusivo_me": False, "estado": "MS", "municipio": "Campo Grande",
        "status": EditalStatus.PUBLICADO,
    },
    # ── ES ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0019/2026-GOVS-020",
        "orgao": "Instituto Federal do Espírito Santo",
        "uasg": "10.658.428/0001-91",
        "objeto": "Aquisição de equipamentos audiovisuais — projetores, telas de projeção, sistemas de som e câmeras para salas de aula e auditórios — exclusivo ME/EPP",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 210_000.00,
        "data_abertura": N() + timedelta(days=3),
        "data_encerramento": N() + timedelta(days=22),
        "exclusivo_me": True, "estado": "ES", "municipio": "Vitória",
        "status": EditalStatus.PUBLICADO,
    },
    # ── AL ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0020/2026-PMAL-021",
        "orgao": "Prefeitura Municipal de Maceió",
        "uasg": "12.200.135/0001-90",
        "objeto": "Contratação de empresa para serviços de fotografia, filmagem e produção audiovisual para eventos institucionais — exclusivo microempresa",
        "modalidade": "Dispensa de Licitação",
        "valor_estimado": 45_000.00,
        "data_abertura": N() + timedelta(days=1),
        "data_encerramento": N() + timedelta(days=8),
        "exclusivo_me": True, "estado": "AL", "municipio": "Maceió",
        "status": EditalStatus.PUBLICADO,
    },
    # ── SE ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0021/2026-UFS-022",
        "orgao": "Universidade Federal de Sergipe",
        "uasg": "15.261.880/0001-60",
        "objeto": "Fornecimento de gás liquefeito de petróleo (GLP) em botijões de 13 kg e 45 kg para as unidades da UFS",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 68_000.00,
        "data_abertura": N() + timedelta(days=5),
        "data_encerramento": N() + timedelta(days=25),
        "exclusivo_me": True, "estado": "SE", "municipio": "Aracaju",
        "status": EditalStatus.PUBLICADO,
    },
    # ── PI ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0022/2026-GOVPI-023",
        "orgao": "Secretaria de Educação do Estado do Piauí",
        "uasg": "06.554.758/0001-90",
        "objeto": "Aquisição de materiais didáticos, livros, apostilas e kits escolares para distribuição nas escolas públicas estaduais",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 1_200_000.00,
        "data_abertura": N() + timedelta(days=8),
        "data_encerramento": N() + timedelta(days=50),
        "exclusivo_me": False, "estado": "PI", "municipio": "Teresina",
        "status": EditalStatus.PUBLICADO,
    },
    # ── RN ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0023/2026-UFRN-024",
        "orgao": "Universidade Federal do Rio Grande do Norte",
        "uasg": "24.365.710/0001-83",
        "objeto": "Contratação de serviços de limpeza e conservação predial com fornecimento de materiais nos campi da UFRN — cota reservada ME/EPP",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 730_000.00,
        "data_abertura": N() + timedelta(days=7),
        "data_encerramento": N() + timedelta(days=40),
        "exclusivo_me": True, "estado": "RN", "municipio": "Natal",
        "status": EditalStatus.PUBLICADO,
    },
    # ── PB ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0024/2026-GOVPB-025",
        "orgao": "Secretaria de Infraestrutura da Paraíba",
        "uasg": "09.168.704/0001-42",
        "objeto": "Contratação de empresa para construção de passarelas e calçadas acessíveis em municípios do interior da Paraíba",
        "modalidade": "Concorrência Eletrônica",
        "valor_estimado": 12_000_000.00,
        "data_abertura": N() + timedelta(days=25),
        "data_encerramento": N() + timedelta(days=130),
        "exclusivo_me": False, "estado": "PB", "municipio": "João Pessoa",
        "status": EditalStatus.PUBLICADO,
    },
    # ── RO ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0025/2026-GOVRO-026",
        "orgao": "Governo do Estado de Rondônia — SEFIN",
        "uasg": "04.716.258/0001-52",
        "objeto": "Aquisição de sistemas de energia solar fotovoltaica para prédios públicos estaduais — exclusivo ME/EPP",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 450_000.00,
        "data_abertura": N() + timedelta(days=13),
        "data_encerramento": N() + timedelta(days=60),
        "exclusivo_me": True, "estado": "RO", "municipio": "Porto Velho",
        "status": EditalStatus.PUBLICADO,
    },
    # ── AC ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0026/2026-GOVAC-027",
        "orgao": "Secretaria de Saúde do Acre",
        "uasg": "63.606.815/0001-54",
        "objeto": "Contratação de empresa para serviços de manutenção de equipamentos hospitalares — eletrocardiógrafos, desfibriladores e monitores multiparamétricos",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 280_000.00,
        "data_abertura": N() + timedelta(days=9),
        "data_encerramento": N() + timedelta(days=45),
        "exclusivo_me": False, "estado": "AC", "municipio": "Rio Branco",
        "status": EditalStatus.PUBLICADO,
    },
    # ── RR ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0027/2026-GOVRR-028",
        "orgao": "Governo do Estado de Roraima — SEPLAN",
        "uasg": "84.094.525/0001-40",
        "objeto": "Aquisição de veículos tipo pickup 4x4 para apoio às ações de fiscalização ambiental e defesa civil",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 960_000.00,
        "data_abertura": N() + timedelta(days=18),
        "data_encerramento": N() + timedelta(days=75),
        "exclusivo_me": False, "estado": "RR", "municipio": "Boa Vista",
        "status": EditalStatus.PUBLICADO,
    },
    # ── AP ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0028/2026-GOVAP-029",
        "orgao": "Secretaria de Educação do Amapá",
        "uasg": "34.925.131/0001-78",
        "objeto": "Fornecimento de uniformes escolares — camisetas, calças e tênis — para alunos da rede pública estadual — exclusivo ME/EPP",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 380_000.00,
        "data_abertura": N() + timedelta(days=5),
        "data_encerramento": N() + timedelta(days=28),
        "exclusivo_me": True, "estado": "AP", "municipio": "Macapá",
        "status": EditalStatus.PUBLICADO,
    },
    # ── TO ──────────────────────────────────────────────────────────────────
    {
        "numero_controle": "0029/2026-UFT-030",
        "orgao": "Universidade Federal do Tocantins",
        "uasg": "05.149.726/0001-01",
        "objeto": "Contratação de serviços de internet banda larga e links dedicados para os campi da UFT em Palmas, Araguaína e Gurupi",
        "modalidade": "Pregão Eletrônico",
        "valor_estimado": 420_000.00,
        "data_abertura": N() + timedelta(days=6),
        "data_encerramento": N() + timedelta(days=36),
        "exclusivo_me": False, "estado": "TO", "municipio": "Palmas",
        "status": EditalStatus.PUBLICADO,
    },
]


async def seed() -> None:
    await create_tables()

    async with AsyncSessionLocal() as db:
        for dados in EDITAIS_SEED:
            edital = Edital(**dados)
            db.add(edital)

        await db.commit()

    estados = sorted({e["estado"] for e in EDITAIS_SEED})
    me_epp = sum(1 for e in EDITAIS_SEED if e["exclusivo_me"])
    print(f"✓ {len(EDITAIS_SEED)} editais inseridos — {len(estados)} estados — {me_epp} exclusivo ME/EPP")
    print(f"  Estados: {', '.join(estados)}")


if __name__ == "__main__":
    asyncio.run(seed())
