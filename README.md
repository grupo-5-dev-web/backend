## White Label Resource Scheduling Platform – Backend

A plataforma permite que diferentes negócios configurem regras próprias de agendamento (recursos humanos, equipamentos ou espaços) utilizando a mesma base white label. O backend foi estruturado como um conjunto de microsserviços FastAPI multi-tenant, com regras configuráveis por organização e propagação de eventos.

### Stack e diretrizes
- Python 3.11 + FastAPI em cada serviço
- SQLAlchemy + PostgreSQL (um banco por domínio, suporte a JSONB)
- Alembic por serviço para migrações independentes
- Redis Streams para publicação de eventos (pode evoluir para Kafka)
- Docker Compose para orquestração local
- Nginx como gateway reverso e landing page de documentação

### Estrutura do repositório
```text
backend/
├── docker-compose.yml
├── infra/
│   └── nginx/
│       ├── Dockerfile
│       ├── nginx.conf
│       └── html/
│           └── index.html
└── services/
    ├── shared/
    ├── tenant/
    ├── user/
    ├── resource/
    └── booking/
```
- `services/shared`: utilidades comuns (config, mensageria, helpers de startup) copiadas para cada container.
- `services/<service>`: código FastAPI isolado, com pastas `core`, `models`, `routers`, `schemas` e testes.
- `infra/nginx`: gateway que expõe os serviços e disponibiliza uma landing page com links de Swagger.

> Execução local sem Docker: exporte `PYTHONPATH="$(pwd)/services/shared:$(pwd)/services/<serviço>"` e rode `uvicorn app.main:app --reload` dentro da pasta do serviço.

### Landing page e documentação
- `http://localhost:8000/` (gateway) exibe uma página com links para os Swagger UI de cada serviço.
- Serviços expõem documentação em:
	- `http://localhost:8000/api-docs/tenants` - Tenant Service (gerenciamento de organizações)
	- `http://localhost:8000/api-docs/users` - User Service (usuários multi-tenant)
	- `http://localhost:8000/api-docs/resources` - Resource Service (categorias e recursos)
	- `http://localhost:8000/api-docs/bookings` - Booking Service (reservas e agendamentos)
- Cada endpoint documenta respostas de erro (400/404/409/422) alinhadas às regras de negócio.

### Serviços e responsabilidades
- **tenant**: gerenciamento de tenants (organizações white label), configurações de agendamento (`OrganizationSettings`), labels customizadas, horários comerciais e regras de antecedência/cancelamento.
- **resource**: categorias de recursos (físicos/humanos), recursos com atributos dinâmicos, disponibilidade diária e cálculo de slots disponíveis.
- **user**: perfis de usuários multi-tenant, tipos (admin/user), permissões granulares e metadados de perfil.
- **booking**: criação/atualização/cancelamento de reservas com validações completas (conflitos de horário, janelas de antecedência, horário comercial, intervalo mínimo) e emissão de eventos em Redis Streams.

### Fluxos implementados
- **Regras de agendamento**: provider compartilhado (`services/shared/organization.py`) recupera `OrganizationSettings` do serviço de tenant (HTTP via `httpx`) ou usa defaults. CRUD de bookings verifica horário útil, antecipação máxima, duração múltipla do intervalo e janela de cancelamento.
- **Timezone handling**: cada tenant configura seu timezone (ex: `America/Sao_Paulo`). Horários de entrada (API) sem timezone são interpretados como horário local do tenant. Banco armazena tudo em UTC. Validações (horário comercial, disponibilidade) usam timezone do tenant. Cliente pode enviar horários em qualquer timezone (ISO 8601) e o sistema converte automaticamente.
- **Política de cancelamento**: listagens de reservas (`GET /bookings/`) incluem `can_cancel` calculado dinamicamente, refletindo a janela configurada pelo tenant.
- **Disponibilidade de recursos**: `GET /resources/{id}/availability` monta slots alinhados ao expediente e intervalo do tenant, consulta o serviço de bookings via `BOOKING_SERVICE_URL` para bloquear conflitos e responde com timezone normalizado.
- **Detecção de conflitos**: ao criar ou atualizar reservas, o sistema verifica se já existe booking aprovado/pendente no mesmo recurso e horário, retornando status 409 com lista de conflitos.
- **Arquitetura event-driven**: toda mudança de reserva (`booking.created`, `booking.updated`, `booking.cancelled`, `booking.status_changed`) é publicada em Redis Streams. Serviços de user e resource consomem eventos via Consumer Groups para atualizar caches, enviar notificações e registrar métricas de forma assíncrona e desacoplada.
- **Landing page unificada**: gateway Nginx serve `http://localhost:8000/` com atalhos para a documentação Swagger de cada serviço.

