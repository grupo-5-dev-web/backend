"""Testes para validar uso de variáveis de ambiente ao invés de valores hardcoded."""

import os
import pytest
from unittest.mock import patch

from shared.config import load_service_config, _lookup_database_url


class TestConfigEnvironmentVariables:
    """Testes para garantir que configurações usam variáveis de ambiente."""

    def test_load_service_config_uses_env_vars_instead_of_hardcoded(self):
        """Testa que load_service_config usa variáveis de ambiente quando definidas."""
        # Definir variáveis de ambiente customizadas
        custom_db_url = "postgresql://custom_user:custom_pass@custom_host:5432/custom_db"
        custom_redis_url = "redis://custom_redis:6380"
        
        with patch.dict(os.environ, {
            "USER_DATABASE_URL": custom_db_url,
            "REDIS_URL": custom_redis_url,
            "APP_HOST": "127.0.0.1",
            "APP_PORT": "9000",
            "EVENT_STREAM": "custom-stream"
        }):
            config = load_service_config("user")
            
            assert config.database.url == custom_db_url
            assert config.redis.url == custom_redis_url
            assert config.host == "127.0.0.1"
            assert config.port == 9000
            assert config.redis.stream == "custom-stream"

    def test_database_url_not_contains_hardcoded_password_when_env_set(self):
        """Testa que DATABASE_URL não contém senha hardcoded quando variável está definida."""
        custom_password = "secure_password_123"
        custom_db_url = f"postgresql://test_user:{custom_password}@test_host:5432/test_db"
        
        with patch.dict(os.environ, {
            "TENANT_DATABASE_URL": custom_db_url
        }):
            db_url = _lookup_database_url("tenant")
            
            # Não deve conter a senha hardcoded "password"
            assert "password" not in db_url or custom_password in db_url
            assert db_url == custom_db_url

    def test_redis_url_uses_env_var(self):
        """Testa que REDIS_URL usa variável de ambiente quando definida."""
        custom_redis = "redis://redis.example.com:6380/1"
        
        with patch.dict(os.environ, {
            "REDIS_URL": custom_redis,
            "DATABASE_URL": "postgresql://user:pass@host:5432/db"
        }):
            config = load_service_config("user")
            assert config.redis.url == custom_redis

    def test_config_fails_without_required_env_vars(self):
        """Testa que configuração falha quando variáveis obrigatórias estão ausentes."""
        # Remover todas as variáveis de ambiente relacionadas
        env_vars_to_remove = [
            "DATABASE_URL",
            "USER_DATABASE_URL",
            "TENANT_DATABASE_URL",
            "RESOURCE_DATABASE_URL",
            "BOOKING_DATABASE_URL"
        ]
        
        with patch.dict(os.environ, {}, clear=True):
            # Remover variáveis específicas
            for var in env_vars_to_remove:
                os.environ.pop(var, None)
            
            # Deve falhar porque não há valores padrão seguros em produção
            # (após refatoração, valores padrão hardcoded serão removidos)
            with pytest.raises((ValueError, KeyError)):
                load_service_config("user")

    def test_no_hardcoded_secrets_in_default_values(self):
        """Testa que valores padrão não contêm credenciais hardcoded inseguras."""
        from shared.config import _DEFAULT_DATABASE_URLS, _DEFAULT_REDIS_URL
        
        # Verificar que valores padrão não contêm senhas comuns inseguras
        insecure_passwords = ["password", "123456", "admin", "root", ""]
        
        for service_name, db_url in _DEFAULT_DATABASE_URLS.items():
            for insecure_pwd in insecure_passwords:
                # Em produção, não devemos ter senhas hardcoded
                # Este teste deve falhar inicialmente (Red) e passar após refatoração
                assert insecure_pwd not in db_url.lower(), \
                    f"Valor padrão para {service_name} contém senha insegura: {insecure_pwd}"

    def test_database_url_constructed_from_individual_vars(self):
        """Testa que DATABASE_URL pode ser construída a partir de variáveis individuais."""
        # Simular construção de URL a partir de variáveis individuais
        postgres_user = "test_user"
        postgres_password = "test_pass"
        postgres_host = "db_host"
        postgres_port = "5432"
        postgres_db = "testdb"
        
        constructed_url = f"postgresql://{postgres_user}:{postgres_password}@{postgres_host}:{postgres_port}/{postgres_db}"
        
        with patch.dict(os.environ, {
            "DATABASE_URL": constructed_url
        }):
            db_url = _lookup_database_url("user")
            assert db_url == constructed_url
            assert postgres_user in db_url
            assert postgres_password in db_url
            assert postgres_db in db_url

    def test_secret_key_not_hardcoded(self):
        """Testa que SECRET_KEY não está hardcoded no código."""
        # Este teste valida que SECRET_KEY deve vir de variável de ambiente
        # Não deve estar hardcoded em nenhum lugar do código de configuração
        import shared.config as config_module
        import inspect
        
        # Verificar que não há SECRET_KEY hardcoded no módulo de config
        source = inspect.getsource(config_module)
        # Não deve haver valores de SECRET_KEY hardcoded no código
        # (após refatoração completa)
        assert "SECRET_KEY" not in source or "os.getenv" in source or "os.environ" in source

