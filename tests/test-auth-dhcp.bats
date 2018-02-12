#!/usr/bin/env bats

load common

readonly client_mac_address=de:ad:be:ef:00:00
readonly client_ip_address=141.30.227.13/23
readonly client_hostname=test
readonly gateway_ip_address=141.30.226.1/23
readonly relay_ip_address=10.66.67.1/24
readonly auth_ip=10.66.67.10/24

dhcrelay() {
	ns_exec test-relay dhcrelay -pf /run/test-dhcrelay.pid -4 -a -id eth0 -iu eth1 "$(netaddr.ip "$auth_ip")"
}

ns() {
	ns_exec test-auth "$@"
}

setup() {
	setup_namespace test-auth
	setup_namespace test-relay
	ip link add br-relay up type bridge
	iptables -I FORWARD 1 -m physdev --physdev-is-bridged -i br-relay -o br-relay -j ACCEPT
	link_namespace test-auth br-relay eth0 de:ad:be:ef:00:00
	link_namespace test-relay br-relay eth0
	link_namespace test-relay br-auth eth1
	ns_exec test-relay ip address add "$gateway_ip_address" dev eth0
	ns_exec test-relay ip address add "$relay_ip_address" dev eth1
	dhcrelay
	psql foreign <<-EOF
		TRUNCATE dhcphost;
		INSERT INTO dhcphost VALUES ('${client_mac_address}', '$(netaddr.ip "${client_ip_address}")');
	EOF
	refresh
}

teardown() {
	[[ -f /run/test-dhcrelay.pid ]] && kill "$(</run/test-dhcrelay.pid)"
	unlink_namespace test-relay eth1
	unlink_namespace test-relay eth0
	unlink_namespace test-auth eth0
	iptables -D FORWARD -m physdev --physdev-is-bridged -i br-relay -o br-relay -j ACCEPT
	ip link delete br-relay
	teardown_namespace test-auth
	teardown_namespace test-relay
	psql foreign <<-EOF
		TRUNCATE dhcphost;
	EOF
	refresh
}

@test "check that client can acquire DHCP lease" {
	run ns dhcpcd --noipv4ll --ipv4only --oneshot eth0
	echo "$output" >&2
	[[ $status = 0 ]]
	egrep 'leased [^ ]+ for [0-9]+ seconds' <<<"$output"
	ns cat /etc/resolv.conf >&2
	nameserver=$(ns sed -rne 's/^nameserver (.*)$/\1/p' /etc/resolv.conf)
	[[ "$nameserver" = "$(netaddr.ip "$auth_ip")" ]]
}
