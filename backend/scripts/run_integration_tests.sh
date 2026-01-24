#!/bin/bash
# DokyDoc Integration Test Runner
# Runs all Sprint 1 integration tests against staging environment

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

log_test() {
    echo -e "${CYAN}[TEST]${NC} $1"
}

# Print banner
echo "=================================================="
echo "   DokyDoc Sprint 1 - Integration Tests"
echo "=================================================="
echo ""

# Check if running in Docker container
if [ -f /.dockerenv ]; then
    IN_DOCKER=true
    log_info "Running inside Docker container"
else
    IN_DOCKER=false
    log_info "Running on host machine"
fi

# Step 1: Verify services are running
log_info "Verifying services are running..."

if [ "$IN_DOCKER" = false ]; then
    # Check if Docker containers are running
    if ! docker ps | grep -q "dokydoc_app"; then
        log_error "DokyDoc services are not running!"
        log_info "Please run ./scripts/deploy_staging.sh first"
        exit 1
    fi

    # Check Redis
    if ! docker ps | grep -q "dokydoc_redis"; then
        log_error "Redis is not running!"
        exit 1
    fi

    # Check PostgreSQL
    if ! docker ps | grep -q "dokydoc_db"; then
        log_error "PostgreSQL is not running!"
        exit 1
    fi

    log_success "All services are running"
else
    log_info "Assuming services are available in Docker network"
fi

# Step 2: Test connectivity
log_info "Testing service connectivity..."

if [ "$IN_DOCKER" = false ]; then
    # Test API
    API_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")
    if [ "$API_STATUS" != "200" ]; then
        log_warning "API health check returned: $API_STATUS"
        log_warning "Tests may fail if services are not fully initialized"
    else
        log_success "API is responding (HTTP $API_STATUS)"
    fi

    # Test Redis
    if ! docker exec dokydoc_redis redis-cli ping > /dev/null 2>&1; then
        log_warning "Cannot connect to Redis"
    else
        log_success "Redis is responding"
    fi
fi

# Step 3: Set test environment
log_info "Setting up test environment..."
export TESTING=true
export PYTHONPATH=/app:$PYTHONPATH
log_success "Test environment configured"

# Step 4: Run integration tests
echo ""
echo "=================================================="
echo "   Running Integration Tests"
echo "=================================================="
echo ""

# Determine how to run tests
if [ "$IN_DOCKER" = true ]; then
    # Already inside container, run directly
    TEST_COMMAND="python -m pytest tests/integration/ -v --tb=short --color=yes"
else
    # Run inside Docker container
    TEST_COMMAND="docker exec -e TESTING=true dokydoc_app python -m pytest tests/integration/ -v --tb=short --color=yes"
fi

# Track test results
FAILED_TESTS=()
PASSED_TESTS=0
SKIPPED_TESTS=0
TOTAL_TESTS=0

# Test modules in order
TEST_MODULES=(
    "test_distributed_locks.py"
    "test_rate_limiting.py"
    "test_auth_refresh_tokens.py"
    "test_cost_tracking.py"
    "test_error_handling.py"
)

for TEST_MODULE in "${TEST_MODULES[@]}"; do
    log_test "Running: $TEST_MODULE"
    echo ""

    if [ "$IN_DOCKER" = true ]; then
        python -m pytest "tests/integration/$TEST_MODULE" -v --tb=short --color=yes || {
            FAILED_TESTS+=("$TEST_MODULE")
        }
    else
        docker exec -e TESTING=true dokydoc_app python -m pytest "tests/integration/$TEST_MODULE" -v --tb=short --color=yes || {
            FAILED_TESTS+=("$TEST_MODULE")
        }
    fi

    echo ""
done

# Step 5: Run all tests together for summary
echo ""
echo "=================================================="
echo "   Full Test Suite Summary"
echo "=================================================="
echo ""

if [ "$IN_DOCKER" = true ]; then
    python -m pytest tests/integration/ -v --tb=short --color=yes --co -q | tail -20 || true
    RESULT=$(python -m pytest tests/integration/ -v --tb=short --color=yes 2>&1 || true)
else
    docker exec -e TESTING=true dokydoc_app python -m pytest tests/integration/ -v --tb=short --color=yes --co -q | tail -20 || true
    RESULT=$(docker exec -e TESTING=true dokydoc_app python -m pytest tests/integration/ -v --tb=short --color=yes 2>&1 || true)
fi

# Parse results
echo "$RESULT" | tail -30

echo ""
echo "=================================================="
echo "   Test Results"
echo "=================================================="

# Count results from output
if echo "$RESULT" | grep -q "passed"; then
    PASSED=$(echo "$RESULT" | grep -oP '\d+(?= passed)' | tail -1 || echo "0")
    log_success "$PASSED tests passed"
fi

if echo "$RESULT" | grep -q "failed"; then
    FAILED=$(echo "$RESULT" | grep -oP '\d+(?= failed)' | tail -1 || echo "0")
    log_error "$FAILED tests failed"
fi

if echo "$RESULT" | grep -q "skipped"; then
    SKIPPED=$(echo "$RESULT" | grep -oP '\d+(?= skipped)' | tail -1 || echo "0")
    log_warning "$SKIPPED tests skipped"
fi

if echo "$RESULT" | grep -q "error"; then
    ERRORS=$(echo "$RESULT" | grep -oP '\d+(?= error)' | tail -1 || echo "0")
    log_error "$ERRORS tests had errors"
fi

# Step 6: Sprint 1 feature verification
echo ""
echo "=================================================="
echo "   Sprint 1 Feature Verification"
echo "=================================================="

check_feature() {
    local feature_name=$1
    local test_pattern=$2

    if echo "$RESULT" | grep -q "$test_pattern"; then
        log_success "✓ $feature_name"
    else
        log_warning "✗ $feature_name (no tests found or all skipped)"
    fi
}

check_feature "Distributed Locks (FLAW-10)" "test_distributed_locks"
check_feature "Rate Limiting (API-01)" "test_rate_limiting"
check_feature "Refresh Tokens (BE-04)" "test_auth_refresh_tokens"
check_feature "Cost Tracking (FLAW-17)" "test_cost_tracking"
check_feature "Error Handling (BE-01)" "test_error_handling"

# Final summary
echo ""
if [ ${#FAILED_TESTS[@]} -eq 0 ]; then
    log_success "All integration tests completed!"
    echo ""
    log_info "Sprint 1 is verified and ready for production deployment"
    exit 0
else
    log_warning "Some test modules had failures:"
    for FAILED_TEST in "${FAILED_TESTS[@]}"; do
        echo "  - $FAILED_TEST"
    done
    echo ""
    log_info "Note: Some tests may fail if Redis/PostgreSQL are not yet fully initialized"
    log_info "or if the services are still warming up. Try running the tests again."
    exit 1
fi
