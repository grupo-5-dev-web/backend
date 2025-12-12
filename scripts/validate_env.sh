#!/bin/bash

# Script de validação de variáveis de ambiente
# Valida que todas as variáveis necessárias estão definidas no .env

set -e

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

ENV_FILE="${1:-.env}"

if [ ! -f "$ENV_FILE" ]; then
    echo -e "${RED}❌ Arquivo .env não encontrado: $ENV_FILE${NC}"
    echo -e "${YELLOW}💡 Dica: Copie .env.example para .env e configure as variáveis${NC}"
    exit 1
fi

echo "════════════════════════════════════════════════════════"
echo "   VALIDAÇÃO DE VARIÁVEIS DE AMBIENTE                  "
echo "════════════════════════════════════════════════════════"
echo ""

# Carregar variáveis do .env
set -a
source "$ENV_FILE"
set +a

ERRORS=0
WARNINGS=0

# Função para validar variável obrigatória
validate_required() {
    local var_name=$1
    local var_value="${!var_name}"
    
    if [ -z "$var_value" ]; then
        echo -e "${RED}✗ $var_name: NÃO DEFINIDA${NC}"
        ERRORS=$((ERRORS + 1))
        return 1
    else
        echo -e "${GREEN}✓ $var_name: definida${NC}"
        return 0
    fi
}

# Função para validar formato de URL de banco de dados
validate_db_url_format() {
    local var_name=$1
    local var_value="${!var_name}"
    
    if [ -z "$var_value" ]; then
        return 0  # Variável opcional
    fi
    
    if [[ ! "$var_value" =~ ^postgresql://.+:.+@.+:[0-9]+/.+$ ]]; then
        echo -e "${YELLOW}⚠ $var_name: Formato inválido (esperado: postgresql://user:pass@host:port/db)${NC}"
        WARNINGS=$((WARNINGS + 1))
        return 1
    fi
    
    return 0
}

# Função para validar que não há valores padrão inseguros
validate_no_insecure_defaults() {
    local var_name=$1
    local var_value="${!var_name}"
    local insecure_values=("password" "123456" "admin" "root" "test" "")
    
    for insecure in "${insecure_values[@]}"; do
        if [ "$var_value" = "$insecure" ]; then
            echo -e "${RED}✗ $var_name: Valor inseguro detectado: '$insecure'${NC}"
            ERRORS=$((ERRORS + 1))
            return 1
        fi
    done
    
    return 0
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "1. VALIDANDO VARIÁVEIS OBRIGATÓRIAS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# PostgreSQL - Credenciais gerais
validate_required "POSTGRES_USER"
validate_required "POSTGRES_PASSWORD"
validate_no_insecure_defaults "POSTGRES_PASSWORD"

# PostgreSQL - Nomes de banco de dados
validate_required "POSTGRES_DB_USER"
validate_required "POSTGRES_DB_TENANT"
validate_required "POSTGRES_DB_RESOURCE"
validate_required "POSTGRES_DB_BOOKING"

# Redis
validate_required "REDIS_URL"
validate_db_url_format "REDIS_URL"

# JWT/Security
validate_required "SECRET_KEY"
if [ -n "$SECRET_KEY" ] && [ ${#SECRET_KEY} -lt 32 ]; then
    echo -e "${YELLOW}⚠ SECRET_KEY: Muito curta (mínimo recomendado: 32 caracteres)${NC}"
    WARNINGS=$((WARNINGS + 1))
fi

validate_required "JWT_ALGORITHM"
validate_required "ACCESS_TOKEN_EXPIRE_HOURS"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "2. VALIDANDO FORMATO DE URLs DE BANCO DE DADOS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Validar URLs de banco de dados se definidas diretamente
validate_db_url_format "USER_DATABASE_URL"
validate_db_url_format "TENANT_DATABASE_URL"
validate_db_url_format "RESOURCE_DATABASE_URL"
validate_db_url_format "BOOKING_DATABASE_URL"
validate_db_url_format "DATABASE_URL"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "3. VALIDANDO VALORES SEGUROS"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

# Validar que senhas não são valores padrão inseguros
validate_no_insecure_defaults "POSTGRES_PASSWORD"

# Validar que SECRET_KEY não é um valor padrão comum
if [ -n "$SECRET_KEY" ]; then
    common_secrets=(
        "secret"
        "changeme"
        "default"
        "12345678901234567890123456789012"
    )
    for common in "${common_secrets[@]}"; do
        if [ "$SECRET_KEY" = "$common" ]; then
            echo -e "${RED}✗ SECRET_KEY: Valor padrão inseguro detectado${NC}"
            ERRORS=$((ERRORS + 1))
            break
        fi
    done
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "                RESUMO DA VALIDAÇÃO                    "
echo "════════════════════════════════════════════════════════"

if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
    echo -e "${GREEN}✅ Todas as validações passaram!${NC}"
    exit 0
elif [ $ERRORS -eq 0 ]; then
    echo -e "${YELLOW}⚠ Validação concluída com $WARNINGS aviso(s)${NC}"
    exit 0
else
    echo -e "${RED}❌ Validação falhou com $ERRORS erro(s) e $WARNINGS aviso(s)${NC}"
    exit 1
fi

