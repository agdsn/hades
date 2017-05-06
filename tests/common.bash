ns_exec() {
	local -r namespace="$1"
	shift
	ip netns exec "$namespace" "$@"
}
