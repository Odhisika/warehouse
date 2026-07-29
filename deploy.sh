#!/bin/bash

set -e

echo "🚀 Starting deployment..."

cd /var/www/nexus_warehouse_project
source venv/bin/activate

echo "📥 Fetching latest code..."
git fetch origin
git reset --hard origin/main
git clean -fd

echo "🔐 Fixing permissions (BEFORE Django runs)..."
sudo mkdir -p /var/www/nexus_warehouse_project/logs
sudo touch /var/www/nexus_warehouse_project/logs/payments.log

sudo chown -R lig:www-data /var/www/nexus_warehouse_project
sudo chmod -R 755 /var/www/nexus_warehouse_project
sudo chmod -R 775 /var/www/nexus_warehouse_project/media
sudo chmod -R 775 /var/www/nexus_warehouse_project/logs

echo "📦 Installing dependencies..."
pip install -r requirements.txt

echo "⚙️ Applying database migrations..."
python manage.py migrate --noinput

echo "🧹 Collecting static files..."
python manage.py collectstatic --noinput

echo "🔍 Running Django checks..."
python manage.py check

echo "🔄 Restarting Apache..."
sudo systemctl restart apache2

echo "✅ Deployment complete!"
