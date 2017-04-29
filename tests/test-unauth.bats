#!/usr/bin/env bats

ns() {
	ip netns exec test-unauth "$@"
}

dhcpcd() {
	ns dhcpcd --noipv4ll --ipv4only --oneshot eth0
}

setup() {
	mkdir -p /etc/netns/test-unauth
	truncate -s0 /etc/netns/test-unauth/resolv.conf
	ip netns add test-unauth
	ip link add dev test-unauth type veth peer netns test-unauth name eth0
	ip link set test-unauth up master br-unauth
	ns ip link set dev eth0 up
	ip netns exec unauth ipset flush hades_unauth_whitelist
	# makes dnsmasq forget that it wrote ips into ipset
	kill -HUP $(cat /run/hades/unauth-dns/dnsmasq.pid)
}

teardown() {
	ns ip link del dev eth0
	ip netns delete test-unauth
	rm -rf /etc/netns/test-unauth
}

@test "check that client can aquire DHCP lease" {
	run dhcpcd
	echo "$output" >&2
	[[ $status = 0 ]]
	egrep 'leased [^ ]+ for [0-9]+ seconds' <<<"$output"
}

@test "check that DNS queries get redirected" {
	dhcpcd
	for i in www.google.de www.msftncsi.com unknown.tld; do
		run ns dig +short "$i"
		[[ "$output" = 10.66.0.1 ]]
	done

	run dig +short dns.msftncsi.com
	[[ "$output" = 131.107.255.255 ]]
}

@test "check that client gets 511 error from portal" {
	dhcpcd
	run ns curl -qi http://www.google.de
	echo "$output" >&2
	egrep 'HTTP/[0-9]+\.[0-9]+ 511' <<<"$output"
	egrep '<meta http-equiv="refresh" content=' <<<"$output"
}

@test "check that portal is reachable" {
	dhcpcd
	run ns curl -qi http://captive-portal.agdsn.de
	echo "$output" >&2
	[[ $status = 0 ]]
	egrep 'HTTP/[0-9]+\.[0-9]+ 200' <<<"$output"
}

@test "check that ping 8.8.8.8 results in packet filtering" {
	dhcpcd
	run ns ping -c5 8.8.8.8
	egrep 'Packet Filtered' <<<"$output"
	egrep ' 100% packet loss' <<< "$output"
}

@test "check that pass-through DNS is working" {
	dhcpcd
	for i in agdsn.de ftp.agdsn.de; do
		run ns dig +short agdsn.de
		echo "$output" >&2
		[[ -n "$output" && "$output" != 10.66.0.1 ]]
	done
}

@test "check that pass-through ipset gets updated" {
	ipset_count () {
		ip netns exec unauth ipset list hades_unauth_whitelist | sed -rne 's/^Number of entries: (.*)$/\1/p'
	}

	dhcpcd

	run ipset_count
	echo "$output" >&2
	[[ "$output" -eq 0 ]]
	ns dig +short agdsn.de
	sleep 1
	run ipset_count
	echo "$output" >&2
	[[ "$output" -ge 1 ]]
}

@test "check that pass-through host is reachable" {
	dhcpcd
	for i in agdsn.de ftp.agdsn.de; do
		ns dig agdsn.de >&2
		run ns ping -c5 "$i"
		echo "$output" >&2
		egrep ' 0% packet loss' <<<"$output"
	done
}

@test "check that pass-through HTTP is working" {
	dhcpcd
	run ns curl -qi https://agdsn.de/sipa/news/
	echo "$output" >&2
	[[ $status = 0 ]]
	egrep 'HTTP/[0-9]+\.[0-9] 200' <<<"$output"
}
