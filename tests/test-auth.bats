#!/usr/bin/env bats

load common

dhcpcd() {
	ns_exec test-auth dhcpcd --noipv4ll --ipv4only --oneshot eth0
}

refresh() {
	systemctl start --wait hades-refresh.service
}

data() {
	last_byte=$(printf '%02x' "$1")
	psql foreign <<-EOF
		TRUNCATE dhcphost;
		INSERT INTO dhcphost VALUES ('de:ad:be:ef:00:${last_byte}', '141.30.227.13')
	EOF
	refresh
}

fakedns() {
	psql foreign <<-EOF
		TRUNCATE alternative_dns;
		INSERT INTO alternative_dns VALUES ('141.30.227.13');
	EOF
	refresh
}

setup() {
	setup_namespace test-auth br-auth de:ad:be:ef:00:00
	ns_exec auth ip addr add dev eth2 141.30.226.1/23
	data 0
	psql foreign <<<'TRUNCATE alternative_dns;'
}

teardown() {
	ns_exec auth ip addr del dev eth2 141.30.226.1/23
	teardown_namespace test-auth
	psql foreign <<-EOF
		TRUNCATE dhcphost;
		TRUNCATE alternative_dns;
	EOF
	refresh
}

@test "check that fdw contains data" {
	helper() {
		psql --tuples-only hades <<<'SELECT * FROM foreign_dhcphost;'
	}
	run helper
	grep 'de:ad:be:ef:00:00 | 141.30.227.13' <<<"$output"

	data 1
	run helper
	grep 'de:ad:be:ef:00:01 | 141.30.227.13' <<<"$output"
}

@test "check that refresh syncs the data" {
	helper() {
		psql --tuples-only hades <<<'SELECT * FROM dhcphost;'
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
	ns_exec test-auth cat /etc/resolv.conf >&2
	for i in www.google.de www.msftncsi.com; do
		run ns_exec dig +short "$i"
		echo "$output" >&2
		[[ -n "$output" && "$output" != 10.66.0.1 ]]
	done
}

@test "check that alternative DNS configuration is propagated to ipset" {
	ipset_count () {
		ns_exec auth ipset list hades_alternative_dns -output xml | xmllint --xpath 'count(/ipsets/ipset[@name="hades_alternative_dns"]/members/member/elem)' -
	}
	[[ "$(ipset_count)" = 0 ]]

	fakedns
	[[ "$(ipset_count)" = 1 ]]
	ns_exec auth ipset list hades_alternative_dns -output xml | xmllint --nonet --nocdata --xpath '/ipsets/ipset[@name="hades_alternative_dns"]/members/member/elem[text()="141.30.227.13"]' -
}

@test "check that alternative DNS is working" {
	dhcpcd
	ns_exec test-auth cat /etc/resolv.conf >&2
	for i in www.google.de fake.news.com; do
		run ns_exec test-auth dig +short "$i"
		echo "$output" >&2
		[[ -n "$output" && "$output" != 127.0.0.1 ]]
	done

	fakedns

	run ns_exec test-auth dig +short www.google.de
	[[ -n "$output" && "$output" != 127.0.0.1 ]]

	run ns_exec test-auth dig +short fake.news.com
	[[ "$output" = 127.0.0.1 ]]
}
