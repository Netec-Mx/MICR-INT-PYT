$ErrorActionPreference = 'Stop'
$certs = Join-Path (Split-Path $PSScriptRoot -Parent) 'certs'
New-Item -ItemType Directory -Force -Path $certs | Out-Null
Push-Location $certs
try {
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out jwt-private.pem
    openssl pkey -in jwt-private.pem -pubout -out jwt-public.pem
    openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:3072 -out ca.key
    openssl req -x509 -new -key ca.key -sha256 -days 30 -subj '/CN=Microservices Lab CA' -out ca.crt

    foreach ($item in @(
        @{ Name = 'auth-service'; Usage = 'serverAuth' },
        @{ Name = 'inventory-service'; Usage = 'serverAuth' },
        @{ Name = 'client'; Usage = 'clientAuth' }
    )) {
        $name = $item.Name
        openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$name.key"
        openssl req -new -key "$name.key" -subj "/CN=$name.local" -out "$name.csr"
        $san = if ($item.Usage -eq 'serverAuth') { "DNS:$name.local,IP:127.0.0.1" } else { "DNS:$name.local" }
        "subjectAltName=$san`nextendedKeyUsage=$($item.Usage)" | Set-Content -LiteralPath "$name.ext" -Encoding ascii
        openssl x509 -req -in "$name.csr" -CA ca.crt -CAkey ca.key -CAcreateserial -out "$name.crt" -days 30 -sha256 -extfile "$name.ext"
    }
    openssl verify -CAfile ca.crt auth-service.crt inventory-service.crt client.crt
}
finally {
    Pop-Location
}
