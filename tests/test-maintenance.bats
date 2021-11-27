#!/usr/bin/env bats

load common

readonly client_ip_address=141.30.227.13

data() {
	last_byte=$(printf '%02x' "$1")
	psql foreign <<-EOF
		TRUNCATE auth_dhcp_host;
		INSERT INTO auth_dhcp_host VALUES ('de:ad:be:ef:00:${last_byte}', '${client_ip_address}')
	EOF
	refresh
}

fakedns() {
	psql foreign <<-EOF
		TRUNCATE alternative_dns;
		INSERT INTO alternative_dns VALUES ('${client_ip_address}');
	EOF
	refresh
}

setup() {
	data 0
	psql foreign <<<'TRUNCATE alternative_dns;'
}

teardown() {
	psql foreign <<-EOF
		TRUNCATE auth_dhcp_host;
		TRUNCATE alternative_dns;
	EOF
	refresh
}

@test "check that fdw contains data" {
	helper() {
		psql --tuples-only hades <<<'SELECT * FROM foreign_auth_dhcp_host;'
	}
	run helper
	grep "de:ad:be:ef:00:00 | ${client_ip_address}" <<<"$output"

	data 1
	run helper
	grep "de:ad:be:ef:00:01 | ${client_ip_address}" <<<"$output"
}

@test "check that refresh syncs the data" {
	helper() {
		psql --tuples-only hades <<<'SELECT * FROM auth_dhcp_host;'
	}
	run helper
	grep "de:ad:be:ef:00:00 | ${client_ip_address}" <<<"$output"

	data 1
	run helper
	grep "de:ad:be:ef:00:01 | ${client_ip_address}" <<<"$output"
}

@test "check that alternative DNS configuration is propagated to ipset" {
	ipset_count () {
		ns_exec auth ipset list hades_alternative_dns -output xml | xmllint --nonet --nocdata --xpath 'count(/ipsets/ipset[@name="hades_alternative_dns"]/members/member/elem)' -
	}
	[[ "$(ipset_count)" = 0 ]]

	fakedns
	[[ "$(ipset_count)" = 1 ]]
	ns_exec auth ipset list hades_alternative_dns -output xml | xmllint --nonet --nocdata --xpath '/ipsets/ipset[@name="hades_alternative_dns"]/members/member/elem[text()="'"${client_ip_address}"'"]' -
}

@test "check that dnsmasq host reservations are generated" {
	file=/var/lib/hades/auth-dhcp/dnsmasq-dhcp.hosts
	cat "$file" >&2
	[[ -f "$file" ]]
	[[ "$(<"$file")" = "de:ad:be:ef:00:00,id:*,${client_ip_address}" ]]

	data 1
	[[ -f "$file" ]]
	[[ "$(<"$file")" = "de:ad:be:ef:00:01,id:*,${client_ip_address}" ]]
}
