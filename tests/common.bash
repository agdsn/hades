ns_exec() {
	local -r namespace="$1"
	shift
	ip netns exec "$namespace" "$@"
}

psql() {
	runuser -u hades-database -- psql --host /run/hades/database --echo-errors --no-readline --single-transaction --set=ON_ERROR_STOP=1 "$@"
}
