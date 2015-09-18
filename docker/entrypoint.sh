#!/bin/bash
set -eo pipefail

EX_OK=0
EX_USAGE=64

msg() {
    echo "$@"
}

print_usage() {
    msg "Usage: COMMAND"
    msg ""
    msg "Available commands"
    msg "  agent         Execute the site node agent (Celery worker)"
    msg "  database      Execute the database (currently PostgreSQL)"
    msg "  help          Print this help message"
    msg "  http          Execute the captive portal web server (currently nginx)"
    msg "  firewall      Load the iptables rules"
    msg "  portal        Run the captive portal WSGI application (currently"
    msg "                using uWSGI)"
    msg "  radius        Run the RADIUS server (currently freeRADIUS)"
    msg "  regular-dhcp  Execute the DHCP resolver for the regular VLANs"
    msg "                (currently a noop and handled by a slave dnsmasq run"
    msg "                by the agent)"
    msg "  regular-dns   Execute the DNS resolver for the regular VLANs"
    msg "                (currently unbound)"
    msg "  shell         Start a shell (bash) to debug the container"
    msg "  unauth-dhcp   Run the DHCP server for the unauth VLAN (currently a"
    msg "                noop and handled by dnsmasq of unauth-dns)"
    msg "  unauth-dns    Run the DNS resolver for the unauth VLAN (currently"
    msg "                dnsmasq)"
}

run_agent() {
    exec python3 -m celery.bin.worker --app=hades.agent
}

run_database() {
    PATH="/usr/lib/postgresql/9.4/bin:$PATH"
    pg_ctl start -w -s
    createuser freerad
    createuser hades-agent
    createuser hades-portal
    createdb --owner=hades-agent hades
    psql
    exec postgres
}

run_http() {
    python3 -m hades.config.generate nginx /etc/hades/nginx
    exec nginx -c /etc/hades/nginx/nginx.conf
}

run_firewall() {
    python3 -m hades.config.generate iptables | iptables-restore
}

run_portal() {
    python3 -m hades.config.generate uwsgi /etc/hades/uwsgi.ini
    exec uwsgi --ini=/etc/hades/uwsgi.ini
}

run_radius() {
    python3 -m hades.config.generate freeradius /etc/hades/freeradius
    exec freeradius -f -m -d /etc/hades/freeradius
}

run_regular_dns() {
    python3 -m hades.config.generate unbound /etc/hades/unbound.conf
    exec unbound -c /etc/hades/unbound.conf
}

run_regular_dhcp() {
    python3 -m hades.config.generate regular-dnsmasq /etc/hades/regular-dnsmasq.conf
    exec python3 -m hades.dnsmasq.monitor
}

run_shell() {
    exec bash
}

run_unauth_dhcp() {
    echo "DHCP for the unauth VLAN is currently performed by the dnsmasq "
    echo "instance that provides unauth DNS."
    exit ${EX_OK}
}

run_unauth_dns() {
    python3 -m hades.config.generate unauth-dnsmasq /etc/hades/unauth-dnsmasq.conf
    exec dnsmasq -k -C /etc/hades/unauth-dnsmasq.conf
}

main() {
    python3 -m hades.config.export > ~/env.sh
    source ~/env.sh
    if [[ $# -lt 1 ]]; then
        command=help
    else
        command=$1
    fi
    shift
    case "$command" in
        agent|database|http|firewall|portal|radius|regular-dhcp|regular-dns|shell|unauth-dhcp|unauth-dns)
            run_${command//-/_} $@
            ;;
        help|-h|--help)
            print_usage
            exit ${EX_OK}
            ;;
        *)
            msg "Unknown command: $command"
            print_usage
            exit ${EX_USAGE}
            ;;
    esac
}

main $@
