#!/bin/bash
################################################################################
# DokydDoc — Server Setup Script
# Run ONCE on a fresh Ubuntu 22.04 server as root or sudo user
#
# Usage:
#   ssh root@YOUR_SERVER_IP
#   curl -fsSL https://raw.githubusercontent.com/YOUR_ORG/dokydoc/main/scripts/setup-server.sh | bash
#
# OR copy this file to the server and run:
#   chmod +x setup-server.sh && sudo ./setup-server.sh
################################################################################

set -e  # Exit on any error
set -u  # Treat unset variables as errors

echo "=============================================="
echo " DokydDoc Server Setup — Ubuntu 22.04"
echo "=============================================="

# ── Variables ─────────────────────────────────────────────────────────────────
DEPLOY_USER="dokydoc"
APP_DIR="/home/$DEPLOY_USER/dokydoc"
DOMAIN="${1:-}"  # Pass your domain as first argument: ./setup-server.sh yourdomain.com

# ── System Updates ────────────────────────────────────────────────────────────
echo ""
echo "📦 Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq
apt-get install -y -qq \
    curl wget git unzip \
    ufw fail2ban \
    htop iotop nethogs \
    nginx certbot python3-certbot-nginx

# ── Create deploy user ────────────────────────────────────────────────────────
echo ""
echo "👤 Creating deploy user: $DEPLOY_USER"
if ! id "$DEPLOY_USER" &>/dev/null; then
    useradd -m -s /bin/bash -G sudo,docker "$DEPLOY_USER"
    echo "   User $DEPLOY_USER created"
else
    echo "   User $DEPLOY_USER already exists"
fi

# ── Install Docker ────────────────────────────────────────────────────────────
echo ""
echo "🐳 Installing Docker..."
if ! command -v docker &>/dev/null; then
    curl -fsSL https://get.docker.com | sh
    usermod -aG docker "$DEPLOY_USER"
    systemctl enable docker
    systemctl start docker
    echo "   Docker installed: $(docker --version)"
else
    echo "   Docker already installed: $(docker --version)"
fi

# ── Install Docker Compose ────────────────────────────────────────────────────
echo ""
echo "🐳 Installing Docker Compose..."
if ! command -v docker-compose &>/dev/null; then
    COMPOSE_VERSION="v2.24.1"
    curl -fsSL "https://github.com/docker/compose/releases/download/${COMPOSE_VERSION}/docker-compose-linux-x86_64" \
        -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
    echo "   Docker Compose installed: $(docker-compose --version)"
else
    echo "   Docker Compose already installed: $(docker-compose --version)"
fi

# ── Firewall Setup ────────────────────────────────────────────────────────────
echo ""
echo "🔒 Configuring UFW firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp      # HTTP (redirects to HTTPS)
ufw allow 443/tcp     # HTTPS
# DO NOT open 8000, 5432, 6379, 5555 — these stay internal
ufw --force enable
echo "   Firewall configured. Status:"
ufw status

# ── Fail2ban (brute force protection) ─────────────────────────────────────────
echo ""
echo "🛡️  Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime  = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port    = ssh
logpath = /var/log/auth.log

[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled  = true
filter   = nginx-limit-req
action   = iptables-multiport[name=nginx, port="http,https"]
logpath  = /var/log/nginx/error.log
findtime = 600
bantime  = 7200
maxretry = 10
EOF
systemctl enable fail2ban
systemctl restart fail2ban

# ── Swap space (important for low-RAM servers) ────────────────────────────────
echo ""
echo "💾 Setting up swap space..."
if [ ! -f /swapfile ]; then
    fallocate -l 4G /swapfile
    chmod 600 /swapfile
    mkswap /swapfile
    swapon /swapfile
    echo '/swapfile none swap sw 0 0' >> /etc/fstab
    echo "   4GB swap created"
else
    echo "   Swap already configured"
fi

# ── System tuning for production ───────────────────────────────────────────────
echo ""
echo "⚙️  Tuning system parameters..."
cat >> /etc/sysctl.conf << 'EOF'

# DokydDoc production tuning
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535
vm.swappiness = 10
vm.overcommit_memory = 1
EOF
sysctl -p

# ── Directory structure ───────────────────────────────────────────────────────
echo ""
echo "📁 Creating application directories..."
mkdir -p $APP_DIR
mkdir -p /var/log/dokydoc
mkdir -p /var/www/certbot
chown -R $DEPLOY_USER:$DEPLOY_USER $APP_DIR
chown -R $DEPLOY_USER:$DEPLOY_USER /var/log/dokydoc

# ── SSH key for GitHub Actions ────────────────────────────────────────────────
echo ""
echo "🔑 Setting up SSH for deployments..."
sudo -u $DEPLOY_USER mkdir -p /home/$DEPLOY_USER/.ssh
sudo -u $DEPLOY_USER chmod 700 /home/$DEPLOY_USER/.ssh

echo ""
echo "=============================================="
echo " ✅ Server setup complete!"
echo "=============================================="
echo ""
echo "Next steps:"
echo ""
echo "  1. Add your SSH public key to /home/$DEPLOY_USER/.ssh/authorized_keys"
echo "     (or set up the GitHub deploy key)"
echo ""
echo "  2. Clone your repo:"
echo "     sudo -u $DEPLOY_USER git clone https://github.com/YOUR_ORG/dokydoc $APP_DIR"
echo ""
echo "  3. Set up environment variables:"
echo "     cp $APP_DIR/backend/.env.production.example $APP_DIR/backend/.env"
echo "     nano $APP_DIR/backend/.env  # Fill in all REQUIRED values"
echo ""
echo "  4. Get SSL certificate (replace with your domain):"
echo "     certbot certonly --standalone -d yourdomain.com -d www.yourdomain.com"
echo ""
echo "  5. Update nginx.conf with your domain name, then start services:"
echo "     cd $APP_DIR/backend"
echo "     docker compose -f docker-compose.prod.yml up -d"
echo ""
echo "  6. Run database migrations:"
echo "     docker compose -f docker-compose.prod.yml run --rm app alembic upgrade head"
echo ""
echo "  7. Verify everything is working:"
echo "     curl https://yourdomain.com/health"
echo ""
