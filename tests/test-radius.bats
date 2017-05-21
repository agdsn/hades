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
readonly known_vlan_name=1KnownVLAN
readonly unknown_vlan_name=1UnknownVLAN
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
		VALUES (1, 'test', 'Egress-VLAN-Name', '+=', '${known_vlan_name}'),
		(1, 'unknown', 'Egress-VLAN-Name', ':=', '${unknown_vlan_name}');
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

do_request() {
	eval "local -A request_attributes=${1#*=}"
	eval "local -A filter_attributes=${2#*=}"
	local radclient
	# Set some default attributes if not present
	: ${request_attributes[NAS-IP-Address]="${nas_ip}"}
	: ${request_attributes[NAS-Identifier]= "\"${nas_name}\""}
	: ${request_attributes[NAS-Port-Type]=Ethernet}
	: ${request_attributes[NAS-Port-Id]="\"${nas_port_id}\""}
	: ${request_attributes[Called-Station-Id]="\"$(lowercase $(mac_sextuple "${nas_mac}" -))\""}

	local request
	for attribute in "${!request_attributes[@]}"; do
		request="${request:+${request}$'\n'}${attribute} = ${request_attributes[$attribute]}"
	done
	echo "$request"

	local filter
	for attribute in "${!filter_attributes[@]}"; do
		filter="${filter:+${filter}$'\n'}${attribute} == ${filter_attributes[$attribute]}"
	done
	echo "$filter"

	if [[ -n ${request_attributes[EAP-Password]+1} ]]; then
		radeapclient localhost auth "$secret" -f/dev/fd/3 3<<<"$request" 0</dev/null
		return 1
	else
		radclient localhost auth "$secret" -f/dev/fd/3:/dev/fd/4 3<<<"$request" 4<<<"$filter" 0</dev/null
	fi
}

@test "check that a known MAC address authenticates via CHAP correctly" {
	declare -Ar request=(
		[Service-Type]=Call-Check
		[Framed-Protocol]=PPP
		[User-Name]="\"$(uppercase $(mac_triple "${known_user_mac}" -))\""
		[Calling-Station-Id]="\"$(lowercase $(mac_sextuple "${known_user_mac}" -))\""
		[CHAP-Password]="\"$(uppercase $(mac_triple "${known_user_mac}" -))\""
	)
	declare -Ar filter=(
		[Packet-Type]=Access-Accept
		[Egress-VLAN-Name]="\"${known_vlan_name}\""
	)
	do_request "$(declare -p request)" "$(declare -p filter)"
}

@test "check that a known MAC address authenticates via EAP-MD5 correctly" {
	declare -Ar request=(
		[Service-Type]=Call-Check
		[Framed-Protocol]=PPP
		[User-Name]="\"$(lowercase $(mac_triple "${known_user_mac}" ''))\""
		[Calling-Station-Id]="\"$(lowercase $(mac_sextuple "${known_user_mac}" -))\""
		[EAP-MD5-Password]="\"$(lowercase $(mac_triple "${known_user_mac}" ''))\""
		[EAP-Type-Identity]="\"$(lowercase $(mac_triple "${known_user_mac}" ''))\""
	)
	declare -Ar filter=(
		[Packet-Type]=Access-Accept
		[Egress-VLAN-Name]="\"${unknown_vlan_name}\""
	)
	do_request "$(declare -p request)" "$(declare -p filter)"
}

@test "check that a unknown MAC address authenticates via CHAP correctly" {
	declare -Ar request=(
		[Service-Type]=Call-Check
		[Framed-Protocol]=PPP
		[User-Name]="\"$(uppercase $(mac_triple "${unknown_user_mac}" -))\""
		[Calling-Station-Id]="\"$(lowercase $(mac_sextuple "${unknown_user_mac}" -))\""
		[CHAP-Password]="\"$(uppercase $(mac_triple "${unknown_user_mac}" -))\""
	)
	declare -Ar filter=(
		[Packet-Type]=Access-Accept
		[Egress-VLAN-Name]="\"${unknown_vlan_name}\""
	)
	do_request "$(declare -p request)" "$(declare -p filter)"
}

@test "check that a spoofed MAC address will be rejected" {
	declare -Ar request=(
		[Service-Type]=Call-Check
		[Framed-Protocol]=PPP
		[User-Name]="\"$(uppercase $(mac_triple "${known_user_mac}" -))\""
		[Calling-Station-Id]="\"$(lowercase $(mac_sextuple "${unknown_user_mac}" -))\""
		[CHAP-Password]="\"$(uppercase $(mac_triple "${known_user_mac}" -))\""
	)
	declare -Ar filter=(
		[Packet-Type]=Access-Reject
	)
	do_request "$(declare -p request)" "$(declare -p filter)"
}
