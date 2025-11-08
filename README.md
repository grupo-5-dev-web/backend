### 🗂 Estrutura de Pastas

As pastas estão estruturadas da seguinte maneira, a exemplo de **Tenant**:

```text
├── tenant/
│   └── app/
│       ├── main.py                 # Ponto de entrada da aplicação FastAPI
│       ├── core/                   # Configurações principais (ex: banco de dados, env)
│       ├── models/                 # Modelos ORM que representam as tabelas (Entidades do banco)
│       ├── routers/                # Para as operações do serviço
│       │   ├── __init__.py         
│       │   ├── crud.py             # Operações de banco de dados (Create, Read, Update, Delete)
│       │   ├── endpoints.py        # Define os endpoints da API (lida com as requisições HTTP)
│       │   └── validators.py       # Regras e validações de negócio do serviço específico
│       ├── schemas/                # Modelos Pydantic (validação de entrada e saída)
│       │   └── tenant_schema.py    # Definidas as estruturas de dados específicas do Tenant para validação
│       └── utils/                  # Funções auxiliares e utilitárias (caso necessário)

```

Cada pasta é um serviço dentro da arquitetura de microsserviços do projeto.

### Rodando o projeto
No terminal da pasta raíz, rodar:
1. Para construir imagens docker
```
docker compose build
```
2. Para subir os containers
```
docker compose up
```
3. Se necessário:

parar containers
```
docker compose down
```

rebuildar containers (opcional, reconstrói imagens e reinicia containers)
```
docker-compose up --build
```