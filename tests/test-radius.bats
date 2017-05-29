#!/usr/bin/env bats

load common

readonly nas_mac=00:00:00:00:00:00
readonly nas_ip=127.0.0.1
readonly nas_port=1
readonly nas_port_id=A1
readonly nas_name=localhost
readonly secret=testing123
readonly known_user_ip=141.30.226.100
readonly known_user_mac=40-61-86-1c-df-fd
readonly unknown_user_mac=1e-a7-de-ad-be-ef
readonly known_vlan_name=1KnownVLAN
readonly unknown_vlan_name=1UnknownVLAN

setup() {
	psql foreign <<-EOF
		INSERT INTO radcheck ("Priority", "NASIPAddress", "NASPortId", "UserName", "Attribute", "Op", "Value")
		VALUES (1, inet '${nas_ip}', '${nas_port_id}', '$(lowercase $(mac_sextuple ${known_user_mac} :))', 'Calling-Station-Id', '==', '$(lowercase $(mac_sextuple "${nas_mac}" -))');
		INSERT INTO radusergroup ("Priority", "NASIPAddress", "NASPortId", "UserName", "GroupName")
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

	if [[ -n ${request_attributes[EAP-MD5-Password]+1} ]]; then
		radeapclient -t 3 -f/dev/fd/3 localhost auto "$secret" 3<<<"$request" 0</dev/null
		return 1
	else
		radclient -t 3 -f/dev/fd/3:/dev/fd/4 localhost auto "$secret" 3<<<"$request" 4<<<"$filter" 0</dev/null
	fi
}

@test "check that a known MAC address authenticates via CHAP correctly" {
	declare -Ar request=(
		[Packet-Type]=Access-Request
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
		[Packet-Type]=Access-Request
		[Service-Type]=Call-Check
		[Framed-Protocol]=PPP
		[User-Name]="\"$(lowercase $(mac_triple "${known_user_mac}" ''))\""
		[Calling-Station-Id]="\"$(lowercase $(mac_sextuple "${known_user_mac}" -))\""
		[EAP-Code]=Response
		[EAP-MD5-Password]="\"$(lowercase $(mac_triple "${known_user_mac}" ''))\""
		[EAP-Type-Identity]="\"$(lowercase $(mac_triple "${known_user_mac}" ''))\""
		[Message-Authenticator]=0x00
	)
	declare -Ar filter=(
		[Packet-Type]=Access-Accept
		[Egress-VLAN-Name]="\"${unknown_vlan_name}\""
	)
	do_request "$(declare -p request)" "$(declare -p filter)"
}

@test "check that a unknown MAC address authenticates via CHAP correctly" {
	declare -Ar request=(
		[Packet-Type]=Access-Request
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
		[Packet-Type]=Access-Request
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

@test "check that accounting works" {
	local -r session_id=$(printf '%4x' ${RANDOM})
	declare -Ar request_template=(
		[Packet-Type]=Accounting-Request
		[User-Name]="\"$(uppercase $(mac_triple "${known_user_mac}" -))\""
		[Service-Type]=Framed-User
		[Framed-IP-Address]=${known_user_ip}
		[Calling-Station-Id]="\"$(lowercase $(mac_sextuple "${known_user_mac}" -))\""
		[Acct-Authentic]=RADIUS
		[Acct-Session-Id]="\"${session_id}\""
	)

	declare -A start_request="$(strip "$(declare -p request_template)")"
	start_request+=(
		[Acct-Status-Type]=Start
		[Acct-Delay-Time]=2
	)

	declare -A update_request="$(strip "$(declare -p request_template)")"
	update_request+=(
		[Acct-Status-Type]=Interim-Update
		[Acct-Delay-Time]=3
		[Acct-Input-Packets]=4
		[Acct-Input-Octets]=256
		[Acct-Output-Packets]=1024
		[Acct-Output-Octets]=10
		[Acct-Session-Time]=10
	)

	declare -A stop_request="$(strip "$(declare -p request_template)")"
	stop_request+=(
		[Acct-Status-Type]=Stop
		[Acct-Delay-Time]=2
		[Acct-Input-Packets]=8
		[Acct-Input-Octets]=512
		[Acct-Output-Packets]=4096
		[Acct-Output-Octets]=40
		[Acct-Session-Time]=60
	)

	declare -Ar filter=(
		[Packet-Type]=Accounting-Response
	)

	do_request "$(declare -p start_request)" "$(declare -p filter)"
	do_request "$(declare -p update_request)" "$(declare -p filter)"
	do_request "$(declare -p stop_request)" "$(declare -p filter)"
}
