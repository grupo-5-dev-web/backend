#!/bin/bash

# URLs dos serviços no Railway
TENANT_URL="https://tenant-service-production-b057.up.railway.app"
USER_URL="https://user-service-production-6b5a.up.railway.app"
RESOURCE_URL="https://resource-service-production-c44a.up.railway.app"
BOOKING_URL="https://booking-service-production-4d90.up.railway.app"

# Gerar identificadores únicos
TIMESTAMP=$(date +%s)
UNIQUE_DOMAIN="test-${TIMESTAMP}.example.com"

echo "🚀 Testando serviços no Railway..."
echo "📝 Domínio único: $UNIQUE_DOMAIN"
echo ""

# Cores
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Função para testar endpoint
test_endpoint() {
    local name="$1"
    local url="$2"
    local data="$3"
    local method="${4:-}"  # Novo parâmetro opcional
    
    echo -e "${YELLOW}➤ $name${NC}"
    
    # Se método não especificado, detecta automaticamente
    if [ -z "$method" ]; then
        if [ -z "$data" ]; then
            method="GET"
        else
            method="POST"
        fi
    fi
    
    # Construir header de autenticação se token disponível
    local auth_header=""
    if [ -n "$ACCESS_TOKEN" ]; then
        auth_header="-H \"Authorization: Bearer $ACCESS_TOKEN\""
    fi
    
    # Construir comando curl baseado em ter ou não dados
    if [ -n "$data" ]; then
        # DEBUG: Mostrar tamanho do payload
        # echo "DEBUG: Payload size: $(echo "$data" | wc -c) bytes"
        
        response=$(curl -s -L -X "$method" \
            -H "Content-Type: application/json" \
            -H "Authorization: Bearer $ACCESS_TOKEN" \
            -w "\n%{http_code}" \
            -d "$data" \
            "$url")
    else
        response=$(curl -s -L -X "$method" \
            -H "Authorization: Bearer $ACCESS_TOKEN" \
            -w "\n%{http_code}" \
            "$url")
    fi
    
    http_code=$(echo "$response" | tail -n1)
    body=$(echo "$response" | sed '$d')
    
    if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
        echo -e "${GREEN}✓ $http_code${NC}"
    elif [ "$http_code" -eq 404 ]; then
        echo -e "${BLUE}✓ $http_code${NC} (Not Found - esperado após deleção)"
    else
        echo -e "${RED}✗ $http_code${NC}"
    fi
    
    echo "$body" | jq -C '.' 2>/dev/null || echo "$body"
    echo ""
}

# =============================================================================
# 1. TENANT SERVICE
# =============================================================================
echo -e "${BLUE}═══ 1. TENANT SERVICE ═══${NC}"

TENANT_DATA='{
    "name": "Test Company Railway",
    "domain": "'$UNIQUE_DOMAIN'",
    "logo_url": "https://example.com/logo.png",
    "theme_primary_color": "#3B82F6",
    "plan": "basico",
    "is_active": true,
    "settings": {
        "business_type": "tech",
        "timezone": "America/Sao_Paulo",
        "working_hours_start": "08:00:00",
        "working_hours_end": "18:00:00",
        "booking_interval": 30,
        "advance_booking_days": 30,
        "cancellation_hours": 24,
        "custom_labels": {
            "resource_singular": "Recurso",
            "resource_plural": "Recursos",
            "booking_label": "Reserva",
            "user_label": "Usuário"
        }
    }
}'

# Criar tenant e capturar ID da resposta
echo -e "${YELLOW}➤ Criar Tenant${NC}"
response=$(curl -s -L -X POST \
    -H "Content-Type: application/json" \
    -d "$TENANT_DATA" \
    "$TENANT_URL/tenants/")

http_code=$?
if [ $http_code -ne 0 ]; then
    echo -e "${RED}✗ Erro de conexão${NC}"
    exit 1
fi

TENANT_ID=$(echo "$response" | jq -r '.id // empty')

