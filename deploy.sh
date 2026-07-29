#!/bin/bash
set -e

# ============================================
# Nexus Warehouse - Ubuntu Apache Deployment
# ============================================

# Configuration
PROJECT_NAME="nexus_warehouse_project"
PROJECT_DIR="/var/www/$PROJECT_NAME"
VENV_DIR="$PROJECT_DIR/venv"
PYTHON_VERSION="python3"
APACHE_CONF="/etc/apache2/sites-available/${PROJECT_NAME}.conf"
STATIC_ROOT="$PROJECT_DIR/staticfiles"
MEDIA_ROOT="$PROJECT_DIR/media"
DB_DIR="$PROJECT_DIR/branch_dbs"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${GREEN}=== Nexus Warehouse Deployment Script ===${NC}"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo -e "${RED}Error: This script must be run as root (sudo)${NC}"
    exit 1
fi

# Update system packages
echo -e "${YELLOW}[1/8] Updating system packages...${NC}"
apt-get update
apt-get upgrade -y

# Install required packages
echo -e "${YELLOW}[2/8] Installing required packages...${NC}"
apt-get install -y \
    apache2 \
    libapache2-mod-wsgi-py3 \
    python3 \
    python3-pip \
    python3-venv \
    sqlite3 \
    git \
    curl

# Enable Apache modules
echo -e "${YELLOW}[3/8] Enabling Apache modules...${NC}"
a2enmod wsgi
a2enmod rewrite
a2enmod headers
a2enmod ssl

# Create project directory structure
echo -e "${YELLOW}[4/8] Setting up project directory...${NC}"
mkdir -p "$PROJECT_DIR"
mkdir -p "$STATIC_ROOT"
mkdir -p "$MEDIA_ROOT"
mkdir -p "$DB_DIR"
mkdir -p /var/log/apache2

# Copy project files (assuming script runs from project root)
CURRENT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
rsync -av --exclude='venv' --exclude='__pycache__' --exclude='*.pyc' \
    "$CURRENT_DIR/" "$PROJECT_DIR/"

# Set ownership
chown -R www-data:www-data "$PROJECT_DIR"
chmod -R 755 "$PROJECT_DIR"

# Create virtual environment and install dependencies
echo -e "${YELLOW}[5/8] Setting up Python virtual environment...${NC}"
if [ ! -d "$VENV_DIR" ]; then
    $PYTHON_VERSION -m venv "$VENV_DIR"
fi
source "$VENV_DIR/bin/activate"
pip install --upgrade pip
pip install -r "$PROJECT_DIR/requirements.txt"
pip install mod_wsgi

# Django setup
echo -e "${YELLOW}[6/8] Running Django setup...${NC}"
cd "$PROJECT_DIR"
export DJANGO_SETTINGS_MODULE=nexus_warehouse.settings
export DJANGO_SECRET_KEY="$(openssl rand -hex 32)"
export DJANGO_DEBUG="False"
export DJANGO_ALLOWED_HOSTS="$(hostname -I | awk '{print $1}'),localhost,127.0.0.1"

"$VENV_DIR/bin/python" manage.py collectstatic --noinput
"$VENV_DIR/bin/python" manage.py migrate --noinput
"$VENV_DIR/bin/python" manage.py createsuperuser --noinput || true

# Set permissions for SQLite databases
chmod 775 "$DB_DIR"
chown -R www-data:www-data "$DB_DIR"

# Create Apache configuration
echo -e "${YELLOW}[7/8] Creating Apache configuration...${NC}"
cat > "$APACHE_CONF" <<EOF
<VirtualHost *:80>
    ServerName $(hostname -I | awk '{print $1}')
    ServerAlias localhost
    DocumentRoot $PROJECT_DIR

    # Django WSGI
    WSGIDaemonProcess $PROJECT_NAME python-home=$VENV_DIR python-path=$PROJECT_DIR
    WSGIProcessGroup $PROJECT_NAME
    WSGIScriptAlias / $PROJECT_DIR/nexus_warehouse/wsgi.py

    # Static files
    Alias /static/ $STATIC_ROOT/
    <Directory $STATIC_ROOT>
        Require all granted
    </Directory>

    # Media files
    Alias /media/ $MEDIA_ROOT/
    <Directory $MEDIA_ROOT>
        Require all granted
    </Directory>

    # Project directory
    <Directory $PROJECT_DIR>
        <Files wsgi.py>
            Require all granted
        </Files>
    </Directory>

    # Logging
    ErrorLog /var/log/apache2/${PROJECT_NAME}_error.log
    CustomLog /var/log/apache2/${PROJECT_NAME}_access.log combined

    # Security headers
    Header always set X-Content-Type-Options nosniff
    Header always set X-Frame-Options DENY
    Header always set X-XSS-Protection "1; mode=block"
</VirtualHost>
EOF

# Enable site and restart Apache
echo -e "${YELLOW}[8/8] Activating Apache site...${NC}"
a2ensite "$PROJECT_NAME"
systemctl restart apache2
systemctl enable apache2

# Create environment file for future use
cat > "$PROJECT_DIR/.env" <<EOF
DJANGO_SECRET_KEY=$DJANGO_SECRET_KEY
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=$(hostname -I | awk '{print $1}'),localhost,127.0.0.1
EOF
chmod 600 "$PROJECT_DIR/.env"
chown www-data:www-data "$PROJECT_DIR/.env"

echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo -e "${GREEN}Project installed at: $PROJECT_DIR${NC}"
echo -e "${GREEN}Apache config: $APACHE_CONF${NC}"
echo -e "${GREEN}Access at: http://$(hostname -I | awk '{print $1}')${NC}"
echo ""
echo -e "${YELLOW}Next steps:${NC}"
echo "1. Create superuser: sudo -u www-data $PROJECT_DIR/venv/bin/python $PROJECT_DIR/manage.py createsuperuser"
echo "2. Set DEBUG=False in .env for production"
echo "3. Configure SSL with certbot for HTTPS"