### Exemplo de fluxo completo
```bash
# 1. Criar tenant com regras de agendamento
curl -X POST http://localhost:8000/tenants/ -H "Content-Type: application/json" -d '{
  "name": "Academia Fit",
  "domain": "academia-fit.com",
  "logo_url": "https://exemplo.com/logo.png",
  "theme_primary_color": "#FF5722",
  "plan": "profissional",
  "settings": {
    "business_type": "fitness",
    "timezone": "America/Sao_Paulo",
    "working_hours_start": "06:00:00",
    "working_hours_end": "22:00:00",
    "booking_interval": 60,
    "advance_booking_days": 30,
    "cancellation_hours": 24,
    "custom_labels": {
      "resource_singular": "Sala",
      "resource_plural": "Salas",
      "booking_label": "Aula",
      "user_label": "Aluno"
    }
  }
}'
# Resposta: {"id": "d49eccff-6586-44cc-b723-719f78a6f9f9", ...}

# 2. Criar usuário
curl -X POST http://localhost:8000/users/ -H "Content-Type: application/json" -d '{
  "tenant_id": "d49eccff-6586-44cc-b723-719f78a6f9f9",
  "name": "João Silva",
  "email": "joao.silva@academiafit.com",
  "user_type": "user",
  "permissions": {"can_book": true}
}'
# Resposta: {"id": "6a899ad5-12bb-43ee-90ac-4d6f5091f6ae", ...}

# 3. Criar categoria de recurso
curl -X POST http://localhost:8000/categories/ -H "Content-Type: application/json" -d '{
  "tenant_id": "d49eccff-6586-44cc-b723-719f78a6f9f9",
  "name": "Salas de Aula",
  "description": "Espaços para aulas coletivas",
  "type": "fisico",
  "icon": "room",
  "color": "#4CAF50"
}'
# Resposta: {"id": "6a37c359-0684-4e73-b86a-69afe164c7c9", ...}

# 4. Criar recurso
curl -X POST http://localhost:8000/resources/ -H "Content-Type: application/json" -d '{
  "tenant_id": "d49eccff-6586-44cc-b723-719f78a6f9f9",
  "category_id": "6a37c359-0684-4e73-b86a-69afe164c7c9",
  "name": "Sala 1 - Spinning",
  "description": "Sala equipada para aulas de spinning",
  "capacity": 20,
  "location": "Andar 2"
}'
# Resposta: {"id": "d4a90dee-9261-44df-a362-e6c12db591e2", ...}

# 5. Criar reserva válida
curl -X POST http://localhost:8000/bookings/ -H "Content-Type: application/json" -d '{
  "tenant_id": "d49eccff-6586-44cc-b723-719f78a6f9f9",
  "resource_id": "d4a90dee-9261-44df-a362-e6c12db591e2",
  "user_id": "6a899ad5-12bb-43ee-90ac-4d6f5091f6ae",
  "client_id": "6a899ad5-12bb-43ee-90ac-4d6f5091f6ae",
  "start_time": "2025-12-05T14:00:00Z",
  "end_time": "2025-12-05T15:00:00Z",
  "notes": "Aula de Spinning - Iniciantes"
}'
# Resposta: {"id": "b6a2c6bc-5809-47ad-9aa7-6cf2adc35f42", "status": "pendente", ...}

# 6. Tentar criar reserva com conflito (retorna 409)
curl -X POST http://localhost:8000/bookings/ -H "Content-Type: application/json" -d '{
  "tenant_id": "d49eccff-6586-44cc-b723-719f78a6f9f9",
  "resource_id": "d4a90dee-9261-44df-a362-e6c12db591e2",
  "user_id": "6a899ad5-12bb-43ee-90ac-4d6f5091f6ae",
  "client_id": "6a899ad5-12bb-43ee-90ac-4d6f5091f6ae",
  "start_time": "2025-12-05T14:30:00Z",
  "end_time": "2025-12-05T15:30:00Z"
}'
# Resposta 409: {
#   "success": false,
#   "error": "conflict",
#   "message": "Recurso já possui reserva neste intervalo",
#   "conflicts": [{"booking_id": "b6a2c6bc-...", "start_time": "...", "end_time": "..."}]
# }

# 7. Listar reservas do tenant
curl "http://localhost:8000/bookings/?tenant_id=d49eccff-6586-44cc-b723-719f78a6f9f9"
# Resposta: [{"id": "...", "can_cancel": false, ...}]
```

