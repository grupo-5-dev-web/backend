#!/bin/bash

# Test script based on Postman collection
# Tests all endpoints to ensure compatibility with current system

set -e

BASE_URL="http://localhost:8000"
TENANT_URL="$BASE_URL/tenants"
USER_URL="$BASE_URL/users"
CATEGORY_URL="$BASE_URL/categories"
RESOURCE_URL="$BASE_URL/resources"
BOOKING_URL="$BASE_URL/bookings"

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Helper function to print test results
print_result() {
    local test_name=$1
    local status=$2
    local details=$3
    
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if [ "$status" = "PASS" ]; then
        echo -e "${GREEN}✓ PASS${NC}: $test_name"
        PASSED_TESTS=$((PASSED_TESTS + 1))
    else
        echo -e "${RED}✗ FAIL${NC}: $test_name - $details"
        FAILED_TESTS=$((FAILED_TESTS + 1))
    fi
}

# Helper function to check HTTP status code
check_status() {
    local actual=$1
    local expected=$2
    local test_name=$3
    
    if [ "$actual" = "$expected" ]; then
        print_result "$test_name" "PASS"
        return 0
    else
        print_result "$test_name" "FAIL" "Expected $expected, got $actual"
        return 1
    fi
}

# Helper function to extract JSON field
extract_json() {
    local json=$1
    local field=$2
    echo "$json" | grep -o "\"$field\"[[:space:]]*:[[:space:]]*\"[^\"]*\"" | sed 's/.*"\([^"]*\)"/\1/' | head -1
}

echo "========================================"
echo "   POSTMAN ENDPOINTS TEST SUITE"
echo "========================================"
echo ""

# Store created IDs for cleanup
CREATED_TENANT_ID=""
CREATED_USER_ID=""
CREATED_ADMIN_ID=""
CREATED_CATEGORY_ID=""
CREATED_RESOURCE_ID=""
CREATED_BOOKING_ID=""
ADMIN_TOKEN=""
USER_TOKEN=""

# ========================================
# SECTION 1: TENANT TESTS
# ========================================
echo "=========================================="
echo "SECTION 1: TENANT SERVICE TESTS"
echo "=========================================="
echo ""

# Test 1.1: Create Tenant
echo "Test 1.1: Create Tenant"
# Generate unique domain to avoid conflicts
UNIQUE_SUFFIX=$(date +%s)
tenant_data="{
  \"name\": \"Postman Test Tenant\",
  \"domain\": \"postman-test-${UNIQUE_SUFFIX}\",
  \"logo_url\": \"https://logo.png\",
  \"theme_primary_color\": \"#ff0000\",
  \"plan\": \"profissional\",
  \"is_active\": true,
  \"settings\": {
    \"business_type\": \"gym\",
    \"timezone\": \"America/Recife\",
    \"working_hours_start\": \"08:00:00\",
    \"working_hours_end\": \"18:00:00\",
    \"booking_interval\": 30,
    \"advance_booking_days\": 7,
    \"cancellation_hours\": 2,
    \"custom_labels\": {
      \"resource_singular\": \"sala\",
      \"resource_plural\": \"salas\",
      \"booking_label\": \"reserva\",
      \"user_label\": \"usuário\"
    }
  }
}"

response=$(curl -s -X POST "$TENANT_URL/" \
    -H "Content-Type: application/json" \
    -d "$tenant_data")

CREATED_TENANT_ID=$(extract_json "$response" "id")

if [ -n "$CREATED_TENANT_ID" ]; then
    print_result "Create Tenant" "PASS"
    echo "  Created Tenant ID: $CREATED_TENANT_ID"
else
    print_result "Create Tenant" "FAIL" "No ID returned"
    echo "  Response: $response"
fi
echo ""

# Test 1.2: Get All Tenants
echo "Test 1.2: Get All Tenants"
status_code=$(curl -s -o /dev/null -w "%{http_code}" "$TENANT_URL/")
check_status "$status_code" "200" "Get All Tenants"
echo ""

