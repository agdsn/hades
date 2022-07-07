get_leases_csv() {
	psql_query_csv hades -c 'SELECT "IPAddress", "MAC" FROM auth_dhcp_lease'
}

assert_leases() {
	local -r expected="$1"; shift
	local -r time_before=$(date +%s)
	local leases;
	# We need a retry mechanism because we have to wait for the dnsmasq hook to be executed
	# and for the result to be processed by the dhcp_script.
	# All of this happens asynchronously.
	while (( ($(date +%s) - time_before) < 5 ))
	do
		leases=$(get_leases_csv)
		if [[ "$leases" == "$expected" ]]; then
			return 0;
		fi;
		sleep 0.5;
	done;
	echo "$leases"
	return 1;
}