### Arquitetura Event-Driven com Redis Streams

O sistema implementa comunicação assíncrona baseada em eventos usando **Redis Streams** com **Consumer Groups**, permitindo processamento distribuído e garantias de entrega.

#### Componentes

**EventPublisher** (`services/shared/messaging.py`)
- Publica eventos no Redis Stream `booking-events`
- Cada evento contém: `event_type`, `payload` (JSON) e `metadata` (tenant_id)
- Usado pelo Booking Service para emitir eventos após mudanças de estado

**EventConsumer** (`services/shared/event_consumer.py`)
- Consumidor genérico baseado em `XREADGROUP` (Redis Streams)
- Suporta múltiplos consumidores no mesmo grupo para load balancing
- Processa mensagens pendentes no startup (recuperação de falhas)
- Handlers registrados por tipo de evento
- Graceful shutdown com cancelamento de tasks asyncio

#### Eventos Publicados (Booking Service)

| Evento | Payload | Quando |
|--------|---------|--------|
| `booking.created` | `booking_id`, `user_id`, `resource_id`, `status`, `start_time`, `end_time` | Nova reserva criada |
| `booking.updated` | `booking_id`, `resource_id`, `changes` (dict de mudanças) | Reserva atualizada |
| `booking.cancelled` | `booking_id`, `resource_id`, `reason`, `cancelled_by` | Reserva cancelada |
| `booking.status_changed` | `booking_id`, `old_status`, `new_status` | Status alterado |

#### Consumer Groups Implementados

**user-service** (consome `booking-events`)
- `handle_booking_created`: Processa novas reservas para envio de notificações
- `handle_booking_cancelled`: Gerencia cancelamentos e notificações
- `handle_booking_status_changed`: Reage a mudanças de status

**resource-service** (consome `booking-events`)
- `handle_booking_created`: Atualiza métricas e invalida cache de disponibilidade
- `handle_booking_cancelled`: Libera slots e atualiza estatísticas
- `handle_booking_updated`: Reprocessa disponibilidade se horário mudou

#### Vantagens da Arquitetura

✅ **Desacoplamento**: Booking Service não precisa conhecer consumers  
✅ **Escalabilidade**: Múltiplos workers no mesmo consumer group  
✅ **Confiabilidade**: Consumer groups garantem processamento único  
✅ **Recuperação**: Mensagens pendentes são reprocessadas no startup  
✅ **Rastreabilidade**: Logs estruturados de cada evento processado  

#### Monitoramento

```bash
# Total de eventos publicados
docker exec redis redis-cli XLEN booking-events

# Status dos consumer groups
docker exec redis redis-cli XINFO GROUPS booking-events

# Mensagens pendentes (não processadas)
docker exec redis redis-cli XPENDING booking-events user-service

# Ver últimos eventos
docker exec redis redis-cli XRANGE booking-events - + COUNT 10

# Logs de consumers
docker logs user 2>&1 | grep -i "event\|booking"
docker logs resource 2>&1 | grep -i "event\|booking"
```

#### Documentação Detalhada

Para documentação técnica completa sobre a arquitetura event-driven, consulte:
- **[docs/EVENT_ARCHITECTURE.md](docs/EVENT_ARCHITECTURE.md)**: Guia completo com componentes, fluxos, monitoramento, troubleshooting e boas práticas.

#### Extensibilidade

Para adicionar novos consumers:

