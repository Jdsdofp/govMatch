# Task 6 — SchedulerService com APScheduler

## Status: DONE

## O que foi feito

1. **Instalação**: `apscheduler==3.11.2` instalado; adicionado `apscheduler>=3.10.4` em `requirements.txt`.

2. **`services/scheduler_service.py`**: `SchedulerService` com `AsyncIOScheduler`, método `register()` com jitter ±10%, `_executar_fonte()` criando própria sessão via `AsyncSessionLocal`, `get_status()` retornando lista com campos pedidos.

3. **`api/routes/scheduler.py`**: Rota `GET /api/v1/scheduler/status` retornando status de todas as fontes.

4. **`main.py`**: Instância global `scheduler` criada antes do lifespan; lifespan atualizado com `scheduler.start()` no startup e `scheduler.shutdown()` + `browser_pool.close_all()` no shutdown; `scheduler_router` incluído.

5. **`tests/services/test_scheduler_service.py`**: 2 testes unitários, todos passando.

## Correção aplicada

APScheduler 3.11 usa `__slots__` para `next_run_time`; o atributo não é inicializado quando o scheduler não está rodando. Substituído `job.next_run_time` por `getattr(job, "next_run_time", None)` em `get_status()`.

## Resultados dos testes

- `tests/services/test_scheduler_service.py`: 2/2 PASSED
- `tests/`: 14/14 PASSED
- `python -c "from main import app, scheduler; print('OK', len(scheduler._sources), 'fontes')"` → `OK 1 fontes`