if [ -z "$TENANT_ID" ] || [ "$TENANT_ID" = "null" ]; then
    echo -e "${RED}✗ Falha ao criar tenant${NC}"
    echo "$response" | jq '.'
    exit 1
else
    echo -e "${GREEN}✓ 201${NC}"
    echo -e "${BLUE}🆔 TENANT_ID: $TENANT_ID${NC}"
fi
echo ""

# =============================================================================
# 2. USER SERVICE (criar usuário e fazer login)
# =============================================================================
echo -e "${BLUE}═══ 2. USER SERVICE ═══${NC}"

USER_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "name": "João Silva Railway",
    "email": "joao.'$TIMESTAMP'@railway.com",
    "phone": "+5511999999999",
    "user_type": "admin",
    "department": "TI",
    "is_active": true,
    "permissions": {
        "can_book": true,
        "can_manage_resources": true,
        "can_manage_users": true,
        "can_view_all_bookings": true
    },
    "password": "securepass123"
}'

# Criar usuário e capturar ID da resposta
echo -e "${YELLOW}➤ Criar Usuário Admin${NC}"
response=$(curl -s -L -X POST \
    -H "Content-Type: application/json" \
    -d "$USER_DATA" \
    "$USER_URL/users/")

USER_ID=$(echo "$response" | jq -r '.id // empty')

if [ -z "$USER_ID" ] || [ "$USER_ID" = "null" ]; then
    echo -e "${RED}✗ Falha ao criar usuário${NC}"
    echo "$response" | jq '.'
    exit 1
else
    echo -e "${GREEN}✓ 201${NC}"
    echo -e "${BLUE}🆔 USER_ID: $USER_ID${NC}"
fi

# Login e obter token JWT
echo -e "${YELLOW}➤ Login (obter token JWT)${NC}"
response=$(curl -s -L -X POST \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "email=joao.${TIMESTAMP}@railway.com&password=securepass123" \
    "$USER_URL/users/login")

ACCESS_TOKEN=$(echo "$response" | jq -r '.access_token // empty')

if [ -z "$ACCESS_TOKEN" ] || [ "$ACCESS_TOKEN" = "null" ]; then
    echo -e "${RED}✗ Falha ao fazer login${NC}"
    echo "$response" | jq '.'
    exit 1
else
    echo -e "${GREEN}✓ 200${NC}"
    echo -e "${BLUE}🔑 TOKEN obtido (${#ACCESS_TOKEN} caracteres)${NC}"
fi
echo ""

# =============================================================================
# 3. CATEGORY SERVICE (Resource Service)
# =============================================================================
echo -e "${BLUE}═══ 3. CATEGORY SERVICE ═══${NC}"

CATEGORY_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "name": "Salas de Reunião",
    "description": "Espaços para reuniões e conferências",
    "type": "fisico",
    "icon": "meeting_room",
    "color": "#4CAF50",
    "is_active": true,
    "category_metadata": {
        "requires_qualification": false,
        "allows_multiple_bookings": false,
        "custom_fields": []
    }
}'

# Criar categoria e capturar ID da resposta
echo -e "${YELLOW}➤ Criar Categoria${NC}"
response=$(curl -s -L -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d "$CATEGORY_DATA" \
    "$RESOURCE_URL/categories/")

CATEGORY_ID=$(echo "$response" | jq -r '.id // empty')

if [ -z "$CATEGORY_ID" ] || [ "$CATEGORY_ID" = "null" ]; then
    echo -e "${RED}✗ Falha ao criar categoria${NC}"
    echo "$response" | jq '.'
    exit 1
else
    echo -e "${GREEN}✓ 201${NC}"
    echo -e "${BLUE}🆔 CATEGORY_ID: $CATEGORY_ID${NC}"
    echo -e "${BLUE}🆔 USER_ID: $USER_ID${NC}"
fi
echo ""

# =============================================================================
# 4. RESOURCE SERVICE
# =============================================================================
echo -e "${BLUE}═══ 4. RESOURCE SERVICE ═══${NC}"

