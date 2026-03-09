#!/bin/bash
# Test Anki setup endpoints

BASE_URL="http://localhost:8000/api/v1/auth"

echo "🧪 Testing Anki Setup API Endpoints"
echo "======================================"
echo ""

# Test 1: Register new user (should check Anki)
echo "Test 1: Register new user with Anki check"
echo "-------------------------------------------"
TIMESTAMP=$(date +%s)
USERNAME="testuser_${TIMESTAMP}"

REGISTER_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/register/" \
  -H "Content-Type: application/json" \
  -d "{
    \"username\": \"${USERNAME}\",
    \"email\": \"${USERNAME}@test.com\",
    \"password\": \"testpass123\",
    \"password_confirm\": \"testpass123\"
  }")

HTTP_CODE=$(echo "$REGISTER_RESPONSE" | tail -n1)
RESPONSE_BODY=$(echo "$REGISTER_RESPONSE" | sed '$d')

echo "HTTP Status: $HTTP_CODE"
echo "Response:"
echo "$RESPONSE_BODY" | python3 -m json.tool 2>/dev/null || echo "$RESPONSE_BODY"
echo ""

# Extract token if registration succeeded
if [ "$HTTP_CODE" = "201" ]; then
    TOKEN=$(echo "$RESPONSE_BODY" | python3 -c "import sys, json; print(json.load(sys.stdin)['token'])" 2>/dev/null)
    echo "✅ Registration succeeded! Token: ${TOKEN:0:20}..."
    
    # Test 2: Check Anki status
    echo ""
    echo "Test 2: Check Anki status for registered user"
    echo "-----------------------------------------------"
    curl -s "${BASE_URL}/check-anki/" \
      -H "Authorization: Token $TOKEN" | python3 -m json.tool
    echo ""
    
    # Test 3: Get AnkiConnect download info
    echo ""
    echo "Test 3: Get AnkiConnect installation guide"
    echo "--------------------------------------------"
    curl -s "${BASE_URL}/download-ankiconnect/" \
      -H "Authorization: Token $TOKEN" | python3 -m json.tool
    echo ""
elif [ "$HTTP_CODE" = "424" ]; then
    echo "⚠️  Registration blocked - Anki setup required"
    echo "   This is expected behavior when Anki is not ready"
else
    echo "❌ Unexpected response code: $HTTP_CODE"
fi

# Test 4: Login existing user
echo ""
echo "Test 4: Login with existing user (with Anki check)"
echo "---------------------------------------------------"
LOGIN_RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "${BASE_URL}/login/" \
  -H "Content-Type: application/json" \
  -d '{
    "username": "testuser",
    "password": "testpass123"
  }')

LOGIN_HTTP_CODE=$(echo "$LOGIN_RESPONSE" | tail -n1)
LOGIN_BODY=$(echo "$LOGIN_RESPONSE" | sed '$d')

echo "HTTP Status: $LOGIN_HTTP_CODE"
echo "Response:"
echo "$LOGIN_BODY" | python3 -m json.tool 2>/dev/null || echo "$LOGIN_BODY"
echo ""

if [ "$LOGIN_HTTP_CODE" = "200" ]; then
    echo "✅ Login succeeded with Anki check"
elif [ "$LOGIN_HTTP_CODE" = "424" ]; then
    echo "⚠️  Login blocked - Anki setup required"
else
    echo "❌ Login failed"
fi

echo ""
echo "======================================"
echo "✅ All API endpoint tests completed"
echo "======================================"
