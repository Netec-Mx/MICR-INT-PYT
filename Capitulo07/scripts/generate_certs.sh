#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CERTS="$ROOT/certs"
mkdir -p "$CERTS"
cd "$CERTS"

openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out jwt-private.pem
openssl pkey -in jwt-private.pem -pubout -out jwt-public.pem
openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out ca.key
openssl req -x509 -new -key ca.key -sha256 -days 30 -subj "/CN=Microservices Lab CA" -out ca.crt

issue_cert() {
  local name="$1" eku="$2"
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$name.key"
  openssl req -new -key "$name.key" -subj "/CN=$name.local" -out "$name.csr"
  local san="DNS:$name.local"
  [ "$eku" = "serverAuth" ] && san="$san,IP:127.0.0.1"
  printf 'subjectAltName=%s\nextendedKeyUsage=%s\n' "$san" "$eku" > "$name.ext"
  openssl x509 -req -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial \
    -out "$name.crt" -days 30 -sha256 -extfile "$name.ext"
}

issue_cert auth-service serverAuth
issue_cert inventory-service serverAuth
issue_cert client clientAuth
chmod 600 ./*.key jwt-private.pem
openssl verify -CAfile ca.crt auth-service.crt inventory-service.crt client.crt
