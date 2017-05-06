#!/usr/bin/env bats

ns() {
	ip netns exec test-auth "$@"
}

dhcpcd() {
	ns dhcpcd --noipv4ll --ipv4only --oneshot eth0
}

postgresql() {
	runuser -u hades-database -- psql --host /run/hades/database --echo-errors --no-readline --single-transaction --set=ON_ERROR_STOP=1 "$@"
}

refresh() {
	systemctl start --wait hades-refresh.service
}

data() {
	last_byte=$(printf '%02x' "$1")
	echo "DELETE FROM dhcphost;" | postgresql foreign
	echo "INSERT INTO dhcphost VALUES ('de:ad:be:ef:00:${last_byte}', '141.30.227.13');" | postgresql foreign
	refresh
}

fakedns() {
	echo "DELETE FROM alternative_dns;" | postgresql foreign
	echo "INSERT INTO alternative_dns VALUES ('141.30.227.13');" | postgresql foreign
	refresh
}

setup() {
	mkdir -p /etc/netns/test-auth
	truncate -s0 /etc/netns/test-auth/resolv.conf
	ip netns add test-auth
	ip link add dev test-auth type veth peer netns test-auth name eth0 address de:ad:be:ef:00:00
	ip link set test-auth up master br-auth
	ns ip link set dev eth0 up
	ip netns exec auth ip addr add dev eth2 141.30.226.1/23
	data 0
	echo "DELETE FROM alternative_dns;" | postgresql foreign
}

teardown() {
	ip netns exec auth ip addr del dev eth2 141.30.226.1/23
	ns ip link del dev eth0
	ip netns delete test-auth
	rm -rf /etc/netns/test-auth
	echo "DELETE FROM dhcphost;" | postgresql foreign
	echo "DELETE FROM alternative_dns;" | postgresql foreign
	refresh
}

@test "check that fdw contains data" {
	helper() {
		echo "SELECT * FROM foreign_dhcphost;" | postgresql -at hades
	}
	run helper
	grep 'de:ad:be:ef:00:00 | 141.30.227.13' <<<"$output"

	data 1
	run helper
	grep 'de:ad:be:ef:00:01 | 141.30.227.13' <<<"$output"
}

@test "check that refresh syncs the data" {
	helper() {
		echo "SELECT * FROM dhcphost;" | postgresql -at hades
	}
	run helper
	grep 'de:ad:be:ef:00:00 | 141.30.227.13' <<<"$output"

	data 1
	run helper
	grep 'de:ad:be:ef:00:01 | 141.30.227.13' <<<"$output"
}

@test "check that dnsmasq host reservations are generated" {
	file=/var/hades/auth-dhcp/dnsmasq-dhcp.hosts
	cat "$file" >&2
	[[ -f "$file" ]]
	[[ "$(cat "$file")" = "de:ad:be:ef:00:00,141.30.227.13" ]]

	data 1
	[[ -f "$file" ]]
	[[ "$(cat "$file")" = "de:ad:be:ef:00:01,141.30.227.13" ]]
}

@test "check that client can aquire DHCP lease" {
	run dhcpcd
	echo "$output" >&2
	[[ $status = 0 ]]
	egrep 'leased [^ ]+ for [0-9]+ seconds' <<<"$output"
}

@test "check that DNS queries get answered" {
	dhcpcd
	ns cat /etc/resolv.conf >&2
	for i in www.google.de www.msftncsi.com; do
		run ns dig +short "$i"
		echo "$output" >&2
		[[ -n "$output" && "$output" != 10.66.0.1 ]]
	done
}

@test "check that alternative DNS configuration is propagated to ipset" {
	ipset_count () {
		ip netns exec auth ipset list hades_alternative_dns | sed -rne 's/^Number of entries: (.*)$/\1/p'
	}
	[[ "$(ipset_count)" = 0 ]]

	fakedns
	[[ "$(ipset_count)" = 1 ]]
	ip netns exec auth ipset list hades_alternative_dns | grep '141.30.227.13'
}

@test "check that alternative DNS is working" {
	dhcpcd
	ns cat /etc/resolv.conf >&2
	for i in www.google.de fake.news.com; do
		run ns dig +short "$i"
		echo "$output" >&2
		[[ -n "$output" && "$output" != 127.0.0.1 ]]
	done

	fakedns

	run ns dig +short www.google.de
	[[ -n "$output" && "$output" != 127.0.0.1 ]]

	run ns dig +short fake.news.com
	[[ "$output" = 127.0.0.1 ]]
}
