readonly mac_regex='([0-9a-f]{2})[^0-9a-f]?([0-9a-f]{2})[^0-9a-f]?([0-9a-f]{2})[^0-9a-f]?([0-9a-f]{2})[^0-9a-f]?([0-9a-f]{2})[^0-9a-f]?([0-9a-f]{2})'

lowercase() {
	printf "%s" "${@,,}"
}

uppercase() {
	printf "%s" "${@^^}"
}

join() {
	local IFS="$1"
	shift
	printf "%s" "$*"
}

mac_plain() {
	[[ $1 =~ $mac_regex ]]
	printf "%s%s%s%s%s%s" "${BASH_REMATCH[@]:1}"
}

mac_duo() {
	[[ $1 =~ $mac_regex ]]
	printf "%s%s%s$2%s%s%s" "${BASH_REMATCH[@]:1}"
}

mac_triple() {
	[[ $1 =~ $mac_regex ]]
	printf "%s%s$2%s%s$2%s%s" "${BASH_REMATCH[@]:1}"
}

mac_sextuple() {
	[[ $1 =~ $mac_regex ]]
	printf "%s$2%s$2%s$2%s$2%s$2%s" "${BASH_REMATCH[@]:1}"
}

strip() {
	echo "${1#*=}"
}

ns_exec() {
	local -r namespace="$1"
	shift
	ip netns exec "$namespace" "$@"
}

assert_equals() {
	[[ "$1" = "$2" ]] || (echo "Assertion failed: $1 != $2" && return 1)
}

assert_array_equals()
{
	[[ "$1" != first ]] && local -n first="$1"
	[[ "$2" != second ]] && local -n second="$2"
	if [[ ${#first[@]} -ne ${#second[@]} ]]; then
		echo "Array size mismatch: ${#first[@]} != ${#second[@]}"
		return 1
	fi
	for (( i=0; i < ${#first[@]}; i++)); do
		if [[ "${first[$i]}" != "${second[$i]}" ]]; then
			echo "Mismatch at index $i: ${first[$i]} != ${second[$i]}"
			return 1
		fi
	done
	return 0
}

pg_escape_string() {
	if [[ -n $* ]]; then
		printf "%s" \'"$(sed -e "s/'/''/g" <<<"$*")"\'
	else
		echo -n NULL
	fi
}

pg_escape_array_value() {
	sed -e 's/[\\"]/\\&/g' <<<"$*"
}

pg_escape_array() {
	local -a values=()
	for element in "$@"; do
		if [[ -n $element ]]; then
			values+=('"'"$(pg_escape_array_value "${element}")"'"')
		else
			values+=('NULL')
		fi
	done
	echo -n \'\{
	join , "${values[@]}"
	echo -n \}\'
}

pg_encode_hex()
{
	echo -n \\x
	echo -n "$*" | xxd -p
}

psql() {
	runuser -u hades-database -- psql --host /run/hades/database --echo-errors --no-readline --single-transaction --set=ON_ERROR_STOP=1 "$@"
}

psql_query() {
	psql --quiet --no-align --tuples-only "$@"
}

psql_mapfile() {
	local -r var="$1"
	shift
	local -r lastpipe="$(shopt -p lastpipe)"
	shopt -s lastpipe
	psql_query --field-separator-zero --record-separator-zero "$@" | mapfile -d '' "$var"
	eval "${lastpipe}"
}

refresh() {
	systemctl start --wait hades-refresh.service
}

netaddr.broadcast() {
	python -c "import sys, netaddr; print(netaddr.IPNetwork(sys.argv[1]).broadcast)" "$1"
}

netaddr.ip() {
	python -c "import sys, netaddr; print(netaddr.IPNetwork(sys.argv[1]).ip)" "$1"
}

netaddr.cidr() {
	python -c "import sys, netaddr; print(netaddr.IPNetwork(sys.argv[1]).cidr)" "$1"
}

netaddr.netmask() {
	python -c "import sys, netaddr; print(netaddr.IPNetwork(sys.argv[1]).netmask)" "$1"
}

netaddr.network() {
	python -c "import sys, netaddr; print(netaddr.IPNetwork(sys.argv[1]).network)" "$1"
}

netaddr.prefixlen() {
	python -c "import sys, netaddr; print(netaddr.IPNetwork(sys.argv[1]).prefixlen)" "$1"
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