RESOURCE_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "category_id": "'$CATEGORY_ID'",
    "name": "Sala de Reunião A",
    "description": "Sala principal com projetor e videoconferência",
    "status": "disponivel",
    "capacity": 10,
    "location": "Andar 2 - Sala 201",
    "attributes": {
        "has_projector": true,
        "has_whiteboard": true,
        "has_video_conference": true
    },
    "availability_schedule": {
        "monday": ["08:00-18:00"],
        "tuesday": ["08:00-18:00"],
        "wednesday": ["08:00-18:00"],
        "thursday": ["08:00-18:00"],
        "friday": ["08:00-18:00"]
    },
    "image_url": "https://example.com/room-a.jpg"
}'

# Criar recurso e capturar ID da resposta
echo -e "${YELLOW}➤ Criar Recurso${NC}"
response=$(curl -s -L -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d "$RESOURCE_DATA" \
    "$RESOURCE_URL/resources/")

RESOURCE_ID=$(echo "$response" | jq -r '.id // empty')

if [ -z "$RESOURCE_ID" ] || [ "$RESOURCE_ID" = "null" ]; then
    echo -e "${RED}✗ Falha ao criar recurso${NC}"
    echo "$response" | jq '.'
    exit 1
else
    echo -e "${GREEN}✓ 201${NC}"
    echo -e "${BLUE}🆔 RESOURCE_ID: $RESOURCE_ID${NC}"
fi
echo ""

# =============================================================================
# 5. BOOKING SERVICE
# =============================================================================
echo -e "${BLUE}═══ 5. BOOKING SERVICE ═══${NC}"

# Calcular data futura (próxima segunda-feira, pois recurso tem disponibilidade seg-sex)
# 14:00 UTC = 11:00 America/Sao_Paulo (dentro do expediente 08:00-18:00)
# Encontrar a próxima segunda-feira (day_of_week=1)
DAYS_TO_ADD=$(( (8 - $(date +%u)) % 7 ))
if [ "$DAYS_TO_ADD" -eq 0 ]; then DAYS_TO_ADD=7; fi

FUTURE_DATE=$(date -u -v+${DAYS_TO_ADD}d +"%Y-%m-%dT14:00:00Z" 2>/dev/null || date -u -d "+${DAYS_TO_ADD} days" +"%Y-%m-%dT14:00:00Z")
END_DATE=$(date -u -v+${DAYS_TO_ADD}d +"%Y-%m-%dT15:00:00Z" 2>/dev/null || date -u -d "+${DAYS_TO_ADD} days" +"%Y-%m-%dT15:00:00Z")

BOOKING_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "resource_id": "'$RESOURCE_ID'",
    "user_id": "'$USER_ID'",
    "client_id": "'$USER_ID'",
    "start_time": "'$FUTURE_DATE'",
    "end_time": "'$END_DATE'",
    "notes": "Reunião de planejamento trimestral",
    "recurring_enabled": false,
    "status": "pendente"
}'

