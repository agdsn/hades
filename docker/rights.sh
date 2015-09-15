#!/bin/bash
set -eo pipefail
mkdir -p /etc/hades /var/lib/hades /run/hades

for SERVICE in agent portal; do
    useradd --system --create-home --home-dir /var/lib/hades/${SERVICE} hades-${SERVICE}
    install -o hades-${SERVICE} -g hades-${SERVICE} -d /run/hades/${SERVICE}
done
