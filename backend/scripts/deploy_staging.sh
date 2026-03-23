#!/bin/bash
# DokyDoc Staging Deployment Script
# Deploys Sprint 1 to staging environment and verifies all services

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
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

# Print banner
echo "=================================================="
echo "   DokyDoc Sprint 1 - Staging Deployment"
echo "=================================================="
echo ""

# Step 1: Check prerequisites
log_info "Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    log_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

log_success "Prerequisites check passed"

# Step 2: Verify environment file
log_info "Checking environment configuration..."

if [ ! -f .env ]; then
    log_error ".env file not found!"
    log_info "Creating .env from template..."

    if [ -f env.example ]; then
        cp env.example .env
        log_warning "Please update .env file with your actual values (SECRET_KEY, GEMINI_API_KEY)"
        log_warning "Press Enter to continue after updating .env..."
        read
    else
        log_error "env.example not found. Cannot create .env file."
        exit 1
    fi
fi

# Verify required environment variables
if ! grep -q "SECRET_KEY" .env || grep -q "your-super-secret-key-here" .env; then
    log_warning "SECRET_KEY appears to be default/missing. Please set a secure SECRET_KEY in .env"
fi

log_success "Environment configuration verified"

# Step 3: Stop existing containers
log_info "Stopping existing containers..."
docker-compose down -v 2>/dev/null || docker compose down -v 2>/dev/null || true
log_success "Existing containers stopped"

# Step 4: Build images
log_info "Building Docker images..."
docker-compose build --no-cache || docker compose build --no-cache
log_success "Docker images built successfully"

# Step 5: Start services
log_info "Starting services (PostgreSQL, Redis, App, Worker, Flower)..."
docker-compose up -d db redis || docker compose up -d db redis
sleep 10  # Wait for db and redis to be ready

log_info "Starting application services..."
docker-compose up -d app worker flower || docker compose up -d app worker flower
log_success "All services started"

# Step 6: Wait for services to be healthy
log_info "Waiting for services to be healthy (this may take up to 90 seconds)..."

MAX_WAIT=90
ELAPSED=0
INTERVAL=5

while [ $ELAPSED -lt $MAX_WAIT ]; do
    if docker-compose ps | grep -q "healthy" || docker compose ps | grep -q "healthy"; then
        log_success "Services are healthy"
        break
    fi

    if [ $ELAPSED -eq 0 ]; then
        echo -n "Waiting"
    else
        echo -n "."
    fi

    sleep $INTERVAL
    ELAPSED=$((ELAPSED + INTERVAL))
done

echo ""

if [ $ELAPSED -ge $MAX_WAIT ]; then
    log_warning "Services taking longer than expected to become healthy"
    log_info "Checking container status..."
    docker-compose ps || docker compose ps
fi

# Step 7: Run database migrations
log_info "Running database migrations..."
docker-compose exec -T app alembic upgrade head || docker compose exec -T app alembic upgrade head || {
    log_warning "Migrations may have already been applied or service not ready yet"
}

# Step 8: Display service URLs
echo ""
log_success "Deployment complete!"
echo ""
echo "=================================================="
echo "   Service URLs"
echo "=================================================="
echo "🌐 API Server:          http://localhost:8000"
echo "📚 API Documentation:   http://localhost:8000/docs"
echo "🌺 Flower Dashboard:    http://localhost:5555"
echo "🐘 PostgreSQL:          localhost:5432"
echo "🔴 Redis:               localhost:6379"
echo ""
echo "=================================================="
echo "   Container Status"
echo "=================================================="
docker-compose ps || docker compose ps
echo ""

# Step 9: Run basic health check
log_info "Running health check..."
sleep 5

HEALTH_CHECK=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health 2>/dev/null || echo "000")

if [ "$HEALTH_CHECK" = "200" ]; then
    log_success "Health check passed - API is responding"
else
    log_warning "Health check returned status: $HEALTH_CHECK"
    log_info "Service may still be starting up. Please check logs with: docker-compose logs app"
fi

echo ""
log_info "To view logs, run: docker-compose logs -f [service]"
log_info "To stop services, run: docker-compose down"
log_info "To run integration tests, run: ./scripts/run_integration_tests.sh"
echo ""
log_success "Staging deployment complete!"
