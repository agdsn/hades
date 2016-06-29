#!/usr/bin/env bash
set -euo pipefail

source /usr/local/bin/functions.sh

print_usage() {
	msg "\
Usage: $0 { start | stop }

Commands:
  start                 Configure hades network settings
  stop                  Deconfigure hades network settings

Options:
  -h --help             Print this message"
}

add_address() {
	local -r namespace="$1"
	local -r interface="$2"
	local -r address="$3"

	local netns
	if [[ -z "$namespace" ]]; then
		msg "Adding $address to $interface"
		netns=""
	else
		msg "Adding $address to $interface in namespace $namespace"
		netns="ip netns exec $namespace"
	fi
	$netns ip address add "$address" dev "$interface"
}

netaddr_ip() {
	/opt/hades/bin/python -c "import netaddr; print(netaddr.IPNetwork('$1').ip)"
}

create_bridge_if_not_exists() {
	local -r interface="$1"
	local -r address="$2"
	local -r sysfs_path="/sys/class/net/$interface"
	msg "Creating bridge $interface"
	if [[ -d "$sysfs_path" ]]; then
		if [[ ! -d "$sysfs_path/bridge" ]]; then
			error "Error: $interface must be a bridge."
			return 2
		fi
	else
		ip link add "$interface" type bridge
		# Like brctl setfd
		echo 0 > "$sysfs_path/bridge/forward_delay"
		# Like brctl stp
		echo 0 > "$sysfs_path/bridge/stp_state"
		if [[ -n "$address" ]]; then
			add_address "" "$interface" "$address"
		fi
		ip link set up dev "$interface"
	fi
}

attach_bridge_port() {
	local -r bridge="$1"
	local -r slave="$2"
	msg "Attaching interface $slave to bridge $bridge"
	ip link set "$slave" master "$bridge"
}

link_namespace() {
	local -r namespace="$1"
	local -r parent_interface="$2"
	local -r parent_address="$3"
	local -r namespace_interface="$4"
	local -r namespace_address="$5"

	msg "Linking network namespace $namespace via veth pair $parent_interface <-> $namespace_interface"
	ip link add name "$parent_interface" type veth peer netns "$namespace" name "$namespace_interface"
	if [[ -n "$parent_address" ]]; then
		add_address "" "$parent_interface" "$parent_address"
	fi
	if [[ -n "$namespace_address" ]]; then
		add_address "$namespace" "$namespace_interface" "$namespace_address"
	fi
	ip link set dev "$parent_interface" up
	ip netns exec "$namespace" ip link set dev "$namespace_interface" up
}

setup_namespace_common_pre() {
	local -r namespace="$1"
	local -r interface="$2"
	local -r parent_address="$3"
	local -r namespace_address="$4"

	msg "Creating network namespace $namespace"
	ip netns add "$namespace"
	ip netns exec "$namespace" ip link set dev lo up
	ip netns exec "$namespace" sysctl --quiet net.ipv4.ip_nonlocal_bind=1

	link_namespace "$namespace" "${namespace}-veth0" "$parent_address" eth0 "$namespace_address"
	ip netns exec "$namespace" ip route add default via $(netaddr_ip "$namespace_address")

	link_namespace "$namespace" "${namespace}-veth1" "" eth1 ""
	attach_bridge_port "$HADES_VRRP_BRIDGE" "${namespace}-veth1"

	msg "Moving interface $interface to network namespace $namespace as eth2"
	ip link set dev "$interface" netns "$namespace" name eth2
	ip netns exec "$namespace" ip link set dev eth2 up
}

setup_namespace_auth() {
	:
}

setup_namespace_unauth() {
	msg "Creating ipset"
	ip netns exec unauth ipset create "$HADES_UNAUTH_WHITELIST_IPSET" hash:ip
}

setup_namespace_common_post() {
	local -r namespace="$1"
	local -r interface="$2"

	msg "Loading iptables rules for network namespace $namespace"
	python3 -m hades.bin.generate_config "iptables-${namespace}.j2" | ip netns exec "$namespace" iptables-restore
}

setup_host_network() {
	sysctl --quiet net.ipv4.ip_nonlocal_bind=1
	if [[ "$HADES_CREATE_DUMMY_INTERFACES" = True ]]; then
		local interface
		for interface in "$HADES_RADIUS_INTERFACE" "$HADES_VRRP_INTERFACE" "$HADES_AUTH_INTERFACE" "$HADES_UNAUTH_INTERFACE"; do
			if [[ -d "/sys/class/net/$interface" ]]; then
				continue
			fi
			msg "Creating dummy interface $interface"
			ip link add name "$interface" type dummy
			ip link set up dev "$interface"
		done
	fi
	create_bridge_if_not_exists "$HADES_VRRP_BRIDGE" "$HADES_VRRP_LISTEN_RADIUS"

	python3 -m hades.bin.generate_config iptables-main.j2 | iptables-restore
}

do_start() {
	setup_host_network
	setup_namespace_common_pre auth   "$HADES_AUTH_INTERFACE"   "$HADES_NETNS_MAIN_AUTH_LISTEN"   "$HADES_NETNS_AUTH_LISTEN"
	setup_namespace_common_pre unauth "$HADES_UNAUTH_INTERFACE" "$HADES_NETNS_MAIN_UNAUTH_LISTEN" "$HADES_NETNS_UNAUTH_LISTEN"
	setup_namespace_auth
	setup_namespace_unauth
	setup_namespace_common_post auth   "$HADES_AUTH_INTERFACE"
	setup_namespace_common_post unauth "$HADES_UNAUTH_INTERFACE"
}

teardown_namespace() {
	local -r namespace="$1"
	local -r interface="$2"
	local -a pids=()
	if ! ip netns pids "$namespace" | readarray -t pids; then
		return
	fi
	if (( ${#pids[@]} > 0 )); then
		error "Error: Network namespace $namespace has still processes running. PIDs: ${pids[*]}"
		return 2
	fi

	msg "Moving interface $interface back from network namespace $namespace to parent"
	ip netns exec "$namespace" ip link set eth2 netns $$ name "$interface"

	msg "Deleting network namespace $namespace"
	ip link delete dev "${namespace}-veth0"
	ip link delete dev "${namespace}-veth1"
	ip netns delete "$namespace"
}

do_stop() {
	teardown_namespace auth   "$HADES_AUTH_INTERFACE"
	teardown_namespace unauth "$HADES_UNAUTH_INTERFACE"

	msg "Resetting iptables"
	local -a tables=()
	readarray -t tables < /proc/net/ip_tables_names
	local -Ar chains=(
		['raw']='PREROUTING OUTPUT'
		['mangle']='PREROUTING INPUT FORWARD OUTPUT POSTROUTING'
		['nat']='PREROUTING INPUT OUTPUT POSTROUTING'
		['filter']='INPUT FORWARD OUTPUT'
		['security']='INPUT FORWARD OUTPUT'
	)
	for table in "${tables[@]}"; do
		iptables --table "$table" --flush
		iptables --table "$table" --delete-chain
		for chain in ${chains[$table]}; do
			iptables --table "$table" --policy "$chain" ACCEPT
		done
	done
}

main() {
	if (( $# != 1)); then
		print_usage
		exit "$EX_USAGE"
	fi
	case "$1" in
		-h|--help)
			print_usage
			exit "$EX_OK"
			;;
		start|stop)
			load_config
			do_$1
			;;
		*)
			print_usage
			exit "$EX_USAGE"
			;;
	esac
}

main "$@"