1. Registre handlers em `app/main.py`:
```python
import os
import logging
from shared import EventConsumer

logger = logging.getLogger(__name__)

consumer = EventConsumer(
    redis_url=os.getenv("REDIS_URL"),
    stream_name="booking-events",
    group_name="meu-servico",
    consumer_name="worker-1"
)

async def handle_booking_created(event_type: str, payload: dict):
    logger.info(f"Processando {event_type}: {payload}")
    # sua lógica aqui

consumer.register_handler("booking.created", handle_booking_created)
```

2. Inicie consumer no lifespan:
```python
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI
from shared import cleanup_consumer

@asynccontextmanager
async def app_lifespan(app: FastAPI):
    consumer_task = asyncio.create_task(consumer.start())
    yield
    await cleanup_consumer(consumer, consumer_task, logger)
```

### Testes automatizados
- `pytest` configurado para cada serviço com bancos SQLite isolados.
- **Booking**: ciclo completo de reservas, conflitos de horário, validações de janelas de antecedência/cancelamento e flag `can_cancel`.
- **Resource**: fluxo CRUD de categorias e recursos, cálculo de disponibilidade com slots e bloqueio de conflitos.
- **Tenant**: configurações organizacionais, validações de horário comercial e labels customizadas.
- **User**: criação multi-tenant, permissões e validações de email.
- **Event Consumers**: testes de handlers de eventos (user e resource services), processamento de mensagens e graceful shutdown.
- **Shared**: testes do EventConsumer, EventPublisher e utilitários compartilhados.
- Executar toda a suíte: `.venv/bin/pytest`
- Executar serviço específico: `.venv/bin/pytest services/booking/tests`
- Testes usam `@pytest.mark.anyio` para funções async (consistência com FastAPI/anyio)

### Startup compartilhado
- Utilitário `shared.startup.database_lifespan_factory` registra lifespan async com tentativas e logs para criação de tabelas.
- Todos os serviços usam essa fábrica em `app/main.py`, evitando duplicação de código e warnings de API deprecada.

### Migrações (Alembic)
- Cada serviço possui `alembic.ini` e diretório `alembic/` próprios.
- Execução em containers:
	- `docker compose run --rm tenant alembic upgrade head`
	- `docker compose run --rm user alembic upgrade head`
	- `docker compose run --rm resource alembic upgrade head`
	- `docker compose run --rm booking alembic upgrade head`
- Execução local: garantir `PYTHONPATH` apontando para `shared` + serviço antes de rodar Alembic.

### Configuração local do backend

#### Com Docker Compose (recomendado)
```bash
docker compose build        # builda todos os serviços (deps atualizadas)
docker compose up           # sobe postgres, redis, serviços e gateway
docker compose down         # desmonta ambiente
docker compose up --build   # rebuild rápido quando muda requirements/Dockerfile
docker compose up --build --force-recreate # rebuilda tudo (mais adequado para novas dep.)
```
- O compose injeta automaticamente variáveis cruzadas (`TENANT_SERVICE_URL`, `RESERVATION_SERVICE_URL`) para que os serviços consultem configurações e conflitos em tempo real.

#### Ambiente local sem Docker
1. Crie e ative um virtualenv (ou utilize `.venv`): `python3 -m venv .venv && source .venv/bin/activate`.
2. Instale dependências mínimas (ex.: `pip install fastapi uvicorn sqlalchemy alembic httpx` para o serviço de bookings).
3. Exporte o `PYTHONPATH` apontando para `services/shared` e para o serviço desejado:
	```bash
	export PYTHONPATH="$(pwd)/services/shared:$(pwd)/services/booking"
	```
4. Rode as migrações se necessário (`alembic upgrade head`).
5. Inicie o serviço com `uvicorn app.main:app --reload --port 8000` a partir da pasta do serviço.
6. Configure as URLs necessárias para integrações entre serviços:
	```bash
	export TENANT_SERVICE_URL="http://localhost:8001"
	export RESOURCE_SERVICE_URL="http://localhost:8002/resources"
	export USER_SERVICE_URL="http://localhost:8003/users"
	export BOOKING_SERVICE_URL="http://localhost:8004/bookings"
	```
	> **Nota**: Os serviços adicionam automaticamente os prefixes corretos (ex: `/tenants` para tenant service).
7. Repita o processo para cada microserviço em portas diferentes caso queira o ecossistema completo.

