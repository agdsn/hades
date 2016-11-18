#!/bin/bash
set -euo pipefail
source /opt/hades/bin/functions.sh
load_config

readonly -A users=(
	['agent']="$HADES_AGENT_USER"
	['auth-dhcp']="$HADES_AUTH_DNSMASQ_USER"
	['auth-dns']="$HADES_UNBOUND_USER"
	['auth-vrrp']='root'
	['database']="$HADES_POSTGRESQL_USER"
	['radius']="$HADES_RADIUS_USER"
	['radius-vrrp']='root'
	['unauth-dns']="$HADES_UNAUTH_DNSMASQ_USER"
	['unauth-http']="$HADES_PORTAL_USER"
	['unauth-portal']="$HADES_PORTAL_USER"
	['unauth-vrrp']='root'
)
readonly -A groups=(
	['agent']="$HADES_AGENT_GROUP"
	['auth-dhcp']="$HADES_AUTH_DNSMASQ_GROUP"
	['auth-dns']="$HADES_UNBOUND_GROUP"
	['auth-vrrp']='root'
	['database']="$HADES_POSTGRESQL_GROUP"
	['radius']="$HADES_RADIUS_GROUP"
	['radius-vrrp']='root'
	['unauth-dns']="$HADES_UNAUTH_DNSMASQ_GROUP"
	['unauth-http']="$HADES_PORTAL_GROUP"
	['unauth-portal']="$HADES_PORTAL_GROUP"
	['unauth-vrrp']='root'
)

if [[ ! -d /var/lib/hades ]]; then
	mkdir -p /var/lib/hades
fi

if ! getent group "$HADES_SYSTEM_GROUP" &>/dev/null; then
	addgroup --quiet --system "$HADES_SYSTEM_GROUP"
fi

for service in "${!users[@]}"; do
	user="${users[$service]}"
	group="${groups[$service]}"
	directory="/var/lib/hades/$service"
	if ! getent group "$group" &>/dev/null; then
		addgroup --quiet --system "$group"
	fi
	if ! getent passwd "$user" &>/dev/null; then
		adduser --quiet --system --home "$directory" --no-create-home --ingroup "$group" --disabled-password "$user"
		adduser --quiet "$user" "$HADES_SYSTEM_GROUP"
	fi
	if [[ ! -d "$directory" ]]; then
		install --directory --owner="$user" --group="$group" --mode=0755 "$directory"
	fi
done