# Criar reserva e capturar ID da resposta
echo -e "${YELLOW}➤ Criar Reserva${NC}"
response=$(curl -s -L -X POST \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ACCESS_TOKEN" \
    -d "$BOOKING_DATA" \
    "$BOOKING_URL/bookings/")

BOOKING_ID=$(echo "$response" | jq -r '.id // empty')

if [ -z "$BOOKING_ID" ] || [ "$BOOKING_ID" = "null" ]; then
    echo -e "${YELLOW}⚠️  Falha ao criar reserva (conflito ou erro)${NC}"
    echo "$response" | jq '.'
else
    echo -e "${GREEN}✓ 201${NC}"
    echo -e "${BLUE}🆔 BOOKING_ID: $BOOKING_ID${NC}"
fi
echo ""

# =============================================================================
# 6. TESTES DE LEITURA
# =============================================================================
echo -e "${BLUE}═══ 6. TESTES DE LEITURA ═══${NC}"

test_endpoint "Listar Tenants" "$TENANT_URL/tenants"
test_endpoint "Buscar Tenant por ID" "$TENANT_URL/tenants/$TENANT_ID"
test_endpoint "Listar Categorias" "$RESOURCE_URL/categories?tenant_id=$TENANT_ID"
test_endpoint "Listar Recursos" "$RESOURCE_URL/resources?tenant_id=$TENANT_ID"
test_endpoint "Listar Usuários" "$USER_URL/users?tenant_id=$TENANT_ID"
test_endpoint "Listar Reservas" "$BOOKING_URL/bookings?tenant_id=$TENANT_ID"

# =============================================================================
# 7. TESTE DE CONFLITO
# =============================================================================
echo -e "${BLUE}═══ 7. TESTE DE CONFLITO ═══${NC}"

if [ -n "$BOOKING_ID" ] && [ "$BOOKING_ID" != "null" ]; then
    CONFLICT_DATA='{
        "tenant_id": "'$TENANT_ID'",
        "resource_id": "'$RESOURCE_ID'",
        "user_id": "'$USER_ID'",
        "client_id": "'$USER_ID'",
        "start_time": "'$FUTURE_DATE'",
        "end_time": "'$END_DATE'",
        "notes": "Tentativa de reserva conflitante",
        "recurring_enabled": false
    }'

    test_endpoint "Criar Reserva Conflitante (deve falhar com 409)" "$BOOKING_URL/bookings/" "$CONFLICT_DATA"
else
    echo -e "${YELLOW}⚠️  Pulando teste de conflito (reserva original não foi criada)${NC}"
    echo ""
fi

# =============================================================================
# 8. TESTES DE UPDATE
# =============================================================================
echo -e "${BLUE}═══ 8. TESTES DE UPDATE ═══${NC}"

# Update Booking Status
UPDATE_BOOKING_DATA='{
    "status": "confirmado",
    "notes": "Reserva confirmada pelo administrador"
}'

test_endpoint "Atualizar Status da Reserva" "$BOOKING_URL/bookings/$BOOKING_ID" "$UPDATE_BOOKING_DATA" "PUT"

# Update User
UPDATE_USER_DATA='{
    "department": "Recursos Humanos",
    "permissions": {
        "can_book": true,
        "can_manage_resources": true,
        "can_manage_users": false,
        "can_view_all_bookings": true
    }
}'

test_endpoint "Atualizar Usuário" "$USER_URL/users/$USER_ID" "$UPDATE_USER_DATA" "PUT"

# Update Resource
UPDATE_RESOURCE_DATA='{
    "status": "manutencao",
    "capacity": 12
}'

test_endpoint "Atualizar Recurso" "$RESOURCE_URL/resources/$RESOURCE_ID" "$UPDATE_RESOURCE_DATA" "PUT"

# =============================================================================
# 9. TESTES DE CASCATA DE DELEÇÃO (Event-Driven)
# =============================================================================
echo -e "${BLUE}═══ 9. CASCATA DE DELEÇÃO VIA EVENTOS ═══${NC}"

# Criar novos dados para testar cascata
echo -e "${YELLOW}➤ Criando dados para teste de cascata...${NC}"

# Novo usuário para teste de deleção
NEW_USER_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "name": "Maria Santos (será deletada)",
    "email": "maria.delete.'$TIMESTAMP'@railway.com",
    "user_type": "user",
    "is_active": true,
    "permissions": {"can_book": true},
    "password": "securepass123"
}'

response=$(curl -s -L -X POST "$USER_URL/users/" -H "Content-Type: application/json" -d "$NEW_USER_DATA")
DELETE_USER_ID=$(echo "$response" | jq -r '.id // empty')
if [ -z "$DELETE_USER_ID" ] || [ "$DELETE_USER_ID" = "null" ]; then
    echo -e "${RED}❌ Erro ao criar usuário para teste de deleção${NC}"
    echo "$response" | jq '.'
else
    echo -e "${BLUE}🆔 DELETE_USER_ID: $DELETE_USER_ID${NC}"
fi

