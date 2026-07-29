#!/bin/bash

set -e

echo "🚀 Starting deployment..."

cd /var/www/warehouse
source venv/bin/activate

echo "📥 Fetching latest code..."
git fetch origin
git reset --hard origin/main
git clean -fd

echo "🔐 Fixing permissions (BEFORE Django runs)..."
sudo mkdir -p /var/www/warehouse/logs
sudo touch /var/www/warehouse/logs/payments.log
suod mkdir -p /var/www/warehouse/media

sudo chown -R lig:www-data /var/www/warehouse
sudo chmod -R 755 /var/www/warehouse
sudo chmod -R 775 /var/www/warehouse/media
sudo chmod -R 775 /var/www/warehouse/logs

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
