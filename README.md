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
    ├── resource/
    ├── reservation/
    └── user/
```
- `services/shared`: utilidades comuns (config, mensageria, helpers de startup) copiadas para cada container.
- `services/<service>`: código FastAPI isolado, com pastas `core`, `models`, `routers`, `schemas` e testes.
- `infra/nginx`: gateway que expõe os serviços e disponibiliza uma landing page com links de Swagger.

> Execução local sem Docker: exporte `PYTHONPATH="$(pwd)/services/shared:$(pwd)/services/<serviço>"` e rode `uvicorn app.main:app --reload` dentro da pasta do serviço.

### Landing page e documentação
- `http://localhost:8000/` (gateway) exibe uma página com links para os Swagger UI de cada serviço.
- Serviços expõem documentação em:
	- `http://localhost:8000/tenants/docs`
	- `http://localhost:8000/resources/docs`
	- `http://localhost:8000/users/docs`
	- `http://localhost:8000/reservations/docs`
- Cada endpoint de reserva documenta respostas de erro (400/409) alinhadas às regras de negócio de agendamento.

### Serviços e responsabilidades
- **tenant**: gerenciamento de tenants, configurações (`OrganizationSettings`), labels customizadas, comunicação com outros domínios.
- **resource**: categorias, recursos, disponibilidade diária (`availability_schedule`) e atributos dinâmicos.
- **user**: perfis multi-tenant, papéis e permissões.
- **reservation**: criação/atualização/cancelamento de bookings com validações baseadas nas configurações do tenant (horário comercial, antecedência, intervalo, janela de cancelamento) e emissão de eventos em Redis Streams.

### Fluxos implementados
- **Regras de agendamento**: provider compartilhado (`services/shared/organization.py`) recupera `OrganizationSettings` do serviço de tenant (HTTP via `httpx`) ou usa defaults. CRUD de bookings verifica horário útil, antecipação máxima, duração múltipla do intervalo e janela de cancelamento.
- **Política de cancelamento**: listagens de reservas (`GET /reservations/bookings/`) incluem `can_cancel` calculado dinamicamente, refletindo a janela configurada pelo tenant.
- **Disponibilidade de recursos**: `GET /resources/{id}/availability` monta slots alinhados ao expediente e intervalo do tenant, consulta o serviço de reservas via `RESERVATION_SERVICE_URL` para bloquear conflitos e responde com timezone normalizado.
- **Eventos de reserva**: toda mudança (`booking.created`, `booking.updated`, `booking.cancelled`, `booking.status_changed`) vai para o Redis Stream definido em `shared.EventPublisher`, viabilizando consumidores assíncronos (notificações, analytics, billing).
- **Landing page unificada**: gateway Nginx serve `http://localhost:8000/` com atalhos para a documentação Swagger de cada serviço.

### Testes automatizados
- `pytest` configurado para cada serviço com bancos SQLite isolados.
- Reservas: ciclo completo, conflitos, validações de horário, janelas de cancelamento e flag `can_cancel`.
- Recursos: fluxo CRUD e cálculo de disponibilidade (incluindo datas passadas e alinhamento de intervalos).
- Executar toda a suíte: `.venv/bin/pytest`
- Executar apenas reservas: `.venv/bin/pytest services/reservation/tests`
- Executar apenas recursos: `.venv/bin/pytest services/resource/tests`

### Startup compartilhado
- Utilitário `shared.startup.database_lifespan_factory` registra lifespan async com tentativas e logs para criação de tabelas.
- Todos os serviços usam essa fábrica em `app/main.py`, evitando duplicação de código e warnings de API deprecada.

### Migrações (Alembic)
- Cada serviço possui `alembic.ini` e diretório `alembic/` próprios.
- Execução em containers:
	- `docker compose run --rm tenant alembic upgrade head`
	- `docker compose run --rm resource alembic upgrade head`
	- `docker compose run --rm user alembic upgrade head`
	- `docker compose run --rm reservation alembic upgrade head`
- Execução local: garantir `PYTHONPATH` apontando para `shared` + serviço antes de rodar Alembic.

### Configuração local do backend

#### Com Docker Compose (recomendado)
```bash
docker compose build        # builda todos os serviços (deps atualizadas)
docker compose up           # sobe postgres, redis, serviços e gateway
docker compose down         # desmonta ambiente
docker compose up --build   # rebuild rápido quando muda requirements/Dockerfile
```
- O compose injeta automaticamente variáveis cruzadas (`TENANT_SERVICE_URL`, `RESERVATION_SERVICE_URL`) para que os serviços consultem configurações e conflitos em tempo real.

#### Ambiente local sem Docker
1. Crie e ative um virtualenv (ou utilize `.venv`): `python3 -m venv .venv && source .venv/bin/activate`.
2. Instale dependências mínimas (ex.: `pip install fastapi uvicorn sqlalchemy alembic httpx` para o serviço de reservas).
3. Exporte o `PYTHONPATH` apontando para `services/shared` e para o serviço desejado:
	```bash
	export PYTHONPATH="$(pwd)/services/shared:$(pwd)/services/reservation"
	```
4. Rode as migrações se necessário (`alembic upgrade head`).
5. Inicie o serviço com `uvicorn app.main:app --reload --port 8000` a partir da pasta do serviço.
6. Configure as URLs necessárias para integrações entre serviços, por exemplo:
	```bash
	export TENANT_SERVICE_URL="http://localhost:8001/tenants"
	export RESERVATION_SERVICE_URL="http://localhost:8002/reservations"
	```
	ajustando as portas conforme os serviços que estiverem rodando localmente.
7. Repita o processo para cada microserviço em portas diferentes caso queira o ecossistema completo.

### TODO
- Implementar consumidores para os eventos publicados no Redis (ex.: notificações, faturamento, audit trail).
- Adicionar autenticação/autorização centralizada (JWT + scopes) e propagar identidade do usuário entre serviços.
- Expandir endpoints de relatórios/analytics aplicando as mesmas políticas de agenda do tenant.
- Criar testes de integração entre serviços validando disponibilidade + reserva em tempo real.
- Automatizar lint/CI com execução de testes e verificação de segurança.
