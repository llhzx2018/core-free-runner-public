#!/usr/bin/env bash
set -Eeuo pipefail
sed -i '/^git fetch origin feature\/v2\.5\.10-scratch-uaui$/d;/^git checkout -B feature\/v2\.5\.10-scratch-uaui origin\/feature\/v2\.5\.10-scratch-uaui$/d' scripts/p02-v2510-scratch-uaui-v3.sh
bash scripts/p02-v2510-scratch-uaui-v3.sh