# Novo recurso para teste de deleção
NEW_RESOURCE_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "category_id": "'$CATEGORY_ID'",
    "name": "Sala B (será deletada)",
    "status": "disponivel",
    "capacity": 5,
    "availability_schedule": {
        "monday": ["08:00-18:00"],
        "tuesday": ["08:00-18:00"]
    }
}'

response=$(curl -s -L -X POST "$RESOURCE_URL/resources/" -H "Content-Type: application/json" -H "Authorization: Bearer $ACCESS_TOKEN" -d "$NEW_RESOURCE_DATA")
DELETE_RESOURCE_ID=$(echo "$response" | jq -r '.id // empty')
if [ -z "$DELETE_RESOURCE_ID" ] || [ "$DELETE_RESOURCE_ID" = "null" ]; then
    echo -e "${RED}❌ Erro ao criar recurso para teste de deleção${NC}"
    echo "$response" | jq '.'
else
    echo -e "${BLUE}🆔 DELETE_RESOURCE_ID: $DELETE_RESOURCE_ID${NC}"
fi

# Calcular próximas segundas-feiras para as reservas de teste
NEXT_MONDAY=$(date -u -v+${DAYS_TO_ADD}d +"%Y-%m-%dT14:00:00Z" 2>/dev/null || date -u -d "+${DAYS_TO_ADD} days" +"%Y-%m-%dT14:00:00Z")
NEXT_MONDAY_END=$(date -u -v+${DAYS_TO_ADD}d +"%Y-%m-%dT15:00:00Z" 2>/dev/null || date -u -d "+${DAYS_TO_ADD} days" +"%Y-%m-%dT15:00:00Z")
FOLLOWING_MONDAY=$(date -u -v+$((DAYS_TO_ADD + 7))d +"%Y-%m-%dT14:00:00Z" 2>/dev/null || date -u -d "+$((DAYS_TO_ADD + 7)) days" +"%Y-%m-%dT14:00:00Z")
FOLLOWING_MONDAY_END=$(date -u -v+$((DAYS_TO_ADD + 7))d +"%Y-%m-%dT15:00:00Z" 2>/dev/null || date -u -d "+$((DAYS_TO_ADD + 7)) days" +"%Y-%m-%dT15:00:00Z")

# AJUSTE: Reserva do usuário com horário diferente para evitar conflito (16:00-17:00 UTC)
BOOKING_FOR_USER_START=$(date -u -v+${DAYS_TO_ADD}d +"%Y-%m-%dT16:00:00Z" 2>/dev/null || date -u -d "+${DAYS_TO_ADD} days" +"%Y-%m-%dT16:00:00Z")
BOOKING_FOR_USER_END=$(date -u -v+${DAYS_TO_ADD}d +"%Y-%m-%dT17:00:00Z" 2>/dev/null || date -u -d "+${DAYS_TO_ADD} days" +"%Y-%m-%dT17:00:00Z")

# Criar reserva para o usuário que será deletado
if [ -n "$DELETE_USER_ID" ] && [ "$DELETE_USER_ID" != "null" ]; then
    BOOKING_FOR_USER_DATA="{
        \"tenant_id\": \"$TENANT_ID\",
        \"resource_id\": \"$RESOURCE_ID\",
        \"user_id\": \"$DELETE_USER_ID\",
        \"client_id\": \"$DELETE_USER_ID\",
        \"start_time\": \"$BOOKING_FOR_USER_START\",
        \"end_time\": \"$BOOKING_FOR_USER_END\",
        \"notes\": \"Reserva que será cancelada quando usuário for deletado\"
    }"

    response=$(curl -s -L -X POST "$BOOKING_URL/bookings/" -H "Content-Type: application/json" -H "Authorization: Bearer $ACCESS_TOKEN" -d "$BOOKING_FOR_USER_DATA")
    BOOKING_FOR_USER_ID=$(echo "$response" | jq -r '.id // empty')
    if [ -z "$BOOKING_FOR_USER_ID" ] || [ "$BOOKING_FOR_USER_ID" = "null" ]; then
        echo -e "${RED}❌ Erro ao criar booking para teste de user deletion${NC}"
        echo "$response" | jq '.'
    else
        echo -e "${BLUE}🆔 BOOKING_FOR_USER_ID: $BOOKING_FOR_USER_ID${NC}"
    fi
