#!/bin/sh
set -eu

: "${API_BASE:=/api}"

cat > /usr/share/nginx/html/config.js <<EOF
window.CLOUDCART_API_BASE = "${API_BASE}";
EOF

exec nginx -g "daemon off;"
