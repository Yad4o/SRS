#!/usr/bin/env bash
# =============================================================================
# scripts/generate-dev-cert.sh
#
# Generates a self-signed TLS certificate + key for LOCAL DEVELOPMENT ONLY,
# so the nginx service in docker-compose.yml has something to terminate TLS
# with. Browsers will show a "not secure" warning for self-signed certs —
# that's expected locally; click through it or `curl -k`.
#
# For production, use Let's Encrypt/Certbot or your provider's managed
# certificate instead. See docs/deployment/NGINX.md.
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SSL_DIR="${SCRIPT_DIR}/../ssl"

mkdir -p "${SSL_DIR}"

if [[ -f "${SSL_DIR}/privkey.pem" || -f "${SSL_DIR}/fullchain.pem" ]]; then
    echo "Certs already exist in ${SSL_DIR} — remove them first if you want to regenerate."
    exit 1
fi

openssl req -x509 -nodes -newkey rsa:2048 \
    -days 365 \
    -keyout "${SSL_DIR}/privkey.pem" \
    -out "${SSL_DIR}/fullchain.pem" \
    -subj "/C=US/ST=Dev/L=Dev/O=SRS Local Dev/CN=localhost" \
    -addext "subjectAltName=DNS:localhost,IP:127.0.0.1"

chmod 600 "${SSL_DIR}/privkey.pem"

echo ""
echo "Self-signed dev certificate generated at:"
echo "  ${SSL_DIR}/fullchain.pem"
echo "  ${SSL_DIR}/privkey.pem"
echo ""
echo "Start the stack with: docker compose --env-file .env up -d"
echo "Then visit: https://localhost  (you'll need to accept the browser warning)"
