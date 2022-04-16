#!/usr/bin/env bats

load common

# Test fixtures
mac_address=de:ad:be:ef:00:00
ip_address=192.168.1.13
hostname=test
supplied_hostname=hal
domain=example.com
relay_ip_address=192.168.1.1
tags=(tag1 tag2)
interface=eth0
client_id=01:de:ad:be:ef:00:00
circuit_id=A15
subscriber_id=john@example.com
remote_id=192.168.1.1
vendor_class="MSFT 5.0"
requested_options=(1 2 3)
time_remaining=86400
now=$(date +'%s')
expires_at="$(( ${now} + ${time_remaining} ))"
user_classes=(foo bar)

setup() {
	psql_query hades -c 'TRUNCATE auth_dhcp_lease;'
}

teardown() {
	psql_query hades -c 'TRUNCATE auth_dhcp_lease;'
}

insert_lease() {
	psql_query hades <<-EOF
		INSERT INTO auth_dhcp_lease (
		"MAC", "IPAddress", "Hostname", "Domain", "SuppliedHostname",
		"ExpiresAt", "RelayIPAddress", "Tags", "ClientID", "CircuitID",
		"SubscriberID", "RemoteID", "VendorClass", "RequestedOptions",
		"UserClasses"
		) VALUES (
			$(pg_escape_string "${mac_address}"),
			$(pg_escape_string "${ip_address}"),
			$(pg_escape_string "${hostname}"),
			$(pg_escape_string "${domain}"),
			$(pg_escape_string "${supplied_hostname}"),
			TO_TIMESTAMP(${expires_at}),
			$(pg_escape_string "${relay_address}"),
			$(pg_escape_array "${tags[@]}"),
			'\x${client_id//:}',
			$(pg_escape_string "${circuit_id}"),
			$(pg_escape_string "${subscriber_id}"),
			$(pg_escape_string "${remote_id}"),
			$(pg_escape_string "${vendor_class}"),
			$(pg_escape_array "${requested_options[@]}"),
			$(pg_escape_array "${user_classes[@]}")
		);
	EOF
}

setup_env_from_fixtures() {
	[[ $1 != env ]] && local -n env="$1"
	env[DNSMASQ_DOMAIN]="${domain}"
	env[DNSMASQ_SUPPLIED_HOSTNAME]="${supplied_hostname}"
	env[DNSMASQ_LEASE_EXPIRES]="${expires_at}"
	env[DNSMASQ_INTERFACE]="${interface}"
	env[DNSMASQ_TIME_REMAINING]="${time_remaining}"
	env[DNSMASQ_RELAY_ADDRESS]="${relay_ip_address}"
	env[DNSMASQ_TAGS]="$(join ' ' "${tags[@]}")"
	env[DNSMASQ_CLIENT_ID]="${client_id}"
	env[DNSMASQ_CIRCUIT_ID]="${circuit_id}"
	env[DNSMASQ_SUBSCRIBER_ID]="${subscriber_id}"
	env[DNSMASQ_REMOTE_ID]="${remote_id}"
	env[DNSMASQ_VENDOR_CLASS]="${vendor_class}"
	env[DNSMASQ_REQUESTED_OPTIONS]="$(join ',' "${requested_options[@]}")"
	set_user_classes env "${user_classes[@]}"
	set_dhcp_script_socket env
}

