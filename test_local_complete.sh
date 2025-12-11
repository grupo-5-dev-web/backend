#!/bin/bash

# Script de Teste Completo - Ambiente Local
# Testa todos os endpoints + autenticação JWT + cascata de deleção via eventos

# Cores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# URLs dos serviços (LOCAL - via nginx)
BASE_URL="http://localhost:8000"
TENANT_URL="$BASE_URL/tenants"
USER_URL="$BASE_URL/users"
RESOURCE_URL="$BASE_URL/resources"
BOOKING_URL="$BASE_URL/bookings"
CATEGORY_URL="$BASE_URL/categories"

echo "════════════════════════════════════════════════════════"
echo "   TESTE COMPLETO COM AUTENTICAÇÃO JWT - LOCAL         "
echo "════════════════════════════════════════════════════════"
echo ""

# Gerar domínio único com timestamp
UNIQUE_DOMAIN="local-test-$(date +%s).example.com"
ADMIN_EMAIL="admin-$(date +%s)@test.com"
USER_EMAIL="user-$(date +%s)@test.com"
ADMIN_PASSWORD="admin12345"
USER_PASSWORD="user12345"

# Calcular próxima segunda-feira
DAYS_TO_ADD=$(( (8 - $(date +%u)) % 7 ))
if [ "$DAYS_TO_ADD" -eq 0 ]; then
    DAYS_TO_ADD=7
fi

FUTURE_DATE=$(date -u -v+${DAYS_TO_ADD}d +"%Y-%m-%dT14:00:00Z" 2>/dev/null || date -u -d "+${DAYS_TO_ADD} days" +"%Y-%m-%dT14:00:00Z")
FUTURE_DATE_END=$(date -u -v+${DAYS_TO_ADD}d +"%Y-%m-%dT15:00:00Z" 2>/dev/null || date -u -d "+${DAYS_TO_ADD} days" +"%Y-%m-%dT15:00:00Z")

echo "═══ 1. CRIAR TENANT ═══"
TENANT_DATA='{
    "name": "Empresa Teste Local",
    "domain": "'$UNIQUE_DOMAIN'",
    "logo_url": "https://example.com/logo.png",
    "theme_primary_color": "#007bff",
    "plan": "profissional",
    "settings": {
        "business_type": "consultoria",
        "timezone": "America/Sao_Paulo",
        "working_hours_start": "08:00:00",
        "working_hours_end": "18:00:00",
        "booking_interval": 30,
        "advance_booking_days": 60,
        "cancellation_hours": 24,
        "custom_labels": {
            "resource_singular": "Sala",
            "resource_plural": "Salas",
            "booking_label": "Reserva",
            "user_label": "Colaborador"
        }
    }
}'

echo "➤ Criar Tenant"
response=$(curl -s -w "\n%{http_code}" -X POST "$TENANT_URL/" -H "Content-Type: application/json" -d "$TENANT_DATA")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
TENANT_ID=$(echo "$body" | jq -r '.id // empty')

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ] && [ -n "$TENANT_ID" ]; then
    echo -e "${GREEN}✓ $http_code${NC}"
    echo -e "${BLUE}🆔 TENANT_ID: $TENANT_ID${NC}"
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
    exit 1
fi
echo ""

echo "═══ 2. CRIAR CATEGORIA ═══"
CATEGORY_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "name": "Salas de Reunião Local",
    "description": "Espaços para reuniões e conferências",
    "type": "fisico",
    "icon": "meeting_room",
    "color": "#4CAF50"
}'

echo "➤ Criar Categoria"
response=$(curl -s -w "\n%{http_code}" -X POST "$CATEGORY_URL/" -H "Content-Type: application/json" -d "$CATEGORY_DATA")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
CATEGORY_ID=$(echo "$body" | jq -r '.id // empty')

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ] && [ -n "$CATEGORY_ID" ]; then
    echo -e "${GREEN}✓ $http_code${NC}"
    echo -e "${BLUE}🆔 CATEGORY_ID: $CATEGORY_ID${NC}"
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
    exit 1
fi
echo ""

echo "═══ 3. CRIAR USUÁRIO ADMIN ═══"
ADMIN_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "name": "Admin User",
    "email": "'$ADMIN_EMAIL'",
    "phone": "+5511999999999",
    "user_type": "admin",
    "department": "TI",
    "password": "'$ADMIN_PASSWORD'",
    "permissions": {
        "can_book": true,
        "can_manage_resources": true,
        "can_manage_users": true,
        "can_view_all_bookings": true
    }
}'

