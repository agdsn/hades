#!/usr/bin/env bats

load common

readonly client_mac_address=de:ad:be:ef:00:00
readonly client_ip_address=10.66.10.10/19
readonly nameserver_ip_address=10.66.0.1/19

readonly -A messages=(
	[default_in_payment]="late with paying your fees"
	[membership_ended]="membership status does not"
	[security]="security problems"
	[traffic]="exceeded your traffic limit"
	[unknown]="don't recognize your MAC address"
	[violation]="violated our Terms of Services"
	[wrong_port]="you live in a different room"
	[good]="Your network connectivity should work in a few minutes."
)

ns() {
	ns_exec test-portal "$@"
}

setup() {
	log_test_start
	setup_namespace test-portal
	link_namespace test-portal br-unauth eth0 "${client_mac_address}"
	ns ip addr add dev eth0 "${client_ip_address}"
	ns ip route add default via $(netaddr.ip "${nameserver_ip_address}")
	echo "nameserver $(netaddr.ip "${nameserver_ip_address}")" > /etc/netns/test-portal/resolv.conf
	psql foreign <<-EOF
		TRUNCATE radusergroup;
	EOF
	psql hades <<-EOF
		TRUNCATE radpostauth;
		REFRESH MATERIALIZED VIEW radusergroup;
	EOF
}

teardown() {
	unlink_namespace test-portal eth0
	teardown_namespace test-portal
	psql foreign <<-EOF
		TRUNCATE radusergroup;
	EOF
	psql hades <<-EOF
		TRUNCATE radpostauth;
		REFRESH MATERIALIZED VIEW radusergroup;
	EOF
	log_test_stop
}

insert_radusergroup() {
	local -r groups=("$@")
	for group in "${groups[@]}"; do
		psql foreign <<-EOF
			INSERT INTO radusergroup ("Priority", "NASIPAddress", "NASPortId", "UserName", "GroupName")
			VALUES (1, inet '127.0.0.1', 'A1', '${client_mac_address}', '${group}');
		EOF
	done

	psql hades <<-EOF
		REFRESH MATERIALIZED VIEW radusergroup;
	EOF
}

insert_radpostauth() {
	local -r -a groups=("$@")
	local groups_string=
	for group in "${groups[@]}"; do
		[[ -n "${groups_string}" ]] && groups_string="${groups_string}, "
		groups_string="${groups_string}${group}"
	done
	groups_string='{'"${groups_string}"'}'

	psql hades <<-EOF
		INSERT INTO radpostauth ("UserName", "NASIPAddress", "NASPortId", "PacketType", "Groups", "Reply", "AuthDate")
		VALUES ('${client_mac_address}', '127.0.0.1', 'A1', 'Access-Accept', '${groups_string}', '{}', now());
	EOF
}

portal_test_helper() {
	local -r -a groups=("$@")
	run ns curl -qiL http://captive-portal.agdsn.de/
	echo "${output}" >&2
	[[ ${status} = 0 ]]
	for group in "${groups[@]}"; do
		fgrep "${messages[$group]}" <<<"${output}"
	done
}

@test "check default_in_payment case" {
	insert_radusergroup default_in_payment
	insert_radpostauth default_in_payment
	portal_test_helper default_in_payment
}

@test "check membership_ended case" {
	insert_radusergroup membership_ended
	insert_radpostauth membership_ended
	portal_test_helper membership_ended
}

@test "check security case" {
	insert_radusergroup security
	insert_radpostauth security
	portal_test_helper security
}

@test "check traffic case" {
	insert_radusergroup traffic
	insert_radpostauth traffic
	portal_test_helper traffic
}

@test "check violation case" {
	insert_radusergroup violation
	insert_radpostauth violation
	portal_test_helper violation
}

@test "check multiple cases" {
	insert_radusergroup default_in_payment traffic violation
	insert_radpostauth default_in_payment traffic violation
	portal_test_helper default_in_payment traffic violation
}

@test "check unknown case" {
	insert_radpostauth unknown
	portal_test_helper unknown
}

@test "check wrong_port-not-wrong_port case" {
	insert_radusergroup Wu5_untagged
	insert_radpostauth unknown
	portal_test_helper good
}

@test "check wrong_port case" {
	insert_radusergroup Wu5_untagged
	insert_radpostauth unknown

	psql hades <<-EOF
		UPDATE radpostauth SET "NASPortId" = 'A2';
	EOF

	portal_test_helper wrong_port
}