set_user_classes() {
	[[ $1 != env ]] && local -n env="$1"
	shift
	for (( i = 0; $# > 0; i++ )); do
		env["DNSMASQ_USER_CLASS$i"]="$1"
		shift
	done
}

set_dhcp_script_socket() {
	[[ $1 != env ]] && local -n env="$1"
	env[HADES_DHCP_SCRIPT_SOCKET]="/run/hades/auth-dhcp/script.sock"
}

lease_count() {
	psql_query hades -c 'SELECT COUNT(*) FROM "auth_dhcp_lease"'
}


execute_auth_script() {
	[[ $1 != env ]] && local -n env="$1"
	shift
	local -a foo
	for var in "${!env[@]}"; do
		foo+=("${var}=${env[$var]}")
	done
	runuser -u hades-auth-dhcp env "${foo[@]}" hades-dhcp-script "$@"
}

assert_simple_fields() {
	local -r mac_address="$1"; shift
	local -r ip_address="$1"; shift
	local -r hostname="$1"; shift
	local -r domain="$1"; shift
	local -r supplied_hostname="$1"; shift
	local -r expires_at="$1"; shift
	local -r relay_ip_address="$1"; shift
	local -r client_id="$1"; shift
	local -r circuit_id="$1"; shift
	local -r subscriber_id="$1"; shift
	local -r remote_id="$1"; shift
	local -r vendor_class="$1"; shift

	local -a result=()
	psql_mapfile result hades -c 'SELECT "MAC", "IPAddress", "Hostname", "Domain", "SuppliedHostname", EXTRACT(EPOCH FROM "ExpiresAt"), "RelayIPAddress", "ClientID", "CircuitID", "SubscriberID", "RemoteID", "VendorClass" FROM auth_dhcp_lease LIMIT 1'
	echo "${result[@]}"

	assert_equals "${result[0]}"  "${mac_address}"
	assert_equals "${result[1]}"  "${ip_address}"
	assert_equals "${result[2]}"  "${hostname}"
	assert_equals "${result[3]}"  "${domain}"
	assert_equals "${result[4]}"  "${supplied_hostname}"
	assert_equals "${result[5]}"  "${expires_at}"
	assert_equals "${result[6]}"  "${relay_ip_address}"
	assert_equals "${result[7]}"  "\\x${client_id//:}"
	assert_equals "${result[8]}"  "$(pg_encode_hex "${circuit_id}")"
	assert_equals "${result[9]}"  "$(pg_encode_hex "${subscriber_id}")"
	assert_equals "${result[10]}" "$(pg_encode_hex "${remote_id}")"
	assert_equals "${result[11]}" "${vendor_class}"
}

assert_requested_options() {
	local -rn _expected="$1"
	local -a _got=()

	psql_mapfile _got hades -c 'SELECT unnest("RequestedOptions") FROM "auth_dhcp_lease"'
	assert_array_equals _expected _got
}

assert_tags() {
	local -rn _expected="$1"
	local -a _got=()

	psql_mapfile _got hades -c 'SELECT unnest("Tags") FROM "auth_dhcp_lease"'
	assert_array_equals _expected _got
}

assert_user_classes() {
	local -rn _expected="$1"
	local -a _got=()

	psql_mapfile _got hades -c 'SELECT unnest("UserClasses") FROM "auth_dhcp_lease"'
	assert_array_equals _expected _got
}

@test "check that leases can be added" {
	local -A env=()
	setup_env_from_fixtures env
	run execute_auth_script env add "${mac_address}" "${ip_address}" "${hostname}"

	echo "$output"
	[[ ${status} -eq 0 ]]

	[[ $(lease_count) -eq 1 ]]
	
	assert_simple_fields "${mac_address}" "${ip_address}" "${hostname}" "${domain}" "${supplied_hostname}" "${expires_at}" "${relay_ip_address}" "${client_id}" "${circuit_id}" "${subscriber_id}" "${remote_id}" "${vendor_class}"
	assert_requested_options requested_options
	assert_tags tags
	assert_user_classes user_classes
}

@test "check the output of init" {
	insert_lease
	printf "%s\n" "$(set_user_classes "${user_classes[@]}")"

	local -A env=()
	set_dhcp_script_socket env
	run execute_auth_script env init

	echo "$output"
	[[ $status -eq 0 ]]
	[[ "$expires_at $mac_address $ip_address $hostname $client_id" = $output ]]
}

@test "check that leases can be deleted" {
	insert_lease

	local -A env=(
		[DNSMASQ_LEASE_EXPIRES]="${now}"
		[DNSMASQ_INTERFACE]="${interface}"
		[DNSMASQ_RELAY_ADDRESS]="${relay_ip_address}"
		[DNSMASQ_CLIENT_ID]="${client_id}"
	)
  set_dhcp_script_socket env

	run execute_auth_script env del "${mac_address}" "${ip_address}" "${hostname}"

	echo "$output"
	[[ $status -eq 0 ]]
	[[ $(lease_count) -eq 0 ]]
}

@test "check that hostname is updated" {
	insert_lease
	local -A env=()
	setup_env_from_fixtures env
	env[DNSMASQ_OLD_HOSTNAME]="${hostname}"
	local new_hostname="new_${hostname}"

	run execute_auth_script env old "${mac_address}" "${ip_address}" "${new_hostname}"

	echo "$output"
	[[ $status -eq 0 ]]
	[[ $(lease_count) -eq 1 ]]

	assert_simple_fields "${mac_address}" "${ip_address}" "${new_hostname}" "${domain}" "${supplied_hostname}" "${expires_at}" "${relay_ip_address}" "${client_id}" "${circuit_id}" "${subscriber_id}" "${remote_id}" "${vendor_class}"
	assert_requested_options requested_options
	assert_tags tags
	assert_user_classes user_classes
}

@test "check that expiry time is updated" {
	insert_lease
	local -A env=()
	setup_env_from_fixtures env
	local new_expires_at="$(( $expires_at + 3600 ))"
	env[DNSMASQ_LEASE_EXPIRES]="${new_expires_at}"
	env[DNSMASQ_TIME_REMAINING]="${new_expires_at}"

	run execute_auth_script env old "${mac_address}" "${ip_address}" "${hostname}"

	echo "$output"
	[[ $status -eq 0 ]]
	[[ $(lease_count) -eq 1 ]]

	assert_simple_fields "${mac_address}" "${ip_address}" "${hostname}" "${domain}" "${supplied_hostname}" "${new_expires_at}" "${relay_ip_address}" "${client_id}" "${circuit_id}" "${subscriber_id}" "${remote_id}" "${vendor_class}"
	assert_requested_options requested_options
	assert_tags tags
	assert_user_classes user_classes
}