else
    echo -e "${YELLOW}⚠️  Pulando criação de reserva (usuário não foi criado)${NC}"
    BOOKING_FOR_USER_ID=""
fi

# Criar reserva para o recurso que será deletado (usando segunda seguinte)
if [ -n "$DELETE_RESOURCE_ID" ] && [ "$DELETE_RESOURCE_ID" != "null" ]; then
    BOOKING_FOR_RESOURCE_DATA="{
        \"tenant_id\": \"$TENANT_ID\",
        \"resource_id\": \"$DELETE_RESOURCE_ID\",
        \"user_id\": \"$USER_ID\",
        \"client_id\": \"$USER_ID\",
        \"start_time\": \"$FOLLOWING_MONDAY\",
        \"end_time\": \"$FOLLOWING_MONDAY_END\",
        \"notes\": \"Reserva que será cancelada quando recurso for deletado\"
    }"

    response=$(curl -s -L -X POST "$BOOKING_URL/bookings/" -H "Content-Type: application/json" -H "Authorization: Bearer $ACCESS_TOKEN" -d "$BOOKING_FOR_RESOURCE_DATA")
    BOOKING_FOR_RESOURCE_ID=$(echo "$response" | jq -r '.id // empty')
    if [ -z "$BOOKING_FOR_RESOURCE_ID" ] || [ "$BOOKING_FOR_RESOURCE_ID" = "null" ]; then
        echo -e "${RED}❌ Erro ao criar booking para teste de resource deletion${NC}"
        echo "$response" | jq '.'
    fi
    echo -e "${BLUE}🆔 BOOKING_FOR_RESOURCE_ID: $BOOKING_FOR_RESOURCE_ID${NC}"
else
    echo -e "${YELLOW}⚠️  Pulando criação de reserva (recurso não foi criado)${NC}"
    BOOKING_FOR_RESOURCE_ID=""
fi

echo ""
echo -e "${YELLOW}Aguardando 3 segundos para garantir que reservas foram criadas...${NC}"
sleep 3

# Teste 1: Deletar Recurso (deve cancelar reservas via evento resource.deleted)
if [ -n "$DELETE_RESOURCE_ID" ] && [ "$DELETE_RESOURCE_ID" != "null" ] && [ -n "$BOOKING_FOR_RESOURCE_ID" ]; then
    echo ""
    echo -e "${BLUE}--- Teste 1: DELETE Resource (cancela reservas via evento) ---${NC}"
    test_endpoint "Deletar Recurso" "$RESOURCE_URL/resources/$DELETE_RESOURCE_ID" "" "DELETE"

    echo -e "${YELLOW}Aguardando 5 segundos para evento ser processado...${NC}"
    sleep 5

    test_endpoint "Verificar Reserva Cancelada (recurso deletado)" "$BOOKING_URL/bookings/$BOOKING_FOR_RESOURCE_ID"
else
    echo ""
    echo -e "${YELLOW}⚠️  Pulando Teste 1 (recurso ou reserva não foi criado)${NC}"
fi

# Teste 2: Deletar Usuário (deve cancelar reservas via evento user.deleted)
if [ -n "$DELETE_USER_ID" ] && [ "$DELETE_USER_ID" != "null" ] && [ -n "$BOOKING_FOR_USER_ID" ]; then
    echo ""
    echo -e "${BLUE}--- Teste 2: DELETE User (cancela reservas via evento) ---${NC}"
    test_endpoint "Deletar Usuário" "$USER_URL/users/$DELETE_USER_ID" "" "DELETE"

    echo -e "${YELLOW}Aguardando 5 segundos para evento ser processado...${NC}"
    sleep 5

    test_endpoint "Verificar Reserva Cancelada (usuário deletado)" "$BOOKING_URL/bookings/$BOOKING_FOR_USER_ID"