### 🔧 Pipeline CI (GitHub Actions)

O pipeline de CI executa automaticamente as seguintes etapas em cada Pull Request aberto, atualizado ou com novos commits para a branch main:

- Lint (Ruff): verifica o estilo e possíveis erros de código em todo o backend.

- Testes por serviço: roda a suíte de testes de cada microsserviço separadamente (tenant, resource, reservation, user).

- Coverage Report: gera relatórios de cobertura (pytest --cov) para cada serviço e disponibiliza como artifact no GitHub Actions.

- Validação dos Dockerfiles: executa docker compose build para garantir que todas as imagens Docker continuam buildando corretamente.

### TODO

#### 🔴 Segurança e Infraestrutura
- [ ] **Hash seguro de senhas**: Substituir implementação placeholder em `user/app/routers/crud.py` por `passlib[bcrypt]` ou `argon2-cffi`.
- [ ] **Variáveis de ambiente**: Extrair credenciais hardcoded do `docker-compose.yml` para `.env` (postgres passwords, redis).
- [ ] **Rate limiting**: Configurar limites por IP/tenant no Nginx usando `limit_req_zone` e `limit_req`.
- [ ] **CORS configurável**: Adicionar configuração de CORS por ambiente (dev permite `*`, prod restringe domínios).

#### 🟡 Observabilidade e Qualidade
- [ ] **Health checks em serviços**: Adicionar endpoints `/health` e `/ready` em cada FastAPI app para monitoramento Docker/Kubernetes.
- [ ] **Logging estruturado**: Padronizar logs JSON com contexto (tenant_id, request_id, trace_id) usando `structlog` ou `python-json-logger`.
- [ ] **Métricas (Prometheus)**: Expor `/metrics` com contadores de requests, latências e erros via `prometheus-fastapi-instrumentator`.
- [ ] **Testes de integração**: Criar suíte validando fluxo completo (tenant settings → disponibilidade → criação de booking com conflitos).
- [ ] **Coverage reports**: Configurar `pytest-cov` para gerar relatórios HTML e manter cobertura acima de 80%.
- [ ] **Lint e formatação**: Adicionar `ruff` ou `black + isort + flake8` em pre-commit hooks e CI.

#### 🟢 Funcionalidades e Evolução
- [x] **Consumidores de eventos**: Implementado com Redis Streams e Consumer Groups. User e Resource services já consomem eventos de booking para notificações e métricas.
- [ ] **Notificações por email/SMS**: Integrar com provedor externo (SendGrid, Twilio) nos handlers de eventos.
- [ ] **Audit trail**: Criar consumer dedicado para persistir histórico completo de eventos em banco separado.
- [ ] **Webhooks para tenants**: Permitir configuração de URLs para receber eventos via HTTP POST.
- [ ] **Autenticação centralizada**: Adicionar serviço de auth com JWT (access + refresh tokens), scopes por tenant e middleware de validação.
- [ ] **Cache Redis**: Cachear `OrganizationSettings` e disponibilidade de recursos com TTL configurável.
- [ ] **Recurring bookings**: Implementar lógica de recorrência usando `recurring_pattern` (diário, semanal, mensal).
- [ ] **Relatórios e analytics**: Endpoints de estatísticas (taxa de ocupação, bookings por categoria, cancelamentos) respeitando políticas do tenant.
- [ ] **Soft delete aprimorado**: Unificar estratégia de exclusão lógica (usar `deleted_at` timestamp em vez de múltiplos `is_active`).

#### 🛠️ Melhorias Técnicas
- [ ] **Requirements files**: Criar `requirements.txt` por serviço (substituir `RUN pip install` inline nos Dockerfiles).
- [ ] **Database migrations CLI**: Script helper para rodar todas as migrações de uma vez (`./migrate.sh all` ou `make migrate`).
- [ ] **Documentação de arquitetura**: Adicionar diagramas (C4, sequence) mostrando comunicação entre serviços e fluxo de eventos.
- [ ] **Error handling padronizado**: Criar middleware global para transformar exceções em respostas JSON consistentes com trace_id.
- [ ] **Dependency injection avançada**: Avaliar uso de `dependency-injector` para gerenciar settings providers e clientes externos.
