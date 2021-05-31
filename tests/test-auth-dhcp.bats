#!/usr/bin/env bats

load common

readonly client_mac_address=de:ad:be:ef:00:00
readonly client_ip_address=141.30.227.13/23
readonly client_hostname=test
readonly gateway_ip_address=141.30.226.1/23
readonly relay_ip_address=10.66.67.1/24
readonly auth_ip=10.66.67.10/24
readonly dhcpcd_script="${BATS_TEST_DIRNAME}/dhcpcd-script.bash"
readonly dhcrelay_pid_file=/run/test-dhcrelay.pid

dhcrelay() {
	ns_exec test-relay dhcrelay -pf "$dhcrelay_pid_file" -4 -a -id eth0 -iu eth1 "$(netaddr.ip "$auth_ip")"
}

ns() {
	ns_exec test-auth "$@"
}

setup() {
	script_output_dir="$(mktemp -d)"
	setup_namespace test-auth
	setup_namespace test-relay
	ip link add br-relay up type bridge
	iptables -I FORWARD 1 -m physdev --physdev-is-bridged -i br-relay -o br-relay -j ACCEPT
	link_namespace test-auth br-relay eth0 "$client_mac_address"
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
	[[ -d "$script_output_dir" ]] && rm -rf "$script_output_dir"
	[[ -f "$dhcrelay_pid_file" ]] && kill "$(<"$dhcrelay_pid_file")" || :
	rm -f "$dhcrelay_pid_file"
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
	run ns dhcpcd \
		--config /dev/null \
		--script "$dhcpcd_script" \
		--env script_output_dir="$script_output_dir" \
		--env variable=env \
		--option domain_name_servers,domain_name,domain_search,host_name \
		--timeout 10 \
		--noipv4ll \
		--ipv4only \
		--oneshot eth0 \
		;
	echo "$output" >&2
	[[ $status = 0 ]]
	[[ -f "${script_output_dir}/BOUND" ]]
	source "${script_output_dir}/BOUND"
	declare -p env
	[[ "${env[new_broadcast_address]}" = "$(netaddr.broadcast "$gateway_ip_address")" ]]
	[[ "${env[new_dhcp_lease_time]}" = "86400" ]]
	[[ "${env[new_dhcp_rebinding_time]}" = "75600" ]]
	[[ "${env[new_dhcp_renewal_time]}" = "43200" ]]
	[[ "${env[new_dhcp_server_identifier]}" = "$(netaddr.ip "$auth_ip")" ]]
	[[ "${env[new_domain_name]}" = users.agdsn.de ]]
	[[ "${env[new_domain_name_servers]}" = "$(netaddr.ip "$auth_ip")" ]]
	[[ "${env[new_ip_address]}" = "$(netaddr.ip "$client_ip_address")" ]]
	[[ "${env[new_network_number]}" = "$(netaddr.network "$gateway_ip_address")" ]]
	[[ "${env[new_routers]}" = "$(netaddr.ip "$gateway_ip_address")" ]]
	[[ "${env[new_subnet_cidr]}" = "$(netaddr.prefixlen "$gateway_ip_address")" ]]
	[[ "${env[new_subnet_mask]}" = "$(netaddr.netmask "$gateway_ip_address")" ]]
}
