import asyncio
from datetime import datetime, timedelta
from database.engine import AsyncSessionLocal
from database.models import Edital, EditalStatus

async def main():
    async with AsyncSessionLocal() as db:
        db.add(Edital(
            numero_controle="0013/2026-PMSLZ-013",
            orgao="Prefeitura Municipal de São Luís",
            uasg="06.223.132/0001-60",
            objeto="Contratação de serviços de TI e suporte técnico para a Secretaria de Administração",
            modalidade="Pregão Eletrônico",
            valor_estimado=320_000.00,
            data_abertura=datetime.now() + timedelta(days=4),
            data_encerramento=datetime.now() + timedelta(days=30),
            exclusivo_me=False,
            estado="MA",
            municipio="São Luís",
            status=EditalStatus.PUBLICADO,
        ))
        await db.commit()
        print("✓ Edital MA inserido.")

asyncio.run(main())
