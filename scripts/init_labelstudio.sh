#!/bin/bash
# Initialize Label Studio: create default user, project, and print API key.
# Usage: bash scripts/init_labelstudio.sh [LS_URL]
#
# Prerequisites: Label Studio must be running (docker compose up labelstudio).
# Reads LABEL_STUDIO_URL from .env or uses http://localhost:8080 as default.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

# Source .env if it exists
if [ -f "$PROJECT_DIR/.env" ]; then
    set -a
    # shellcheck disable=SC1091
    source "$PROJECT_DIR/.env"
    set +a
fi

LS_URL="${1:-${LABEL_STUDIO_URL:-http://localhost:8080}}"
LS_EMAIL="${LABEL_STUDIO_ADMIN_EMAIL:-admin@pet-pipeline.local}"
LS_PASSWORD="${LABEL_STUDIO_ADMIN_PASSWORD:-admin123456}"

echo "=== Label Studio Initialization ==="
echo "URL: $LS_URL"
echo "Admin email: $LS_EMAIL"

# Wait for Label Studio to be healthy
echo "Waiting for Label Studio to be ready..."
for i in $(seq 1 30); do
    if curl -sf "$LS_URL/health" > /dev/null 2>&1; then
        echo "Label Studio is ready."
        break
    fi
    if [ "$i" -eq 30 ]; then
        echo "ERROR: Label Studio not responding at $LS_URL after 30 attempts."
        echo "Make sure to run: docker compose up -d labelstudio"
        exit 1
    fi
    sleep 2
done

# Create admin user (Label Studio API for user signup)
echo "Creating admin user..."
SIGNUP_RESPONSE=$(curl -sf -X POST "$LS_URL/user/signup" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$LS_EMAIL\", \"password\": \"$LS_PASSWORD\"}" \
    2>&1) || true

if echo "$SIGNUP_RESPONSE" | python3 -c "import sys,json; json.load(sys.stdin)['id']" 2>/dev/null; then
    echo "Admin user created: $LS_EMAIL"
else
    echo "Admin user already exists or signup API differs — proceeding with login."
fi

# Login to get session token
echo "Logging in..."
LOGIN_RESPONSE=$(curl -sf -c - -X POST "$LS_URL/user/login" \
    -H "Content-Type: application/json" \
    -d "{\"email\": \"$LS_EMAIL\", \"password\": \"$LS_PASSWORD\"}" \
    2>&1) || true

# Get API token
echo "Retrieving API token..."
API_TOKEN=$(curl -sf "$LS_URL/api/current-user/token" \
    -H "Content-Type: application/json" \
    -u "$LS_EMAIL:$LS_PASSWORD" \
    2>/dev/null | python3 -c "import sys,json; print(json.load(sys.stdin).get('token',''))" 2>/dev/null) || true

if [ -z "$API_TOKEN" ]; then
    echo ""
    echo "WARNING: Could not auto-retrieve API token."
    echo "Please:"
    echo "  1. Open $LS_URL in your browser"
    echo "  2. Log in with: $LS_EMAIL / $LS_PASSWORD"
    echo "  3. Go to Account & Settings → Access Token"
    echo "  4. Copy the token and add to .env: LABEL_STUDIO_API_KEY=<token>"
    exit 0
fi

echo "API Token: $API_TOKEN"

# Create default project for pet-annotation review
echo "Creating pet-annotation-review project..."
LABELING_CONFIG='<View>
  <Image name="image" value="$image"/>
  <Header value="Species: $species"/>
  <TextArea name="vlm_output" toName="image" value="$vlm_output"
    editable="true" maxSubmissions="1" rows="15"/>
  <Choices name="review_decision" toName="image" choice="single" required="true">
    <Choice value="approve"/>
    <Choice value="reject"/>
    <Choice value="correct"/>
  </Choices>
</View>'

PROJECT_RESPONSE=$(curl -sf -X POST "$LS_URL/api/projects" \
    -H "Authorization: Token $API_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{
        \"title\": \"pet-annotation-review\",
        \"description\": \"Human review of VLM annotations for quality assurance and DPO pair generation.\",
        \"label_config\": $(python3 -c "import json; print(json.dumps('''$LABELING_CONFIG'''))")
    }" 2>&1) || true

PROJECT_ID=$(echo "$PROJECT_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('id',''))" 2>/dev/null) || true

if [ -n "$PROJECT_ID" ]; then
    echo "Project created: pet-annotation-review (ID: $PROJECT_ID)"
else
    echo "Project may already exist — check $LS_URL/projects"
fi

# Update .env file with the API key
ENV_FILE="$PROJECT_DIR/.env"
if [ -f "$ENV_FILE" ]; then
    if grep -q "^LABEL_STUDIO_API_KEY=" "$ENV_FILE"; then
        sed -i.bak "s|^LABEL_STUDIO_API_KEY=.*|LABEL_STUDIO_API_KEY=$API_TOKEN|" "$ENV_FILE"
        rm -f "$ENV_FILE.bak"
        echo "Updated LABEL_STUDIO_API_KEY in .env"
    else
        echo "LABEL_STUDIO_API_KEY=$API_TOKEN" >> "$ENV_FILE"
        echo "Added LABEL_STUDIO_API_KEY to .env"
    fi
fi

echo ""
echo "=== Label Studio initialization complete ==="
echo "URL:       $LS_URL"
echo "Email:     $LS_EMAIL"
echo "API Token: $API_TOKEN"
echo ""
echo "Use with pet-annotation CLI:"
echo "  pet-annotation ls-import --ls-url $LS_URL --ls-key $API_TOKEN"
echo "  pet-annotation ls-export --ls-url $LS_URL --ls-key $API_TOKEN"
