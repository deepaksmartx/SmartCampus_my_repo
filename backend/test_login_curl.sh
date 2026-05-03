#!/bin/bash
# Simple curl-based login test script
# Usage: bash test_login_curl.sh

BASE_URL="http://localhost:8000"
TIMESTAMP=$(date +%s)
TEST_EMAIL="curltest_$TIMESTAMP@example.com"
TEST_PASSWORD="TestPass123!"
TEST_NAME="Curl Test User"

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║         LOGIN TEST USING CURL                             ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"

# Step 1: Register
echo -e "\n${YELLOW}[1/3] Registering user...${NC}"
REGISTER_PAYLOAD=$(cat <<EOF
{
  "name": "$TEST_NAME",
  "email": "$TEST_EMAIL",
  "password": "$TEST_PASSWORD",
  "role": "Student",
  "phone_number": "9876543210"
}
EOF
)

REGISTER_RESPONSE=$(curl -s -X POST "$BASE_URL/users/register" \
  -H "Content-Type: application/json" \
  -d "$REGISTER_PAYLOAD")

if echo "$REGISTER_RESPONSE" | grep -q "successfully"; then
  echo -e "${GREEN}✅ Registration successful${NC}"
else
  echo -e "${RED}❌ Registration failed: $REGISTER_RESPONSE${NC}"
  exit 1
fi

# Step 2: Login
echo -e "\n${YELLOW}[2/3] Logging in...${NC}"

LOGIN_RESPONSE=$(curl -s -X POST "$BASE_URL/login" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "username=$TEST_EMAIL&password=$TEST_PASSWORD")

TOKEN=$(echo "$LOGIN_RESPONSE" | grep -o '"access_token":"[^"]*' | cut -d'"' -f4)

if [ -z "$TOKEN" ]; then
  echo -e "${RED}❌ Login failed: $LOGIN_RESPONSE${NC}"
  exit 1
fi

echo -e "${GREEN}✅ Login successful!${NC}"
echo -e "   Token: ${TOKEN:0:50}..."

# Step 3: Get Profile
echo -e "\n${YELLOW}[3/3] Fetching profile...${NC}"

PROFILE_RESPONSE=$(curl -s -X GET "$BASE_URL/users/profile" \
  -H "Authorization: Bearer $TOKEN")

if echo "$PROFILE_RESPONSE" | grep -q "$TEST_EMAIL"; then
  echo -e "${GREEN}✅ Profile retrieved successfully!${NC}"
  echo "$PROFILE_RESPONSE" | grep -o '"name":"[^"]*' | cut -d'"' -f4 | xargs -I {} echo "   Name: {}"
  echo "$PROFILE_RESPONSE" | grep -o '"email":"[^"]*' | cut -d'"' -f4 | xargs -I {} echo "   Email: {}"
  echo "$PROFILE_RESPONSE" | grep -o '"role":"[^"]*' | cut -d'"' -f4 | xargs -I {} echo "   Role: {}"
else
  echo -e "${RED}❌ Profile fetch failed: $PROFILE_RESPONSE${NC}"
  exit 1
fi

echo -e "\n${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║  ✅ ALL TESTS PASSED!                                     ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