echo "➤ Criar Admin"
response=$(curl -s -w "\n%{http_code}" -X POST "$USER_URL/" -H "Content-Type: application/json" -d "$ADMIN_DATA")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
ADMIN_ID=$(echo "$body" | jq -r '.id // empty')

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ] && [ -n "$ADMIN_ID" ]; then
    echo -e "${GREEN}✓ $http_code${NC}"
    echo -e "${BLUE}🆔 ADMIN_ID: $ADMIN_ID${NC}"
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
    exit 1
fi
echo ""

echo "═══ 4. LOGIN ADMIN (obter JWT token) ═══"
echo "➤ Login com email: $ADMIN_EMAIL"
response=$(curl -s -w "\n%{http_code}" -X POST "$USER_URL/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "email=$ADMIN_EMAIL&password=$ADMIN_PASSWORD")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
ADMIN_TOKEN=$(echo "$body" | jq -r '.access_token // empty')

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ] && [ -n "$ADMIN_TOKEN" ]; then
    echo -e "${GREEN}✓ $http_code${NC}"
    echo -e "${CYAN}🔐 Token obtido (primeiros 50 chars): ${ADMIN_TOKEN:0:50}...${NC}"
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
    exit 1
fi
echo ""

echo "═══ 5. TESTAR GET /users/me (usuário autenticado) ═══"
echo "➤ GET /users/me com token"
response=$(curl -s -w "\n%{http_code}" -X GET "$USER_URL/me" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo -e "${GREEN}✓ $http_code${NC}"
    echo "$body" | jq '{id, name, email, user_type}'
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
    exit 1
fi
echo ""

echo "═══ 6. CRIAR USUÁRIO COMUM ═══"
USER_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "name": "João Silva User",
    "email": "'$USER_EMAIL'",
    "phone": "+5511988888888",
    "user_type": "user",
    "department": "Vendas",
    "password": "'$USER_PASSWORD'",
    "permissions": {
        "can_book": true,
        "can_manage_resources": false,
        "can_manage_users": false,
        "can_view_all_bookings": false
    }
}'

echo "➤ Criar User (sem autenticação - signup público)"
response=$(curl -s -w "\n%{http_code}" -X POST "$USER_URL/" -H "Content-Type: application/json" -d "$USER_DATA")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
USER_ID=$(echo "$body" | jq -r '.id // empty')

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ] && [ -n "$USER_ID" ]; then
    echo -e "${GREEN}✓ $http_code${NC}"
    echo -e "${BLUE}🆔 USER_ID: $USER_ID${NC}"
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
    exit 1
fi
echo ""

echo "═══ 7. CRIAR RECURSO (autenticado como admin) ═══"
RESOURCE_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "category_id": "'$CATEGORY_ID'",
    "name": "Sala de Reunião Principal",
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

echo "➤ Criar Recurso (com token admin)"
response=$(curl -s -w "\n%{http_code}" -X POST "$RESOURCE_URL/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$RESOURCE_DATA")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
RESOURCE_ID=$(echo "$body" | jq -r '.id // empty')

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ] && [ -n "$RESOURCE_ID" ]; then
    echo -e "${GREEN}✓ $http_code${NC}"
    echo -e "${BLUE}🆔 RESOURCE_ID: $RESOURCE_ID${NC}"
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
    exit 1
fi
echo ""

echo "═══ 8. CRIAR RESERVA (autenticado como admin) ═══"
BOOKING_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "resource_id": "'$RESOURCE_ID'",
    "user_id": "'$ADMIN_ID'",
    "client_id": "'$ADMIN_ID'",
    "start_time": "'$FUTURE_DATE'",
    "end_time": "'$FUTURE_DATE_END'",
    "notes": "Reunião de planejamento trimestral"
}'

echo "➤ Criar Reserva (com token admin)"
response=$(curl -s -w "\n%{http_code}" -X POST "$BOOKING_URL/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$BOOKING_DATA")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
BOOKING_ID=$(echo "$body" | jq -r '.id // empty')

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ] && [ -n "$BOOKING_ID" ]; then
    echo -e "${GREEN}✓ $http_code${NC}"
    echo -e "${BLUE}🆔 BOOKING_ID: $BOOKING_ID${NC}"
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
    exit 1
