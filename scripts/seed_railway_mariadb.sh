#!/usr/bin/env bash
# Seed the Railway MariaDB with FHIR data from seed_fhir_data.sql
#
# Method: SSH into the OpenEMR service (which has network access to mariadb.railway.internal),
# write the SQL to a temp file on the remote, then execute it. (Piping stdin fails due to TTY.)
#
# Prerequisites:
#   - railway login
#   - Project linked: cd openemr-system && railway link
#   - OpenEMR service must be awake (visit the app URL or disable "Sleep when idle")
#
# Usage: ./openemr-agent/scripts/seed_railway_mariadb.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SEED_SQL="${SCRIPT_DIR}/seed_fhir_data.sql"

if [[ ! -f "$SEED_SQL" ]]; then
  echo "Error: seed file not found: $SEED_SQL"
  exit 1
fi

echo "Seeding Railway MariaDB via OpenEMR SSH..."
SEED_B64=$(base64 -i "$SEED_SQL" 2>/dev/null || base64 < "$SEED_SQL")
if railway ssh -s openemr "echo '$SEED_B64' | base64 -d > /tmp/seed.sql && mysql -h \$MYSQL_HOST -u \$MYSQL_USER -p\$MYSQL_PASSWORD \$MYSQL_DATABASE -A < /tmp/seed.sql && rm /tmp/seed.sql && echo Done"; then
  echo "Seed completed successfully."
else
  echo "Seed failed or OpenEMR service may be sleeping. Try:"
  echo "  1. Visit your OpenEMR URL to wake the service"
  echo "  2. Disable 'Sleep when idle' in Railway service settings"
  echo "  3. Re-run this script"
  exit 1
fi
