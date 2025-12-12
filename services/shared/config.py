"""Configuration helpers reused by microservices."""

from __future__ import annotations

from dataclasses import dataclass
import os
import warnings
from typing import Dict, Optional

# Valores padrão apenas para desenvolvimento local
# ⚠️ AVISO: Estes valores contêm credenciais inseguras e devem ser usados APENAS em desenvolvimento
# Em produção, todas as variáveis de ambiente devem ser definidas explicitamente
_DEFAULT_DATABASE_URLS: Dict[str, str] = {
    "tenant": "postgresql://user:password@db_tenant:5432/tenantdb",
    "resource": "postgresql://user:password@db_resource:5432/resourcedb",
    "booking": "postgresql://user:password@db_booking:5432/bookingdb",
    "user": "postgresql://user:password@db_user:5432/userdb",
}

_DEFAULT_REDIS_URL = "redis://redis:6379/0"
_DEFAULT_EVENT_STREAM = "booking-events"
_DEFAULT_HOST = "0.0.0.0"
_DEFAULT_PORT = 8000

# Valores inseguros que não devem ser usados em produção
_INSECURE_PASSWORDS = {"password", "123456", "admin", "root", "test", ""}
_INSECURE_SECRET_KEYS = {
    "secret",
    "changeme",
    "default",
    "ca76563c37354029ac4e02d96427a444dce2f9401ddb366afee9e70219885ef44add634887d2956d1cabaec071d4b78d61d4b84bfae6aec80213f0a27d350864",
}


@dataclass(frozen=True)
class DatabaseConfig:
    url: str


@dataclass(frozen=True)
class RedisConfig:
    url: str
    stream: str


@dataclass(frozen=True)
class ServiceConfig:
    name: str
    host: str
    port: int
    database: DatabaseConfig
    redis: RedisConfig


def _lookup_database_url(service_name: str) -> str:
    """Lookup database URL from environment variables with fallback to defaults.
    
    ⚠️ AVISO: Valores padrão contêm credenciais inseguras e devem ser usados
    apenas em desenvolvimento. Em produção, defina variáveis de ambiente.
    """
    service_env = f"{service_name.upper()}_DATABASE_URL"
    db_url = (
        os.getenv(service_env)
        or os.getenv("DATABASE_URL")
        or _DEFAULT_DATABASE_URLS.get(service_name, "")
    )
    
    # Validar que não estamos usando valores padrão inseguros em produção
    if db_url and db_url in _DEFAULT_DATABASE_URLS.values():
        # Verificar se estamos em produção (não desenvolvimento)
        env = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
        if env in ("production", "prod"):
            raise ValueError(
                f"Valores padrão de banco de dados não podem ser usados em produção. "
                f"Defina {service_env} ou DATABASE_URL como variável de ambiente."
            )
        # Em desenvolvimento, apenas avisar
        warnings.warn(
            f"Usando valor padrão de banco de dados para {service_name}. "
            f"Em produção, defina {service_env} ou DATABASE_URL.",
            UserWarning,
            stacklevel=2
        )
    
    return db_url


def _validate_no_insecure_password(password: Optional[str], context: str = "") -> None:
    """Valida que uma senha não é um valor padrão inseguro."""
    if password and password.lower() in _INSECURE_PASSWORDS:
        env = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
        if env in ("production", "prod"):
            raise ValueError(
                f"Senha insegura detectada em {context}. "
                "Use uma senha forte em produção."
            )
        warnings.warn(
            f"Senha insegura detectada em {context}. "
            "Use uma senha forte em produção.",
            UserWarning,
            stacklevel=3
        )


def _validate_secret_key(secret_key: Optional[str]) -> None:
    """Valida que SECRET_KEY não é um valor padrão inseguro."""
    if not secret_key:
        return
    
    if secret_key in _INSECURE_SECRET_KEYS:
        env = os.getenv("ENVIRONMENT", os.getenv("ENV", "development")).lower()
        if env in ("production", "prod"):
            raise ValueError(
                "SECRET_KEY não pode ser um valor padrão inseguro em produção. "
                "Gere uma chave segura com: openssl rand -hex 64"
            )
        warnings.warn(
            "SECRET_KEY parece ser um valor padrão inseguro. "
            "Em produção, gere uma chave segura com: openssl rand -hex 64",
            UserWarning,
            stacklevel=3
        )
    
    if len(secret_key) < 32:
        warnings.warn(
            f"SECRET_KEY muito curta ({len(secret_key)} caracteres). "
            "Recomendado mínimo de 32 caracteres.",
            UserWarning,
            stacklevel=3
        )


def load_service_config(service_name: str) -> ServiceConfig:
    """Aggregate configuration for a given service using env vars with sane fallbacks.
    
    ⚠️ AVISO: Valores padrão são apenas para desenvolvimento.
    Em produção, defina todas as variáveis de ambiente necessárias.
    
    Args:
        service_name: Nome do serviço (user, tenant, resource, booking)
        
    Returns:
        ServiceConfig: Configuração do serviço
        
    Raises:
        ValueError: Se DATABASE_URL não estiver configurado ou se valores
                   inseguros forem detectados em produção
    """

    normalized_name = service_name.lower()
    db_url = _lookup_database_url(normalized_name)
    if not db_url:
        raise ValueError(
            f"DATABASE_URL not configured for service '{normalized_name}'. "
            f"Set DATABASE_URL or {normalized_name.upper()}_DATABASE_URL."
        )

    # Validar senha no DATABASE_URL se possível extrair
    if ":" in db_url and "@" in db_url:
        try:
            # Tentar extrair senha da URL (formato: postgresql://user:pass@host:port/db)
            auth_part = db_url.split("@")[0].split("://")[1]
            if ":" in auth_part:
                password = auth_part.split(":")[1]
                _validate_no_insecure_password(password, f"DATABASE_URL para {service_name}")
        except (IndexError, ValueError):
            pass  # Se não conseguir extrair, continua sem validação

    host = os.getenv("APP_HOST", _DEFAULT_HOST)
    port = int(os.getenv("APP_PORT", str(_DEFAULT_PORT)))

    redis_url = os.getenv("REDIS_URL", _DEFAULT_REDIS_URL)
    stream_name = os.getenv("EVENT_STREAM", _DEFAULT_EVENT_STREAM)

    # Validar SECRET_KEY se disponível
    secret_key = os.getenv("SECRET_KEY")
    if secret_key:
        _validate_secret_key(secret_key)

    return ServiceConfig(
        name=normalized_name,
        host=host,
        port=port,
        database=DatabaseConfig(url=db_url),
        redis=RedisConfig(url=redis_url, stream=stream_name),
    )
