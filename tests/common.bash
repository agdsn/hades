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

setup_namespace() {
	local -r namespace="$1"
	local -r bridge="$2"
	local -r mac="$3"
	mkdir -p "/etc/netns/$namespace"
	truncate --size=0 "/etc/netns/${namespace}/resolv.conf"
	ip netns add "$namespace"
	ip link add dev "veth-$namespace" type veth peer netns "$namespace" name eth0 address "$mac"
	ip link set "veth-$namespace" up master "$bridge"
	ns_exec "$namespace" ip link set dev eth0 up
}

teardown_namespace() {
	local -r namespace="$1"
	ip netns pids "$namespace" | xargs --no-run-if-empty kill -SIGKILL
	ns_exec "$namespace" ip link del dev eth0
	ip netns delete "$namespace"
	rm -rf "/etc/netns/$namespace"
}
