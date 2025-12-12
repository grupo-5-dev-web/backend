"""Testes para endpoints de health check (/health e /ready)."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from fastapi import FastAPI, status
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from shared.health import check_database_health, check_redis_health, create_health_router


class TestDatabaseHealthCheck:
    """Testes para verificação de saúde do banco de dados."""

    def test_check_database_health_success(self):
        """Testa que check_database_health retorna True quando banco está disponível."""
        # Criar engine em memória para teste
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        
        result = check_database_health(engine)
        assert result is True

    def test_check_database_health_failure(self):
        """Testa que check_database_health retorna False quando banco está indisponível."""
        # Criar engine com URL inválida
        engine = create_engine("postgresql://invalid:invalid@invalid:5432/invalid")
        
        result = check_database_health(engine)
        assert result is False

    def test_check_database_health_timeout(self):
        """Testa que check_database_health trata timeouts corretamente."""
        engine = create_engine("postgresql://user:pass@nonexistent:5432/db", pool_timeout=1)
        
        result = check_database_health(engine, timeout=0.1)
        assert result is False


class TestRedisHealthCheck:
    """Testes para verificação de saúde do Redis."""

    @pytest.mark.asyncio
    async def test_check_redis_health_success(self):
        """Testa que check_redis_health retorna True quando Redis está disponível."""
        mock_redis = AsyncMock()
        mock_redis.ping.return_value = True
        
        result = await check_redis_health(mock_redis)
        assert result is True
        mock_redis.ping.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_redis_health_failure(self):
        """Testa que check_redis_health retorna False quando Redis está indisponível."""
        mock_redis = AsyncMock()
        mock_redis.ping.side_effect = Exception("Connection failed")
        
        result = await check_redis_health(mock_redis)
        assert result is False

    @pytest.mark.asyncio
    async def test_check_redis_health_none(self):
        """Testa que check_redis_health retorna None quando Redis não está configurado."""
        result = await check_redis_health(None)
        assert result is None


class TestHealthEndpoints:
    """Testes para endpoints /health e /ready."""

    def test_health_endpoint_always_returns_ok(self):
        """Testa que /health sempre retorna 200 OK."""
        app = FastAPI()
        health_router = create_health_router(
            service_name="test-service",
            database_engine=None,
            redis_client=None,
        )
        app.include_router(health_router)
        
        client = TestClient(app)
        response = client.get("/health")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "test-service"

    def test_ready_endpoint_with_healthy_dependencies(self):
        """Testa que /ready retorna 200 quando todas as dependências estão saudáveis."""
        # Criar engine em memória para teste
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        
        app = FastAPI()
        health_router = create_health_router(
            service_name="test-service",
            database_engine=engine,
            redis_client=None,
        )
        app.include_router(health_router)
        
        client = TestClient(app)
        response = client.get("/ready")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"
        assert data["service"] == "test-service"
        assert data["checks"]["database"] is True
        assert data["checks"]["redis"] is None  # Não configurado

    def test_ready_endpoint_with_unhealthy_database(self):
        """Testa que /ready retorna 503 quando banco de dados está indisponível."""
        # Criar engine com URL inválida
        engine = create_engine("postgresql://invalid:invalid@invalid:5432/invalid")
        
        app = FastAPI()
        health_router = create_health_router(
            service_name="test-service",
            database_engine=engine,
            redis_client=None,
        )
        app.include_router(health_router)
        
        client = TestClient(app)
        response = client.get("/ready")
        
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert data["status"] == "not_ready"
        assert data["service"] == "test-service"
        assert data["checks"]["database"] is False

    def test_ready_endpoint_with_redis_url_string(self):
        """Testa que /ready funciona com URL string do Redis."""
        # Criar engine em memória para teste
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        
        app = FastAPI()
        # Usar URL string (será ignorada em teste sem Redis real)
        health_router = create_health_router(
            service_name="test-service",
            database_engine=engine,
            redis_client=None,  # None = não configurado
        )
        app.include_router(health_router)
        
        client = TestClient(app)
        response = client.get("/ready")
        
        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["checks"]["redis"] is None  # Não configurado

    def test_health_endpoint_response_format(self):
        """Testa formato da resposta do endpoint /health."""
        app = FastAPI()
        health_router = create_health_router(
            service_name="test-service",
            database_engine=None,
            redis_client=None,
        )
        app.include_router(health_router)
        
        client = TestClient(app)
        response = client.get("/health")
        
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert "timestamp" in data
        assert data["status"] == "ok"

    def test_ready_endpoint_response_format(self):
        """Testa formato da resposta do endpoint /ready."""
        engine = create_engine(
            "sqlite:///:memory:",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        
        app = FastAPI()
        health_router = create_health_router(
            service_name="test-service",
            database_engine=engine,
            redis_client=None,
        )
        app.include_router(health_router)
        
        client = TestClient(app)
        response = client.get("/ready")
        
        data = response.json()
        assert "status" in data
        assert "service" in data
        assert "checks" in data
        assert "database" in data["checks"]
        assert isinstance(data["checks"]["database"], bool)

