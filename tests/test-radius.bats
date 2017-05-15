#!/usr/bin/env bats

load common

readonly nas_mac=00:00:00:00:00:00
readonly nas_ip=127.0.0.1
readonly nas_port=1
readonly nas_port_id=A1
readonly nas_name=localhost
readonly secret=testing123
readonly known_user_mac=40-61-86-1c-df-fd
readonly unknown_user_mac=1e-a7-de-ad-be-ef
readonly mac_regex='([0-9a-f]{2})[^0-9a-f]?([0-9a-f]{2})[^0-9a-f]?([0-9a-f]{2})[^0-9a-f]?([0-9a-f]{2})[^0-9a-f]?([0-9a-f]{2})[^0-9a-f]?([0-9a-f]{2})'


lowercase() {
	printf "%s" "${@,,}"
}

uppercase() {
	printf "%s" "${@^^}"
}

mac_duo() {
	[[ $1 =~ $mac_regex ]]
	printf "%s%s%s$2%s%s%s" "${BASH_REMATCH[@]:1}"
}

mac_triple() {
	[[ $1 =~ $mac_regex ]]
	printf "%s%s$2%s%s$2%s%s" "${BASH_REMATCH[@]:1}"
}

mac_sextuple() {
	[[ $1 =~ $mac_regex ]]
	printf "%s$2%s$2%s$2%s$2%s$2%s" "${BASH_REMATCH[@]:1}"
}


setup() {
	psql foreign <<-EOF
		INSERT INTO radcheck ("Priority", "NASIpAddress", "NASPortId", "UserName", "Attribute", "Op", "Value")
		VALUES (1, inet '${nas_ip}', '${nas_port_id}', '$(lowercase $(mac_sextuple ${known_user_mac} :))', 'Calling-Station-Id', '==', '$(lowercase $(mac_sextuple "${nas_mac}" -))');
		INSERT INTO radusergroup ("Priority", "NASIpAddress", "NASPortId", "UserName", "GroupName")
		VALUES (1, inet '${nas_ip}', '${nas_port_id}', '$(lowercase $(mac_sextuple ${known_user_mac} :))', 'test'),
		(1, NULL, NULL, 'unknown', 'unknown');
		INSERT INTO radgroupreply ("Priority", "GroupName", "Attribute", "Op", "Value")
		VALUES (1, 'test', 'Egress-VLAN-Name', '+=', '1KnownVlan'),
		(1, 'unknown', 'Egress-VLAN-Name', ':=', '1UnknownVlan');
		EOF
	refresh
}

teardown() {
	psql foreign <<-EOF
		TRUNCATE radcheck;
		TRUNCATE radusergroup;
		TRUNCATE radgroupreply;
		EOF
	refresh
}

access_request() {
	local -r calling_station_id="$1"
	local -r user_name="$2"
	local -r password="$3"
	radclient localhost auth "$secret" -f/dev/fd/3:/dev/fd/4 3<<-EOF 4<&0 0</dev/null
		Framed-MTU = 1466
		NAS-IP-Address = ${nas_ip}
		NAS-Identifier = "${nas_name}"
		User-Name = "${user_name}"
		Service-Type = Call-Check
		Framed-Protocol = PPP
		NAS-Port = ${nas_port}
		NAS-Port-Type = Ethernet
		NAS-Port-Id = "${nas_port_id}"
		Called-Station-Id = "$(lowercase $(mac_sextuple "${nas_mac}" -))"
		Calling-Station-Id = "${calling_station_id}"
		Connect-Info = "CONNECT Ethernet 1000Mbps Full duplex"
		CHAP-Password = "${password}"
		MS-RAS-Vendor = 11
		HP-Capability-Advert = 0x011a0000000b28
		HP-Capability-Advert = 0x011a0000000b2e
		HP-Capability-Advert = 0x011a0000000b30
		HP-Capability-Advert = 0x011a0000000b3d
		HP-Capability-Advert = 0x0138
		HP-Capability-Advert = 0x013a
		HP-Capability-Advert = 0x0140
		HP-Capability-Advert = 0x0141
		HP-Capability-Advert = 0x0151
		EOF
}

expect_accept() {
	access_request "$@" <<-EOF
	Packet-Type == Access-Accept
	Egress-VLAN-Name =* ANY
	EOF
}

expect_reject() {
	access_request "$@" <<-EOF
	Packet-Type == Access-Reject
	EOF
}

@test "check that a known MAC address authenticates correctly" {
	local -r calling_station_id="$(lowercase $(mac_sextuple "${known_user_mac}" -))"
	local -r user_name="$(uppercase $(mac_triple "${known_user_mac}" -))"
	local -r password="$(uppercase $(mac_triple "${known_user_mac}" -))"
	expect_accept "$calling_station_id" "$user_name"  "$password"
}

@test "check that a unknown MAC address authenticates correctly" {
	local -r calling_station_id="$(lowercase $(mac_sextuple "${unknown_user_mac}" -))"
	local -r user_name="$(uppercase $(mac_triple "${unknown_user_mac}" -))"
	local -r password="$(uppercase $(mac_triple "${unknown_user_mac}" -))"
	expect_accept "$calling_station_id" "$user_name"  "$password"
}

@test "check that a spoofed MAC address will be rejected" {
	local -r calling_station_id="$(lowercase $(mac_sextuple "${unknown_user_mac}" -))"
	local -r user_name="$(uppercase $(mac_triple "${known_user_mac}" -))"
	local -r password="$(uppercase $(mac_triple "${known_user_mac}" -))"
	expect_reject "$calling_station_id" "$user_name"  "$password"
}
