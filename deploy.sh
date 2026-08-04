#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$REPO_DIR"

echo "==> Backing up databases before deploy..."
BACKUP_DIR="$REPO_DIR/.backups/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"
for db in db.sqlite3 branch_dbs/*.sqlite3; do
    if [ -f "$db" ]; then
        cp "$db" "$BACKUP_DIR/"
    fi
done
echo "==> Database backups saved to $BACKUP_DIR"

echo "==> Pulling latest changes from git..."
git pull

echo "==> Fixing ownership and permissions..."
sudo chown -R lig:www-data "$REPO_DIR" --exclude=venv --exclude=media --exclude=.backups 2>/dev/null || true
sudo find "$REPO_DIR" -type d -not -path "*/media/*" -not -path "*/venv/*" -not -path "*/.backups/*" -exec chmod 755 {} +
sudo find "$REPO_DIR" -type f -not -path "*/media/*" -not -path "*/venv/*" -not -path "*/.backups/*" -exec chmod 664 {} +
sudo chmod +x "$REPO_DIR/deploy.sh"

echo "==> Ensuring media directories exist and are writable..."
sudo mkdir -p "$REPO_DIR"/media/brand
sudo mkdir -p "$REPO_DIR"/media/signatures
sudo mkdir -p "$REPO_DIR"/media/delivery_photos
sudo chown -R www-data:www-data "$REPO_DIR/media"
sudo find "$REPO_DIR/media" -type d -exec chmod 775 {} +
sudo find "$REPO_DIR/media" -type f -exec chmod 664 {} +

echo "==> Ensuring branch_dbs directory is writable..."
sudo mkdir -p "$REPO_DIR/branch_dbs"
sudo chown lig:www-data "$REPO_DIR/branch_dbs"
sudo chmod 775 "$REPO_DIR/branch_dbs"

echo "==> Adding safe directory for git..."
sudo git config --global --add safe.directory "$REPO_DIR"


VENV_DIR="$REPO_DIR/venv"

echo "==> Ensuring venv executables are runnable..."
sudo chmod +x "$VENV_DIR"/bin/*

echo "==> Installing dependencies..."
"$VENV_DIR/bin/pip" install -r requirements.txt

echo "==> Applying database migrations..."
"$VENV_DIR/bin/python" manage.py migrate --noinput

echo "==> Applying branch database migrations..."
"$VENV_DIR/bin/python" manage.py migrate_branches

echo "==> Seeding default data (creates ACCRA branch, users, and branch tables if missing)..."
"$VENV_DIR/bin/python" manage.py seed_data

echo "==> Re-running branch migrations after seeding..."
"$VENV_DIR/bin/python" manage.py migrate_branches

echo "==> Collecting static files..."
"$VENV_DIR/bin/python" manage.py collectstatic --noinput

echo "==> Running Django checks..."
"$VENV_DIR/bin/python" manage.py check

echo "==> Restarting Apache..."
sudo systemctl restart apache2

echo "==> Fixing SQLite database permissions..."
sudo chown lig:www-data "$REPO_DIR"/db.sqlite3 "$REPO_DIR"/branch_dbs/*.sqlite3 2>/dev/null || true
sudo chmod 664 "$REPO_DIR"/db.sqlite3 "$REPO_DIR"/branch_dbs/*.sqlite3 2>/dev/null || true
sudo chown lig:www-data "$REPO_DIR"
sudo chmod 775 "$REPO_DIR"
sudo chmod 775 "$REPO_DIR/media"

echo "==> Deployment complete!"
