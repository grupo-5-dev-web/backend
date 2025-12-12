"""Testes para configuração de CORS."""

import os
import pytest
from unittest.mock import patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from fastapi.middleware.cors import CORSMiddleware

from shared.cors import configure_cors, get_cors_origins


class TestCorsConfiguration:
    """Testes para configuração de CORS."""

    def test_get_cors_origins_development_allows_all(self):
        """Testa que em desenvolvimento permite todos os domínios (*)."""
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            origins = get_cors_origins()
            assert origins == ["*"]

    def test_get_cors_origins_production_restricts_domains(self):
        """Testa que em produção restringe a domínios específicos."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com,https://admin.example.com"
        }):
            origins = get_cors_origins()
            assert origins == ["https://app.example.com", "https://admin.example.com"]

    def test_get_cors_origins_production_no_config_raises_error(self):
        """Testa que em produção sem CORS_ORIGINS configurado levanta erro."""
        with patch.dict(os.environ, {"ENVIRONMENT": "production"}, clear=True):
            with pytest.raises(ValueError, match="CORS_ORIGINS must be set in production"):
                get_cors_origins()

    def test_get_cors_origins_defaults_to_development(self):
        """Testa que sem ENVIRONMENT definido, assume desenvolvimento."""
        with patch.dict(os.environ, {}, clear=True):
            origins = get_cors_origins()
            assert origins == ["*"]

    def test_get_cors_origins_handles_whitespace(self):
        """Testa que remove espaços em branco dos domínios."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": " https://app.example.com , https://admin.example.com "
        }):
            origins = get_cors_origins()
            assert origins == ["https://app.example.com", "https://admin.example.com"]

    def test_get_cors_origins_empty_string_in_production_raises_error(self):
        """Testa que string vazia em produção levanta erro."""
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": ""
        }):
            with pytest.raises(ValueError, match="CORS_ORIGINS must be set in production"):
                get_cors_origins()


class TestConfigureCors:
    """Testes para função configure_cors."""

    def test_configure_cors_adds_middleware(self):
        """Testa que configure_cors adiciona middleware CORS ao app."""
        app = FastAPI()
        
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            configure_cors(app)
        
        # Verificar que middleware foi adicionado
        middleware_classes = [type(m).__name__ for m in app.user_middleware]
        assert "CORSMiddleware" in middleware_classes

    def test_configure_cors_development_allows_all(self):
        """Testa que em desenvolvimento permite todos os métodos e headers."""
        app = FastAPI()
        
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            configure_cors(app)
        
        client = TestClient(app)
        
        # Testar OPTIONS request (preflight)
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "Content-Type",
            }
        )
        
        assert response.status_code == 200
        assert response.headers.get("Access-Control-Allow-Origin") == "*"
        assert response.headers.get("Access-Control-Allow-Methods") is not None
        assert response.headers.get("Access-Control-Allow-Headers") is not None

    def test_configure_cors_production_restricts_origins(self):
        """Testa que em produção restringe a origens específicas."""
        app = FastAPI()
        
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com"
        }):
            configure_cors(app)
        
        client = TestClient(app)
        
        # Testar com origem permitida
        response = client.options(
            "/",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "POST",
            }
        )
        
        assert response.status_code == 200
        assert response.headers.get("Access-Control-Allow-Origin") == "https://app.example.com"
        
        # Testar com origem não permitida
        response = client.options(
            "/",
            headers={
                "Origin": "https://evil.com",
                "Access-Control-Request-Method": "POST",
            }
        )
        
        # Deve retornar 200 mas sem Access-Control-Allow-Origin
        assert response.status_code == 200
        assert response.headers.get("Access-Control-Allow-Origin") != "https://evil.com"

    def test_configure_cors_allows_credentials_in_production(self):
        """Testa que em produção permite credentials quando configurado."""
        app = FastAPI()
        
        with patch.dict(os.environ, {
            "ENVIRONMENT": "production",
            "CORS_ORIGINS": "https://app.example.com",
            "CORS_ALLOW_CREDENTIALS": "true"
        }):
            configure_cors(app)
        
        client = TestClient(app)
        
        response = client.options(
            "/",
            headers={
                "Origin": "https://app.example.com",
                "Access-Control-Request-Method": "POST",
            }
        )
        
        assert response.headers.get("Access-Control-Allow-Credentials") == "true"

    def test_configure_cors_defaults_credentials_false(self):
        """Testa que por padrão não permite credentials."""
        app = FastAPI()
        
        with patch.dict(os.environ, {"ENVIRONMENT": "development"}):
            configure_cors(app)
        
        client = TestClient(app)
        
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            }
        )
        
        # Em desenvolvimento com *, credentials não deve estar presente
        # (CORS spec: quando Access-Control-Allow-Origin é *, credentials não pode ser true)
        assert response.headers.get("Access-Control-Allow-Credentials") != "true"

    def test_configure_cors_custom_max_age(self):
        """Testa que configura max_age quando especificado."""
        app = FastAPI()
        
        with patch.dict(os.environ, {
            "ENVIRONMENT": "development",
            "CORS_MAX_AGE": "3600"
        }):
            configure_cors(app)
        
        client = TestClient(app)
        
        response = client.options(
            "/",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
            }
        )
        
        assert response.headers.get("Access-Control-Max-Age") == "3600"