fi
echo ""

echo "═══ 9. LISTAR RECURSOS (com autenticação) ═══"
echo "➤ Listar Tenants (público)"
response=$(curl -s -w "\n%{http_code}" "$TENANT_URL/")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
count=$(echo "$body" | jq -r 'length')
echo -e "${GREEN}✓ $http_code${NC} - $count tenants"

echo "➤ Listar Categorias (público)"
response=$(curl -s -w "\n%{http_code}" "$CATEGORY_URL/?tenant_id=$TENANT_ID")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
count=$(echo "$body" | jq -r 'length')
echo -e "${GREEN}✓ $http_code${NC} - $count categorias"

echo "➤ Listar Recursos do Tenant (com auth)"
response=$(curl -s -w "\n%{http_code}" "$RESOURCE_URL/?tenant_id=$TENANT_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
count=$(echo "$body" | jq -r 'length')
echo -e "${GREEN}✓ $http_code${NC} - $count recursos"

echo "➤ Listar Usuários do Tenant (requer admin)"
response=$(curl -s -w "\n%{http_code}" "$USER_URL/?tenant_id=$TENANT_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    count=$(echo "$body" | jq -r 'length')
    echo -e "${GREEN}✓ $http_code${NC} - $count usuários"
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
fi

echo "➤ Listar Reservas do Tenant (com auth)"
response=$(curl -s -w "\n%{http_code}" "$BOOKING_URL/?tenant_id=$TENANT_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
count=$(echo "$body" | jq -r 'length')
echo -e "${GREEN}✓ $http_code${NC} - $count reservas"
echo ""

echo "═══ 10. TESTES DE OPERAÇÕES AUTENTICADAS ═══"

echo "--- 10.1: GET Tenant Settings (com auth) ---"
response=$(curl -s -w "\n%{http_code}" "$TENANT_URL/$TENANT_ID/settings" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo -e "${GREEN}✓ $http_code${NC} - Settings obtidas"
    echo "$body" | jq '{timezone, working_hours_start, working_hours_end}'
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
fi
echo ""

echo "--- 10.2: UPDATE Tenant (com auth) ---"
UPDATE_TENANT_DATA='{"name": "Academia XPTO Updated"}'
response=$(curl -s -w "\n%{http_code}" -X PUT "$TENANT_URL/$TENANT_ID" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$UPDATE_TENANT_DATA")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo -e "${GREEN}✓ $http_code${NC} - Tenant atualizado"
    echo "$body" | jq '{id, name, plan}'
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
fi
echo ""

echo "--- 10.3: GET Resource Availability (com auth) ---"
# Extrair data do FUTURE_DATE (formato: 2025-12-16T14:00:00Z -> 2025-12-16)
AVAILABILITY_DATE=$(echo "$FUTURE_DATE" | cut -d'T' -f1)
response=$(curl -s -w "\n%{http_code}" "$RESOURCE_URL/$RESOURCE_ID/availability?data=$AVAILABILITY_DATE" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo -e "${GREEN}✓ $http_code${NC} - Disponibilidade obtida"
    echo "$body" | jq '.slots[:3]' # Mostrar primeiros 3 slots
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
fi
echo ""

echo "--- 10.4: GET Recurso por ID (com auth) ---"
response=$(curl -s -w "\n%{http_code}" "$RESOURCE_URL/$RESOURCE_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo -e "${GREEN}✓ $http_code${NC} - Recurso obtido"
    echo "$body" | jq '{id, name, status, capacity}'
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
fi
echo ""

echo "--- 10.5: UPDATE Reserva (com auth) ---"
UPDATE_BOOKING_DATA='{"notes": "Reunião alterada via teste", "status": "confirmado"}'
response=$(curl -s -w "\n%{http_code}" -X PUT "$BOOKING_URL/$BOOKING_ID" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$UPDATE_BOOKING_DATA")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo -e "${GREEN}✓ $http_code${NC} - Reserva atualizada"
    echo "$body" | jq '{id, status, notes}'
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
fi
echo ""

echo "═══ 11. TESTE DE CONFLITO DE RESERVA ═══"
echo "➤ Criar Reserva Conflitante (deve falhar com 409)"
response=$(curl -s -w "\n%{http_code}" -X POST "$BOOKING_URL/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$BOOKING_DATA")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
if [ "$http_code" -eq 409 ]; then
    echo -e "${RED}✗ 409${NC} - Conflito detectado corretamente ✓"
    echo "$body" | jq '.'
else
    echo -e "${RED}❌ ERRO: Esperava 409, recebeu $http_code${NC}"
    echo "$body" | jq '.'
fi
echo ""

echo "═══ 12. TESTE DE PERMISSÕES (user comum tentando admin endpoints) ═══"
echo "➤ Login como User Comum"
response=$(curl -s -w "\n%{http_code}" -X POST "$USER_URL/login" \
    -H "Content-Type: application/x-www-form-urlencoded" \
    -d "email=$USER_EMAIL&password=$USER_PASSWORD")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
USER_TOKEN=$(echo "$body" | jq -r '.access_token // empty')

if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ] && [ -n "$USER_TOKEN" ]; then
    echo -e "${GREEN}✓ $http_code${NC}"
    echo -e "${CYAN}🔐 User Token obtido${NC}"
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
fi
echo ""

echo "➤ User tentando listar usuários (deve falhar com 403)"
response=$(curl -s -w "\n%{http_code}" "$USER_URL/?tenant_id=$TENANT_ID" \
    -H "Authorization: Bearer $USER_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
if [ "$http_code" -eq 403 ]; then
    echo -e "${RED}✗ 403${NC} - Permissão negada corretamente ✓"
    echo "$body" | jq '.detail'
else
    echo -e "${RED}❌ ERRO: Esperava 403, recebeu $http_code${NC}"
    echo "$body" | jq '.'
fi
echo ""

echo "➤ User acessando próprio perfil (deve funcionar)"
response=$(curl -s -w "\n%{http_code}" "$USER_URL/me" \
    -H "Authorization: Bearer $USER_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
if [ "$http_code" -ge 200 ] && [ "$http_code" -lt 300 ]; then
    echo -e "${GREEN}✓ $http_code${NC} - Acesso ao próprio perfil OK"
    echo "$body" | jq '{id, name, email, user_type}'
else
    echo -e "${RED}✗ $http_code${NC}"
    echo "$body" | jq '.'
fi
echo ""

echo "═══ 13. CASCATA DE DELEÇÃO VIA EVENTOS ═══"
echo "➤ Criando dados para teste de cascata..."

# Criar usuário que será deletado
DELETE_USER_DATA='{
    "tenant_id": "'$TENANT_ID'",
    "name": "Maria Santos (será deletada)",
    "email": "maria.delete.'$(date +%s)'@test.com",
    "user_type": "user",
    "password": "delete123",
    "permissions": {"can_book": true}
}'
response=$(curl -s -X POST "$USER_URL/" -H "Content-Type: application/json" -d "$DELETE_USER_DATA")
DELETE_USER_ID=$(echo "$response" | jq -r '.id')
echo -e "${BLUE}🆔 DELETE_USER_ID: $DELETE_USER_ID${NC}"

# Criar recurso que será deletado (com auth)
DELETE_RESOURCE_DATA='{
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
response=$(curl -s -X POST "$RESOURCE_URL/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$DELETE_RESOURCE_DATA")
DELETE_RESOURCE_ID=$(echo "$response" | jq -r '.id')
echo -e "${BLUE}🆔 DELETE_RESOURCE_ID: $DELETE_RESOURCE_ID${NC}"

# Calcular horários diferentes para evitar conflitos
BOOKING_FOR_USER_START=$(date -u -v+${DAYS_TO_ADD}d +"%Y-%m-%dT16:00:00Z" 2>/dev/null || date -u -d "+${DAYS_TO_ADD} days" +"%Y-%m-%dT16:00:00Z")
BOOKING_FOR_USER_END=$(date -u -v+${DAYS_TO_ADD}d +"%Y-%m-%dT17:00:00Z" 2>/dev/null || date -u -d "+${DAYS_TO_ADD} days" +"%Y-%m-%dT17:00:00Z")
FOLLOWING_MONDAY=$(date -u -v+$((DAYS_TO_ADD + 7))d +"%Y-%m-%dT14:00:00Z" 2>/dev/null || date -u -d "+$((DAYS_TO_ADD + 7)) days" +"%Y-%m-%dT14:00:00Z")
FOLLOWING_MONDAY_END=$(date -u -v+$((DAYS_TO_ADD + 7))d +"%Y-%m-%dT15:00:00Z" 2>/dev/null || date -u -d "+$((DAYS_TO_ADD + 7)) days" +"%Y-%m-%dT15:00:00Z")

# Criar reserva para usuário que será deletado (com auth do admin)
BOOKING_FOR_USER_DATA="{
    \"tenant_id\": \"$TENANT_ID\",
    \"resource_id\": \"$RESOURCE_ID\",
    \"user_id\": \"$DELETE_USER_ID\",
    \"client_id\": \"$DELETE_USER_ID\",
    \"start_time\": \"$BOOKING_FOR_USER_START\",
    \"end_time\": \"$BOOKING_FOR_USER_END\",
    \"notes\": \"Reserva que será cancelada quando usuário for deletado\"
}"
response=$(curl -s -X POST "$BOOKING_URL/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$BOOKING_FOR_USER_DATA")
BOOKING_FOR_USER_ID=$(echo "$response" | jq -r '.id // empty')
echo -e "${BLUE}🆔 BOOKING_FOR_USER_ID: $BOOKING_FOR_USER_ID${NC}"

# Criar reserva para recurso que será deletado (com auth do admin)
BOOKING_FOR_RESOURCE_DATA="{
    \"tenant_id\": \"$TENANT_ID\",
    \"resource_id\": \"$DELETE_RESOURCE_ID\",
    \"user_id\": \"$ADMIN_ID\",
    \"client_id\": \"$ADMIN_ID\",
    \"start_time\": \"$FOLLOWING_MONDAY\",
    \"end_time\": \"$FOLLOWING_MONDAY_END\",
    \"notes\": \"Reserva que será cancelada quando recurso for deletado\"
}"
response=$(curl -s -X POST "$BOOKING_URL/" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer $ADMIN_TOKEN" \
    -d "$BOOKING_FOR_RESOURCE_DATA")
BOOKING_FOR_RESOURCE_ID=$(echo "$response" | jq -r '.id // empty')
echo -e "${BLUE}🆔 BOOKING_FOR_RESOURCE_ID: $BOOKING_FOR_RESOURCE_ID${NC}"

echo ""
echo "Aguardando 3 segundos para garantir que reservas foram criadas..."
sleep 3
echo ""

echo "--- Teste 1: DELETE Resource (cancela reservas via evento) ---"
echo "➤ Deletar Recurso (com auth)"
response=$(curl -s -w "\n%{http_code}" -X DELETE "$RESOURCE_URL/$DELETE_RESOURCE_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
echo -e "${GREEN}✓ $http_code${NC}"

echo "Aguardando 5 segundos para evento ser processado..."
sleep 5

echo "➤ Verificar Reserva Cancelada (recurso deletado)"
response=$(curl -s -w "\n%{http_code}" -L "$BOOKING_URL/$BOOKING_FOR_RESOURCE_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
status=$(echo "$body" | jq -r '.status')
if [ "$status" = "cancelado" ]; then
    echo -e "${GREEN}✓ SUCESSO: Reserva foi cancelada automaticamente!${NC}"
    echo "Status: $status"
else
    echo -e "${RED}❌ FALHOU: Reserva ainda está com status='$status' (esperado: 'cancelado')${NC}"
fi
echo ""

echo "--- Teste 2: DELETE User (cancela reservas via evento) ---"
echo "➤ Deletar Usuário (com auth)"
response=$(curl -s -w "\n%{http_code}" -X DELETE "$USER_URL/$DELETE_USER_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
echo -e "${GREEN}✓ $http_code${NC}"

echo "Aguardando 5 segundos para evento ser processado..."
sleep 5

echo "➤ Verificar Reserva Cancelada (usuário deletado)"
response=$(curl -s -w "\n%{http_code}" -L "$BOOKING_URL/$BOOKING_FOR_USER_ID" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
http_code=$(echo "$response" | tail -n1)
body=$(echo "$response" | sed '$d')
status=$(echo "$body" | jq -r '.status')
if [ "$status" = "cancelado" ]; then
    echo -e "${GREEN}✓ SUCESSO: Reserva foi cancelada automaticamente!${NC}"
    echo "Status: $status"
else
    echo -e "${RED}❌ FALHOU: Reserva ainda está com status='$status' (esperado: 'cancelado')${NC}"
fi
echo ""

echo "--- Teste 3: DELETE Tenant (cascata completa via eventos) ---"
# Criar tenant isolado para teste de cascata
ISOLATED_TENANT_DATA='{
    "name": "Tenant para Deletar",
    "domain": "delete-'$(date +%s)'.example.com",
    "logo_url": "https://example.com/logo.png",
    "theme_primary_color": "#FF0000",
    "plan": "basico",
    "settings": {
        "business_type": "test",
        "timezone": "UTC",
        "working_hours_start": "08:00:00",
        "working_hours_end": "18:00:00",
        "booking_interval": 30,
        "advance_booking_days": 30,
        "cancellation_hours": 24,
        "custom_labels": {"resource_singular": "Item", "resource_plural": "Items", "booking_label": "Booking", "user_label": "User"}
    }
}'
response=$(curl -s -X POST "$TENANT_URL/" -H "Content-Type: application/json" -d "$ISOLATED_TENANT_DATA")
DELETE_TENANT_ID=$(echo "$response" | jq -r '.id')
echo -e "${BLUE}🆔 DELETE_TENANT_ID: $DELETE_TENANT_ID${NC}"

# Criar recursos no tenant isolado
# Criar admin para tenant isolado
test_admin_email="test-admin-$(date +%s)@example.com"
admin_data='{"tenant_id": "'$DELETE_TENANT_ID'", "name": "Test Admin", "email": "'$test_admin_email'", "user_type": "admin", "password": "admin123", "permissions": {"can_book": true, "can_manage_resources": true, "can_manage_users": true}}'
response=$(curl -s -X POST "$USER_URL/" -H "Content-Type: application/json" -d "$admin_data")
test_admin_id=$(echo "$response" | jq -r '.id')

# Login como admin do tenant isolado
response=$(curl -s -X POST "$USER_URL/login" -H "Content-Type: application/x-www-form-urlencoded" -d "email=$test_admin_email&password=admin123")
test_admin_token=$(echo "$response" | jq -r '.access_token')

cat_data='{"tenant_id": "'$DELETE_TENANT_ID'", "name": "Test Category", "type": "fisico"}'
response=$(curl -s -X POST "$CATEGORY_URL/" -H "Content-Type: application/json" -d "$cat_data")
test_cat_id=$(echo "$response" | jq -r '.id')

res_data='{"tenant_id": "'$DELETE_TENANT_ID'", "category_id": "'$test_cat_id'", "name": "Test Resource", "status": "disponivel", "availability_schedule": {"monday": ["08:00-18:00"]}}'
response=$(curl -s -X POST "$RESOURCE_URL/" -H "Content-Type: application/json" -H "Authorization: Bearer $test_admin_token" -d "$res_data")
test_res_id=$(echo "$response" | jq -r '.id')

user_data='{"tenant_id": "'$DELETE_TENANT_ID'", "name": "Test User", "email": "test.'$(date +%s)'@example.com", "user_type": "user", "password": "user123", "permissions": {"can_book": true}}'
response=$(curl -s -X POST "$USER_URL/" -H "Content-Type: application/json" -d "$user_data")
test_user_id=$(echo "$response" | jq -r '.id')

book_data='{"tenant_id": "'$DELETE_TENANT_ID'", "resource_id": "'$test_res_id'", "user_id": "'$test_admin_id'", "client_id": "'$test_admin_id'", "start_time": "'$(date -u -v+$((DAYS_TO_ADD + 14))d +"%Y-%m-%dT14:00:00Z" 2>/dev/null || date -u -d "+$((DAYS_TO_ADD + 14)) days" +"%Y-%m-%dT14:00:00Z")'", "end_time": "'$(date -u -v+$((DAYS_TO_ADD + 14))d +"%Y-%m-%dT15:00:00Z" 2>/dev/null || date -u -d "+$((DAYS_TO_ADD + 14)) days" +"%Y-%m-%dT15:00:00Z")'"}'
response=$(curl -s -X POST "$BOOKING_URL/" -H "Content-Type: application/json" -H "Authorization: Bearer $test_admin_token" -d "$book_data")
test_booking_id=$(echo "$response" | jq -r '.id')

echo "Recursos criados no tenant isolado:"
echo "  Admin: $test_admin_id"
echo "  Category: $test_cat_id"
echo "  Resource: $test_res_id"
echo "  User: $test_user_id"
echo "  Booking: $test_booking_id"
echo ""

echo "Aguardando 2 segundos..."
sleep 2

echo "➤ Deletar Tenant (cascata completa - com auth do admin do tenant)"
response=$(curl -s -w "\n%{http_code}" -X DELETE "$TENANT_URL/$DELETE_TENANT_ID" \
    -H "Authorization: Bearer $test_admin_token")
http_code=$(echo "$response" | tail -n1)
echo -e "${GREEN}✓ $http_code${NC}"

echo "Aguardando 5 segundos para eventos serem processados..."
sleep 5

echo "Verificando se recursos foram deletados em cascata:"
echo "(Note: Token do tenant deletado não funciona mais, usando token do admin principal)"

echo "➤ Verificar Usuário Deletado (404 esperado)"
status_code=$(curl -s -L -o /dev/null -w "%{http_code}" "$USER_URL/$test_user_id" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
if [ "$status_code" -eq 404 ]; then
    echo -e "${GREEN}✓ SUCESSO: Usuário foi deletado (404)${NC}"
else
    echo -e "${RED}❌ FALHOU: Usuário ainda existe (status: $status_code)${NC}"
fi

echo "➤ Verificar Recurso Deletado (404 esperado)"
status_code=$(curl -s -L -o /dev/null -w "%{http_code}" "$RESOURCE_URL/$test_res_id" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
if [ "$status_code" -eq 404 ]; then
    echo -e "${GREEN}✓ SUCESSO: Recurso foi deletado (404)${NC}"
else
    echo -e "${RED}❌ FALHOU: Recurso ainda existe (status: $status_code)${NC}"
fi

echo "➤ Verificar Categoria Deletada (404 esperado)"
status_code=$(curl -s -L -o /dev/null -w "%{http_code}" "$CATEGORY_URL/$test_cat_id")
if [ "$status_code" -eq 404 ]; then
    echo -e "${GREEN}✓ SUCESSO: Categoria foi deletada (404)${NC}"
else
    echo -e "${RED}❌ FALHOU: Categoria ainda existe (status: $status_code)${NC}"
fi

echo "➤ Verificar Reserva Deletada (404 esperado)"
status_code=$(curl -s -L -o /dev/null -w "%{http_code}" "$BOOKING_URL/$test_booking_id" \
    -H "Authorization: Bearer $ADMIN_TOKEN")
if [ "$status_code" -eq 404 ]; then
    echo -e "${GREEN}✓ SUCESSO: Reserva foi deletada (404)${NC}"
else
    echo -e "${RED}❌ FALHOU: Reserva ainda existe (status: $status_code)${NC}"
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "                TESTES FINALIZADOS                      "
echo "════════════════════════════════════════════════════════"
echo ""
echo -e "${CYAN}📋 RESUMO DOS TESTES:${NC}"
echo "  ✅ Criação de Tenant e Settings"
echo "  ✅ Criação de Categoria"
echo "  ✅ Criação de Usuários (Admin + User)"
echo "  ✅ Autenticação JWT (Login + Token)"
echo "  ✅ GET /users/me (usuário autenticado)"
echo "  ✅ Criação de Recursos (autenticado)"
echo "  ✅ Criação de Reservas (autenticado)"
echo "  ✅ Listagem de recursos (com auth)"
echo "  ✅ Operações de UPDATE (Tenant, Booking)"
echo "  ✅ GET Resource Availability (autenticado)"
echo "  ✅ Teste de Conflito de Reserva (409)"
echo "  ✅ Teste de Permissões (User vs Admin)"
echo "  ✅ Cascata de deleção - User (via eventos)"
echo "  ✅ Cascata de deleção - Resource (via eventos)"
echo "  ✅ Cascata de deleção - Tenant completo (via eventos)"
echo ""
echo -e "${GREEN}Se todos os testes passaram:${NC}"
echo "✅ Sistema de autenticação JWT funcionando!"
echo "✅ Sistema de permissões funcionando!"
echo "✅ Sistema de eventos funcionando localmente!"
echo "✅ Todos os endpoints com autenticação OK!"
echo ""
echo -e "${YELLOW}Se algum teste falhou:${NC}"
echo "❌ Verificar logs dos containers:"
echo "   docker logs booking"
echo "   docker logs resource"
echo "   docker logs user"
echo "   docker logs tenant"
echo ""
echo -e "${CYAN}Para testar novamente:${NC}"
echo "   ./test_local_complete.sh"
