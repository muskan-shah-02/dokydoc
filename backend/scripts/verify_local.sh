#!/bin/bash
# Local Verification Script (No Docker Required)
# Verifies Sprint 1 code structure and integrations

set -e

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=================================================="
echo "   DokyDoc Sprint 1 - Local Verification"
echo "=================================================="
echo ""

echo -e "${BLUE}[INFO]${NC} Verifying Sprint 1 implementations..."
echo ""

# Check file existence and sizes
echo "File Verification:"
echo "-------------------"

verify_file() {
    local file=$1
    local min_size=$2

    if [ -f "$file" ]; then
        size=$(stat -f%z "$file" 2>/dev/null || stat -c%s "$file" 2>/dev/null)
        if [ "$size" -gt "$min_size" ]; then
            echo -e "${GREEN}✓${NC} $file (${size} bytes)"
        else
            echo -e "${YELLOW}!${NC} $file exists but is small (${size} bytes)"
        fi
    else
        echo -e "${YELLOW}✗${NC} $file not found"
    fi
}

verify_file "app/services/lock_service.py" 3000
verify_file "app/middleware/rate_limiter.py" 2000
verify_file "app/tasks.py" 4000
verify_file "app/services/document_parser.py" 10000
verify_file "tests/integration/test_distributed_locks.py" 3000
verify_file "tests/integration/test_rate_limiting.py" 3000
verify_file "tests/integration/test_auth_refresh_tokens.py" 3000
verify_file "tests/integration/test_cost_tracking.py" 3000
verify_file "tests/integration/test_error_handling.py" 3000

echo ""
echo "Integration Verification:"
echo "-------------------------"

# Check for key integrations
if grep -q "from app.services.lock_service import" app/tasks.py; then
    echo -e "${GREEN}✓${NC} lock_service integrated in tasks.py"
else
    echo -e "${YELLOW}✗${NC} lock_service not found in tasks.py"
fi

if grep -q "from app.middleware.rate_limiter import limiter" main.py; then
    echo -e "${GREEN}✓${NC} rate_limiter integrated in main.py"
else
    echo -e "${YELLOW}✗${NC} rate_limiter not found in main.py"
fi

if grep -q "@limiter.limit" app/api/endpoints/billing.py; then
    echo -e "${GREEN}✓${NC} rate limiting applied to endpoints"
else
    echo -e "${YELLOW}✗${NC} rate limiting not applied to endpoints"
fi

echo ""
echo "Test Count:"
echo "-----------"

test_count=$(grep -r "def test_" tests/integration/ | wc -l | tr -d ' ')
echo -e "${GREEN}✓${NC} $test_count integration test methods found"

echo ""
echo "Deployment Scripts:"
echo "-------------------"

verify_file "scripts/deploy_staging.sh" 1000
verify_file "scripts/run_integration_tests.sh" 1000
verify_file "Dockerfile" 500
verify_file "docker-compose.yml" 2000

echo ""
echo -e "${GREEN}[SUCCESS]${NC} Local verification complete!"
echo ""
echo "Next steps:"
echo "1. Review DEPLOYMENT_GUIDE.md for full deployment instructions"
echo "2. On a machine with Docker, run: ./scripts/deploy_staging.sh"
echo "3. Then run tests with: ./scripts/run_integration_tests.sh"
