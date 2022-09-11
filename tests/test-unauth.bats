#!/usr/bin/env bats

load common

readonly client_mac_address=de:ad:be:ef:00:00
readonly client_ip_address=10.66.10.10/19
readonly nameserver_ip_address=10.66.0.1
readonly dnsmasq_pidfile=/run/hades/unauth-dns/dnsmasq.pid
readonly dhcpcd_conf="${BATS_TEST_DIRNAME}/dhcpcd.conf"

ns() {
	ns_exec test-unauth "$@"
}

setup() {
	log_test_start
	setup_namespace test-unauth
	link_namespace test-unauth br-unauth eth0 "$client_mac_address"
	ns ip addr add dev eth0 "$client_ip_address"
	ns ip route add default via "$nameserver_ip_address"
	echo "nameserver $nameserver_ip_address" | ns tee /etc/resolv.conf >/dev/null
	ip netns exec unauth ipset flush hades_unauth_whitelist
	# makes dnsmasq forget that it wrote ips into ipset
	if [[ -f "$dnsmasq_pidfile" ]]; then
		kill -HUP $(cat "$dnsmasq_pidfile")
	fi
}

teardown() {
	unlink_namespace test-unauth eth0
	teardown_namespace test-unauth
	log_test_stop
}

@test "check that client can acquire unauth DHCP lease" {
	ns ip addr flush dev eth0
	ns truncate -s0 /etc/resolv.conf
	run ns dhcpcd --config "${dhcpcd_conf}" eth0
	echo "$output" >&2
	[[ $status = 0 ]]
	lease_line=$(egrep 'leased [^ ]+ for [0-9]+ seconds' <<<"$output")
	ip=$(sed -E 's/^.*leased ([^ ]+) for.*$/\1/' <<<"$lease_line")
	ns cat /etc/resolv.conf >&2
	nameserver=$(ns sed -rne 's/^nameserver (.*)$/\1/p' /etc/resolv.conf)
	[[ "$nameserver" = "$nameserver_ip_address" ]]

	# shellcheck disable=SC2001
	# shellcheck disable=SC2016
	run psql --no-align --tuples-only hades <<-EOF
		select "IPAddress" from unauth_dhcp_lease where "MAC"='$client_mac_address'
	EOF
	[[ "$output" == "$ip" ]]

	# RELEASE
	run ns dhcpcd --config "${dhcpcd_conf}" --release eth0
	run psql --no-align --tuples-only hades <<-EOF
		select count(*) from unauth_dhcp_lease where "MAC"='$client_mac_address'
	EOF
	hexdump -C <<<"$output"
	[[ "$output" == "0" ]]

	run ns dhcpcd --config "${dhcpcd_conf}" --exit eth0
}

@test "check that DNS queries get redirected" {
	for i in www.google.de www.msftncsi.com unknown.tld; do
		run ns dig +timeout=1 +short "$i"
		[[ "$output" = 10.66.0.1 ]]
	done

	run ns dig +timeout=1 +short dns.msftncsi.com
	[[ "$output" = 131.107.255.255 ]]
}

@test "check that client gets 511 error from portal" {
	run ns curl -qi http://www.google.de
	echo "$output" >&2
	egrep 'HTTP/[0-9]+\.[0-9]+ 511' <<<"$output"
	egrep '<meta http-equiv="refresh" content=' <<<"$output"
}

@test "check that portal is reachable" {
	run ns curl -qi http://captive-portal.agdsn.de
	echo "$output" >&2
	[[ $status = 0 ]]
	egrep 'HTTP/[0-9]+\.[0-9]+ 200' <<<"$output"
}

@test "check that ping 8.8.8.8 results in packet filtering" {
	run ns ping -n -i0.1 -c10 8.8.8.8
	echo "$output" >&2
	egrep 'Packet filtered' <<<"$output"
	egrep ' 100% packet loss' <<< "$output"
}

@test "check that pass-through DNS is working" {
	for i in agdsn.de ftp.agdsn.de; do
		run ns dig +timeout=1 +short agdsn.de
		echo "$output" >&2
		[[ -n $output && $output != 10.66.0.1 && $output =~ [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+ ]]
	done
}

@test "check that pass-through ipset gets updated" {
	ipset_count () {
		ip netns exec unauth ipset list hades_unauth_whitelist | sed -rne 's/^Number of entries: (.*)$/\1/p'
	}

	run ipset_count
	echo "$output" >&2
	[[ "$output" -eq 0 ]]
	ns dig +timeout=1 +short agdsn.de
	sleep 1
	run ipset_count
	echo "$output" >&2
	[[ "$output" -ge 1 ]]
}

@test "check that pass-through host is reachable" {
	for i in mail.agdsn.de ftp.agdsn.de; do
		ns dig +timeout=1 agdsn.de >&2
		run ns ping -n -i0.1 -c10 "$i"
		echo "$output" >&2
		egrep ' 0% packet loss' <<<"$output"
	done
}

@test "check that pass-through HTTP is working" {
	run ns curl -qi https://ftp.agdsn.de/pub/
	echo "$output" >&2
	[[ $status = 0 ]]
	egrep 'HTTP/[0-9]+\.[0-9] 200' <<<"$output"
}
