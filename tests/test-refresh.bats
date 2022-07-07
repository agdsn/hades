#!/usr/bin/env bats

load common
load common-dhcp

readonly old_hostname="Old and busted"
readonly new_hostname="New hotness"
readonly old_ip=141.30.228.30
readonly new_ip=141.30.228.31
readonly old_mac=00:de:ad:be:ef:00
readonly new_mac=00:de:ad:be:ef:ff


insert_auth_dhcp_host() {
	# truncate auth_dhcp_host and insert a single lease
	eval "local -A reservation=${1#*=}"
	psql foreign <<-EOF
		TRUNCATE auth_dhcp_host;
		INSERT INTO auth_dhcp_host ("MAC", "IPAddress", "Hostname")
		VALUES ('$(mac_sextuple "${reservation[mac]}" :)', inet '${reservation[ip]}', '${reservation[hostname]}')
	EOF
}

setup_file() {
	suspend_timers
}

teardown_file() {
	resume_timers
}

setup() {
	log_test_start
	# `auth_dhcp_lease` filled with precisely one reservation:
	# ($old_mac, $old_ip, $old_hostname)
	declare -Ar host_reservation=(
		[mac]=$(mac_sextuple ${old_mac} :)
		[ip]=${old_ip}
		[hostname]=${old_hostname}
	)
	insert_auth_dhcp_host "$(declare -p host_reservation)"
	psql hades <<-EOF
		truncate auth_dhcp_lease;
		insert into auth_dhcp_lease ("MAC", "IPAddress", "ExpiresAt")
		values ('$(mac_sextuple ${old_mac} :)', inet '${old_ip}', '2222-01-01');
		refresh materialized view auth_dhcp_host;
	EOF
	systemctl restart hades-auth-dhcp
}

teardown() {
	sleep 2  # as to not anger the systemd timeouts (cleaner solution would be to deconfigure)
	log_test_stop
}

@test "check that a refresh does not change a valid lease" {
	refresh
	assert_leases "${old_ip},${old_mac}"
}

@test "check that a forced refresh does not change a valid lease" {
	forced_refresh
	assert_leases "${old_ip},${old_mac}"
}

@test "check that deleting the reservation removes the lease" {
	psql foreign -c 'TRUNCATE auth_dhcp_host'
	refresh
	assert_leases ""
}

@test "check that changing the hostname does not remove the lease" {
	declare -Ar reservation=(
		[mac]=${old_mac}
		[ip]=${old_ip}
		[hostname]=${new_hostname}
	)
	insert_auth_dhcp_host "$(declare -p reservation)"
	refresh
	assert_leases "${old_ip},${old_mac}"
}

@test "check that changing the IP removes the lease" {
	declare -Ar reservation=(
		[mac]=${old_mac}
		[ip]=${new_ip}
		[hostname]=${new_hostname}
	)
	insert_auth_dhcp_host "$(declare -p reservation)"
	refresh
	assert_leases ""
}

@test "check that a refresh deletes an unknown lease" {
	# completely unknown, new reservation:
	# the diff just detects our old reservation as removed,
	# and this new reservation as something different.
	# Thus, any lease will be cleaned up.
	declare -Ar reservation=(
		[mac]=${new_mac}
		[ip]=${new_ip}
		[hostname]=${new_hostname}
	)
	insert_auth_dhcp_host "$(declare -p reservation)"
	refresh
	assert_leases ""
}

@test "check that a forced refresh deletes an unknown lease" {
	declare -Ar reservation=(
		[mac]=${new_mac}
		[ip]=${new_ip}
		[hostname]=${new_hostname}
	)
	insert_auth_dhcp_host "$(declare -p reservation)"
	forced_refresh
	assert_leases ""
}