# Test 1.3: Get Tenant by ID
echo "Test 1.3: Get Tenant by ID"
if [ -n "$CREATED_TENANT_ID" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$TENANT_URL/$CREATED_TENANT_ID")
    check_status "$status_code" "200" "Get Tenant by ID"
else
    print_result "Get Tenant by ID" "FAIL" "No tenant ID available"
fi
echo ""

# ========================================
# SECTION 2: USER TESTS
# ========================================
echo "=========================================="
echo "SECTION 2: USER SERVICE TESTS"
echo "=========================================="
echo ""

# Test 2.1: Create Admin User
echo "Test 2.1: Create Admin User"
if [ -n "$CREATED_TENANT_ID" ]; then
    admin_data="{
      \"tenant_id\": \"$CREATED_TENANT_ID\",
      \"name\": \"Postman Admin\",
      \"email\": \"postman-admin-${UNIQUE_SUFFIX}@test.com\",
      \"phone\": \"81999999999\",
      \"user_type\": \"admin\",
      \"department\": \"Management\",
      \"is_active\": true,
      \"permissions\": {
        \"can_book\": true,
        \"can_manage_resources\": true,
        \"can_manage_users\": true,
        \"can_manage_tenants\": true
      },
      \"metadata\": {},
      \"password\": \"senha1234\"
    }"
    
    response=$(curl -s -X POST "$USER_URL/" \
        -H "Content-Type: application/json" \
        -d "$admin_data")
    
    CREATED_ADMIN_ID=$(extract_json "$response" "id")
    
    if [ -n "$CREATED_ADMIN_ID" ]; then
        print_result "Create Admin User" "PASS"
        echo "  Created Admin ID: $CREATED_ADMIN_ID"
    else
        print_result "Create Admin User" "FAIL" "No ID returned"
        echo "  Response: $response"
    fi
else
    print_result "Create Admin User" "FAIL" "No tenant ID available"
fi
echo ""

# Test 2.2: Admin Login
echo "Test 2.2: Admin Login"
if [ -n "$CREATED_ADMIN_ID" ]; then
    response=$(curl -s -X POST "$USER_URL/login" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "email=postman-admin-${UNIQUE_SUFFIX}@test.com&password=senha1234")
    
    ADMIN_TOKEN=$(extract_json "$response" "access_token")
    
    if [ -n "$ADMIN_TOKEN" ]; then
        print_result "Admin Login" "PASS"
        echo "  Token obtained (length: ${#ADMIN_TOKEN})"
    else
        print_result "Admin Login" "FAIL" "No token returned"
        echo "  Response: $response"
    fi
else
    print_result "Admin Login" "FAIL" "No admin user available"
fi
echo ""

# Test 2.3: Create Regular User
echo "Test 2.3: Create Regular User"
if [ -n "$CREATED_TENANT_ID" ]; then
    user_data="{
      \"tenant_id\": \"$CREATED_TENANT_ID\",
      \"name\": \"Postman User\",
      \"email\": \"postman-user-${UNIQUE_SUFFIX}@test.com\",
      \"phone\": \"81988888888\",
      \"user_type\": \"user\",
      \"department\": \"Operations\",
      \"is_active\": true,
      \"permissions\": {
        \"can_book\": true,
        \"can_manage_resources\": false,
        \"can_manage_users\": false,
        \"can_manage_tenants\": false
      },
      \"metadata\": {},
      \"password\": \"senha1234\"
    }"
    
    response=$(curl -s -X POST "$USER_URL/" \
        -H "Content-Type: application/json" \
        -d "$user_data")
    
    CREATED_USER_ID=$(extract_json "$response" "id")
    
    if [ -n "$CREATED_USER_ID" ]; then
        print_result "Create Regular User" "PASS"
        echo "  Created User ID: $CREATED_USER_ID"
    else
        print_result "Create Regular User" "FAIL" "No ID returned"
        echo "  Response: $response"
    fi
else
    print_result "Create Regular User" "FAIL" "No tenant ID available"
fi
echo ""