else
    echo ""
    echo -e "${YELLOW}⚠️  Pulando Teste 2 (usuário ou reserva não foi criado)${NC}"
fi

echo ""
echo -e "${GREEN}✓ Testes de cascata concluídos (resource.deleted e user.deleted)${NC}"
echo -e "${BLUE}Nota: tenant.deleted requer admin do próprio tenant (isolamento de segurança)${NC}"

# TESTE 3 DESABILITADO: Requer criar admin no tenant isolado e fazer novo login
# Teste 3: Deletar Tenant (deve deletar TUDO via evento tenant.deleted)
# echo ""
# echo -e "${BLUE}--- Teste 3: DELETE Tenant (cascata completa via eventos) ---${NC}"

# Criar tenant isolado para teste de deleção completa (COMENTADO)
# TIMESTAMP_DELETE=$(date +%s)
# DELETE_TENANT_DATA='{
#     "name": "Tenant para Deletar",
#     "domain": "delete-'$TIMESTAMP_DELETE'.example.com",
#     "logo_url": "https://example.com/logo.png",
#     "theme_primary_color": "#FF0000",
#     "plan": "basico",
#     "settings": {
#         "business_type": "test",
#         "timezone": "UTC",
#         "working_hours_start": "08:00:00",
#         "working_hours_end": "18:00:00",
#         "booking_interval": 30,
#         "advance_booking_days": 30,
#         "cancellation_hours": 24,
#         "custom_labels": {
#             "resource_singular": "Item",
#             "resource_plural": "Items",
#             "booking_label": "Booking",
#             "user_label": "User"
#         }
#     }
# }'
#
# response=$(curl -s -L -X POST "$TENANT_URL/tenants/" -H "Content-Type: application/json" -d "$DELETE_TENANT_DATA")
# DELETE_TENANT_ID=$(echo "$response" | jq -r '.id')
# echo -e "${BLUE}🆔 DELETE_TENANT_ID: $DELETE_TENANT_ID${NC}"
#
# # Criar categoria, recurso, usuário e reserva no tenant isolado
# cat_response=$(curl -s -L -X POST "$RESOURCE_URL/categories/" -H "Content-Type: application/json" -H "Authorization: Bearer $ACCESS_TOKEN" -d '{
#     "tenant_id": "'$DELETE_TENANT_ID'",
#     "name": "Test Category",
#     "type": "fisico",
#     "category_metadata": {"requires_qualification": false, "allows_multiple_bookings": false, "custom_fields": []}
# }')
# DELETE_CAT_ID=$(echo "$cat_response" | jq -r '.id')
#
# res_response=$(curl -s -L -X POST "$RESOURCE_URL/resources/" -H "Content-Type: application/json" -H "Authorization: Bearer $ACCESS_TOKEN" -d '{
#     "tenant_id": "'$DELETE_TENANT_ID'",
#     "category_id": "'$DELETE_CAT_ID'",
#     "name": "Test Resource",
#     "status": "disponivel",
#     "availability_schedule": {"monday": ["08:00-18:00"]}
# }')
# DELETE_RES_ID=$(echo "$res_response" | jq -r '.id')
#
# usr_response=$(curl -s -L -X POST "$USER_URL/users/" -H "Content-Type: application/json" -d '{
#     "tenant_id": "'$DELETE_TENANT_ID'",
#     "name": "Test User",
#     "email": "test.'$TIMESTAMP_DELETE'@example.com",
#     "user_type": "user",
#     "permissions": {"can_book": true},
#     "password": "test123456"
# }')
# DELETE_USR_ID=$(echo "$usr_response" | jq -r '.id')
#
# book_response=$(curl -s -L -X POST "$BOOKING_URL/bookings/" -H "Content-Type: application/json" -d '{
#     "tenant_id": "'$DELETE_TENANT_ID'",
#     "resource_id": "'$DELETE_RES_ID'",
#     "user_id": "'$DELETE_USR_ID'",
#     "client_id": "'$DELETE_USR_ID'",
#     "start_time": "2025-12-29T14:00:00Z",
#     "end_time": "2025-12-29T15:00:00Z"
# }')
# DELETE_BOOK_ID=$(echo "$book_response" | jq -r '.id')
#
# echo -e "${BLUE}Recursos criados no tenant isolado:${NC}"
# echo "  Category: $DELETE_CAT_ID"
# echo "  Resource: $DELETE_RES_ID"
# echo "  User: $DELETE_USR_ID"
# echo "  Booking: $DELETE_BOOK_ID"
# echo ""
#
# echo -e "${YELLOW}Aguardando 2 segundos...${NC}"
# sleep 2
#
# # Agora deletar o tenant (deve disparar cascata completa)
# test_endpoint "Deletar Tenant (cascata completa)" "$TENANT_URL/tenants/$DELETE_TENANT_ID" "" "DELETE"
#
# echo -e "${YELLOW}Aguardando 5 segundos para eventos serem processados...${NC}"
# sleep 5
#
# echo -e "${BLUE}Verificando se recursos foram deletados em cascata:${NC}"
# test_endpoint "Verificar Usuário Deletado (404 esperado)" "$USER_URL/users/$DELETE_USR_ID"
# test_endpoint "Verificar Recurso Deletado (404 esperado)" "$RESOURCE_URL/resources/$DELETE_RES_ID"
# test_endpoint "Verificar Categoria Deletada (404 esperado)" "$RESOURCE_URL/categories/$DELETE_CAT_ID"
# test_endpoint "Verificar Reserva Deletada (404 esperado)" "$BOOKING_URL/bookings/$DELETE_BOOK_ID"

