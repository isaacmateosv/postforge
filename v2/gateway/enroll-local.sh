#!/usr/bin/env bash
# Copyright © 2026 Isaac Mateo Sarzosa Valencia and contributors.
# SPDX-License-Identifier: GPL-3.0-or-later
# Run on the Mac at a private terminal. Never pass passwords as arguments.
set -euo pipefail

if [ "$#" -ne 2 ] || [ ! -t 0 ] || [ ! -t 1 ]; then
  echo "Usage at an interactive terminal: $0 <gateway-config-directory> <user-email>" >&2
  exit 2
fi
directory="$(cd "$1" && pwd -P)"
email="$2"
root="$(cd "$(dirname "$0")/../.." && pwd -P)"
image="authelia/authelia:4.39@sha256:bd97cff4fcbf715b5ff1f9ae286afbe6033afce385302520b0368122d43a6f54"
scratch="$(mktemp -d "$directory/.enrollment.XXXXXX")"
qr="$scratch/enrollment.png"
trap 'rm -f "$qr"; rmdir "$scratch"' EXIT
trap 'exit 130' HUP INT TERM

echo "Choose a gateway password. Enter it only at Authelia’s prompts."
docker run --rm -it --network none "$image" authelia crypto hash generate argon2
echo "Copy the Digest value (beginning with \$argon2id\$), then paste it at the hidden prompt."
python3 "$root/v2/gateway_setup.py" --directory "$directory" add-user "$email"

# Only the QR goes to the private host file. The CLI can also print the TOTP URI.
docker run --rm --network none -v "$directory:/config" "$image" \
  authelia storage user totp generate "$email" --config /config/configuration.yml \
  --issuer PostForge --path "/config/${scratch##*/}/enrollment.png" >/dev/null
chmod 600 "$qr"
if [ "$(uname)" = Darwin ]; then
  open -a Preview "$qr"
else
  printf 'Open this private QR file on the local computer: %s\n' "$qr"
fi
read -r -p "After the user scans the QR, close it and press Enter to remove the image. " confirmation
echo "Enrollment saved locally. The public tunnel has not changed."