# Test 2.4: User Login
echo "Test 2.4: User Login"
if [ -n "$CREATED_USER_ID" ]; then
    response=$(curl -s -X POST "$USER_URL/login" \
        -H "Content-Type: application/x-www-form-urlencoded" \
        -d "email=postman-user-${UNIQUE_SUFFIX}@test.com&password=senha1234")
    
    USER_TOKEN=$(extract_json "$response" "access_token")
    
    if [ -n "$USER_TOKEN" ]; then
        print_result "User Login" "PASS"
        echo "  Token obtained (length: ${#USER_TOKEN})"
    else
        print_result "User Login" "FAIL" "No token returned"
        echo "  Response: $response"
    fi
else
    print_result "User Login" "FAIL" "No regular user available"
fi
echo ""

# Test 2.5: Get User Me (authenticated)
echo "Test 2.5: Get User Me (authenticated)"
if [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$USER_URL/me" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get User Me"
else
    print_result "Get User Me" "FAIL" "No token available"
fi
echo ""

# Test 2.6: Get All Users from Tenant
echo "Test 2.6: Get All Users from Tenant"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$USER_URL/?tenant_id=$CREATED_TENANT_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get All Users from Tenant"
else
    print_result "Get All Users from Tenant" "FAIL" "Missing tenant ID or token"
fi
echo ""

# Test 2.7: Get User by ID
echo "Test 2.7: Get User by ID"
if [ -n "$CREATED_USER_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$USER_URL/$CREATED_USER_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get User by ID"
else
    print_result "Get User by ID" "FAIL" "Missing user ID or token"
fi
echo ""

# Test 2.8: Update User
echo "Test 2.8: Update User"
if [ -n "$CREATED_USER_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    update_data='{"department": "Customer Service"}'
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$USER_URL/$CREATED_USER_ID" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -d "$update_data")
    check_status "$status_code" "200" "Update User"
else
    print_result "Update User" "FAIL" "Missing user ID or token"
fi
echo ""

# Test 2.9: Get Tenant Settings
echo "Test 2.9: Get Tenant Settings"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$TENANT_URL/$CREATED_TENANT_ID/settings" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get Tenant Settings"
else
    print_result "Get Tenant Settings" "FAIL" "Missing tenant ID or token"
fi
echo ""

# Test 2.10: Update Tenant Settings
echo "Test 2.10: Update Tenant Settings"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    settings_data='{
      "timezone": "America/Fortaleza",
      "working_hours_start": "09:00:00",
      "working_hours_end": "17:00:00"
    }'
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$TENANT_URL/$CREATED_TENANT_ID/settings" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -d "$settings_data")
    check_status "$status_code" "200" "Update Tenant Settings"
else
    print_result "Update Tenant Settings" "FAIL" "Missing tenant ID or token"
fi
echo ""

# ========================================
# SECTION 3: CATEGORY TESTS
# ========================================
echo "=========================================="
echo "SECTION 3: CATEGORY SERVICE TESTS"
echo "=========================================="
echo ""

# Test 3.1: Create Category
echo "Test 3.1: Create Category"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    category_data="{
      \"tenant_id\": \"$CREATED_TENANT_ID\",
      \"name\": \"Postman Test Category\",
      \"description\": \"Category for testing\",
      \"type\": \"fisico\",
      \"icon\": \"meeting\",
      \"color\": \"#00aa00\"
    }"
    
    response=$(curl -s -X POST "$CATEGORY_URL/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -d "$category_data")
    
    CREATED_CATEGORY_ID=$(extract_json "$response" "id")
    
    if [ -n "$CREATED_CATEGORY_ID" ]; then
        print_result "Create Category" "PASS"
        echo "  Created Category ID: $CREATED_CATEGORY_ID"
    else
        print_result "Create Category" "FAIL" "No ID returned"
        echo "  Response: $response"
    fi
else
    print_result "Create Category" "FAIL" "Missing tenant ID or token"
fi
echo ""

# Test 3.2: Get Categories by Tenant ID
echo "Test 3.2: Get Categories by Tenant ID"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$CATEGORY_URL/?tenant_id=$CREATED_TENANT_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get Categories by Tenant ID"
else
    print_result "Get Categories by Tenant ID" "FAIL" "Missing tenant ID or token"
fi
echo ""

# Test 3.3: Get Category by ID
echo "Test 3.3: Get Category by ID"
if [ -n "$CREATED_CATEGORY_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$CATEGORY_URL/$CREATED_CATEGORY_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get Category by ID"
else
    print_result "Get Category by ID" "FAIL" "Missing category ID or token"
fi
echo ""

# Test 3.4: Update Category
echo "Test 3.4: Update Category"
if [ -n "$CREATED_CATEGORY_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    update_data='{"description": "Updated description"}'
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$CATEGORY_URL/$CREATED_CATEGORY_ID" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -d "$update_data")
    check_status "$status_code" "200" "Update Category"
else
    print_result "Update Category" "FAIL" "Missing category ID or token"
fi
echo ""

# ========================================
# SECTION 4: RESOURCE TESTS
# ========================================
echo "=========================================="
echo "SECTION 4: RESOURCE SERVICE TESTS"
echo "=========================================="
echo ""

# Test 4.1: Create Resource
echo "Test 4.1: Create Resource"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$CREATED_CATEGORY_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    resource_data="{
      \"tenant_id\": \"$CREATED_TENANT_ID\",
      \"category_id\": \"$CREATED_CATEGORY_ID\",
      \"name\": \"Postman Test Resource\",
      \"description\": \"Resource for testing\",
      \"status\": \"disponivel\",
      \"capacity\": 10,
      \"location\": \"1º andar\",
      \"attributes\": {\"projector\": true, \"whiteboard\": true},
      \"availability_schedule\": {
        \"monday\": [\"08:00-12:00\", \"14:00-18:00\"],
        \"tuesday\": [\"08:00-18:00\"]
      },
      \"image_url\": \"https://example.com/image.jpg\"
    }"
    
    response=$(curl -s -X POST "$RESOURCE_URL/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -d "$resource_data")
    
    CREATED_RESOURCE_ID=$(extract_json "$response" "id")
    
    if [ -n "$CREATED_RESOURCE_ID" ]; then
        print_result "Create Resource" "PASS"
        echo "  Created Resource ID: $CREATED_RESOURCE_ID"
    else
        print_result "Create Resource" "FAIL" "No ID returned"
        echo "  Response: $response"
    fi
else
    print_result "Create Resource" "FAIL" "Missing tenant ID, category ID, or token"
fi
echo ""

# Test 4.2: Get All Resources
echo "Test 4.2: Get All Resources"
if [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$RESOURCE_URL/" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get All Resources"
else
    print_result "Get All Resources" "FAIL" "No token available"
fi
echo ""

# Test 4.3: Get Resources by Tenant ID
echo "Test 4.3: Get Resources by Tenant ID"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$RESOURCE_URL/?tenant_id=$CREATED_TENANT_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get Resources by Tenant ID"
else
    print_result "Get Resources by Tenant ID" "FAIL" "Missing tenant ID or token"
fi
echo ""

# Test 4.4: Get Resources by Category ID
echo "Test 4.4: Get Resources by Category ID"
if [ -n "$CREATED_CATEGORY_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$RESOURCE_URL/?category_id=$CREATED_CATEGORY_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get Resources by Category ID"
else
    print_result "Get Resources by Category ID" "FAIL" "Missing category ID or token"
fi
echo ""

# Test 4.5: Get Resource by ID
echo "Test 4.5: Get Resource by ID"
if [ -n "$CREATED_RESOURCE_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$RESOURCE_URL/$CREATED_RESOURCE_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get Resource by ID"
else
    print_result "Get Resource by ID" "FAIL" "Missing resource ID or token"
fi
echo ""

# Test 4.6: Get Resource Availability
echo "Test 4.6: Get Resource Availability"
if [ -n "$CREATED_RESOURCE_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    # Use a date in the future
    test_date="2025-12-16"
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$RESOURCE_URL/$CREATED_RESOURCE_ID/availability?data=$test_date" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get Resource Availability"
else
    print_result "Get Resource Availability" "FAIL" "Missing resource ID or token"
fi
echo ""

# Test 4.7: Update Resource
echo "Test 4.7: Update Resource"
if [ -n "$CREATED_RESOURCE_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    update_data='{"name": "Updated Postman Resource", "capacity": 15}'
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$RESOURCE_URL/$CREATED_RESOURCE_ID" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $ADMIN_TOKEN" \
        -d "$update_data")
    check_status "$status_code" "200" "Update Resource"
else
    print_result "Update Resource" "FAIL" "Missing resource ID or token"
fi
echo ""

# ========================================
# SECTION 5: BOOKING TESTS
# ========================================
echo "=========================================="
echo "SECTION 5: BOOKING SERVICE TESTS"
echo "=========================================="
echo ""

# Test 5.1: Create Booking
echo "Test 5.1: Create Booking"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$CREATED_RESOURCE_ID" ] && [ -n "$CREATED_USER_ID" ] && [ -n "$USER_TOKEN" ]; then
    booking_data="{
      \"tenant_id\": \"$CREATED_TENANT_ID\",
      \"resource_id\": \"$CREATED_RESOURCE_ID\",
      \"user_id\": \"$CREATED_USER_ID\",
      \"client_id\": \"$CREATED_USER_ID\",
      \"start_time\": \"2025-12-16T14:00:00\",
      \"end_time\": \"2025-12-16T15:00:00\",
      \"notes\": \"Postman test booking\",
      \"recurring_enabled\": false
    }"
    
    response=$(curl -s -X POST "$BOOKING_URL/" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -d "$booking_data")
    
    CREATED_BOOKING_ID=$(extract_json "$response" "id")
    
    if [ -n "$CREATED_BOOKING_ID" ]; then
        print_result "Create Booking" "PASS"
        echo "  Created Booking ID: $CREATED_BOOKING_ID"
    else
        print_result "Create Booking" "FAIL" "No ID returned"
        echo "  Response: $response"
    fi
else
    print_result "Create Booking" "FAIL" "Missing required IDs or token"
fi
echo ""

# Test 5.2: Get Booking by ID
echo "Test 5.2: Get Booking by ID"
if [ -n "$CREATED_BOOKING_ID" ] && [ -n "$USER_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$BOOKING_URL/$CREATED_BOOKING_ID" \
        -H "Authorization: Bearer $USER_TOKEN")
    check_status "$status_code" "200" "Get Booking by ID"
else
    print_result "Get Booking by ID" "FAIL" "Missing booking ID or token"
fi
echo ""

# Test 5.3: Get All Bookings from Tenant
echo "Test 5.3: Get All Bookings from Tenant"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$BOOKING_URL/?tenant_id=$CREATED_TENANT_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get All Bookings from Tenant"
else
    print_result "Get All Bookings from Tenant" "FAIL" "Missing tenant ID or token"
fi
echo ""

# Test 5.4: Get Bookings by Resource ID
echo "Test 5.4: Get Bookings by Resource ID"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$CREATED_RESOURCE_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$BOOKING_URL/?tenant_id=$CREATED_TENANT_ID&resource_id=$CREATED_RESOURCE_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "200" "Get Bookings by Resource ID"
else
    print_result "Get Bookings by Resource ID" "FAIL" "Missing required IDs or token"
fi
echo ""

# Test 5.5: Get Bookings by User ID
echo "Test 5.5: Get Bookings by User ID"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$CREATED_USER_ID" ] && [ -n "$USER_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" "$BOOKING_URL/?tenant_id=$CREATED_TENANT_ID&user_id=$CREATED_USER_ID" \
        -H "Authorization: Bearer $USER_TOKEN")
    check_status "$status_code" "200" "Get Bookings by User ID"
else
    print_result "Get Bookings by User ID" "FAIL" "Missing required IDs or token"
fi
echo ""

# Test 5.6: Update Booking
echo "Test 5.6: Update Booking"
if [ -n "$CREATED_BOOKING_ID" ] && [ -n "$USER_TOKEN" ]; then
    update_data='{"notes": "Updated booking notes", "status": "confirmado"}'
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X PUT "$BOOKING_URL/$CREATED_BOOKING_ID" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -d "$update_data")
    check_status "$status_code" "200" "Update Booking"
else
    print_result "Update Booking" "FAIL" "Missing booking ID or token"
fi
echo ""

# Test 5.7: Cancel Booking
echo "Test 5.7: Cancel Booking"
if [ -n "$CREATED_BOOKING_ID" ] && [ -n "$USER_TOKEN" ]; then
    cancel_data='{"reason": "Testing cancellation"}'
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH "$BOOKING_URL/$CREATED_BOOKING_ID/cancel" \
        -H "Content-Type: application/json" \
        -H "Authorization: Bearer $USER_TOKEN" \
        -d "$cancel_data")
    check_status "$status_code" "200" "Cancel Booking"
else
    print_result "Cancel Booking" "FAIL" "Missing booking ID or token"
fi
echo ""

# ========================================
# SECTION 6: CLEANUP
# ========================================
echo "=========================================="
echo "SECTION 6: CLEANUP (DELETE TESTS)"
echo "=========================================="
echo ""

# Test 6.1: Delete Resource
echo "Test 6.1: Delete Resource"
if [ -n "$CREATED_RESOURCE_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$RESOURCE_URL/$CREATED_RESOURCE_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "204" "Delete Resource"
else
    print_result "Delete Resource" "FAIL" "Missing resource ID or token"
fi
echo ""

# Test 6.2: Delete Category
echo "Test 6.2: Delete Category"
if [ -n "$CREATED_CATEGORY_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$CATEGORY_URL/$CREATED_CATEGORY_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "204" "Delete Category"
else
    print_result "Delete Category" "FAIL" "Missing category ID or token"
fi
echo ""

# Test 6.3: Delete Regular User
echo "Test 6.3: Delete Regular User"
if [ -n "$CREATED_USER_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$USER_URL/$CREATED_USER_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "204" "Delete Regular User"
else
    print_result "Delete Regular User" "FAIL" "Missing user ID or token"
fi
echo ""

# Test 6.4: Delete Admin User
echo "Test 6.4: Delete Admin User"
if [ -n "$CREATED_ADMIN_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$USER_URL/$CREATED_ADMIN_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "204" "Delete Admin User"
else
    print_result "Delete Admin User" "FAIL" "Missing admin ID or token"
fi
echo ""

# Test 6.5: Delete Tenant
echo "Test 6.5: Delete Tenant"
if [ -n "$CREATED_TENANT_ID" ] && [ -n "$ADMIN_TOKEN" ]; then
    status_code=$(curl -s -o /dev/null -w "%{http_code}" -X DELETE "$TENANT_URL/$CREATED_TENANT_ID" \
        -H "Authorization: Bearer $ADMIN_TOKEN")
    check_status "$status_code" "204" "Delete Tenant"
else
    print_result "Delete Tenant" "FAIL" "Missing tenant ID or token"
fi
echo ""

# ========================================
# FINAL SUMMARY
# ========================================
echo "=========================================="
echo "           TEST SUMMARY"
echo "=========================================="
echo ""
echo "Total Tests:  $TOTAL_TESTS"
echo -e "${GREEN}Passed:       $PASSED_TESTS${NC}"
echo -e "${RED}Failed:       $FAILED_TESTS${NC}"
echo ""

if [ $FAILED_TESTS -eq 0 ]; then
    echo -e "${GREEN}✓ ALL TESTS PASSED!${NC}"
    echo ""
    exit 0
else
    PASS_RATE=$((PASSED_TESTS * 100 / TOTAL_TESTS))
    echo -e "${YELLOW}Pass Rate: ${PASS_RATE}%${NC}"
    echo ""
    exit 1
fi