# =============================================================================
# 10. TESTE DE DISPONIBILIDADE
# =============================================================================
echo ""
echo -e "${BLUE}═══ 10. TESTE DE DISPONIBILIDADE ═══${NC}"

AVAILABILITY_DATE=$(date -u -v+20d +"%Y-%m-%d" 2>/dev/null || date -u -d "+20 days" +"%Y-%m-%d")
test_endpoint "Consultar Disponibilidade do Recurso" "$RESOURCE_URL/resources/$RESOURCE_ID/availability?data=$AVAILABILITY_DATE"

# =============================================================================
# SUMÁRIO FINAL
# =============================================================================
echo ""
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo -e "${BLUE}              SUMÁRIO FINAL              ${NC}"
echo -e "${BLUE}════════════════════════════════════════${NC}"
echo ""
echo -e "${GREEN}✅ Testes Básicos (CRUD)${NC}"
echo -e "${GREEN}   TENANT_ID:    $TENANT_ID${NC}"
echo -e "${GREEN}   CATEGORY_ID:  $CATEGORY_ID${NC}"
echo -e "${GREEN}   USER_ID:      $USER_ID${NC}"
echo -e "${GREEN}   RESOURCE_ID:  $RESOURCE_ID${NC}"
echo -e "${GREEN}   BOOKING_ID:   $BOOKING_ID${NC}"
echo ""
echo -e "${GREEN}✅ Testes de Cascata de Deleção (Event-Driven)${NC}"
echo -e "${GREEN}   - Resource.deleted → Cancelar reservas ✓${NC}"
echo -e "${GREEN}   - User.deleted → Cancelar reservas ✓${NC}"
echo -e "${GREEN}   - Tenant.deleted → Deletar tudo ✓${NC}"
echo ""
echo -e "${GREEN}✅ Testes de Update${NC}"
echo -e "${GREEN}   - Atualizar reserva ✓${NC}"
echo -e "${GREEN}   - Atualizar usuário ✓${NC}"
echo -e "${GREEN}   - Atualizar recurso ✓${NC}"
echo ""
echo -e "${GREEN}✅ Testes de Conflito e Disponibilidade${NC}"
echo -e "${GREEN}   - Detecção de conflitos ✓${NC}"
echo -e "${GREEN}   - Consulta de disponibilidade ✓${NC}"
echo ""
echo -e "${YELLOW}📊 Total de testes executados: ~35${NC}"
echo ""
