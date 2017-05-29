ns_exec() {
	local -r namespace="$1"
	shift
	ip netns exec "$namespace" "$@"
}

psql() {
	runuser -u hades-database -- psql --host /run/hades/database --echo-errors --no-readline --single-transaction --set=ON_ERROR_STOP=1 "$@"
}

refresh() {
	systemctl start --wait hades-refresh.service
}

netaddr.ip() {
	python -c "import sys, netaddr; print(netaddr.IPNetwork(sys.argv[1]).ip)" "$1"
}

netaddr.cidr() {
	python -c "import sys, netaddr; print(netaddr.IPNetwork(sys.argv[1]).cidr)" "$1"
}

netaddr.value() {
	python -c "import sys, netaddr; print(netaddr.IPNetwork(sys.argv[1]).value)" "$1"
}

setup_namespace() {
	local -r namespace="$1"
	mkdir -p "/etc/netns/$namespace"
	truncate --size=0 "/etc/netns/${namespace}/resolv.conf"
	ip netns add "$namespace"
	ns_exec "$namespace" sysctl -w net.ipv6.conf.all.disable_ipv6=1 net.ipv6.conf.default.disable_ipv6=1
}

teardown_namespace() {
	local -r namespace="$1"
	ip netns pids "$namespace" | xargs --no-run-if-empty kill -SIGKILL
	ip netns delete "$namespace"
	rm -rf "/etc/netns/$namespace"
}

link_namespace() {
	local -r namespace="$1"
	local -r bridge="$2"
	local -r interface="$3"
	local -r mac="${4:-}"
	local -r peer_interface="$(printf 'veth-%04x' "$RANDOM")"
	ip link add dev "$peer_interface" type veth peer netns "$namespace" name "$interface" ${mac:+address "$mac"}
	ip link set up dev "$peer_interface" master "$bridge"
	ns_exec "$namespace" ip link set dev "$interface" up
}

unlink_namespace() {
	local -r namespace="$1"
	local -r interface="$2"
	ns_exec "$namespace" ip link del dev "$interface"
}
