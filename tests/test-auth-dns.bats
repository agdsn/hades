#!/usr/bin/env bats

load common

readonly client_mac_address=de:ad:be:ef:00:00
readonly client_ip_address=141.30.227.13/23
readonly relay_ip_address=10.66.67.1/24
readonly nameserver_ip_address=10.66.67.10/24
readonly gateway_ip_address=141.30.226.1/23

fakedns() {
	psql foreign <<-EOF
		TRUNCATE alternative_dns;
		INSERT INTO alternative_dns VALUES ('$(netaddr.ip "${client_ip_address}")');
	EOF
	refresh
}

ns() {
	ns_exec test-auth "$@"
}

setup() {
	mkdir /etc/netns/test-auth
	setup_namespace test-auth
	setup_namespace test-relay
	echo "nameserver $(netaddr.ip "${nameserver_ip_address}")" > /etc/netns/test-auth/resolv.conf
	ns_exec test-relay sysctl -w net.ipv4.ip_forward=1 net.ipv4.conf.all.forwarding=1 net.ipv4.conf.default.forwarding=1
	ip link add br-relay up type bridge
	iptables -I FORWARD 1 -m physdev --physdev-is-bridged -i br-relay -o br-relay -j ACCEPT
	link_namespace test-auth br-relay eth0
	link_namespace test-relay br-relay eth0
	link_namespace test-relay br-auth eth1
	ns_exec test-relay ip address add "$gateway_ip_address" dev eth0
	ns_exec test-relay ip address add "$relay_ip_address" dev eth1
	ns ip address add dev eth0 "$client_ip_address"
	ns ip route add default via $(netaddr.ip "${gateway_ip_address}")
	echo test-auth routes:
	ns_exec test-auth ip route
	echo test-relay routes:
	ns_exec test-relay ip route
	echo auth routes:
	ns_exec auth ip route
	psql foreign <<-EOF
		TRUNCATE dhcphost;
		TRUNCATE alternative_dns;
		INSERT INTO dhcphost VALUES ('${client_mac_address}', '$(netaddr.ip "${client_ip_address}")')
	EOF
	refresh
}

teardown() {
	psql foreign <<-EOF
		TRUNCATE dhcphost;
		TRUNCATE alternative_dns;
	EOF
	refresh
	unlink_namespace test-relay eth1
	unlink_namespace test-relay eth0
	unlink_namespace test-auth eth0
	iptables -D FORWARD -m physdev --physdev-is-bridged -i br-relay -o br-relay -j ACCEPT
	ip link delete br-relay
	teardown_namespace test-auth
	teardown_namespace test-relay
}

@test "check that DNS queries get answered" {
	ns cat /etc/resolv.conf >&2
	for i in www.google.de www.msftncsi.com; do
		run ns dig +timeout=1 +short "$i"
		echo "$output" >&2
		[[ -n $output && $output != 10.66.0.1 && $output =~ [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+ ]]
	done
}

@test "check that alternative DNS is working" {
	ns cat /etc/resolv.conf >&2
	for i in www.google.de fake.news.com; do
		run ns dig +timeout=1 +short "$i"
		echo "$output" >&2
		[[ -n "$output" && "$output" != 127.0.0.1 ]]
	done

	fakedns

	run ns dig +timeout=1 +short www.google.de
	[[ -n "$output" && "$output" != 127.0.0.1 ]]

	run ns dig +timeout=1 +short fake.news.com
	[[ "$output" = 127.0.0.1 ]]
}
