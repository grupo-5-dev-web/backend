## White Label Resource Scheduling Platform – Backend

A plataforma permite que diferentes negócios configurem regras próprias de agendamento (recursos humanos, equipamentos ou espaços) utilizando a mesma base white label. O backend está sendo estruturado para suportar multi-tenant, regras configuráveis por organização e propagação de eventos para outros domínios interessados.

### Stack e diretrizes
- Python 3.11 + FastAPI (serviços leves e independentes)
- SQLAlchemy + PostgreSQL (cada contexto com banco dedicado e JSONB para campos flexíveis)
- Redis (fila/transporte inicial para eventos de reserva; pode evoluir para Kafka)
- Nginx como gateway/reverso proxy e roteador de serviços
- Conteinerização via Docker e orquestração local com `docker compose`

### Estrutura do repositório
```text
backend/
├── docker-compose.yml
├── infra/
│   └── nginx/
└── services/
	├── shared/
	├── reservation/
	├── resource/
	├── tenant/
	└── user/
```
- `services/shared`: utilidades comuns (configuração centralizada, mensageria) copiadas para todos os contêineres.
- `services/*`: cada serviço FastAPI isolado, com seu `Dockerfile` e a pasta `app/` contendo camadas (`core`, `models`, `routers`, `schemas`).
- `infra/nginx`: reverse proxy que concentra a exposição pública e roteia chamadas para os serviços internos.
- `docker-compose.yml`: orquestra os serviços de aplicação, bancos PostgreSQL por domínio e serviços de suporte.

> Para executar serviços localmente sem Docker, exporte `PYTHONPATH="$(pwd)/services/shared:$(pwd)/services/<serviço>"` antes de iniciar o `uvicorn`, garantindo que o pacote `shared` seja encontrado.

### Serviços e responsabilidades
- `tenant`: gerencia configurações da organização e metadados white label (nome, domínio, identidade visual, labels customizadas, regras de agendamento padrão).
- `resource`: mantém categorias, recursos físicos/humanos/software e disponibilidade de cada item.
- `user`: guarda perfis, permissões e metadados dependentes do tipo de negócio (admin, manager, professional, client).
- `reservation`: centraliza políticas de booking, recorrência, conflitos, cancelamentos e emite eventos para interessadas (notificações, billing, BI).

Cada serviço expõe documentação interativa no endereço padrão do container (`/docs` via Swagger UI e `/redoc`). Quando executados pelo `nginx` local, os prefixos externos ficam:
- `GET http://localhost:8000/tenants/docs`
- `GET http://localhost:8000/resources/docs`
- `GET http://localhost:8000/users/docs`
- `GET http://localhost:8000/reservations/docs`

### Modelagem e alinhamento ao diagrama UML
- `organization_settings`: consolidar timezone, horários úteis, intervalos mínimos, limites de antecedência e rótulos customizados.
- `resource_categories` → `resources`: manter metadados flexíveis (`metadata`/`attributes`) e horários por recurso (`availability_schedule`).
- `users`: perfil, permissões agregadas e campos específicos por tipo de tenant.
- `bookings`: assegurar validações de conflito, janelas comerciais e cancelamentos (campos de auditoria e recorrência).
- Recomenda-se criar tabelas auxiliares para auditoria/event sourcing (por exemplo `booking_events`) e vincular histórico de alterações relevantes.

### Eventos e escalabilidade
- Reservas geram eventos (`booking.created`, `booking.cancelled`, `booking.status_changed`) publicados via Redis Stream/RabbitMQ/Kafka.
- Consumidores potenciais: notificações, sincronização externa (webhooks), dashboards/BI, billing.
- Garantir idempotência dos handlers e versão do schema (event envelopes com `event_version`).
- Multi-tenant: cada requisição deve carregar `X-Tenant-ID`/`X-Tenant-Domain`; os serviços consultam `tenant` para validar regras e aplicar timezone.
- Pensar em circuit breakers entre serviços (HTTP/REST) e caching leve para configurações estáticas (`organization_settings`).

### Ambiente de desenvolvimento
- Construir imagens: `docker compose build`
- Subir stack completa: `docker compose up`
- Parar containers: `docker compose down`
- Rebuild específico em caso de alterações de dependências: `docker compose up --build`

### Próximos passos sugeridos
- Expandir modelos SQLAlchemy nos serviços `resource`, `user` e `reservation` para refletir o esquema completo descrito acima.
- Implementar camada de autenticação/autorização unificada (JWT + scopes por serviço).
- Introduzir módulo de mensageria compartilhado (`shared/messaging`) para padronizar emissão/consumo de eventos.
- Criar testes automatizados (unitários + integração com banco em memória) para validações críticas de reserva e conflito.
- Atualizar o diagrama UML incorporando entidades auxiliares (auditoria, eventos, custom fields) e relacionamento multi-tenant explícito.