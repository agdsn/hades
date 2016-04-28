#!/bin/bash
set -euo pipefail
mkdir -p /etc/hades /var/lib/hades

for SERVICE in agent portal; do
    useradd --system --create-home --home-dir /var/lib/hades/${SERVICE} hades-${SERVICE}
done
