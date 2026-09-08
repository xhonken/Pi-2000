#!/usr/bin/env bash
# Output only the public CA certificate. Shell redirection runs as your own user.
set -euo pipefail
if [[ ${1:-} == --help ]]; then
  echo "Usage: sudo $0 > pi2000web-root.crt"
  echo "Exports Caddy's public LAN CA certificate, never its private key."
  exit 0
fi
if [[ $# -ne 0 || $EUID -ne 0 ]]; then
  echo "Usage: sudo $0 > pi2000web-root.crt" >&2
  exit 2
fi
certificate=/var/lib/caddy/.local/share/caddy/pki/authorities/local/root.crt
if [[ ! -s $certificate ]]; then
  echo 'Local CA certificate not found. Complete an internal-TLS installation first.' >&2
  exit 1
fi
cat -- "$certificate"
